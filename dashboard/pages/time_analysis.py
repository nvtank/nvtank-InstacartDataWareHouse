"""Shopping rhythm analysis using truthful normalized comparisons."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.components import (
    download_frame,
    format_integer,
    format_percent,
    insight_card,
    load_repository_data,
    page_header,
    plotly_chart,
    require_columns,
)
from dashboard.data import AnalyticsRepository
from dashboard.styles import CATEGORICAL_PALETTE, COLORS, style_figure


def show(repository: AnalyticsRepository) -> None:
    page_header(
        "Shopping rhythm",
        (
            "Understand recurring day-of-week and hour-of-day demand patterns. The "
            "source has no calendar dates, so this page does not imply a dated trend."
        ),
        eyebrow="Demand timing",
    )

    day = load_repository_data(
        repository,
        "day_trends",
        loading_label="Loading day-of-week aggregates…",
    )
    hour = load_repository_data(
        repository,
        "hour_trends",
        loading_label="Loading hour aggregates…",
    )
    comparison = load_repository_data(
        repository,
        "weekend_comparison",
        loading_label="Loading normalized weekday comparison…",
    )

    day_ok = require_columns(
        day,
        ("order_dow", "dow_name", "orders", "share_pct"),
        context="Day-of-week",
    )
    hour_ok = require_columns(
        hour,
        ("order_hour", "orders", "share_pct"),
        context="Hour-of-day",
    )

    st.subheader("Recurring weekly pattern")
    left, right = st.columns(2)
    if day_ok:
        with left:
            day_chart = px.bar(
                day.sort_values("order_dow"),
                x="dow_name",
                y="share_pct",
                title="Share of orders by day",
                labels={"dow_name": "Day", "share_pct": "Order share (%)"},
                color_discrete_sequence=[COLORS["blue"]],
            )
            day_chart.update_traces(hovertemplate="%{x}<br>%{y:.1f}% of orders<extra></extra>")
            plotly_chart(style_figure(day_chart), key="time-day-share")
    if hour_ok:
        with right:
            hour_chart = px.line(
                hour.sort_values("order_hour"),
                x="order_hour",
                y="share_pct",
                markers=True,
                title="Share of orders by hour",
                labels={"order_hour": "Hour", "share_pct": "Order share (%)"},
                color_discrete_sequence=[COLORS["primary"]],
            )
            hour_chart.update_traces(
                line={"width": 3},
                marker={"size": 6},
                hovertemplate="%{x}:00<br>%{y:.1f}% of orders<extra></extra>",
            )
            hour_chart.update_xaxes(tickmode="linear", tick0=0, dtick=3)
            plotly_chart(style_figure(hour_chart), key="time-hour-share")

    if day_ok and hour_ok:
        peak_day = day.loc[day["orders"].idxmax()]
        quiet_day = day.loc[day["orders"].idxmin()]
        peak_hour = hour.loc[hour["orders"].idxmax()]
        insight_left, insight_right = st.columns(2)
        with insight_left:
            insight_card(
                "Weekly concentration",
                (
                    f"{peak_day['dow_name']} is highest at {peak_day['share_pct']:.1f}% "
                    f"of orders; {quiet_day['dow_name']} is lowest."
                ),
            )
        with insight_right:
            insight_card(
                "Daily peak",
                (
                    f"The busiest recurring hour is "
                    f"{int(peak_hour['order_hour']):02d}:00 with "
                    f"{format_integer(peak_hour['orders'])} orders."
                ),
            )

    st.subheader("Weekend versus weekday, normalized")
    st.caption(
        "Weekend covers two day categories and weekday covers five. "
        "The primary comparison therefore uses average orders per day category, "
        "while raw totals remain visible for auditability."
    )
    comparison_ok = require_columns(
        comparison,
        (
            "day_type",
            "orders",
            "days_in_group",
            "avg_orders_per_day",
            "avg_basket_size",
            "avg_reorder_rate_pct",
        ),
        context="Weekend comparison",
    )
    if comparison_ok:
        normalized_chart = px.bar(
            comparison,
            x="day_type",
            y="avg_orders_per_day",
            color="day_type",
            color_discrete_sequence=CATEGORICAL_PALETTE[:2],
            title="Average orders per represented day",
            labels={"day_type": "Day group", "avg_orders_per_day": "Average orders/day"},
            text_auto=",.0f",
        )
        normalized_chart.update_layout(showlegend=False)
        normalized_chart.update_traces(
            hovertemplate="%{x}<br>%{y:,.0f} average orders/day<extra></extra>"
        )
        plotly_chart(
            style_figure(normalized_chart, height=390),
            key="time-weekend-normalized",
        )

        indexed = comparison.set_index("day_type")
        weekend = indexed.loc["Weekend"] if "Weekend" in indexed.index else None
        weekday = indexed.loc["Weekday"] if "Weekday" in indexed.index else None
        if weekend is not None and weekday is not None:
            baseline = float(weekday["avg_orders_per_day"])
            difference = (
                (float(weekend["avg_orders_per_day"]) / baseline - 1) * 100 if baseline else 0.0
            )
            comparison_left, comparison_right = st.columns(2)
            with comparison_left:
                insight_card(
                    "Normalized traffic difference",
                    (
                        f"Weekend average daily traffic is {abs(difference):.1f}% "
                        f"{'higher' if difference >= 0 else 'lower'} than weekday traffic."
                    ),
                )
            with comparison_right:
                insight_card(
                    "Basket and reorder context",
                    (
                        f"Weekend basket size averages {weekend['avg_basket_size']:.1f} "
                        f"items with a {format_percent(weekend['avg_reorder_rate_pct'])} "
                        "mean reorder ratio."
                    ),
                )

        st.dataframe(
            comparison,
            width="stretch",
            hide_index=True,
            column_config={
                "orders": st.column_config.NumberColumn(format="%d"),
                "avg_orders_per_day": st.column_config.NumberColumn(format="%.0f"),
                "avg_basket_size": st.column_config.NumberColumn(format="%.2f"),
                "avg_reorder_rate_pct": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

    with st.expander("View and download timing aggregates"):
        if day_ok:
            st.markdown("#### Day-of-week data")
            st.dataframe(day, width="stretch", hide_index=True)
            download_frame(
                day,
                label="Download day data",
                file_name="instacart-day-distribution.csv",
                key="time-download-day",
            )
        if hour_ok:
            st.markdown("#### Hour-of-day data")
            st.dataframe(hour, width="stretch", hide_index=True)
            download_frame(
                hour,
                label="Download hour data",
                file_name="instacart-hour-distribution.csv",
                key="time-download-hour",
            )
