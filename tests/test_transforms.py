import pandas as pd
import pytest

from etl.quality import DataQualityError
from etl.transforms import (
    categorize_aisle,
    categorize_department,
    transform_aisles,
    transform_departments,
    transform_order_details,
    transform_orders,
    transform_products,
)


def test_category_rules_are_case_insensitive_and_have_fallbacks() -> None:
    assert categorize_department(" Fresh Produce ") == "Food"
    assert categorize_department("DAIRY EGGS") == "Beverage"
    assert categorize_department("international") == "General"
    assert categorize_aisle("Frozen Desserts") == "Frozen"
    assert categorize_aisle("Sparkling Water") == "Beverage"
    assert categorize_aisle("international") == "General"


def test_transform_departments_copies_input_and_adds_categories() -> None:
    source = pd.DataFrame(
        {
            "department_id": ["1", "2", "3"],
            "department": ["produce", "personal care", "other"],
            "ignored": [True, True, True],
        }
    )
    original = source.copy(deep=True)

    result = transform_departments(source)

    pd.testing.assert_frame_equal(source, original)
    assert result.to_dict(orient="records") == [
        {"department_id": 1, "department_name": "produce", "dept_category": "Food"},
        {
            "department_id": 2,
            "department_name": "personal care",
            "dept_category": "Personal Care",
        },
        {"department_id": 3, "department_name": "other", "dept_category": "General"},
    ]
    assert str(result["department_id"].dtype) == "int64"


def test_transform_aisles_adds_type_and_uses_canonical_columns() -> None:
    source = pd.DataFrame(
        {
            "aisle_id": [1, 2, 3],
            "aisle": ["fresh vegetables", "cookies cakes", "unknown"],
        }
    )

    result = transform_aisles(source)

    assert result.columns.tolist() == ["aisle_id", "aisle_name", "aisle_type"]
    assert result["aisle_type"].tolist() == ["Fresh", "Snacks", "General"]


def test_transform_products_coerces_identifiers_and_ignores_extra_columns() -> None:
    source = pd.DataFrame(
        {
            "product_id": ["10", "20"],
            "product_name": ["Banana", "Tea"],
            "aisle_id": ["1", "2"],
            "department_id": ["3", "4"],
            "source_note": ["a", "b"],
        }
    )

    result = transform_products(source)

    assert result.columns.tolist() == [
        "product_id",
        "product_name",
        "aisle_id",
        "department_id",
        "product_category",
    ]
    assert result["product_category"].tolist() == ["General", "General"]
    assert all(str(result[column].dtype) == "int64" for column in result.columns[[0, 2, 3]])


def test_transform_orders_filters_test_rows_and_preserves_first_order_null() -> None:
    source = pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "user_id": [50, 50, 60],
            "eval_set": ["prior", "train", "test"],
            "order_number": [1, 2, 1],
            "order_dow": [0, 6, 4],
            "order_hour_of_day": [9, 18, 12],
            "days_since_prior_order": [None, 7.0, None],
        }
    )

    result = transform_orders(source)

    assert result["order_id"].tolist() == [1, 2]
    assert result["time_id"].tolist() == [9, 618]
    assert pd.isna(result.loc[result["order_id"].eq(1), "days_since_prior_order"]).all()
    assert result["total_items"].tolist() == [0, 0]
    assert result["reorder_ratio"].tolist() == [0.0, 0.0]


def test_transform_orders_returns_typed_empty_shape_for_test_only_chunk() -> None:
    source = pd.DataFrame(
        {
            "order_id": [1],
            "user_id": [50],
            "eval_set": ["test"],
            "order_number": [1],
            "order_dow": [0],
            "order_hour_of_day": [9],
            "days_since_prior_order": [None],
        }
    )

    result = transform_orders(source)

    assert result.empty
    assert result.columns.tolist() == [
        "order_id",
        "user_id",
        "time_id",
        "order_number",
        "days_since_prior_order",
        "order_dow",
        "total_items",
        "reorder_ratio",
    ]


def test_transform_order_details_creates_nullable_time_key_and_quantity() -> None:
    source = pd.DataFrame(
        {
            "order_id": [1, 1],
            "product_id": [10, 11],
            "add_to_cart_order": [1, 2],
            "reordered": [0, 1],
        }
    )

    result = transform_order_details(source, dataset="prior_details")

    assert result.columns.tolist() == [
        "order_id",
        "product_id",
        "time_id",
        "add_to_cart_order",
        "reordered",
        "quantity",
    ]
    assert str(result["time_id"].dtype) == "Int64"
    assert result["time_id"].isna().all()
    assert result["quantity"].tolist() == [1, 1]


def test_transforms_fail_before_mutating_invalid_source() -> None:
    invalid = pd.DataFrame({"department_id": [1], "department": [" "]})

    with pytest.raises(DataQualityError, match="blank"):
        transform_departments(invalid)

    assert invalid.loc[0, "department"] == " "
