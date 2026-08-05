from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from etl.quality import (
    WAREHOUSE_CHECKS,
    DataQualityError,
    WarehouseCheckResult,
    require_allowed_values,
    require_columns,
    require_integer_values,
    require_no_nulls,
    require_non_blank_strings,
    require_non_empty,
    require_range,
    require_resolved_detail_times,
    require_source_files,
    require_unique,
    run_warehouse_checks,
    validate_aisles,
    validate_departments,
    validate_order_details,
    validate_orders,
    validate_products,
)


def valid_orders() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "user_id": [10, 10, 20],
            "eval_set": ["prior", "train", "test"],
            "order_number": [1, 2, 1],
            "order_dow": [0, 6, 3],
            "order_hour_of_day": [9, 18, 12],
            "days_since_prior_order": [None, 7.0, None],
        }
    )


def test_require_source_files_accepts_present_paths_and_rejects_bad_keys(tmp_path: Path) -> None:
    orders = tmp_path / "orders.csv"
    orders.touch()
    csv_files = {"orders": orders, "products": tmp_path / "products.csv"}

    require_source_files(csv_files, ["orders"])

    with pytest.raises(DataQualityError, match="Unknown source file keys: missing, unknown"):
        require_source_files(csv_files, ["unknown", "missing"])
    with pytest.raises(DataQualityError, match="Missing source files"):
        require_source_files(csv_files, ["orders", "products"])


def test_primitive_dataframe_contracts_accept_valid_values() -> None:
    frame = pd.DataFrame({"id": [1, 2], "name": ["one", "two"], "optional": [None, 3]})

    require_columns(frame, ["id", "name"], "fixture")
    require_non_empty(frame, "fixture")
    require_no_nulls(frame, ["id", "name"], "fixture")
    require_non_blank_strings(frame, ["name"], "fixture")
    require_integer_values(frame, ["id", "optional"], "fixture", allow_null=True)
    require_range(frame, "optional", 0, 10, "fixture", allow_null=True)
    require_allowed_values(frame, "id", {1, 2}, "fixture")
    require_unique(frame, ["id"], "fixture")


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (lambda: require_columns(pd.DataFrame({"id": [1]}), ["name"], "fixture"), "missing"),
        (lambda: require_non_empty(pd.DataFrame(), "fixture"), "no rows"),
        (
            lambda: require_no_nulls(pd.DataFrame({"id": [None]}), ["id"], "fixture"),
            "NULL",
        ),
        (
            lambda: require_non_blank_strings(
                pd.DataFrame({"name": ["  "]}), ["name"], "fixture"
            ),
            "blank",
        ),
        (
            lambda: require_integer_values(
                pd.DataFrame({"id": ["1.5"]}), ["id"], "fixture"
            ),
            "integers",
        ),
        (
            lambda: require_range(pd.DataFrame({"id": [11]}), "id", 1, 10, "fixture"),
            "between 1 and 10",
        ),
        (
            lambda: require_allowed_values(
                pd.DataFrame({"kind": ["unknown"]}), "kind", {"prior", "train"}, "fixture"
            ),
            "unsupported",
        ),
        (
            lambda: require_unique(pd.DataFrame({"id": [1, 1]}), ["id"], "fixture"),
            "duplicate",
        ),
    ],
)
def test_primitive_dataframe_contracts_show_actionable_errors(operation, message: str) -> None:
    with pytest.raises(DataQualityError, match=message):
        operation()


def test_dataset_validators_accept_small_deterministic_frames() -> None:
    validate_departments(
        pd.DataFrame({"department_id": [1, 2], "department": ["produce", "beverages"]})
    )
    validate_aisles(pd.DataFrame({"aisle_id": [1, 2], "aisle": ["fresh fruit", "tea"]}))
    validate_products(
        pd.DataFrame(
            {
                "product_id": [1, 2],
                "product_name": ["Banana", "Tea"],
                "aisle_id": [1, 2],
                "department_id": [1, 2],
            }
        )
    )
    validate_orders(valid_orders())
    validate_order_details(
        pd.DataFrame(
            {
                "order_id": [1, 1],
                "product_id": [1, 2],
                "add_to_cart_order": [1, 2],
                "reordered": [0, 1],
            }
        ),
        dataset="details_fixture",
    )


def test_order_validator_preserves_first_order_null_contract() -> None:
    invalid = valid_orders()
    invalid.loc[0, "days_since_prior_order"] = 3.0
    invalid.loc[1, "days_since_prior_order"] = None

    with pytest.raises(DataQualityError, match="must be NULL only for order_number=1"):
        validate_orders(invalid)


def test_order_detail_validator_rejects_duplicate_cart_positions() -> None:
    details = pd.DataFrame(
        {
            "order_id": [1, 1],
            "product_id": [10, 11],
            "add_to_cart_order": [1, 1],
            "reordered": [0, 1],
        }
    )

    with pytest.raises(DataQualityError, match="add_to_cart_order"):
        validate_order_details(details)


def test_warehouse_check_result_exposes_pass_status() -> None:
    assert WarehouseCheckResult("good", actual=0, expected=0).passed is True
    assert WarehouseCheckResult("bad", actual=1, expected=0).passed is False


def test_require_resolved_detail_times_accepts_clean_reconciliation() -> None:
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "unresolved": None,
        "mismatched": 0,
        "orphaned": 0,
    }

    require_resolved_detail_times(connection)


def test_require_resolved_detail_times_reports_every_failure() -> None:
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "unresolved": 2,
        "mismatched": 3,
        "orphaned": 1,
    }

    with pytest.raises(DataQualityError) as error:
        require_resolved_detail_times(connection)

    assert "unresolved=2" in str(error.value)
    assert "mismatched=3" in str(error.value)
    assert "orphaned=1" in str(error.value)


def scalar_result(value: int) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def test_run_warehouse_checks_returns_complete_passing_results() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [
        scalar_result(check.expected) for check in WAREHOUSE_CHECKS
    ]

    results = run_warehouse_checks(connection)

    assert [result.name for result in results] == [check.name for check in WAREHOUSE_CHECKS]
    assert all(result.passed for result in results)


def test_run_warehouse_checks_aggregates_failures() -> None:
    connection = MagicMock()
    actual_values = [167, 2, 0, 0, 0, 0, 1]
    connection.execute.side_effect = [scalar_result(value) for value in actual_values]

    with pytest.raises(DataQualityError) as error:
        run_warehouse_checks(connection)

    assert "time_dimension_rows: expected 168, got 167" in str(error.value)
    assert "duplicate_orders: expected 0, got 2" in str(error.value)
    assert "users_without_orders: expected 0, got 1" in str(error.value)
