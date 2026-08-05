"""Derive order- and customer-level metrics after fact loading."""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import get_engine


class MetricUpdateError(RuntimeError):
    """Raised when derived warehouse metrics fail reconciliation."""


@dataclass(frozen=True, slots=True)
class MetricUpdateResult:
    orders_updated: int
    users_upserted: int
    elapsed_seconds: float


def update_fact_orders_metrics(engine: Engine) -> int:
    """Populate both order metrics with one aggregation scan of the line-item fact."""
    statement = text(
        """
        UPDATE Fact_Orders orders
        JOIN (
            SELECT
                order_id,
                COUNT(*) AS total_items,
                AVG(reordered) AS reorder_ratio
            FROM Fact_Order_Details
            GROUP BY order_id
        ) metrics ON orders.order_id = metrics.order_id
        SET
            orders.total_items = metrics.total_items,
            orders.reorder_ratio = metrics.reorder_ratio
        """
    )
    with engine.begin() as connection:
        result = connection.execute(statement)
    return max(result.rowcount or 0, 0)


def populate_dim_users(engine: Engine) -> int:
    """Build reproducible behavioral user attributes from fully reconciled orders."""
    statement = text(
        """
        INSERT INTO Dim_User (
            user_id,
            user_segment,
            first_order_dow,
            avg_basket_size,
            total_orders,
            total_products_purchased,
            avg_days_between_orders,
            last_order_date_id
        )
        SELECT
            user_id,
            CASE
                WHEN COUNT(*) >= 50 THEN 'VIP'
                WHEN COUNT(*) >= 20 THEN 'Frequent'
                WHEN COUNT(*) >= 10 THEN 'Regular'
                ELSE 'New'
            END AS user_segment,
            MAX(CASE WHEN order_number = 1 THEN order_dow END) AS first_order_dow,
            AVG(total_items) AS avg_basket_size,
            COUNT(*) AS total_orders,
            SUM(total_items) AS total_products_purchased,
            AVG(days_since_prior_order) AS avg_days_between_orders,
            CAST(
                SUBSTRING_INDEX(
                    GROUP_CONCAT(time_id ORDER BY order_number DESC), ',', 1
                ) AS UNSIGNED
            ) AS last_order_date_id
        FROM Fact_Orders
        GROUP BY user_id
        ON DUPLICATE KEY UPDATE
            user_segment = VALUES(user_segment),
            first_order_dow = VALUES(first_order_dow),
            avg_basket_size = VALUES(avg_basket_size),
            total_orders = VALUES(total_orders),
            total_products_purchased = VALUES(total_products_purchased),
            avg_days_between_orders = VALUES(avg_days_between_orders),
            last_order_date_id = VALUES(last_order_date_id)
        """
    )
    with engine.begin() as connection:
        result = connection.execute(statement)
    return max(result.rowcount or 0, 0)


def validate_derived_metrics(engine: Engine) -> None:
    checks = {
        "orders without line items": "SELECT COUNT(*) FROM Fact_Orders WHERE total_items <= 0",
        "invalid reorder ratios": (
            "SELECT COUNT(*) FROM Fact_Orders "
            "WHERE reorder_ratio < 0 OR reorder_ratio > 1"
        ),
        "users without orders": "SELECT COUNT(*) FROM Dim_User WHERE total_orders <= 0",
    }
    failures: list[str] = []
    with engine.connect() as connection:
        for label, query in checks.items():
            violations = int(connection.execute(text(query)).scalar_one())
            if violations:
                failures.append(f"{label}: {violations:,}")
    if failures:
        raise MetricUpdateError("Derived metric validation failed: " + "; ".join(failures))


def update_all_metrics(engine: Engine) -> MetricUpdateResult:
    started = time.perf_counter()
    orders_updated = update_fact_orders_metrics(engine)
    users_upserted = populate_dim_users(engine)
    validate_derived_metrics(engine)
    return MetricUpdateResult(
        orders_updated=orders_updated,
        users_upserted=users_upserted,
        elapsed_seconds=time.perf_counter() - started,
    )


def main() -> int:
    result = update_all_metrics(get_engine())
    print(
        "Derived metrics complete: "
        f"{result.orders_updated:,} order rows updated, "
        f"{result.users_upserted:,} user rows affected "
        f"in {result.elapsed_seconds:.1f}s."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
