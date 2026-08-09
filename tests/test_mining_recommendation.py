import pandas as pd
import pytest

import mining.recommendation as recommendation
from mining.artifacts import itemset_to_json


@pytest.fixture
def rules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "antecedents_json": itemset_to_json({"1", "2"}),
                "consequents_json": itemset_to_json({"3"}),
                "antecedent_names_json": itemset_to_json({"Milk", "Bread"}),
                "consequent_names_json": itemset_to_json({"Eggs"}),
                "support": 0.30,
                "confidence": 0.80,
                "lift": 1.50,
            },
            {
                "antecedents_json": itemset_to_json({"1"}),
                "consequents_json": itemset_to_json({"4"}),
                "antecedent_names_json": itemset_to_json({"Milk"}),
                "consequent_names_json": itemset_to_json({"Milk, Whole"}),
                "support": 0.20,
                "confidence": 0.70,
                "lift": 1.20,
            },
            {
                "antecedents_json": itemset_to_json({"5"}),
                "consequents_json": itemset_to_json({"1"}),
                "antecedent_names_json": itemset_to_json({"Coffee"}),
                "consequent_names_json": itemset_to_json({"Milk"}),
                "support": 0.10,
                "confidence": 0.60,
                "lift": 1.10,
            },
        ]
    )


def test_rule_recommendations_require_the_complete_exact_antecedent(
    rules: pd.DataFrame,
) -> None:
    assert recommendation.recommend_by_rules(
        ["Milk"], rules, item_space="name"
    ) == ["Milk, Whole"]
    assert recommendation.recommend_by_rules(
        ["Milk", "Bread"], rules, item_space="name"
    ) == ["Eggs", "Milk, Whole"]
    assert recommendation.recommend_by_rules(["Mil"], rules, item_space="name") == []


def test_rule_recommendations_exclude_products_already_in_cart(
    rules: pd.DataFrame,
) -> None:
    recommended = recommendation.recommend_by_rules(
        ["Coffee", "Milk"],
        rules,
        item_space="name",
    )

    assert recommended == ["Milk, Whole"]
    assert "Milk" not in recommended


def test_hybrid_recommendation_uses_weighted_rrf_and_filters_cart(
    monkeypatch: pytest.MonkeyPatch,
    rules: pd.DataFrame,
) -> None:
    def rule_ranking(*args: object, **kwargs: object) -> list[str]:
        return ["Rule only", "Shared", "In cart"]

    def cluster_ranking(*args: object, **kwargs: object) -> list[str]:
        return ["Shared", "Cluster only", "In cart"]

    monkeypatch.setattr(recommendation, "recommend_by_rules", rule_ranking)
    monkeypatch.setattr(recommendation, "recommend_by_cluster", cluster_ranking)

    ranked = recommendation.hybrid_recommend(
        123,
        ["In cart"],
        rules,
        pd.DataFrame(),
        n=3,
        rule_weight=0.75,
        cluster_weight=0.25,
        rrf_k=10,
    )

    assert [product for product, _ in ranked] == ["Shared", "Rule only", "Cluster only"]
    assert dict(ranked) == pytest.approx(
        {
            "Shared": 0.75 / 12 + 0.25 / 11,
            "Rule only": 0.75 / 11,
            "Cluster only": 0.25 / 12,
        }
    )
    assert "In cart" not in dict(ranked)


def test_hybrid_recommendation_keeps_id_rankings_in_one_item_space(
    monkeypatch: pytest.MonkeyPatch,
    rules: pd.DataFrame,
) -> None:
    observed: dict[str, str] = {}

    def rule_ranking(*args: object, **kwargs: object) -> list[str]:
        observed["rules"] = str(kwargs["item_space"])
        return ["4"]

    def cluster_ranking(*args: object, **kwargs: object) -> list[str]:
        observed["cluster"] = str(kwargs["item_space"])
        return ["5"]

    monkeypatch.setattr(recommendation, "recommend_by_rules", rule_ranking)
    monkeypatch.setattr(recommendation, "recommend_by_cluster", cluster_ranking)

    ranked = recommendation.hybrid_recommend(
        123,
        ["1"],
        rules,
        pd.DataFrame(),
        n=2,
        item_space="auto",
    )

    assert observed == {"rules": "id", "cluster": "id"}
    assert {product for product, _ in ranked} == {"4", "5"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n": 0},
        {"rule_weight": -0.1},
        {"rule_weight": 0.0, "cluster_weight": 0.0},
        {"rrf_k": -1},
    ],
)
def test_hybrid_recommendation_validates_rank_fusion_controls(
    kwargs: dict[str, float | int],
) -> None:
    with pytest.raises(ValueError):
        recommendation.hybrid_recommend(
            1,
            ["Milk"],
            pd.DataFrame(),
            pd.DataFrame(),
            **kwargs,
        )


def test_recommendation_parser_requires_user_and_cart() -> None:
    parser = recommendation.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])

    args = parser.parse_args(
        [
            "--user-id",
            "42",
            "--cart",
            "Milk, Whole",
            "Bread",
            "--top-n",
            "5",
            "--rule-weight",
            "0.7",
            "--cluster-weight",
            "0.3",
            "--rrf-k",
            "20",
        ]
    )
    assert args.user_id == 42
    assert args.cart == ["Milk, Whole", "Bread"]
    assert (args.top_n, args.rule_weight, args.cluster_weight, args.rrf_k) == (
        5,
        0.7,
        0.3,
        20,
    )
