"""Data-contract validation for Instacart source files and ETL outputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


class DataQualityError(ValueError):
    """Raised when source data violates a warehouse data contract."""


@dataclass(frozen=True, slots=True)
class WarehouseCheck:
    name: str
    query: str
    expected: int = 0


@dataclass(frozen=True, slots=True)
class WarehouseCheckResult:
    name: str
    actual: int
    expected: int

    @property
    def passed(self) -> bool:
        return self.actual == self.expected


WAREHOUSE_CHECKS = (
    WarehouseCheck("time_dimension_rows", "SELECT COUNT(*) FROM Dim_Time", expected=168),
    WarehouseCheck(
        "duplicate_orders",
        """
        SELECT COUNT(*) FROM (
            SELECT order_id FROM Fact_Orders GROUP BY order_id HAVING COUNT(*) > 1
        ) duplicate_orders
        """,
    ),
    WarehouseCheck(
        "orders_without_items",
        "SELECT COUNT(*) FROM Fact_Orders WHERE total_items <= 0",
    ),
    WarehouseCheck(
        "invalid_order_intervals",
        """
        SELECT COUNT(*) FROM Fact_Orders
        WHERE (order_number = 1 AND days_since_prior_order IS NOT NULL)
           OR (order_number > 1 AND days_since_prior_order IS NULL)
        """,
    ),
    WarehouseCheck(
        "unresolved_detail_times",
        "SELECT COUNT(*) FROM Fact_Order_Details WHERE time_id IS NULL",
    ),
    WarehouseCheck(
        "orphan_detail_products",
        """
        SELECT COUNT(*)
        FROM Fact_Order_Details details
        LEFT JOIN Dim_Product products ON details.product_id = products.product_id
        WHERE products.product_id IS NULL
        """,
    ),
    WarehouseCheck(
        "users_without_orders",
        "SELECT COUNT(*) FROM Dim_User WHERE total_orders <= 0",
    ),
)


def _column_label(columns: Sequence[str]) -> str:
    return ", ".join(columns)


def _sample_rows(
    frame: pd.DataFrame,
    mask: pd.Series,
    columns: Sequence[str],
) -> list[dict[str, Any]]:
    return frame.loc[mask, list(columns)].head(5).to_dict(orient="records")


def require_source_files(csv_files: Mapping[str, Path], keys: Iterable[str]) -> None:
    """Require each named source file before opening a database transaction."""
    unknown = [key for key in keys if key not in csv_files]
    if unknown:
        raise DataQualityError(f"Unknown source file keys: {', '.join(sorted(unknown))}")

    missing = [csv_files[key] for key in keys if not csv_files[key].is_file()]
    if missing:
        formatted = ", ".join(str(path) for path in missing)
        raise DataQualityError(f"Missing source files: {formatted}")


def require_columns(frame: pd.DataFrame, required: Sequence[str], dataset: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise DataQualityError(f"{dataset}: missing required columns: {_column_label(missing)}")


def require_non_empty(frame: pd.DataFrame, dataset: str) -> None:
    if frame.empty:
        raise DataQualityError(f"{dataset}: source contains no rows")


def require_no_nulls(frame: pd.DataFrame, columns: Sequence[str], dataset: str) -> None:
    for column in columns:
        mask = frame[column].isna()
        if mask.any():
            sample = _sample_rows(frame, mask, [column])
            raise DataQualityError(f"{dataset}: {column} contains NULL values; sample={sample}")


def require_non_blank_strings(frame: pd.DataFrame, columns: Sequence[str], dataset: str) -> None:
    require_no_nulls(frame, columns, dataset)
    for column in columns:
        mask = frame[column].astype("string").str.strip().eq("")
        if mask.any():
            sample = _sample_rows(frame, mask, [column])
            raise DataQualityError(f"{dataset}: {column} contains blank values; sample={sample}")


def require_integer_values(
    frame: pd.DataFrame,
    columns: Sequence[str],
    dataset: str,
    *,
    allow_null: bool = False,
) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        invalid_numeric = frame[column].notna() & values.isna()
        non_integer = values.notna() & values.mod(1).ne(0)
        invalid = invalid_numeric | non_integer
        if not allow_null:
            invalid |= frame[column].isna()
        if invalid.any():
            sample = _sample_rows(frame, invalid, [column])
            raise DataQualityError(f"{dataset}: {column} must contain integers; sample={sample}")


def require_range(
    frame: pd.DataFrame,
    column: str,
    minimum: float,
    maximum: float | None,
    dataset: str,
    *,
    allow_null: bool = False,
) -> None:
    values = pd.to_numeric(frame[column], errors="coerce")
    invalid = frame[column].notna() & values.isna()
    invalid |= values.notna() & values.lt(minimum)
    if maximum is not None:
        invalid |= values.notna() & values.gt(maximum)
    if not allow_null:
        invalid |= frame[column].isna()
    if invalid.any():
        upper = "unbounded" if maximum is None else str(maximum)
        sample = _sample_rows(frame, invalid, [column])
        raise DataQualityError(
            f"{dataset}: {column} must be between {minimum} and {upper}; sample={sample}"
        )


def require_allowed_values(
    frame: pd.DataFrame,
    column: str,
    allowed: Iterable[object],
    dataset: str,
) -> None:
    allowed_values = frozenset(allowed)
    invalid = frame[column].isna() | ~frame[column].isin(allowed_values)
    if invalid.any():
        sample = _sample_rows(frame, invalid, [column])
        expected = ", ".join(sorted(str(value) for value in allowed_values))
        raise DataQualityError(
            f"{dataset}: {column} contains unsupported values; "
            f"expected one of {expected}; sample={sample}"
        )


def require_unique(frame: pd.DataFrame, columns: Sequence[str], dataset: str) -> None:
    duplicates = frame.duplicated(subset=list(columns), keep=False)
    if duplicates.any():
        sample = _sample_rows(frame, duplicates, columns)
        raise DataQualityError(
            f"{dataset}: duplicate business key ({_column_label(columns)}); sample={sample}"
        )


def validate_departments(frame: pd.DataFrame) -> None:
    dataset = "departments"
    require_columns(frame, ["department_id", "department"], dataset)
    require_non_empty(frame, dataset)
    require_integer_values(frame, ["department_id"], dataset)
    require_range(frame, "department_id", 1, None, dataset)
    require_non_blank_strings(frame, ["department"], dataset)
    require_unique(frame, ["department_id"], dataset)
    require_unique(frame, ["department"], dataset)


def validate_aisles(frame: pd.DataFrame) -> None:
    dataset = "aisles"
    require_columns(frame, ["aisle_id", "aisle"], dataset)
    require_non_empty(frame, dataset)
    require_integer_values(frame, ["aisle_id"], dataset)
    require_range(frame, "aisle_id", 1, None, dataset)
    require_non_blank_strings(frame, ["aisle"], dataset)
    require_unique(frame, ["aisle_id"], dataset)
    require_unique(frame, ["aisle"], dataset)


def validate_products(frame: pd.DataFrame) -> None:
    dataset = "products"
    columns = ["product_id", "product_name", "aisle_id", "department_id"]
    require_columns(frame, columns, dataset)
    require_non_empty(frame, dataset)
    require_integer_values(frame, ["product_id", "aisle_id", "department_id"], dataset)
    for column in ["product_id", "aisle_id", "department_id"]:
        require_range(frame, column, 1, None, dataset)
    require_non_blank_strings(frame, ["product_name"], dataset)
    require_unique(frame, ["product_id"], dataset)


def validate_orders(frame: pd.DataFrame) -> None:
    dataset = "orders"
    columns = [
        "order_id",
        "user_id",
        "eval_set",
        "order_number",
        "order_dow",
        "order_hour_of_day",
        "days_since_prior_order",
    ]
    require_columns(frame, columns, dataset)
    require_non_empty(frame, dataset)
    integer_columns = ["order_id", "user_id", "order_number", "order_dow", "order_hour_of_day"]
    require_integer_values(frame, integer_columns, dataset)
    require_range(frame, "order_id", 1, None, dataset)
    require_range(frame, "user_id", 1, None, dataset)
    require_range(frame, "order_number", 1, None, dataset)
    require_range(frame, "order_dow", 0, 6, dataset)
    require_range(frame, "order_hour_of_day", 0, 23, dataset)
    require_range(frame, "days_since_prior_order", 0, 30, dataset, allow_null=True)
    require_allowed_values(frame, "eval_set", {"prior", "train", "test"}, dataset)
    require_unique(frame, ["order_id"], dataset)

    order_number = pd.to_numeric(frame["order_number"], errors="coerce")
    first_order = order_number.eq(1)
    days_missing = frame["days_since_prior_order"].isna()
    invalid_first_order = first_order & ~days_missing
    invalid_later_order = ~first_order & days_missing
    invalid = invalid_first_order | invalid_later_order
    if invalid.any():
        sample = _sample_rows(
            frame,
            invalid,
            ["order_id", "order_number", "days_since_prior_order"],
        )
        raise DataQualityError(
            f"{dataset}: days_since_prior_order must be NULL only for "
            f"order_number=1; sample={sample}"
        )


def validate_order_details(frame: pd.DataFrame, dataset: str = "order_products") -> None:
    columns = ["order_id", "product_id", "add_to_cart_order", "reordered"]
    require_columns(frame, columns, dataset)
    require_non_empty(frame, dataset)
    require_integer_values(frame, columns, dataset)
    require_range(frame, "order_id", 1, None, dataset)
    require_range(frame, "product_id", 1, None, dataset)
    require_range(frame, "add_to_cart_order", 1, 32_767, dataset)
    require_allowed_values(frame, "reordered", {0, 1}, dataset)
    require_unique(frame, ["order_id", "product_id"], dataset)
    require_unique(frame, ["order_id", "add_to_cart_order"], dataset)


def require_resolved_detail_times(connection: Connection) -> None:
    """Fail when an order detail cannot be reconciled to its parent order."""
    result = connection.execute(
        text(
            """
            SELECT
                SUM(details.time_id IS NULL) AS unresolved,
                SUM(
                    details.time_id IS NOT NULL
                    AND orders.order_id IS NOT NULL
                    AND details.time_id <> orders.time_id
                ) AS mismatched,
                SUM(orders.order_id IS NULL) AS orphaned
            FROM Fact_Order_Details details
            LEFT JOIN Fact_Orders orders ON details.order_id = orders.order_id
            """
        )
    ).mappings().one()
    failures = {
        label: int(result[label] or 0)
        for label in ("unresolved", "mismatched", "orphaned")
        if int(result[label] or 0) > 0
    }
    if failures:
        summary = ", ".join(f"{label}={count:,}" for label, count in failures.items())
        raise DataQualityError(f"Fact_Order_Details reconciliation failed: {summary}")


def run_warehouse_checks(bind: Engine | Connection) -> tuple[WarehouseCheckResult, ...]:
    """Execute static warehouse contracts and raise once with the complete failure set."""
    owns_connection = isinstance(bind, Engine)
    connection = bind.connect() if owns_connection else bind
    try:
        results = tuple(
            WarehouseCheckResult(
                name=check.name,
                actual=int(connection.execute(text(check.query)).scalar_one()),
                expected=check.expected,
            )
            for check in WAREHOUSE_CHECKS
        )
    finally:
        if owns_connection:
            connection.close()

    failures = [result for result in results if not result.passed]
    if failures:
        summary = "; ".join(
            f"{result.name}: expected {result.expected:,}, got {result.actual:,}"
            for result in failures
        )
        raise DataQualityError(f"Warehouse validation failed: {summary}")
    return results
