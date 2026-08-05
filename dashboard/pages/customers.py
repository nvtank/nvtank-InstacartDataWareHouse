"""Truthful rule-based customer segmentation page."""

from __future__ import annotations

import pandas as pd
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
from dashboard.styles import CATEGORICAL_PALETTE, SEQUENTIAL_SCALE, style_figure

SEGMENT_ORDER = ["VIP", "Frequent", "Regular", "New"]


def _ordered_segments(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.copy()
    rank = {name: index for index, name in enumerate(SEGMENT_ORDER)}
    ordered["_rank"] = ordered["user_segment"].map(rank).fillna(len(rank))
    return ordered.sort_values(["_rank", "user_segment"]).drop(columns="_rank")


def show(repository: AnalyticsRepository) -> None:
    page_header(
        "Customer segments",
        (
            "Compare customer reach, order contribution, and basket behavior using "
            "the deterministic segment rules produced by the ETL pipeline."
        ),
        eyebrow="Customer behavior",
    )
    st.info(
        "These are rule-based warehouse segments, not K-Means clusters. "
        "VIP has at least 50 orders; Frequent 20–49; Regular 10–19; New fewer than 10."
    )

    segments = load_repository_data(
        repository,
        "customer_segments",
        loading_label="Loading customer segments…",
    )
    segment_ok = require_columns(
        segments,
        (
            "user_segment",
            "users",
            "total_orders",
            "avg_orders",
            "avg_basket_size",
            "user_share_pct",
            "order_share_pct",
        ),
        context="Customer segment",
    )
    if segment_ok:
        segments = _ordered_segments(segments)
        share_frame = segments.melt(
            id_vars="user_segment",
            value_vars=["user_share_pct", "order_share_pct"],
            var_name="measure",
            value_name="share_pct",
        )
        share_frame["measure"] = share_frame["measure"].map(
            {
                "user_share_pct": "Customer share",
                "order_share_pct": "Order contribution",
            }
        )
        share_chart = px.bar(
            share_frame,
            x="user_segment",
            y="share_pct",
            color="measure",
            barmode="group",
            color_discrete_sequence=CATEGORICAL_PALETTE[:2],
            title="Customer share versus order contribution",
            labels={
                "user_segment": "Rule-based segment",
                "share_pct": "Share (%)",
                "measure": "Measure",
            },
        )
        share_chart.update_traces(hovertemplate="%{x}<br>%{y:.1f}%<extra>%{fullData.name}</extra>")
        plotly_chart(
            style_figure(share_chart, horizontal_legend=True, legend=True),
            key="customers-segment-share",
        )

        contribution_gap = segments.assign(
            gap=segments["order_share_pct"] - segments["user_share_pct"]
        )
        strongest = contribution_gap.loc[contribution_gap["gap"].idxmax()]
        detail_left, detail_right = st.columns(2)
        with detail_left:
            insight_card(
                "Highest contribution leverage",
                (
                    f"{strongest['user_segment']} customers represent "
                    f"{format_percent(strongest['user_share_pct'])} of customers and "
                    f"{format_percent(strongest['order_share_pct'])} of orders."
                ),
            )
        with detail_right:
            insight_card(
                "Segment shopping depth",
                (
                    f"The leading contribution segment averages "
                    f"{strongest['avg_orders']:.1f} orders and "
                    f"{strongest['avg_basket_size']:.1f} items per basket."
                ),
            )

        st.dataframe(
            segments,
            width="stretch",
            hide_index=True,
            column_config={
                "users": st.column_config.NumberColumn(format="%d"),
                "total_orders": st.column_config.NumberColumn(format="%d"),
                "avg_orders": st.column_config.NumberColumn(format="%.1f"),
                "avg_basket_size": st.column_config.NumberColumn(format="%.1f"),
                "user_share_pct": st.column_config.NumberColumn(format="%.1f%%"),
                "order_share_pct": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
        download_frame(
            segments,
            label="Download segment aggregate",
            file_name="instacart-rule-based-segments.csv",
            key="customers-download-segments",
        )

    st.subheader("Basket size distribution")
    baskets = load_repository_data(
        repository,
        "basket_distribution",
        loading_label="Loading basket distribution…",
    )
    basket_ok = require_columns(
        baskets,
        (
            "bucket_order",
            "basket_size",
            "orders",
            "avg_reorder_rate_pct",
            "order_share_pct",
        ),
        context="Basket distribution",
    )
    if basket_ok:
        baskets = baskets.sort_values("bucket_order").copy()
        basket_chart = px.bar(
            baskets,
            x="basket_size",
            y="orders",
            color="avg_reorder_rate_pct",
            color_continuous_scale=SEQUENTIAL_SCALE,
            title="Orders by basket-size band",
            labels={
                "basket_size": "Basket size",
                "orders": "Orders",
                "avg_reorder_rate_pct": "Mean reorder ratio (%)",
            },
        )
        basket_chart.update_traces(
            hovertemplate=(
                "%{x}<br>%{y:,.0f} orders"
                "<br>Mean reorder ratio: %{marker.color:.1f}%<extra></extra>"
            )
        )
        plotly_chart(
            style_figure(basket_chart),
            key="customers-basket-distribution",
        )
        common = baskets.loc[baskets["orders"].idxmax()]
        insight_card(
            "Most common basket band",
            (
                f"{common['basket_size']} accounts for "
                f"{format_percent(common['order_share_pct'])} of orders "
                f"({format_integer(common['orders'])} orders)."
            ),
        )
        st.dataframe(
            baskets,
            width="stretch",
            hide_index=True,
            column_config={
                "orders": st.column_config.NumberColumn(format="%d"),
                "avg_reorder_rate_pct": st.column_config.NumberColumn(format="%.1f%%"),
                "order_share_pct": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
