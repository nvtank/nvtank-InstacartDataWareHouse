from pathlib import Path

import pandas as pd
import pytest

from mining.artifacts import itemset_from_json
from mining.market_basket import (
    build_parser,
    create_basket_matrix,
    save_frequent_itemsets,
    save_rules,
)


def test_basket_matrix_is_sparse_and_preserves_every_transaction() -> None:
    transactions = [["1", "2"], ["1"], ["3"]]

    matrix = create_basket_matrix(transactions, top_n_products=2)

    assert matrix.columns.tolist() == ["1", "2"]
    assert len(matrix) == len(transactions)
    assert all(isinstance(dtype, pd.SparseDtype) for dtype in matrix.dtypes)
    assert matrix.sparse.to_dense().astype(int).values.tolist() == [
        [1, 1],
        [1, 0],
        [0, 0],
    ]


def test_frequent_itemset_serialization_preserves_exact_ids_and_names(
    tmp_path: Path,
) -> None:
    itemsets = pd.DataFrame(
        {
            "support": [0.4],
            "itemsets": [frozenset({"2", "1"})],
        }
    )
    destination = tmp_path / "frequent_itemsets.csv"

    assert save_frequent_itemsets(
        itemsets,
        destination,
        catalog={"1": "Milk, Whole", "2": "Bread"},
    ) == destination

    saved = pd.read_csv(destination).iloc[0]
    assert itemset_from_json(saved["itemsets_json"]) == frozenset({"1", "2"})
    assert itemset_from_json(saved["item_names_json"]) == frozenset(
        {"Milk, Whole", "Bread"}
    )
    assert saved["length"] == 2


def test_rule_serialization_preserves_exact_antecedents_and_consequents(
    tmp_path: Path,
) -> None:
    rules = pd.DataFrame(
        {
            "antecedents": [frozenset({"1", "2"})],
            "consequents": [frozenset({"3"})],
            "support": [0.2],
            "confidence": [0.5],
            "lift": [1.4],
            "leverage": [0.05],
            "conviction": [1.2],
        }
    )
    destination = tmp_path / "association_rules.csv"

    assert save_rules(
        rules,
        destination,
        catalog={"1": "Milk, Whole", "2": "Bread", "3": "Eggs"},
    ) == destination

    saved = pd.read_csv(destination).iloc[0]
    assert itemset_from_json(saved["antecedents_json"]) == frozenset({"1", "2"})
    assert itemset_from_json(saved["consequents_json"]) == frozenset({"3"})
    assert itemset_from_json(saved["antecedent_names_json"]) == frozenset(
        {"Milk, Whole", "Bread"}
    )
    assert itemset_from_json(saved["consequent_names_json"]) == frozenset({"Eggs"})


def test_market_basket_parser_rejects_sample_and_full_modes_together() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--order-limit", "100", "--full"])

    args = parser.parse_args(["--order-limit", "100", "--seed", "7", "--no-plot"])
    assert (args.order_limit, args.full, args.seed, args.no_plot) == (100, False, 7, True)
