"""Executive overview page."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components import (
    download_frame,
    format_compact_number,
    format_decimal,
    format_percent,
    insight_card,
    load_repository_data,
    page_header,
    plotly_chart,
    require_columns,
)
from dashboard.data import AnalyticsRepository
from dashboard.styles import COLORS, SEQUENTIAL_SCALE, style_figure


def _condense_departments(frame: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    ordered = frame.sort_values("market_share_pct", ascending=False).reset_index(drop=True)
    leaders = ordered.head(top_n).copy()
    remainder = ordered.iloc[top_n:]
    if not remainder.empty:
        leaders.loc[len(leaders)] = {
            "department_name": "All other departments",
            "orders": remainder["orders"].sum(),
            "total_items": remainder["total_items"].sum(),
            "reorder_rate_pct": (
                (remainder["reorder_rate_pct"] * remainder["total_items"]).sum()
                / remainder["total_items"].sum()
            ),
            "unique_products": remainder["unique_products"].sum(),
            "market_share_pct": remainder["market_share_pct"].sum(),
        }
    return leaders.sort_values("market_share_pct", ascending=True)


def show(repository: AnalyticsRepository) -> None:
    page_header(
        "Executive overview",
        (
            "A decision-focused view of order volume, customer reach, basket behavior, "
            "and category mix for the current warehouse snapshot."
        ),
        eyebrow="Instacart Decision Intelligence",
    )

    kpis = load_repository_data(
        repository,
        "overview_kpis",
        loading_label="Loading snapshot KPIs…",
    )
    if not require_columns(
        kpis,
        (
            "total_orders",
            "total_users",
            "total_products",
            "avg_basket_size",
            "avg_reorder_rate_pct",
        ),
        context="Overview KPI",
    ):
        return

    row = kpis.iloc[0]
    st.subheader("Snapshot KPIs")
    first, second = st.columns(2)
    with first:
        orders, customers = st.columns(2)
        orders.metric("Orders", format_compact_number(row["total_orders"]))
        customers.metric("Customers", format_compact_number(row["total_users"]))
    with second:
        basket, reorder = st.columns(2)
        basket.metric("Average basket", format_decimal(row["avg_basket_size"]))
        reorder.metric(
            "Mean order reorder ratio",
            format_percent(row["avg_reorder_rate_pct"]),
        )
    st.caption(
        f"Catalogue coverage: {format_compact_number(row['total_products'])} products · "
        f"{format_compact_number(row.get('total_departments'))} departments · "
        f"{format_compact_number(row.get('total_aisles'))} aisles."
    )

    day = load_repository_data(
        repository,
        "day_trends",
        loading_label="Loading day-of-week distribution…",
    )
    hour = load_repository_data(
        repository,
        "hour_trends",
        loading_label="Loading hourly distribution…",
    )
    departments = load_repository_data(
        repository,
        "departments",
        loading_label="Loading department mix…",
    )

    st.subheader("When customers shop")
    day_ok = require_columns(day, ("dow_name", "orders", "share_pct"), context="Daily trend")
    hour_ok = require_columns(
        hour,
        ("order_hour", "orders", "share_pct"),
        context="Hourly trend",
    )
    left, right = st.columns(2)
    if day_ok:
        with left:
            day_chart = px.bar(
                day,
                x="dow_name",
                y="orders",
                title="Orders by day of week",
                labels={"dow_name": "Day", "orders": "Orders"},
                color_discrete_sequence=[COLORS["blue"]],
            )
            day_chart.update_traces(hovertemplate="%{x}<br>%{y:,.0f} orders<extra></extra>")
            plotly_chart(style_figure(day_chart), key="overview-day-orders")
    if hour_ok:
        with right:
            hour_chart = px.area(
                hour,
                x="order_hour",
                y="orders",
                title="Orders by hour of day",
                labels={"order_hour": "Hour", "orders": "Orders"},
                color_discrete_sequence=[COLORS["primary"]],
            )
            hour_chart.update_traces(
                line={"width": 3},
                hovertemplate="%{x}:00<br>%{y:,.0f} orders<extra></extra>",
            )
            hour_chart.update_xaxes(tickmode="linear", tick0=0, dtick=3)
            plotly_chart(style_figure(hour_chart), key="overview-hour-orders")

    if day_ok and hour_ok:
        peak_day = day.loc[day["orders"].idxmax()]
        peak_hour = hour.loc[hour["orders"].idxmax()]
        insight_left, insight_right = st.columns(2)
        with insight_left:
            insight_card(
                "Highest-volume day",
                f"{peak_day['dow_name']} contributes {peak_day['share_pct']:.1f}% of orders.",
            )
        with insight_right:
            insight_card(
                "Peak ordering hour",
                f"Demand reaches its high point around {int(peak_hour['order_hour']):02d}:00.",
            )

    st.subheader("What customers buy")
    department_ok = require_columns(
        departments,
        ("department_name", "market_share_pct", "total_items", "reorder_rate_pct"),
        context="Department mix",
    )
    if department_ok:
        condensed = _condense_departments(departments)
        department_chart = px.bar(
            condensed,
            x="market_share_pct",
            y="department_name",
            orientation="h",
            color="reorder_rate_pct",
            color_continuous_scale=SEQUENTIAL_SCALE,
            title="Item share across every department",
            labels={
                "market_share_pct": "Item share (%)",
                "department_name": "Department",
                "reorder_rate_pct": "Reorder rate (%)",
            },
        )
        department_chart.update_traces(
            hovertemplate=(
                "%{y}<br>%{x:.1f}% of items<br>Reorder rate: %{marker.color:.1f}%<extra></extra>"
            )
        )
        plotly_chart(
            style_figure(department_chart, height=470),
            key="overview-department-share",
        )
        top_department = departments.loc[departments["market_share_pct"].idxmax()]
        insight_card(
            "Largest item category",
            (
                f"{str(top_department['department_name']).title()} represents "
                f"{top_department['market_share_pct']:.1f}% of all line items."
            ),
        )

    with st.expander("View accessible data tables and downloads"):
        if day_ok:
            st.markdown("#### Day-of-week aggregate")
            st.dataframe(day, width="stretch", hide_index=True)
            download_frame(
                day,
                label="Download day aggregate",
                file_name="instacart-orders-by-day.csv",
                key="overview-download-day",
            )
        if hour_ok:
            st.markdown("#### Hour aggregate")
            st.dataframe(hour, width="stretch", hide_index=True)
            download_frame(
                hour,
                label="Download hour aggregate",
                file_name="instacart-orders-by-hour.csv",
                key="overview-download-hour",
            )
