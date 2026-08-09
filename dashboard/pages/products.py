"""Product and aisle analytics page."""

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
from dashboard.styles import SEQUENTIAL_SCALE, style_figure


def show(repository: AnalyticsRepository) -> None:
    page_header(
        "Products & aisles",
        (
            "Explore high-volume products and repeat-purchase behavior with explicit "
            "support thresholds and department filters."
        ),
        eyebrow="Merchandising signals",
    )

    departments = load_repository_data(
        repository,
        "departments",
        loading_label="Loading department filters…",
    )
    department_options = ["All departments"]
    if require_columns(
        departments,
        ("department_name",),
        context="Department filter",
    ):
        department_options.extend(
            sorted(departments["department_name"].dropna().astype(str).unique())
        )

    st.subheader("Product ranking")
    filter_left, filter_right = st.columns(2)
    with filter_left:
        selected_department = st.selectbox(
            "Department",
            department_options,
            help="Restricts the warehouse aggregate before ranking products.",
        )
    with filter_right:
        visible_limit = st.slider(
            "Products shown",
            min_value=5,
            max_value=30,
            value=15,
            step=5,
        )

    repository_department = (
        None if selected_department == "All departments" else selected_department
    )
    products = load_repository_data(
        repository,
        "products",
        loading_label="Loading product ranking…",
        limit=100,
        department=repository_department,
    )
    product_ok = require_columns(
        products,
        (
            "product_name",
            "department_name",
            "aisle_name",
            "orders",
            "total_items",
            "reorder_rate_pct",
        ),
        context="Product ranking",
    )
    if product_ok:
        search_term = st.text_input(
            "Search within up to 100 loaded top products",
            placeholder="Try banana, milk, or organic…",
            help=(
                "This is a client-side search over the ranked result set, not a "
                "full-catalogue database search."
            ),
        ).strip()
        filtered = products
        if search_term:
            filtered = products[
                products["product_name"]
                .astype(str)
                .str.contains(
                    search_term,
                    case=False,
                    regex=False,
                    na=False,
                )
            ]
        visible = filtered.head(visible_limit).copy()
        if visible.empty:
            st.info("No loaded top product matches this search. Clear the search to continue.")
        else:
            chart_frame = visible.sort_values("orders", ascending=True)
            product_chart = px.bar(
                chart_frame,
                x="orders",
                y="product_name",
                orientation="h",
                color="reorder_rate_pct",
                color_continuous_scale=SEQUENTIAL_SCALE,
                title="Ranked by distinct orders",
                labels={
                    "orders": "Distinct orders",
                    "product_name": "Product",
                    "reorder_rate_pct": "Reorder rate (%)",
                },
                hover_data={"department_name": True, "aisle_name": True},
            )
            product_chart.update_traces(
                hovertemplate=(
                    "%{y}<br>%{x:,.0f} distinct orders"
                    "<br>Reorder rate: %{marker.color:.1f}%<extra></extra>"
                )
            )
            height = max(400, min(720, 34 * len(chart_frame) + 180))
            plotly_chart(
                style_figure(product_chart, height=height),
                key="products-ranking",
            )
            leader = visible.iloc[0]
            insight_card(
                "Highest-volume result",
                (
                    f"{leader['product_name']} appears in "
                    f"{format_integer(leader['orders'])} distinct orders with a "
                    f"{format_percent(leader['reorder_rate_pct'])} reorder rate."
                ),
            )
            st.dataframe(
                visible,
                width="stretch",
                hide_index=True,
                column_config={
                    "orders": st.column_config.NumberColumn(format="%d"),
                    "total_items": st.column_config.NumberColumn(format="%d"),
                    "reorder_rate_pct": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
            download_frame(
                visible,
                label="Download filtered products",
                file_name="instacart-product-ranking.csv",
                key="products-download",
            )

    st.subheader("Aisle loyalty")
    aisle_left, aisle_right = st.columns(2)
    with aisle_left:
        min_items = int(
            st.number_input(
                "Minimum line-item support",
                min_value=0,
                max_value=1_000_000,
                value=10_000,
                step=5_000,
                help="Removes tiny aisles whose reorder rate is less reliable.",
            )
        )
    with aisle_right:
        aisle_limit = st.slider(
            "Aisles shown",
            min_value=5,
            max_value=30,
            value=15,
            step=5,
        )
    aisles = load_repository_data(
        repository,
        "aisles",
        loading_label="Loading aisle aggregates…",
        limit=aisle_limit,
        min_items=min_items,
    )
    aisle_ok = require_columns(
        aisles,
        ("aisle_name", "reorder_rate_pct", "items"),
        context="Aisle ranking",
    )
    if aisle_ok:
        aisle_chart_frame = aisles.sort_values("reorder_rate_pct", ascending=True)
        aisle_chart = px.bar(
            aisle_chart_frame,
            x="reorder_rate_pct",
            y="aisle_name",
            orientation="h",
            color="items",
            color_continuous_scale=SEQUENTIAL_SCALE,
            title="Reorder rate with minimum support applied",
            labels={
                "reorder_rate_pct": "Reorder rate (%)",
                "aisle_name": "Aisle",
                "items": "Line items",
            },
        )
        aisle_chart.update_traces(
            hovertemplate=(
                "%{y}<br>Reorder rate: %{x:.1f}%<br>%{marker.color:,.0f} line items<extra></extra>"
            )
        )
        plotly_chart(
            style_figure(aisle_chart, height=max(420, 32 * len(aisles) + 160)),
            key="products-aisle-ranking",
        )
        best_aisle = aisles.loc[aisles["reorder_rate_pct"].idxmax()]
        insight_card(
            "Strongest repeat signal",
            (
                f"{str(best_aisle['aisle_name']).title()} leads this supported set at "
                f"{format_percent(best_aisle['reorder_rate_pct'])}."
            ),
        )
        st.dataframe(
            aisles,
            width="stretch",
            hide_index=True,
            column_config={
                "reorder_rate_pct": st.column_config.NumberColumn(format="%.1f%%"),
                "items": st.column_config.NumberColumn(format="%d"),
            },
        )
