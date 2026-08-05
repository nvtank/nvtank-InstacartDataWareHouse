"""Streamlit-independent analytics data contract.

Pages should depend on :class:`AnalyticsRepository`, never on SQLAlchemy or on
demo fixtures directly.  This keeps presentation code testable and makes the
data source explicit: callers can request a live MariaDB warehouse, deterministic
demo aggregates, or automatic live-to-demo fallback after a health check.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Final

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

from . import demo_data

REQUIRED_TABLES: Final = frozenset(
    {
        "Dim_Time",
        "Dim_Department",
        "Dim_Aisle",
        "Dim_Product",
        "Dim_User",
        "Fact_Orders",
        "Fact_Order_Details",
    }
)
TABLE_WHITELIST: Final = {
    name: {"kind": kind, "description": description}
    for name, kind, description, _ in demo_data.TABLE_CATALOG
}


class RepositoryConfigurationError(ValueError):
    """Raised when repository settings are invalid."""


class RepositoryUnavailableError(RuntimeError):
    """Raised when explicitly requested live data is unavailable."""


@dataclass(frozen=True)
class RepositoryHealth:
    """Sanitized result of a source health check."""

    healthy: bool
    checked_at: datetime
    checks: Mapping[str, bool]
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceMetadata:
    """User-facing provenance that does not contain credentials."""

    mode: str
    requested_mode: str
    label: str
    is_live: bool
    healthy: bool
    dataset_note: str
    checked_at: datetime
    fallback_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TableMetadata:
    """Lazy table details returned only after a whitelisted table is selected."""

    name: str
    kind: str
    description: str
    row_count_estimate: int | None
    size_mb: float | None
    columns: pd.DataFrame
    indexes: pd.DataFrame
    partitions: pd.DataFrame


class AnalyticsRepository(ABC):
    """Stable data API consumed by the analytics presentation layer."""

    @property
    @abstractmethod
    def source_metadata(self) -> SourceMetadata:
        """Describe where the current data came from."""

    def get_source_metadata(self) -> SourceMetadata:
        """Method-form alias useful to serializers and simple dependency injection."""

        return self.source_metadata

    @abstractmethod
    def health_check(self) -> RepositoryHealth:
        """Validate connectivity, schema contract, and minimum warehouse data."""

    @abstractmethod
    def overview_kpis(self) -> pd.DataFrame:
        """Return one row of high-level warehouse KPIs."""

    @abstractmethod
    def day_trends(self) -> pd.DataFrame:
        """Return all seven day-of-week aggregates."""

    @abstractmethod
    def hour_trends(self) -> pd.DataFrame:
        """Return all 24 hour-of-day aggregates."""

    @abstractmethod
    def weekend_comparison(self) -> pd.DataFrame:
        """Return raw totals and normalized per-day weekday/weekend metrics."""

    @abstractmethod
    def departments(self) -> pd.DataFrame:
        """Return every department and market share across the full population."""

    @abstractmethod
    def products(
        self, *, limit: int = 20, department: str | None = None
    ) -> pd.DataFrame:
        """Return top products, optionally filtered by an exact department."""

    @abstractmethod
    def aisles(
        self, *, limit: int = 15, min_items: int = 10_000
    ) -> pd.DataFrame:
        """Return high-support aisle reorder metrics."""

    @abstractmethod
    def customer_segments(self) -> pd.DataFrame:
        """Return the canonical ``Dim_User.user_segment`` aggregate."""

    @abstractmethod
    def basket_distribution(self) -> pd.DataFrame:
        """Return naturally ordered basket-size buckets."""

    @abstractmethod
    def table_catalog(self) -> pd.DataFrame:
        """Return the safe table choices without querying every table detail."""

    @abstractmethod
    def table_metadata(self, table_name: str) -> TableMetadata:
        """Load metadata for one validated table."""

    @abstractmethod
    def table_sample(self, table_name: str, *, limit: int = 10) -> pd.DataFrame:
        """Load a small sample from one validated table."""

    # Explicit get_* aliases keep page code readable while retaining concise
    # domain method names above.
    def get_overview_kpis(self) -> pd.DataFrame:
        return self.overview_kpis()

    def get_day_trends(self) -> pd.DataFrame:
        return self.day_trends()

    def get_hour_trends(self) -> pd.DataFrame:
        return self.hour_trends()

    def get_weekend_comparison(self) -> pd.DataFrame:
        return self.weekend_comparison()

    def get_departments(self) -> pd.DataFrame:
        return self.departments()

    def get_products(
        self, *, limit: int = 20, department: str | None = None
    ) -> pd.DataFrame:
        return self.products(limit=limit, department=department)

    def get_aisles(
        self, *, limit: int = 15, min_items: int = 10_000
    ) -> pd.DataFrame:
        return self.aisles(limit=limit, min_items=min_items)

    def get_customer_segments(self) -> pd.DataFrame:
        return self.customer_segments()

    def get_basket_distribution(self) -> pd.DataFrame:
        return self.basket_distribution()

    def get_table_catalog(self) -> pd.DataFrame:
        return self.table_catalog()

    def get_table_metadata(self, table_name: str) -> TableMetadata:
        return self.table_metadata(table_name)

    def get_table_sample(
        self, table_name: str, *, limit: int = 10
    ) -> pd.DataFrame:
        return self.table_sample(table_name, limit=limit)


class DemoAnalyticsRepository(AnalyticsRepository):
    """Repository backed by immutable-in-practice deterministic aggregates."""

    def __init__(
        self,
        *,
        requested_mode: str = "demo",
        fallback_reason: str | None = None,
    ) -> None:
        self._requested_mode = requested_mode
        self._fallback_reason = fallback_reason
        self._health = self.health_check()

    @property
    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            mode="demo",
            requested_mode=self._requested_mode,
            label=demo_data.DEMO_DATASET_NAME,
            is_live=False,
            healthy=self._health.healthy,
            dataset_note=demo_data.DEMO_DATASET_NOTE,
            checked_at=self._health.checked_at,
            fallback_reason=self._fallback_reason,
        )

    def health_check(self) -> RepositoryHealth:
        checks = {
            "fixtures_available": True,
            "schema_contract_available": set(TABLE_WHITELIST) == REQUIRED_TABLES,
        }
        self._health = RepositoryHealth(
            healthy=all(checks.values()),
            checked_at=_utcnow(),
            checks=checks,
            message="Deterministic demo aggregates are ready.",
        )
        return self._health

    def overview_kpis(self) -> pd.DataFrame:
        return _copy_frame(demo_data.overview_kpis())

    def day_trends(self) -> pd.DataFrame:
        return _copy_frame(demo_data.orders_by_day())

    def hour_trends(self) -> pd.DataFrame:
        return _copy_frame(demo_data.orders_by_hour())

    def weekend_comparison(self) -> pd.DataFrame:
        return _copy_frame(demo_data.weekend_comparison())

    def departments(self) -> pd.DataFrame:
        return _copy_frame(demo_data.department_performance())

    def products(
        self, *, limit: int = 20, department: str | None = None
    ) -> pd.DataFrame:
        safe_limit = _validated_limit(limit, maximum=100)
        frame = demo_data.top_products()
        if department:
            normalized = department.strip().casefold()
            frame = frame[
                frame["department_name"].str.casefold() == normalized
            ]
        return frame.head(safe_limit).reset_index(drop=True).copy(deep=True)

    def aisles(
        self, *, limit: int = 15, min_items: int = 10_000
    ) -> pd.DataFrame:
        safe_limit = _validated_limit(limit, maximum=134)
        safe_min_items = _validated_nonnegative_int(min_items, "min_items")
        frame = demo_data.aisle_reorder_rates()
        frame = frame[frame["items"] >= safe_min_items]
        return frame.head(safe_limit).reset_index(drop=True).copy(deep=True)

    def customer_segments(self) -> pd.DataFrame:
        return _copy_frame(demo_data.customer_segments())

    def basket_distribution(self) -> pd.DataFrame:
        return _copy_frame(demo_data.basket_distribution())

    def table_catalog(self) -> pd.DataFrame:
        return pd.DataFrame(
            demo_data.TABLE_CATALOG,
            columns=["table_name", "kind", "description", "row_count_estimate"],
        )

    def table_metadata(self, table_name: str) -> TableMetadata:
        safe_name = _validated_table_name(table_name)
        catalog_row = next(
            row for row in demo_data.TABLE_CATALOG if row[0] == safe_name
        )
        columns = pd.DataFrame(
            [
                {
                    "column_name": name,
                    "data_type": data_type,
                    "nullable": nullable,
                    "default": None,
                    "comment": "",
                }
                for name, data_type, nullable in demo_data.TABLE_SCHEMAS[safe_name]
            ]
        )
        indexes = _demo_indexes(safe_name)
        partitions = _demo_partitions(safe_name)
        return TableMetadata(
            name=safe_name,
            kind=catalog_row[1],
            description=catalog_row[2],
            row_count_estimate=int(catalog_row[3]),
            size_mb=None,
            columns=columns,
            indexes=indexes,
            partitions=partitions,
        )

    def table_sample(self, table_name: str, *, limit: int = 10) -> pd.DataFrame:
        safe_name = _validated_table_name(table_name)
        safe_limit = _validated_limit(limit, maximum=100)
        return pd.DataFrame(demo_data.TABLE_SAMPLES[safe_name]).head(safe_limit).copy(
            deep=True
        )


class MariaDBAnalyticsRepository(AnalyticsRepository):
    """Read-only aggregate repository backed by the MariaDB warehouse."""

    def __init__(self, engine: Any, *, requested_mode: str = "live") -> None:
        self._engine = engine
        self._requested_mode = requested_mode
        self._health = RepositoryHealth(
            healthy=False,
            checked_at=_utcnow(),
            checks={"health_check_run": False},
            message="Live warehouse health has not been checked.",
        )

    @property
    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            mode="live",
            requested_mode=self._requested_mode,
            label=_safe_engine_label(self._engine),
            is_live=True,
            healthy=self._health.healthy,
            dataset_note=(
                "Live queries against the batch-loaded Instacart warehouse; "
                "the source has day-of-week and hour fields, not calendar dates."
            ),
            checked_at=self._health.checked_at,
        )

    def health_check(self) -> RepositoryHealth:
        checks: dict[str, bool] = {
            "connection": False,
            "required_tables": False,
            "user_segment_column": False,
            "fact_orders_has_data": False,
            "fact_details_has_data": False,
            "users_have_data": False,
        }
        message = "Live warehouse health check failed."
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                checks["connection"] = True

                table_rows = connection.execute(
                    text(
                        """
                        SELECT TABLE_NAME
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE()
                        """
                    )
                ).fetchall()
                available_tables = {row[0] for row in table_rows}
                checks["required_tables"] = REQUIRED_TABLES.issubset(available_tables)

                if checks["required_tables"]:
                    segment_column = connection.execute(
                        text(
                            """
                            SELECT 1
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = :table_name
                              AND COLUMN_NAME = :column_name
                            LIMIT 1
                            """
                        ),
                        {"table_name": "Dim_User", "column_name": "user_segment"},
                    ).first()
                    checks["user_segment_column"] = segment_column is not None
                    checks["fact_orders_has_data"] = (
                        connection.execute(
                            text("SELECT 1 FROM Fact_Orders LIMIT 1")
                        ).first()
                        is not None
                    )
                    checks["fact_details_has_data"] = (
                        connection.execute(
                            text("SELECT 1 FROM Fact_Order_Details LIMIT 1")
                        ).first()
                        is not None
                    )
                    checks["users_have_data"] = (
                        connection.execute(text("SELECT 1 FROM Dim_User LIMIT 1")).first()
                        is not None
                    )

            healthy = all(checks.values())
            message = (
                "Live warehouse schema and minimum data are ready."
                if healthy
                else "Live warehouse is reachable but its schema or data is incomplete."
            )
        except Exception as exc:  # sanitized intentionally: do not leak URLs or SQL
            healthy = False
            message = f"Live warehouse health check failed ({type(exc).__name__})."

        self._health = RepositoryHealth(
            healthy=healthy,
            checked_at=_utcnow(),
            checks=checks,
            message=message,
        )
        return self._health

    def overview_kpis(self) -> pd.DataFrame:
        return self._read_frame(
            """
            SELECT
                order_metrics.total_orders,
                user_metrics.total_users,
                product_metrics.total_products,
                order_metrics.total_items,
                order_metrics.avg_basket_size,
                order_metrics.avg_reorder_rate_pct,
                product_metrics.total_departments,
                product_metrics.total_aisles
            FROM (
                SELECT
                    COUNT(*) AS total_orders,
                    COALESCE(SUM(total_items), 0) AS total_items,
                    AVG(NULLIF(total_items, 0)) AS avg_basket_size,
                    AVG(reorder_ratio) * 100 AS avg_reorder_rate_pct
                FROM Fact_Orders
            ) AS order_metrics
            CROSS JOIN (
                SELECT COUNT(*) AS total_users FROM Dim_User
            ) AS user_metrics
            CROSS JOIN (
                SELECT
                    COUNT(*) AS total_products,
                    COUNT(DISTINCT department_id) AS total_departments,
                    COUNT(DISTINCT aisle_id) AS total_aisles
                FROM Dim_Product
            ) AS product_metrics
            """
        )

    def day_trends(self) -> pd.DataFrame:
        return self._read_frame(
            """
            SELECT
                t.order_dow,
                t.dow_name,
                COUNT(DISTINCT fo.order_id) AS orders,
                COUNT(DISTINCT fo.order_id) * 100.0
                    / SUM(COUNT(DISTINCT fo.order_id)) OVER () AS share_pct
            FROM Fact_Orders AS fo
            INNER JOIN Dim_Time AS t ON fo.time_id = t.time_id
            GROUP BY t.order_dow, t.dow_name
            ORDER BY t.order_dow
            """
        )

    def hour_trends(self) -> pd.DataFrame:
        return self._read_frame(
            """
            SELECT
                t.order_hour,
                COUNT(DISTINCT fo.order_id) AS orders,
                COUNT(DISTINCT fo.order_id) * 100.0
                    / SUM(COUNT(DISTINCT fo.order_id)) OVER () AS share_pct
            FROM Fact_Orders AS fo
            INNER JOIN Dim_Time AS t ON fo.time_id = t.time_id
            GROUP BY t.order_hour
            ORDER BY t.order_hour
            """
        )

    def weekend_comparison(self) -> pd.DataFrame:
        return self._read_frame(
            """
            SELECT
                CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END
                    AS day_type,
                COUNT(DISTINCT fo.order_id) AS orders,
                COUNT(DISTINCT t.order_dow) AS days_in_group,
                COUNT(DISTINCT fo.order_id) * 1.0
                    / COUNT(DISTINCT t.order_dow) AS avg_orders_per_day,
                AVG(NULLIF(fo.total_items, 0)) AS avg_basket_size,
                AVG(fo.reorder_ratio) * 100 AS avg_reorder_rate_pct
            FROM Fact_Orders AS fo
            INNER JOIN Dim_Time AS t ON fo.time_id = t.time_id
            GROUP BY CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END
            ORDER BY day_type DESC
            """
        )

    def departments(self) -> pd.DataFrame:
        frame = self._read_frame(
            """
            SELECT
                d.department_name,
                COUNT(DISTINCT fod.order_id) AS orders,
                COUNT(*) AS total_items,
                AVG(fod.reordered) * 100 AS reorder_rate_pct,
                COUNT(DISTINCT fod.product_id) AS unique_products
            FROM Fact_Order_Details AS fod
            INNER JOIN Dim_Product AS p ON fod.product_id = p.product_id
            INNER JOIN Dim_Department AS d
                ON p.department_id = d.department_id
            GROUP BY d.department_id, d.department_name
            ORDER BY total_items DESC
            """
        )
        denominator = frame["total_items"].sum() if not frame.empty else 0
        frame["market_share_pct"] = (
            frame["total_items"] / denominator * 100 if denominator else 0.0
        )
        return frame

    def products(
        self, *, limit: int = 20, department: str | None = None
    ) -> pd.DataFrame:
        safe_limit = _validated_limit(limit, maximum=100)
        where_clause = ""
        params: dict[str, Any] = {"limit": safe_limit}
        if department:
            where_clause = "WHERE d.department_name = :department"
            params["department"] = department.strip()
        return self._read_frame(
            f"""
            SELECT
                p.product_name,
                d.department_name,
                a.aisle_name,
                COUNT(DISTINCT fod.order_id) AS orders,
                COUNT(*) AS total_items,
                AVG(fod.reordered) * 100 AS reorder_rate_pct
            FROM Fact_Order_Details AS fod
            INNER JOIN Dim_Product AS p ON fod.product_id = p.product_id
            INNER JOIN Dim_Department AS d
                ON p.department_id = d.department_id
            INNER JOIN Dim_Aisle AS a ON p.aisle_id = a.aisle_id
            {where_clause}
            GROUP BY
                p.product_id,
                p.product_name,
                d.department_name,
                a.aisle_name
            ORDER BY orders DESC
            LIMIT :limit
            """,
            params,
        )

    def aisles(
        self, *, limit: int = 15, min_items: int = 10_000
    ) -> pd.DataFrame:
        safe_limit = _validated_limit(limit, maximum=134)
        safe_min_items = _validated_nonnegative_int(min_items, "min_items")
        return self._read_frame(
            """
            SELECT
                a.aisle_name,
                AVG(fod.reordered) * 100 AS reorder_rate_pct,
                COUNT(*) AS items
            FROM Fact_Order_Details AS fod
            INNER JOIN Dim_Product AS p ON fod.product_id = p.product_id
            INNER JOIN Dim_Aisle AS a ON p.aisle_id = a.aisle_id
            GROUP BY a.aisle_id, a.aisle_name
            HAVING COUNT(*) >= :min_items
            ORDER BY reorder_rate_pct DESC, items DESC
            LIMIT :limit
            """,
            {"min_items": safe_min_items, "limit": safe_limit},
        )

    def customer_segments(self) -> pd.DataFrame:
        return self._read_frame(
            """
            SELECT
                u.user_segment,
                COUNT(*) AS users,
                SUM(u.total_orders) AS total_orders,
                AVG(u.total_orders) AS avg_orders,
                AVG(u.avg_basket_size) AS avg_basket_size,
                COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS user_share_pct,
                SUM(u.total_orders) * 100.0
                    / SUM(SUM(u.total_orders)) OVER () AS order_share_pct
            FROM Dim_User AS u
            WHERE u.user_segment IS NOT NULL
              AND u.user_segment <> ''
            GROUP BY u.user_segment
            ORDER BY avg_orders DESC
            """
        )

    def basket_distribution(self) -> pd.DataFrame:
        return self._read_frame(
            """
            SELECT
                CASE
                    WHEN fo.total_items BETWEEN 1 AND 5 THEN 1
                    WHEN fo.total_items BETWEEN 6 AND 10 THEN 2
                    WHEN fo.total_items BETWEEN 11 AND 20 THEN 3
                    WHEN fo.total_items BETWEEN 21 AND 30 THEN 4
                    ELSE 5
                END AS bucket_order,
                CASE
                    WHEN fo.total_items BETWEEN 1 AND 5 THEN '1-5 items'
                    WHEN fo.total_items BETWEEN 6 AND 10 THEN '6-10 items'
                    WHEN fo.total_items BETWEEN 11 AND 20 THEN '11-20 items'
                    WHEN fo.total_items BETWEEN 21 AND 30 THEN '21-30 items'
                    ELSE '31+ items'
                END AS basket_size,
                COUNT(*) AS orders,
                AVG(fo.reorder_ratio) * 100 AS avg_reorder_rate_pct,
                COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS order_share_pct
            FROM Fact_Orders AS fo
            WHERE fo.total_items > 0
            GROUP BY bucket_order, basket_size
            ORDER BY bucket_order
            """
        )

    def table_catalog(self) -> pd.DataFrame:
        rows = [
            {
                "table_name": name,
                "kind": details["kind"],
                "description": details["description"],
                "row_count_estimate": None,
            }
            for name, details in TABLE_WHITELIST.items()
        ]
        return pd.DataFrame(rows)

    def table_metadata(self, table_name: str) -> TableMetadata:
        safe_name = _validated_table_name(table_name)
        inspector = inspect(self._engine)
        columns = pd.DataFrame(
            [
                {
                    "column_name": column["name"],
                    "data_type": str(column["type"]),
                    "nullable": bool(column["nullable"]),
                    "default": column.get("default"),
                    "comment": column.get("comment") or "",
                }
                for column in inspector.get_columns(safe_name)
            ]
        )
        indexes = pd.DataFrame(
            [
                {
                    "index_name": index.get("name") or "",
                    "columns": ", ".join(index.get("column_names") or []),
                    "unique": bool(index.get("unique")),
                }
                for index in inspector.get_indexes(safe_name)
            ],
            columns=["index_name", "columns", "unique"],
        )
        table_stats = self._read_frame(
            """
            SELECT
                TABLE_ROWS AS row_count_estimate,
                (DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024 AS size_mb
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
            """,
            {"table_name": safe_name},
        )
        partitions = self._read_frame(
            """
            SELECT
                PARTITION_NAME AS partition_name,
                TABLE_ROWS AS row_count_estimate,
                DATA_LENGTH / 1024 / 1024 AS size_mb,
                PARTITION_COMMENT AS comment
            FROM information_schema.PARTITIONS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
              AND PARTITION_NAME IS NOT NULL
            ORDER BY PARTITION_ORDINAL_POSITION
            """,
            {"table_name": safe_name},
        )
        row_count_estimate: int | None = None
        size_mb: float | None = None
        if not table_stats.empty:
            raw_count = table_stats.iloc[0]["row_count_estimate"]
            raw_size = table_stats.iloc[0]["size_mb"]
            row_count_estimate = int(raw_count) if pd.notna(raw_count) else None
            size_mb = float(raw_size) if pd.notna(raw_size) else None
        details = TABLE_WHITELIST[safe_name]
        return TableMetadata(
            name=safe_name,
            kind=details["kind"],
            description=details["description"],
            row_count_estimate=row_count_estimate,
            size_mb=size_mb,
            columns=columns,
            indexes=indexes,
            partitions=partitions,
        )

    def table_sample(self, table_name: str, *, limit: int = 10) -> pd.DataFrame:
        safe_name = _validated_table_name(table_name)
        safe_limit = _validated_limit(limit, maximum=100)
        # SQL identifiers cannot be bound by DBAPI. Interpolation is safe here
        # because ``safe_name`` has been resolved from the fixed whitelist.
        return self._read_frame(
            f"SELECT * FROM `{safe_name}` LIMIT :limit", {"limit": safe_limit}
        )

    def close(self) -> None:
        dispose = getattr(self._engine, "dispose", None)
        if callable(dispose):
            dispose()

    def _read_frame(
        self, statement: str, params: Mapping[str, Any] | None = None
    ) -> pd.DataFrame:
        return pd.read_sql(text(statement), self._engine, params=dict(params or {}))


def create_repository(settings: Any = None) -> AnalyticsRepository:
    """Create a demo, live, or auto-fallback analytics repository.

    Recognized mode keys are ``DASHBOARD_DATA_MODE``, ``dashboard_data_mode``,
    and ``data_mode``.  ``live`` fails closed when the schema/data health check
    does not pass.  ``auto`` attempts the same check and transparently returns a
    demo repository with a sanitized ``fallback_reason`` when live data is not
    ready.

    For tests, callers may inject an ``engine`` setting.  Production callers can
    provide ``database_url`` or DB host/user/password/name fields, including a
    nested ``DB_CONFIG`` mapping compatible with ``etl.config``.
    """

    requested_mode = str(
        _setting(
            settings,
            "DASHBOARD_MODE",
            "DASHBOARD_DATA_MODE",
            "dashboard_mode",
            "dashboard_data_mode",
            "data_mode",
            default="auto",
        )
    ).strip().lower()
    if requested_mode not in {"demo", "live", "auto"}:
        raise RepositoryConfigurationError(
            "DASHBOARD_DATA_MODE must be one of: demo, live, auto."
        )
    if requested_mode == "demo":
        return DemoAnalyticsRepository(requested_mode="demo")

    try:
        engine = _setting(settings, "engine", "DB_ENGINE", default=None)
        if engine is None:
            engine = _build_engine(settings)
        live_repository = MariaDBAnalyticsRepository(
            engine, requested_mode=requested_mode
        )
        health = live_repository.health_check()
    except Exception as exc:
        reason = f"Live source initialization failed ({type(exc).__name__})."
        if requested_mode == "live":
            raise RepositoryUnavailableError(reason) from exc
        return DemoAnalyticsRepository(
            requested_mode="auto", fallback_reason=reason
        )

    if health.healthy:
        return live_repository

    live_repository.close()
    if requested_mode == "live":
        raise RepositoryUnavailableError(health.message)
    return DemoAnalyticsRepository(
        requested_mode="auto", fallback_reason=health.message
    )


def _build_engine(settings: Any) -> Any:
    database_url = _setting(
        settings, "DATABASE_URL", "database_url", "db_url", default=None
    )
    connect_timeout = int(
        _setting(settings, "DB_CONNECT_TIMEOUT", "db_connect_timeout", default=3)
    )
    if database_url:
        connectable = database_url if isinstance(database_url, URL) else str(database_url)
        return create_engine(
            connectable,
            pool_pre_ping=True,
            pool_recycle=1_800,
            connect_args={"connect_timeout": connect_timeout},
        )

    nested = _setting(settings, "DB_CONFIG", "db_config", "database", default={})
    if not isinstance(nested, Mapping):
        nested = {}

    host = _first_present(
        _setting(settings, "DB_HOST", "db_host", default=None),
        _mapping_value(nested, "host"),
        "localhost",
    )
    port = int(
        _first_present(
            _setting(settings, "DB_PORT", "db_port", default=None),
            _mapping_value(nested, "port"),
            3307,
        )
    )
    username = _first_present(
        _setting(settings, "DB_USER", "db_user", default=None),
        _mapping_value(nested, "user"),
        "instacart",
    )
    password = _first_present(
        _setting(settings, "DB_PASSWORD", "db_password", default=None),
        _mapping_value(nested, "password"),
        "",
    )
    database = _first_present(
        _setting(settings, "DB_NAME", "db_name", default=None),
        _mapping_value(nested, "database"),
        "instacart_dwh",
    )
    drivername = str(
        _setting(settings, "DB_DRIVER", "db_driver", default="mysql+pymysql")
    )
    url = URL.create(
        drivername=drivername,
        username=str(username),
        password=str(password),
        host=str(host),
        port=port,
        database=str(database),
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1_800,
        connect_args={"connect_timeout": connect_timeout},
    )


def _setting(settings: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if settings is not None:
            if isinstance(settings, Mapping) and key in settings:
                return settings[key]
            if hasattr(settings, key):
                return getattr(settings, key)
        if key in os.environ:
            return os.environ[key]
    return default


def _mapping_value(mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return mapping[key]
    upper_key = key.upper()
    return mapping.get(upper_key)


def _first_present(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _validated_table_name(table_name: str) -> str:
    if not isinstance(table_name, str) or table_name not in TABLE_WHITELIST:
        allowed = ", ".join(TABLE_WHITELIST)
        raise ValueError(f"table_name must be one of: {allowed}")
    return table_name


def _validated_limit(value: int, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("limit must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return value


def _validated_nonnegative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _copy_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.copy(deep=True).reset_index(drop=True)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _safe_engine_label(engine: Any) -> str:
    url = getattr(engine, "url", None)
    host = getattr(url, "host", None) or "configured host"
    database = getattr(url, "database", None) or "configured database"
    return f"MariaDB warehouse ({host}/{database})"


def _demo_indexes(table_name: str) -> pd.DataFrame:
    primary_columns = {
        "Dim_Time": "time_id",
        "Dim_Department": "department_id",
        "Dim_Aisle": "aisle_id",
        "Dim_Product": "product_id",
        "Dim_User": "user_id",
        "Fact_Orders": "order_id, order_dow",
        "Fact_Order_Details": "detail_id, order_id",
    }
    return pd.DataFrame(
        [
            {
                "index_name": "PRIMARY",
                "columns": primary_columns[table_name],
                "unique": True,
            }
        ]
    )


def _demo_partitions(table_name: str) -> pd.DataFrame:
    if table_name == "Fact_Orders":
        daily = demo_data.orders_by_day()
        return pd.DataFrame(
            {
                "partition_name": "p_" + daily["dow_name"].str.lower(),
                "row_count_estimate": daily["orders"],
                "size_mb": None,
                "comment": daily["dow_name"] + " orders",
            }
        )
    if table_name == "Fact_Order_Details":
        names = [f"p{index}" for index in range(7)] + ["p_max"]
        base_rows, remainder = divmod(demo_data.DEMO_TOTAL_ITEMS, len(names))
        estimates = [
            base_rows + (1 if index < remainder else 0)
            for index in range(len(names))
        ]
        return pd.DataFrame(
            {
                "partition_name": names,
                "row_count_estimate": estimates,
                "size_mb": None,
                "comment": "Representative RANGE partition",
            }
        )
    return pd.DataFrame(
        columns=["partition_name", "row_count_estimate", "size_mb", "comment"]
    )


__all__ = [
    "AnalyticsRepository",
    "DemoAnalyticsRepository",
    "MariaDBAnalyticsRepository",
    "RepositoryConfigurationError",
    "RepositoryHealth",
    "RepositoryUnavailableError",
    "SourceMetadata",
    "TABLE_WHITELIST",
    "TableMetadata",
    "create_repository",
]
