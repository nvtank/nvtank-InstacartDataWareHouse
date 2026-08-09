"""Pure, testable DataFrame transforms for the Instacart warehouse."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from etl.quality import (
    validate_aisles,
    validate_departments,
    validate_order_details,
    validate_orders,
    validate_products,
)

DEPARTMENT_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Food", ("produce", "frozen", "meat", "seafood", "deli")),
    ("Beverage", ("dairy", "beverage", "alcohol")),
    ("Personal Care", ("personal", "beauty", "health")),
    ("Household", ("household", "pets")),
)

AISLE_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Fresh", ("fresh", "produce", "fruit", "vegetable")),
    ("Frozen", ("frozen", "ice")),
    ("Beverage", ("beverage", "drink", "juice", "soda", "water")),
    ("Snacks", ("snack", "candy", "chocolate", "cookies")),
    ("Dairy", ("dairy", "milk", "yogurt", "cheese")),
    ("Dry Goods", ("packaged", "canned", "dry")),
)


def _classify(value: str, rules: Iterable[tuple[str, tuple[str, ...]]], default: str) -> str:
    normalized = value.strip().casefold()
    for label, keywords in rules:
        if any(keyword in normalized for keyword in keywords):
            return label
    return default


def categorize_department(name: str) -> str:
    return _classify(name, DEPARTMENT_CATEGORY_RULES, "General")


def categorize_aisle(name: str) -> str:
    return _classify(name, AISLE_TYPE_RULES, "General")


def transform_departments(source: pd.DataFrame) -> pd.DataFrame:
    validate_departments(source)
    transformed = source.loc[:, ["department_id", "department"]].copy()
    transformed["department_id"] = pd.to_numeric(
        transformed["department_id"], errors="raise"
    ).astype("int64")
    transformed["dept_category"] = transformed["department"].map(categorize_department)
    return transformed.rename(columns={"department": "department_name"})


def transform_aisles(source: pd.DataFrame) -> pd.DataFrame:
    validate_aisles(source)
    transformed = source.loc[:, ["aisle_id", "aisle"]].copy()
    transformed["aisle_id"] = pd.to_numeric(transformed["aisle_id"], errors="raise").astype(
        "int64"
    )
    transformed["aisle_type"] = transformed["aisle"].map(categorize_aisle)
    return transformed.rename(columns={"aisle": "aisle_name"})


def transform_products(source: pd.DataFrame) -> pd.DataFrame:
    validate_products(source)
    columns = ["product_id", "product_name", "aisle_id", "department_id"]
    transformed = source.loc[:, columns].copy()
    for column in ["product_id", "aisle_id", "department_id"]:
        transformed[column] = pd.to_numeric(transformed[column], errors="raise").astype("int64")
    transformed["product_category"] = "General"
    return transformed


def transform_orders(source: pd.DataFrame) -> pd.DataFrame:
    """Create Fact_Orders rows while preserving first-order NULL semantics."""
    validate_orders(source)
    transformed = source.loc[source["eval_set"].isin(["prior", "train"])].copy()
    if transformed.empty:
        return pd.DataFrame(
            columns=[
                "order_id",
                "user_id",
                "time_id",
                "order_number",
                "days_since_prior_order",
                "order_dow",
                "total_items",
                "reorder_ratio",
            ]
        )

    integer_columns = ["order_id", "user_id", "order_number", "order_dow", "order_hour_of_day"]
    for column in integer_columns:
        transformed[column] = pd.to_numeric(transformed[column], errors="raise").astype("int64")
    transformed["days_since_prior_order"] = pd.to_numeric(
        transformed["days_since_prior_order"], errors="raise"
    ).astype("Float64")
    transformed["time_id"] = (
        transformed["order_dow"] * 100 + transformed["order_hour_of_day"]
    ).astype("int64")
    transformed["total_items"] = 0
    transformed["reorder_ratio"] = 0.0

    return transformed.loc[
        :,
        [
            "order_id",
            "user_id",
            "time_id",
            "order_number",
            "days_since_prior_order",
            "order_dow",
            "total_items",
            "reorder_ratio",
        ],
    ]


def transform_order_details(source: pd.DataFrame, dataset: str = "order_products") -> pd.DataFrame:
    """Create line-item facts with NULL time_id until parent-order reconciliation."""
    validate_order_details(source, dataset)
    columns = ["order_id", "product_id", "add_to_cart_order", "reordered"]
    transformed = source.loc[:, columns].copy()
    for column in columns:
        transformed[column] = pd.to_numeric(transformed[column], errors="raise").astype("int64")
    transformed["time_id"] = pd.array([pd.NA] * len(transformed), dtype="Int64")
    transformed["quantity"] = 1
    return transformed.loc[
        :,
        [
            "order_id",
            "product_id",
            "time_id",
            "add_to_cart_order",
            "reordered",
            "quantity",
        ],
    ]
