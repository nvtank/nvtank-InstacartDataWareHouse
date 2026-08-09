"""Department performance and fair, normalized comparisons."""

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

COMPARISON_METRICS = {
    "orders": "Order reach",
    "total_items": "Item volume",
    "unique_products": "Product breadth",
    "reorder_rate_pct": "Reorder rate",
}


def _normalized_comparison(
    departments: pd.DataFrame,
    selected_names: tuple[str, str],
) -> pd.DataFrame:
    """Express unlike department metrics on a comparable 0-100 index."""

    selected = departments[departments["department_name"].isin(selected_names)].copy()
    rows: list[dict[str, object]] = []
    for column, label in COMPARISON_METRICS.items():
        metric_ceiling = pd.to_numeric(departments[column], errors="coerce").max()
        for _, department in selected.iterrows():
            actual = pd.to_numeric(pd.Series([department[column]]), errors="coerce").iloc[0]
            score = 0.0
            if pd.notna(actual) and pd.notna(metric_ceiling) and metric_ceiling > 0:
                score = float(actual) / float(metric_ceiling) * 100
            rows.append(
                {
                    "department_name": department["department_name"],
                    "metric": label,
                    "relative_index": score,
                }
            )
    return pd.DataFrame(rows)


def show(repository: AnalyticsRepository) -> None:
    page_header(
        "Department performance",
        (
            "Compare reach, item volume, assortment breadth, and repeat behavior "
            "without mixing incompatible units on one scale."
        ),
        eyebrow="Portfolio allocation",
    )

    departments = load_repository_data(
        repository,
        "departments",
        loading_label="Loading department aggregates…",
    )
    required = (
        "department_name",
        "orders",
        "total_items",
        "reorder_rate_pct",
        "unique_products",
        "market_share_pct",
    )
    if not require_columns(departments, required, context="Department performance"):
        return

    department_frame = departments.copy()
    department_frame["department_name"] = department_frame["department_name"].astype(str)

    st.subheader("Portfolio view")
    chart_frame = department_frame.nlargest(12, "total_items").sort_values("total_items")
    portfolio_chart = px.bar(
        chart_frame,
        x="total_items",
        y="department_name",
        orientation="h",
        color="reorder_rate_pct",
        color_continuous_scale=SEQUENTIAL_SCALE,
        title="Largest departments by line-item volume",
        labels={
            "total_items": "Line items",
            "department_name": "Department",
            "reorder_rate_pct": "Reorder rate (%)",
        },
        hover_data={"orders": ":,.0f", "market_share_pct": ":.1f"},
    )
    portfolio_chart.update_traces(
        hovertemplate=(
            "%{y}<br>%{x:,.0f} line items<br>Reorder rate: %{marker.color:.1f}%<extra></extra>"
        )
    )
    plotly_chart(
        style_figure(
            portfolio_chart,
            height=max(460, 34 * len(chart_frame) + 170),
        ),
        key="departments-portfolio",
    )

    insight_left, insight_right = st.columns(2)
    volume_leader = department_frame.loc[department_frame["total_items"].idxmax()]
    reorder_leader = department_frame.loc[department_frame["reorder_rate_pct"].idxmax()]
    with insight_left:
        insight_card(
            "Volume leader",
            (
                f"{volume_leader['department_name']} represents "
                f"{format_percent(volume_leader['market_share_pct'])} of line items "
                f"in this snapshot."
            ),
        )
    with insight_right:
        insight_card(
            "Repeat leader",
            (
                f"{reorder_leader['department_name']} has the highest department "
                f"reorder rate at {format_percent(reorder_leader['reorder_rate_pct'])}."
            ),
        )

    st.subheader("Side-by-side comparison")
    department_names = sorted(department_frame["department_name"].unique())
    if len(department_names) < 2:
        st.info("At least two departments are required for a comparison.")
    else:
        selector_left, selector_right = st.columns(2)
        with selector_left:
            first_name = st.selectbox(
                "First department",
                department_names,
                index=0,
                key="department-compare-first",
            )
        second_options = [name for name in department_names if name != first_name]
        with selector_right:
            second_name = st.selectbox(
                "Second department",
                second_options,
                index=0,
                key="department-compare-second",
            )

        normalized = _normalized_comparison(
            department_frame,
            (first_name, second_name),
        )
        comparison_chart = px.bar(
            normalized,
            x="metric",
            y="relative_index",
            color="department_name",
            barmode="group",
            color_discrete_sequence=CATEGORICAL_PALETTE,
            title="Relative performance index by metric",
            labels={
                "metric": "Metric",
                "relative_index": "Index (best department = 100)",
                "department_name": "Department",
            },
        )
        comparison_chart.update_yaxes(range=[0, 105], ticksuffix="")
        comparison_chart.update_traces(
            hovertemplate=("%{x}<br>Relative index: %{y:.1f}<br>%{fullData.name}<extra></extra>")
        )
        plotly_chart(
            style_figure(
                comparison_chart,
                height=440,
                legend=True,
                horizontal_legend=True,
            ),
            key="departments-comparison",
        )
        st.caption(
            "Each score is the department value divided by the highest value for "
            "that metric across all departments in this snapshot. The table below "
            "retains the original units."
        )

        actual = department_frame[
            department_frame["department_name"].isin((first_name, second_name))
        ][list(("department_name", *COMPARISON_METRICS))]
        st.dataframe(
            actual,
            width="stretch",
            hide_index=True,
            column_config={
                "department_name": "Department",
                "orders": st.column_config.NumberColumn(
                    "Distinct orders",
                    format="%d",
                ),
                "total_items": st.column_config.NumberColumn(
                    "Line items",
                    format="%d",
                ),
                "unique_products": st.column_config.NumberColumn(
                    "Unique products",
                    format="%d",
                ),
                "reorder_rate_pct": st.column_config.NumberColumn(
                    "Reorder rate",
                    format="%.1f%%",
                ),
            },
        )
        first_row = actual[actual["department_name"] == first_name].iloc[0]
        second_row = actual[actual["department_name"] == second_name].iloc[0]
        item_difference = int(first_row["total_items"] - second_row["total_items"])
        higher_name = first_name if item_difference >= 0 else second_name
        insight_card(
            "Comparison readout",
            (
                f"{higher_name} has the larger item footprint; the absolute gap is "
                f"{format_integer(abs(item_difference))} line items. Use reorder "
                "rate separately to judge repeat behavior."
            ),
        )

    with st.expander("Department data and download"):
        st.dataframe(
            department_frame,
            width="stretch",
            hide_index=True,
            column_config={
                "orders": st.column_config.NumberColumn(format="%d"),
                "total_items": st.column_config.NumberColumn(format="%d"),
                "unique_products": st.column_config.NumberColumn(format="%d"),
                "reorder_rate_pct": st.column_config.NumberColumn(format="%.1f%%"),
                "market_share_pct": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
        download_frame(
            department_frame,
            label="Download department aggregates",
            file_name="instacart-departments.csv",
            key="departments-download",
        )
