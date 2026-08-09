"""Exact-set and cluster-popularity recommendation with weighted rank fusion."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from etl.config import Settings, get_engine, get_settings
from mining.artifacts import DEFAULT_RESULTS_DIR, itemset_from_json

TEMP_CLUSTER_TABLE = "tmp_instacart_cluster_members"


class RecommendationDataError(ValueError):
    """Raised when recommendation artifacts violate their data contract."""


def _artifact_path(path: Path | str | None, default_name: str) -> Path:
    return Path(path) if path is not None else DEFAULT_RESULTS_DIR / default_name


def load_association_rules(path: Path | str | None = None) -> pd.DataFrame:
    rules_path = _artifact_path(path, "association_rules.csv")
    if not rules_path.is_file():
        raise FileNotFoundError(
            f"Association rules not found at {rules_path}; run instacart-basket first"
        )
    rules = pd.read_csv(rules_path)
    required = {
        "antecedents_json",
        "consequents_json",
        "support",
        "confidence",
        "lift",
    }
    missing = sorted(required.difference(rules.columns))
    if missing:
        raise RecommendationDataError(
            "Association rules use an unsupported schema; rerun market-basket mining. "
            f"Missing: {', '.join(missing)}"
        )
    if rules.empty:
        raise RecommendationDataError("Association-rule artifact is empty")
    prepared = rules.copy()
    prepared["antecedent_items"] = prepared["antecedents_json"].map(itemset_from_json)
    prepared["consequent_items"] = prepared["consequents_json"].map(itemset_from_json)
    if {"antecedent_names_json", "consequent_names_json"}.issubset(prepared.columns):
        prepared["antecedent_name_items"] = prepared["antecedent_names_json"].map(
            itemset_from_json
        )
        prepared["consequent_name_items"] = prepared["consequent_names_json"].map(
            itemset_from_json
        )
    for column in ("support", "confidence", "lift"):
        prepared[column] = pd.to_numeric(prepared[column], errors="raise")
    return prepared


def load_cluster_labels(path: Path | str | None = None) -> pd.DataFrame:
    labels_path = _artifact_path(path, "cluster_labels.csv")
    if not labels_path.is_file():
        raise FileNotFoundError(
            f"Cluster labels not found at {labels_path}; run instacart-cluster first"
        )
    labels = pd.read_csv(labels_path)
    required = {"user_id", "cluster"}
    missing = sorted(required.difference(labels.columns))
    if missing:
        raise RecommendationDataError(f"Cluster labels missing: {', '.join(missing)}")
    if labels.empty:
        raise RecommendationDataError("Cluster-label artifact is empty")
    if labels.loc[:, ["user_id", "cluster"]].isna().any().any():
        raise RecommendationDataError("Cluster labels contain NULL values")

    prepared = labels.loc[:, ["user_id", "cluster"]].copy()
    prepared["user_id"] = pd.to_numeric(prepared["user_id"], errors="raise").astype("int64")
    prepared["cluster"] = pd.to_numeric(prepared["cluster"], errors="raise").astype("int64")
    conflicting = prepared.groupby("user_id")["cluster"].nunique().gt(1)
    if conflicting.any():
        users = conflicting[conflicting].index[:5].tolist()
        raise RecommendationDataError(f"Users have conflicting cluster labels: {users}")
    return prepared.drop_duplicates("user_id").sort_values("user_id").reset_index(drop=True)


def _prepare_rules(rules: pd.DataFrame) -> pd.DataFrame:
    if {"antecedent_items", "consequent_items"}.issubset(rules.columns):
        return rules
    required = {"antecedents_json", "consequents_json", "support", "confidence", "lift"}
    missing = sorted(required.difference(rules.columns))
    if missing:
        raise RecommendationDataError(
            "Rules must use JSON itemsets; missing columns: " + ", ".join(missing)
        )
    prepared = rules.copy()
    prepared["antecedent_items"] = prepared["antecedents_json"].map(itemset_from_json)
    prepared["consequent_items"] = prepared["consequents_json"].map(itemset_from_json)
    if {"antecedent_names_json", "consequent_names_json"}.issubset(prepared.columns):
        prepared["antecedent_name_items"] = prepared["antecedent_names_json"].map(
            itemset_from_json
        )
        prepared["consequent_name_items"] = prepared["consequent_names_json"].map(
            itemset_from_json
        )
    return prepared


def _rule_item_columns(
    cart: frozenset[str],
    rules: pd.DataFrame,
    item_space: str,
) -> tuple[str, str]:
    if item_space not in {"auto", "id", "name"}:
        raise ValueError("item_space must be one of: auto, id, name")
    has_names = {"antecedent_name_items", "consequent_name_items"}.issubset(
        rules.columns
    )
    if item_space == "name":
        if not has_names:
            raise RecommendationDataError("Rules do not contain product-name itemsets")
        return "antecedent_name_items", "consequent_name_items"
    if item_space == "id" or not has_names:
        return "antecedent_items", "consequent_items"

    known_names: set[str] = set()
    for values in rules["antecedent_name_items"]:
        known_names.update(values)
    for values in rules["consequent_name_items"]:
        known_names.update(values)
    if cart.intersection(known_names):
        return "antecedent_name_items", "consequent_name_items"
    return "antecedent_items", "consequent_items"


def recommend_by_rules(
    cart_items: Iterable[object],
    rules: pd.DataFrame,
    n: int = 5,
    *,
    item_space: str = "auto",
) -> list[str]:
    """Apply a rule only when its complete antecedent is an exact cart subset."""
    if n <= 0:
        raise ValueError("n must be positive")
    prepared = _prepare_rules(rules)
    if prepared.empty:
        return []
    cart = frozenset(str(item) for item in cart_items)
    if not cart:
        return []
    antecedent_column, consequent_column = _rule_item_columns(cart, prepared, item_space)

    scores: defaultdict[str, float] = defaultdict(float)
    for row in prepared.itertuples(index=False):
        antecedents = getattr(row, antecedent_column)
        if not antecedents or not antecedents.issubset(cart):
            continue
        quality = float(row.support) * float(row.confidence) * max(float(row.lift), 0.0)
        for product in getattr(row, consequent_column):
            if product not in cart:
                scores[product] += quality
    return [
        product
        for product, _ in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:n]
    ]


def _create_cluster_table(connection: Connection, members: pd.DataFrame) -> None:
    connection.execute(text(f"DROP TEMPORARY TABLE IF EXISTS {TEMP_CLUSTER_TABLE}"))
    connection.execute(
        text(
            f"""
            CREATE TEMPORARY TABLE {TEMP_CLUSTER_TABLE} (
                user_id INT PRIMARY KEY,
                cluster_id INT NOT NULL
            ) ENGINE=MEMORY
            """
        )
    )
    statement = text(
        f"INSERT INTO {TEMP_CLUSTER_TABLE} (user_id, cluster_id) "
        "VALUES (:user_id, :cluster_id)"
    )
    records = [
        {"user_id": int(row.user_id), "cluster_id": int(row.cluster)}
        for row in members.itertuples(index=False)
    ]
    for start in range(0, len(records), 5_000):
        connection.execute(statement, records[start : start + 5_000])


def recommend_by_cluster(
    user_id: int,
    clusters: pd.DataFrame,
    n: int = 5,
    *,
    engine: Engine | None = None,
    settings: Settings | None = None,
    exclude_items: Iterable[object] = (),
    item_space: str = "name",
) -> list[str]:
    """Rank products among users in the same cluster via a connection-local table."""
    if n <= 0:
        raise ValueError("n must be positive")
    if item_space not in {"id", "name"}:
        raise ValueError("item_space must be one of: id, name")
    labels = load_cluster_labels_from_frame(clusters)
    user_rows = labels.loc[labels["user_id"].eq(int(user_id)), "cluster"]
    if user_rows.empty:
        return []
    cluster_id = int(user_rows.iloc[0])
    members = labels.loc[labels["cluster"].eq(cluster_id)]
    excluded = frozenset(str(item) for item in exclude_items)
    resolved = settings or get_settings()
    warehouse_engine = engine or get_engine(resolved)
    candidate_limit = max(50, n * 10)
    query = text(
        f"""
        SELECT
            products.product_id,
            products.product_name,
            COUNT(DISTINCT details.order_id) AS order_count,
            AVG(details.reordered) AS reorder_rate
        FROM {TEMP_CLUSTER_TABLE} members
        JOIN Fact_Orders orders ON members.user_id = orders.user_id
        JOIN Fact_Order_Details details ON orders.order_id = details.order_id
        JOIN Dim_Product products ON details.product_id = products.product_id
        WHERE members.cluster_id = :cluster_id
        GROUP BY products.product_id, products.product_name
        ORDER BY order_count DESC, reorder_rate DESC, products.product_id
        LIMIT :candidate_limit
        """
    )

    with warehouse_engine.begin() as connection:
        _create_cluster_table(connection, members)
        try:
            candidates = pd.read_sql(
                query,
                connection,
                params={"cluster_id": cluster_id, "candidate_limit": candidate_limit},
            )
        finally:
            connection.execute(text(f"DROP TEMPORARY TABLE IF EXISTS {TEMP_CLUSTER_TABLE}"))
    if candidates.empty:
        return []
    recommendations = []
    for row in candidates.itertuples(index=False):
        product_id = str(row.product_id)
        product_name = str(row.product_name)
        if product_name in excluded or product_id in excluded:
            continue
        recommendations.append(product_name if item_space == "name" else product_id)
    return recommendations[:n]


def load_cluster_labels_from_frame(labels: pd.DataFrame) -> pd.DataFrame:
    required = {"user_id", "cluster"}
    missing = sorted(required.difference(labels.columns))
    if missing:
        raise RecommendationDataError(f"Cluster labels missing: {', '.join(missing)}")
    if labels.empty:
        raise RecommendationDataError("Cluster labels are empty")
    if labels.loc[:, ["user_id", "cluster"]].isna().any().any():
        raise RecommendationDataError("Cluster labels contain NULL values")
    prepared = labels.loc[:, ["user_id", "cluster"]].copy()
    prepared["user_id"] = pd.to_numeric(prepared["user_id"], errors="raise").astype("int64")
    prepared["cluster"] = pd.to_numeric(prepared["cluster"], errors="raise").astype("int64")
    conflicting = prepared.groupby("user_id")["cluster"].nunique().gt(1)
    if conflicting.any():
        raise RecommendationDataError("A user has conflicting cluster assignments")
    return prepared.drop_duplicates("user_id")


def hybrid_recommend(
    user_id: int,
    cart_items: Iterable[object],
    rules: pd.DataFrame,
    clusters: pd.DataFrame,
    n: int = 10,
    *,
    engine: Engine | None = None,
    settings: Settings | None = None,
    rule_weight: float = 0.6,
    cluster_weight: float = 0.4,
    rrf_k: int = 60,
    item_space: str = "auto",
) -> list[tuple[str, float]]:
    """Fuse independent rankings with weighted reciprocal-rank fusion."""
    if n <= 0:
        raise ValueError("n must be positive")
    if rule_weight < 0 or cluster_weight < 0 or rule_weight + cluster_weight <= 0:
        raise ValueError("rank-fusion weights must be non-negative with a positive sum")
    if rrf_k < 0:
        raise ValueError("rrf_k must be non-negative")
    cart = frozenset(str(item) for item in cart_items)
    prepared_rules = _prepare_rules(rules)
    antecedent_column, _ = _rule_item_columns(cart, prepared_rules, item_space)
    resolved_item_space = "name" if antecedent_column.startswith("antecedent_name") else "id"
    rule_ranking = recommend_by_rules(
        cart,
        prepared_rules,
        n=n * 3,
        item_space=resolved_item_space,
    )
    cluster_ranking = recommend_by_cluster(
        user_id,
        clusters,
        n=n * 3,
        engine=engine,
        settings=settings,
        exclude_items=cart,
        item_space=resolved_item_space,
    )

    scores: defaultdict[str, float] = defaultdict(float)
    for rank, product in enumerate(rule_ranking, start=1):
        if product not in cart:
            scores[product] += rule_weight / (rrf_k + rank)
    for rank, product in enumerate(cluster_ranking, start=1):
        if product not in cart:
            scores[product] += cluster_weight / (rrf_k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:n]


def evaluate_recommendations(rules: pd.DataFrame | None = None) -> dict[str, float | int]:
    prepared = load_association_rules() if rules is None else _prepare_rules(rules)
    antecedents: set[str] = set()
    consequents: set[str] = set()
    for row in prepared.itertuples(index=False):
        antecedents.update(row.antecedent_items)
        consequents.update(row.consequent_items)
    return {
        "rules": len(prepared),
        "average_lift": float(pd.to_numeric(prepared["lift"]).mean()),
        "high_confidence_rules": int(pd.to_numeric(prepared["confidence"]).ge(0.5).sum()),
        "covered_products": len(antecedents | consequents),
    }


def demo_recommendations(
    *,
    user_id: int,
    cart_items: Sequence[str],
    rules: pd.DataFrame,
    clusters: pd.DataFrame,
    engine: Engine | None = None,
    settings: Settings | None = None,
    n: int = 10,
) -> list[tuple[str, float]]:
    recommendations = hybrid_recommend(
        user_id,
        cart_items,
        rules,
        clusters,
        n,
        engine=engine,
        settings=settings,
        item_space="name",
    )
    for rank, (product, score) in enumerate(recommendations, start=1):
        print(f"{rank:>2}. {product} (rank-fusion score={score:.6f})")
    return recommendations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--cart", nargs="+", required=True, help="Exact product names in the cart")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--rules", type=Path)
    parser.add_argument("--clusters", type=Path)
    parser.add_argument("--rule-weight", type=float, default=0.6)
    parser.add_argument("--cluster-weight", type=float, default=0.4)
    parser.add_argument("--rrf-k", type=int, default=60)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    rules = load_association_rules(args.rules)
    clusters = load_cluster_labels(args.clusters)
    recommendations = hybrid_recommend(
        args.user_id,
        args.cart,
        rules,
        clusters,
        args.top_n,
        settings=settings,
        rule_weight=args.rule_weight,
        cluster_weight=args.cluster_weight,
        rrf_k=args.rrf_k,
        item_space="name",
    )
    if not recommendations:
        print("No recommendations matched the supplied user and cart.")
        return 0
    for rank, (product, score) in enumerate(recommendations, start=1):
        print(f"{rank:>2}. {product} (rank-fusion score={score:.6f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
