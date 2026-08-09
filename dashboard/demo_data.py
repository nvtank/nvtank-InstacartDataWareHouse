"""Deterministic aggregate fixtures for the public dashboard demo.

The values in this module are representative of the Instacart dataset, but they
are deliberately labelled as demo data.  They let the UI, documentation, and
tests exercise the same repository contract without requiring a 1.8 GB local
MariaDB warehouse.
"""

from __future__ import annotations

from typing import Final

import pandas as pd

DEMO_DATASET_NAME: Final = "Instacart representative aggregate snapshot"
DEMO_DATASET_NOTE: Final = (
    "Deterministic demo aggregates; no live database connection and no "
    "calendar-date fields are present in the source dataset."
)
DEMO_TOTAL_ORDERS: Final = 3_346_083
DEMO_TOTAL_USERS: Final = 206_209
DEMO_TOTAL_PRODUCTS: Final = 49_688
DEMO_TOTAL_ITEMS: Final = 33_819_106


def overview_kpis() -> pd.DataFrame:
    """Return a single-row KPI frame using stable representative values."""

    return pd.DataFrame(
        [
            {
                "total_orders": DEMO_TOTAL_ORDERS,
                "total_users": DEMO_TOTAL_USERS,
                "total_products": DEMO_TOTAL_PRODUCTS,
                "total_items": DEMO_TOTAL_ITEMS,
                "avg_basket_size": 10.08,
                "avg_reorder_rate_pct": 59.01,
                "total_departments": 21,
                "total_aisles": 134,
            }
        ]
    )


def orders_by_day() -> pd.DataFrame:
    """Return order totals for every day-of-week category."""

    frame = pd.DataFrame(
        [
            (0, "Sunday", 587_731),
            (1, "Monday", 574_599),
            (2, "Tuesday", 457_016),
            (3, "Wednesday", 427_392),
            (4, "Thursday", 416_992),
            (5, "Friday", 443_429),
            (6, "Saturday", 438_924),
        ],
        columns=["order_dow", "dow_name", "orders"],
    )
    frame["share_pct"] = frame["orders"] / frame["orders"].sum() * 100
    return frame


def orders_by_hour() -> pd.DataFrame:
    """Return the representative 24-hour shopping distribution."""

    counts = [
        22_259,
        12_126,
        7_374,
        5_354,
        5_406,
        9_359,
        29_860,
        89_854,
        174_294,
        252_160,
        282_095,
        278_486,
        266_860,
        271_904,
        276_837,
        277_421,
        266_578,
        223_779,
        178_902,
        137_487,
        102_006,
        76_397,
        60_120,
        39_165,
    ]
    frame = pd.DataFrame({"order_hour": range(24), "orders": counts})
    frame["share_pct"] = frame["orders"] / frame["orders"].sum() * 100
    return frame


def weekend_comparison() -> pd.DataFrame:
    """Compare weekend and weekday traffic on a per-day basis.

    Raw totals remain available for transparency, while ``avg_orders_per_day``
    is the metric that should be used for a truthful two-day versus five-day
    comparison.
    """

    daily = orders_by_day()
    weekend_orders = int(
        daily.loc[daily["order_dow"].isin((0, 6)), "orders"].sum()
    )
    weekday_orders = int(
        daily.loc[~daily["order_dow"].isin((0, 6)), "orders"].sum()
    )
    return pd.DataFrame(
        [
            {
                "day_type": "Weekend",
                "orders": weekend_orders,
                "days_in_group": 2,
                "avg_orders_per_day": weekend_orders / 2,
                "avg_basket_size": 10.16,
                "avg_reorder_rate_pct": 59.30,
            },
            {
                "day_type": "Weekday",
                "orders": weekday_orders,
                "days_in_group": 5,
                "avg_orders_per_day": weekday_orders / 5,
                "avg_basket_size": 10.04,
                "avg_reorder_rate_pct": 58.70,
            },
        ]
    )


def department_performance() -> pd.DataFrame:
    """Return every department so market share is never top-N normalized."""

    rows = [
        ("produce", 29.25, 65.0, 1_680),
        ("dairy eggs", 16.65, 67.0, 1_626),
        ("snacks", 8.58, 57.5, 6_264),
        ("beverages", 7.97, 65.4, 4_365),
        ("frozen", 6.62, 54.2, 4_001),
        ("pantry", 5.56, 34.7, 5_373),
        ("bakery", 3.58, 62.8, 1_516),
        ("canned goods", 3.16, 45.7, 2_091),
        ("deli", 3.13, 60.8, 1_326),
        ("dry goods pasta", 2.56, 46.1, 1_858),
        ("household", 2.30, 40.3, 3_081),
        ("breakfast", 2.10, 56.1, 1_112),
        ("meat seafood", 2.10, 57.3, 907),
        ("personal care", 1.38, 32.2, 6_561),
        ("babies", 1.30, 57.8, 1_081),
        ("international", 0.83, 37.0, 1_130),
        ("alcohol", 0.45, 56.9, 1_059),
        ("pets", 0.30, 60.2, 972),
        ("missing", 0.21, 39.5, 1_258),
        ("bulk", 0.11, 57.7, 38),
        ("other", 1.86, 40.8, 548),
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "department_name",
            "market_share_pct",
            "reorder_rate_pct",
            "unique_products",
        ],
    )
    item_counts = (frame["market_share_pct"] / 100 * DEMO_TOTAL_ITEMS).round().astype(int)
    item_counts.iloc[-1] += DEMO_TOTAL_ITEMS - int(item_counts.sum())
    frame["total_items"] = item_counts
    frame["orders"] = (frame["total_items"] * 0.73).round().astype(int)
    return frame[
        [
            "department_name",
            "orders",
            "total_items",
            "reorder_rate_pct",
            "unique_products",
            "market_share_pct",
        ]
    ].sort_values("total_items", ascending=False, ignore_index=True)


def top_products() -> pd.DataFrame:
    """Return representative high-volume products with stable ordering."""

    rows = [
        ("Banana", "produce", "fresh fruits", 472_565, 488_211, 84.5),
        ("Bag of Organic Bananas", "produce", "fresh fruits", 379_450, 394_930, 84.2),
        ("Organic Strawberries", "produce", "fresh fruits", 258_110, 275_577, 78.0),
        ("Organic Baby Spinach", "produce", "packaged vegetables fruits", 228_220, 251_705, 77.6),
        ("Organic Hass Avocado", "produce", "fresh fruits", 213_584, 220_877, 75.6),
        ("Organic Avocado", "produce", "fresh fruits", 170_131, 184_224, 76.2),
        ("Large Lemon", "produce", "fresh fruits", 152_657, 160_792, 72.9),
        ("Strawberries", "produce", "fresh fruits", 142_951, 149_445, 69.8),
        ("Limes", "produce", "fresh fruits", 136_900, 146_660, 70.5),
        ("Organic Whole Milk", "dairy eggs", "milk", 133_205, 142_813, 78.2),
        ("Organic Raspberries", "produce", "packaged vegetables fruits", 131_150, 137_057, 75.1),
        ("Organic Yellow Onion", "produce", "fresh vegetables", 109_201, 113_426, 67.5),
        ("Organic Garlic", "produce", "fresh vegetables", 105_212, 109_778, 68.4),
        ("Organic Zucchini", "produce", "fresh vegetables", 101_492, 104_823, 64.9),
        ("Organic Blueberries", "produce", "packaged vegetables fruits", 99_800, 105_026, 66.8),
        ("Cucumber Kirby", "produce", "fresh vegetables", 96_815, 100_060, 67.3),
        ("Organic Fuji Apple", "produce", "fresh fruits", 94_207, 98_789, 71.4),
        ("Organic Lemon", "produce", "fresh fruits", 92_640, 96_831, 69.1),
        ("Apple Honeycrisp Organic", "produce", "fresh fruits", 89_734, 93_287, 68.6),
        ("Organic Grape Tomatoes", "produce", "packaged vegetables fruits", 87_312, 91_267, 65.9),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "product_name",
            "department_name",
            "aisle_name",
            "orders",
            "total_items",
            "reorder_rate_pct",
        ],
    )


def aisle_reorder_rates() -> pd.DataFrame:
    """Return representative aisle-level loyalty aggregates."""

    rows = [
        ("milk", 78.18, 923_659),
        ("water seltzer sparkling water", 72.95, 878_150),
        ("fresh fruits", 72.82, 3_790_900),
        ("eggs", 70.55, 472_009),
        ("soy lactosefree", 69.83, 664_493),
        ("packaged produce", 69.08, 289_488),
        ("yogurt", 68.69, 1_502_418),
        ("cream", 68.56, 330_358),
        ("bread", 67.04, 608_469),
        ("refrigerated", 66.31, 599_109),
        ("breakfast bakery", 65.13, 242_617),
        ("packaged vegetables fruits", 64.81, 1_843_805),
        ("energy granola bars", 63.84, 490_431),
        ("frozen breakfast", 62.67, 243_156),
        ("fresh dips tapenades", 62.45, 370_827),
    ]
    return pd.DataFrame(rows, columns=["aisle_name", "reorder_rate_pct", "items"])


def customer_segments() -> pd.DataFrame:
    """Return the rule-based ``Dim_User.user_segment`` demo contract."""

    frame = pd.DataFrame(
        [
            ("VIP", 11_209, 694_958, 11.75),
            ("Frequent", 45_000, 1_350_000, 10.88),
            ("Regular", 70_000, 980_000, 10.14),
            ("New", 80_000, 321_125, 8.91),
        ],
        columns=[
            "user_segment",
            "users",
            "total_orders",
            "avg_basket_size",
        ],
    )
    frame["avg_orders"] = frame["total_orders"] / frame["users"]
    frame["user_share_pct"] = frame["users"] / frame["users"].sum() * 100
    frame["order_share_pct"] = (
        frame["total_orders"] / frame["total_orders"].sum() * 100
    )
    return frame


def basket_distribution() -> pd.DataFrame:
    """Return mutually exclusive, naturally ordered basket buckets."""

    frame = pd.DataFrame(
        [
            (1, "1-5 items", 650_000, 42.1),
            (2, "6-10 items", 1_100_000, 55.8),
            (3, "11-20 items", 1_050_000, 64.9),
            (4, "21-30 items", 400_000, 71.7),
            (5, "31+ items", 146_083, 76.3),
        ],
        columns=["bucket_order", "basket_size", "orders", "avg_reorder_rate_pct"],
    )
    frame["order_share_pct"] = frame["orders"] / frame["orders"].sum() * 100
    return frame


TABLE_CATALOG: Final = (
    ("Dim_Time", "Dimension", "Day-of-week and hour attributes", 168),
    ("Dim_Department", "Dimension", "Product department hierarchy", 21),
    ("Dim_Aisle", "Dimension", "Product aisle hierarchy", 134),
    ("Dim_Product", "Dimension", "Product catalogue", DEMO_TOTAL_PRODUCTS),
    ("Dim_User", "Dimension", "Customer aggregate attributes", DEMO_TOTAL_USERS),
    ("Fact_Orders", "Fact", "Order-level measures", DEMO_TOTAL_ORDERS),
    (
        "Fact_Order_Details",
        "Fact",
        "Order-product line items",
        DEMO_TOTAL_ITEMS,
    ),
)


TABLE_SCHEMAS: Final = {
    "Dim_Time": [
        ("time_id", "INTEGER", False),
        ("order_dow", "TINYINT", False),
        ("dow_name", "VARCHAR(10)", False),
        ("order_hour", "TINYINT", False),
        ("hour_range", "VARCHAR(20)", False),
        ("is_weekend", "BOOLEAN", False),
    ],
    "Dim_Department": [
        ("department_id", "INTEGER", False),
        ("department_name", "VARCHAR(100)", False),
        ("dept_category", "VARCHAR(20)", False),
    ],
    "Dim_Aisle": [
        ("aisle_id", "INTEGER", False),
        ("aisle_name", "VARCHAR(255)", False),
        ("aisle_type", "VARCHAR(30)", False),
    ],
    "Dim_Product": [
        ("product_id", "INTEGER", False),
        ("product_name", "VARCHAR(255)", False),
        ("aisle_id", "INTEGER", False),
        ("department_id", "INTEGER", False),
        ("product_category", "VARCHAR(50)", True),
    ],
    "Dim_User": [
        ("user_id", "INTEGER", False),
        ("user_segment", "VARCHAR(20)", False),
        ("first_order_dow", "TINYINT", True),
        ("avg_basket_size", "DECIMAL(6,2)", True),
        ("total_orders", "INTEGER", True),
        ("total_products_purchased", "INTEGER", True),
        ("avg_days_between_orders", "DECIMAL(6,2)", True),
        ("last_order_date_id", "INTEGER", True),
    ],
    "Fact_Orders": [
        ("order_id", "INTEGER", False),
        ("user_id", "INTEGER", False),
        ("time_id", "INTEGER", False),
        ("order_number", "INTEGER", False),
        ("days_since_prior_order", "DECIMAL(6,2)", True),
        ("total_items", "INTEGER", False),
        ("reorder_ratio", "DECIMAL(5,4)", True),
        ("order_dow", "TINYINT", False),
    ],
    "Fact_Order_Details": [
        ("detail_id", "BIGINT", False),
        ("order_id", "INTEGER", False),
        ("product_id", "INTEGER", False),
        ("time_id", "INTEGER", True),
        ("add_to_cart_order", "SMALLINT", False),
        ("reordered", "BOOLEAN", False),
        ("quantity", "INTEGER", False),
    ],
}


TABLE_SAMPLES: Final = {
    "Dim_Time": [
        {
            "time_id": 0,
            "order_dow": 0,
            "dow_name": "Sunday",
            "order_hour": 0,
            "hour_range": "00-06 Night",
            "is_weekend": True,
        },
        {
            "time_id": 109,
            "order_dow": 1,
            "dow_name": "Monday",
            "order_hour": 9,
            "hour_range": "06-12 Morning",
            "is_weekend": False,
        },
    ],
    "Dim_Department": [
        {"department_id": 4, "department_name": "produce"},
        {"department_id": 16, "department_name": "dairy eggs"},
    ],
    "Dim_Aisle": [
        {"aisle_id": 24, "aisle_name": "fresh fruits"},
        {"aisle_id": 83, "aisle_name": "fresh vegetables"},
    ],
    "Dim_Product": [
        {"product_id": 24852, "product_name": "Banana", "aisle_id": 24, "department_id": 4},
        {
            "product_id": 13176,
            "product_name": "Bag of Organic Bananas",
            "aisle_id": 24,
            "department_id": 4,
        },
    ],
    "Dim_User": [
        {"user_id": 101, "user_segment": "Regular", "avg_basket_size": 10.4, "total_orders": 24},
        {"user_id": 202, "user_segment": "New", "avg_basket_size": 7.8, "total_orders": 4},
    ],
    "Fact_Orders": [
        {
            "order_id": 1001,
            "user_id": 101,
            "time_id": 109,
            "order_number": 8,
            "total_items": 11,
            "reorder_ratio": 0.6364,
            "order_dow": 1,
        },
        {
            "order_id": 1002,
            "user_id": 202,
            "time_id": 610,
            "order_number": 2,
            "total_items": 7,
            "reorder_ratio": 0.4286,
            "order_dow": 6,
        },
    ],
    "Fact_Order_Details": [
        {
            "detail_id": 1,
            "order_id": 1001,
            "product_id": 24852,
            "time_id": 109,
            "add_to_cart_order": 1,
            "reordered": True,
            "quantity": 1,
        },
        {
            "detail_id": 2,
            "order_id": 1002,
            "product_id": 13176,
            "time_id": 610,
            "add_to_cart_order": 1,
            "reordered": False,
            "quantity": 1,
        },
    ],
}
