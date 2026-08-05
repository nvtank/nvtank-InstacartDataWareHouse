from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from dashboard import data, demo_data
from dashboard.data import (
    DemoAnalyticsRepository,
    MariaDBAnalyticsRepository,
    RepositoryConfigurationError,
    RepositoryHealth,
    RepositoryUnavailableError,
    create_repository,
)
from dashboard.pages.departments import COMPARISON_METRICS, _normalized_comparison
from dashboard.pages.overview import _condense_departments


def repository_health(*, healthy: bool, message: str) -> RepositoryHealth:
    return RepositoryHealth(
        healthy=healthy,
        checked_at=datetime(2026, 8, 6, tzinfo=UTC),
        checks={"ready": healthy},
        message=message,
    )


def test_demo_aggregates_reconcile_to_the_snapshot_totals() -> None:
    repository = DemoAnalyticsRepository()
    kpis = repository.overview_kpis().iloc[0]
    day = repository.day_trends()
    hour = repository.hour_trends()
    departments = repository.departments()
    segments = repository.customer_segments()
    baskets = repository.basket_distribution()

    assert int(day["orders"].sum()) == int(kpis["total_orders"])
    assert int(hour["orders"].sum()) == int(kpis["total_orders"])
    assert int(segments["total_orders"].sum()) == int(kpis["total_orders"])
    assert int(baskets["orders"].sum()) == int(kpis["total_orders"])
    assert int(segments["users"].sum()) == int(kpis["total_users"])
    assert int(departments["total_items"].sum()) == int(kpis["total_items"])

    for frame, share_column in [
        (day, "share_pct"),
        (hour, "share_pct"),
        (departments, "market_share_pct"),
        (segments, "user_share_pct"),
        (segments, "order_share_pct"),
        (baskets, "order_share_pct"),
    ]:
        assert frame[share_column].sum() == pytest.approx(100.0)


def test_weekend_comparison_uses_per_day_normalization() -> None:
    repository = DemoAnalyticsRepository()
    comparison = repository.weekend_comparison().set_index("day_type")

    assert comparison.loc["Weekend", "days_in_group"] == 2
    assert comparison.loc["Weekday", "days_in_group"] == 5
    for day_type in ["Weekend", "Weekday"]:
        row = comparison.loc[day_type]
        assert row["avg_orders_per_day"] == pytest.approx(
            row["orders"] / row["days_in_group"]
        )
    assert comparison.loc["Weekday", "orders"] > comparison.loc["Weekend", "orders"]
    assert (
        comparison.loc["Weekend", "avg_orders_per_day"]
        > comparison.loc["Weekday", "avg_orders_per_day"]
    )


def test_demo_repository_returns_deeply_isolated_frames() -> None:
    repository = DemoAnalyticsRepository()
    first = repository.day_trends()
    original_orders = int(first.loc[0, "orders"])
    first.loc[0, "orders"] = -1

    second = repository.day_trends()

    assert int(second.loc[0, "orders"]) == original_orders
    assert int(second.loc[0, "orders"]) != int(first.loc[0, "orders"])

    sample = repository.table_sample("Dim_Product", limit=1)
    original_product = sample.loc[0, "product_name"]
    sample.loc[0, "product_name"] = "mutated"
    assert repository.table_sample("Dim_Product", limit=1).loc[0, "product_name"] == original_product


def test_demo_products_apply_normalized_exact_filter_before_limit() -> None:
    repository = DemoAnalyticsRepository()

    products = repository.products(limit=3, department="  PRODUCE ")
    dairy = repository.products(limit=100, department="dairy eggs")

    assert len(products) == 3
    assert products["department_name"].eq("produce").all()
    assert dairy["department_name"].eq("dairy eggs").all()
    assert dairy["product_name"].tolist() == ["Organic Whole Milk"]


def test_demo_aisles_apply_support_filter_and_limit() -> None:
    repository = DemoAnalyticsRepository()

    aisles = repository.aisles(limit=2, min_items=700_000)

    assert len(aisles) == 2
    assert aisles["items"].ge(700_000).all()
    assert aisles["reorder_rate_pct"].is_monotonic_decreasing


@pytest.mark.parametrize(
    ("method_name", "kwargs", "error_type"),
    [
        ("products", {"limit": 0}, ValueError),
        ("products", {"limit": 101}, ValueError),
        ("products", {"limit": True}, TypeError),
        ("aisles", {"limit": 135}, ValueError),
        ("aisles", {"min_items": -1}, ValueError),
        ("aisles", {"min_items": 1.5}, TypeError),
        ("table_sample", {"table_name": "Dim_Time", "limit": 0}, ValueError),
    ],
)
def test_repository_limits_fail_closed(method_name: str, kwargs: dict, error_type: type[Exception]) -> None:
    repository = DemoAnalyticsRepository()

    with pytest.raises(error_type):
        getattr(repository, method_name)(**kwargs)


@pytest.mark.parametrize("table_name", ["Fact_Orders; DROP DATABASE", "dim_user", ""])
def test_table_whitelist_rejects_unknown_identifiers_before_query(table_name: str) -> None:
    demo_repository = DemoAnalyticsRepository()
    engine = MagicMock()
    live_repository = MariaDBAnalyticsRepository(engine)

    with pytest.raises(ValueError, match="table_name must be one of"):
        demo_repository.table_metadata(table_name)
    with pytest.raises(ValueError, match="table_name must be one of"):
        live_repository.table_sample(table_name)

    engine.assert_not_called()


def test_demo_table_catalog_metadata_and_partitions_match_contract() -> None:
    repository = DemoAnalyticsRepository()

    assert set(repository.table_catalog()["table_name"]) == set(data.TABLE_WHITELIST)
    order_metadata = repository.table_metadata("Fact_Orders")
    detail_metadata = repository.table_metadata("Fact_Order_Details")
    dimension_metadata = repository.table_metadata("Dim_User")

    assert order_metadata.kind == "Fact"
    assert len(order_metadata.partitions) == 7
    assert int(order_metadata.partitions["row_count_estimate"].sum()) == demo_data.DEMO_TOTAL_ORDERS
    assert len(detail_metadata.partitions) == 8
    assert int(detail_metadata.partitions["row_count_estimate"].sum()) == demo_data.DEMO_TOTAL_ITEMS
    assert dimension_metadata.partitions.empty


def test_live_repository_binds_filters_and_limits_as_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = MariaDBAnalyticsRepository(MagicMock())
    read_frame = MagicMock(return_value=pd.DataFrame())
    monkeypatch.setattr(repository, "_read_frame", read_frame)

    repository.products(limit=4, department="  produce ")
    statement, parameters = read_frame.call_args.args

    assert "WHERE d.department_name = :department" in statement
    assert "LIMIT :limit" in statement
    assert parameters == {"limit": 4, "department": "produce"}

    repository.aisles(limit=5, min_items=123)
    _, parameters = read_frame.call_args.args
    assert parameters == {"min_items": 123, "limit": 5}


def test_live_department_share_uses_the_full_result(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = MariaDBAnalyticsRepository(MagicMock())
    aggregate = pd.DataFrame(
        {
            "department_name": ["produce", "dairy eggs"],
            "orders": [75, 25],
            "total_items": [300, 100],
            "reorder_rate_pct": [60.0, 50.0],
            "unique_products": [10, 5],
        }
    )
    monkeypatch.setattr(repository, "_read_frame", MagicMock(return_value=aggregate.copy()))

    result = repository.departments()

    assert result["market_share_pct"].tolist() == pytest.approx([75.0, 25.0])
    assert result["market_share_pct"].sum() == pytest.approx(100.0)


def test_create_repository_demo_never_initializes_an_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_engine = MagicMock()
    monkeypatch.setattr(data, "_build_engine", build_engine)

    repository = create_repository({"DASHBOARD_MODE": "demo"})

    assert isinstance(repository, DemoAnalyticsRepository)
    assert repository.source_metadata.requested_mode == "demo"
    build_engine.assert_not_called()


def test_create_repository_auto_returns_healthy_live_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    healthy = repository_health(healthy=True, message="ready")

    def health_check(repository: MariaDBAnalyticsRepository) -> RepositoryHealth:
        repository._health = healthy
        return healthy

    monkeypatch.setattr(MariaDBAnalyticsRepository, "health_check", health_check)

    repository = create_repository({"DASHBOARD_MODE": "auto", "engine": engine})

    assert isinstance(repository, MariaDBAnalyticsRepository)
    assert repository.source_metadata.is_live is True
    assert repository.source_metadata.healthy is True
    engine.dispose.assert_not_called()


def test_create_repository_auto_falls_back_and_closes_unhealthy_live_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    unhealthy = repository_health(healthy=False, message="schema incomplete")
    monkeypatch.setattr(
        MariaDBAnalyticsRepository,
        "health_check",
        MagicMock(return_value=unhealthy),
    )

    repository = create_repository({"DASHBOARD_MODE": "auto", "engine": engine})

    assert isinstance(repository, DemoAnalyticsRepository)
    assert repository.source_metadata.requested_mode == "auto"
    assert repository.source_metadata.fallback_reason == "schema incomplete"
    engine.dispose.assert_called_once_with()


def test_create_repository_live_fails_closed_and_disposes_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    unhealthy = repository_health(healthy=False, message="warehouse empty")
    monkeypatch.setattr(
        MariaDBAnalyticsRepository,
        "health_check",
        MagicMock(return_value=unhealthy),
    )

    with pytest.raises(RepositoryUnavailableError, match="warehouse empty"):
        create_repository({"DASHBOARD_MODE": "live", "engine": engine})

    engine.dispose.assert_called_once_with()


def test_create_repository_sanitizes_initialization_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(data, "_build_engine", MagicMock(side_effect=OSError("secret URL")))

    fallback = create_repository({"DASHBOARD_MODE": "auto"})
    assert isinstance(fallback, DemoAnalyticsRepository)
    assert fallback.source_metadata.fallback_reason == "Live source initialization failed (OSError)."
    assert "secret URL" not in fallback.source_metadata.fallback_reason

    with pytest.raises(RepositoryUnavailableError, match="OSError"):
        create_repository({"DASHBOARD_MODE": "live"})


def test_create_repository_rejects_unknown_mode() -> None:
    with pytest.raises(RepositoryConfigurationError, match="demo, live, auto"):
        create_repository({"DASHBOARD_MODE": "sometimes"})


def test_department_condensation_preserves_totals_and_uses_weighted_reorder_rate() -> None:
    departments = pd.DataFrame(
        {
            "department_name": ["A", "B", "C", "D"],
            "orders": [100, 80, 40, 20],
            "total_items": [100, 80, 30, 10],
            "reorder_rate_pct": [70.0, 60.0, 50.0, 20.0],
            "unique_products": [10, 8, 3, 1],
            "market_share_pct": [45.0, 35.0, 15.0, 5.0],
        }
    )

    result = _condense_departments(departments, top_n=2)
    remainder = result[result["department_name"] == "All other departments"].iloc[0]

    assert len(result) == 3
    assert result["total_items"].sum() == departments["total_items"].sum()
    assert result["market_share_pct"].sum() == pytest.approx(100.0)
    assert remainder["reorder_rate_pct"] == pytest.approx((50.0 * 30 + 20.0 * 10) / 40)
    assert result["market_share_pct"].is_monotonic_increasing


def test_department_comparison_normalizes_each_metric_against_its_own_ceiling() -> None:
    departments = pd.DataFrame(
        {
            "department_name": ["A", "B", "C"],
            "orders": [100, 50, 200],
            "total_items": [100, 50, 25],
            "unique_products": [20, 40, 10],
            "reorder_rate_pct": [50.0, 75.0, 100.0],
        }
    )

    result = _normalized_comparison(departments, ("A", "B"))

    assert len(result) == len(COMPARISON_METRICS) * 2
    indexed = result.set_index(["metric", "department_name"])["relative_index"]
    assert indexed.loc["Order reach", "A"] == pytest.approx(50.0)
    assert indexed.loc["Order reach", "B"] == pytest.approx(25.0)
    assert indexed.loc["Item volume", "A"] == pytest.approx(100.0)
    assert indexed.loc["Product breadth", "B"] == pytest.approx(100.0)
    assert indexed.loc["Reorder rate", "B"] == pytest.approx(75.0)
    assert result["relative_index"].between(0, 100).all()
