import json
from pathlib import Path

import pytest

from mining.artifacts import ensure_results_dir, itemset_from_json, itemset_to_json


def test_itemset_json_round_trip_preserves_commas_and_normalizes_identifiers() -> None:
    encoded = itemset_to_json({42, "Milk, Whole", "Bread"})

    assert json.loads(encoded) == ["42", "Bread", "Milk, Whole"]
    assert itemset_from_json(encoded) == frozenset({"42", "Bread", "Milk, Whole"})


@pytest.mark.parametrize(
    "value",
    [
        "not-json",
        '{"item":"Milk"}',
        '["Milk",null]',
        '["Milk",1.5]',
        '["Milk",true]',
    ],
)
def test_itemset_from_json_rejects_invalid_artifact_values(value: str) -> None:
    with pytest.raises(ValueError, match="itemset JSON|Itemset JSON"):
        itemset_from_json(value)


def test_ensure_results_dir_creates_nested_destination(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "results"

    assert ensure_results_dir(destination) == destination
    assert destination.is_dir()
