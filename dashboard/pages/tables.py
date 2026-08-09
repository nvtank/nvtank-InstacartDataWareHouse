"""Lazy, safe warehouse catalogue explorer."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.components import (
    format_decimal,
    format_integer,
    load_repository_data,
    page_header,
    require_columns,
)
from dashboard.data import AnalyticsRepository, TableMetadata


def _catalog_label(catalog: pd.DataFrame, table_name: str) -> str:
    row = catalog[catalog["table_name"] == table_name].iloc[0]
    return f"{table_name} · {row['kind']}"


def _render_metadata(metadata: TableMetadata) -> None:
    st.subheader(metadata.name)
    st.caption(f"{metadata.kind} · {metadata.description}")

    metric_left, metric_middle, metric_right = st.columns(3)
    with metric_left:
        st.metric(
            "Estimated rows",
            format_integer(metadata.row_count_estimate),
            help="Warehouse statistics estimate; it may differ from an exact count.",
        )
    with metric_middle:
        size_label = (
            f"{format_decimal(metadata.size_mb, 2)} MB"
            if metadata.size_mb is not None
            else "Not reported"
        )
        st.metric("Estimated storage", size_label)
    with metric_right:
        st.metric("Columns", format_integer(len(metadata.columns)))

    st.markdown("### Schema")
    if metadata.columns.empty:
        st.info("No column metadata is available for this table.")
    else:
        st.dataframe(
            metadata.columns,
            width="stretch",
            hide_index=True,
            column_config={
                "column_name": "Column",
                "data_type": "Data type",
                "nullable": st.column_config.CheckboxColumn("Nullable"),
                "default": "Default",
                "comment": "Comment",
            },
        )

    details_left, details_right = st.columns(2)
    with details_left:
        st.markdown("### Indexes")
        if metadata.indexes.empty:
            st.info("No secondary indexes are reported for this table.")
        else:
            st.dataframe(
                metadata.indexes,
                width="stretch",
                hide_index=True,
                column_config={
                    "index_name": "Index",
                    "columns": "Columns",
                    "unique": st.column_config.CheckboxColumn("Unique"),
                },
            )
    with details_right:
        st.markdown("### Partitions")
        if metadata.partitions.empty:
            st.info("This table has no reported partitions.")
        else:
            st.dataframe(
                metadata.partitions,
                width="stretch",
                hide_index=True,
                column_config={
                    "partition_name": "Partition",
                    "row_count_estimate": st.column_config.NumberColumn(
                        "Estimated rows",
                        format="%d",
                    ),
                    "size_mb": st.column_config.NumberColumn(
                        "Size (MB)",
                        format="%.2f",
                    ),
                    "comment": "Comment",
                },
            )


def show(repository: AnalyticsRepository) -> None:
    page_header(
        "Warehouse explorer",
        (
            "Inspect one whitelisted warehouse table at a time. Metadata is loaded "
            "after selection, and row samples run only when explicitly requested."
        ),
        eyebrow="Data architecture",
    )

    catalog = load_repository_data(
        repository,
        "table_catalog",
        loading_label="Loading warehouse catalogue…",
    )
    if not require_columns(
        catalog,
        ("table_name", "kind", "description", "row_count_estimate"),
        context="Warehouse catalogue",
    ):
        return

    st.subheader("Choose a table")
    selected_table = st.selectbox(
        "Warehouse table",
        catalog["table_name"].astype(str).tolist(),
        format_func=lambda name: _catalog_label(catalog, name),
        help="Only repository-whitelisted dimension and fact tables are available.",
    )
    metadata = load_repository_data(
        repository,
        "table_metadata",
        loading_label=f"Inspecting {selected_table} metadata…",
        table_name=selected_table,
    )
    if metadata is None:
        return
    _render_metadata(metadata)

    st.markdown("### Row sample")
    sample_rows = st.slider(
        "Rows to load",
        min_value=5,
        max_value=25,
        value=10,
        step=5,
        help="This limit is applied by the repository before data reaches the UI.",
    )
    load_sample = st.checkbox(
        f"Load a {sample_rows}-row sample from {selected_table}",
        value=False,
        key=f"table-sample-request-{selected_table}",
    )
    if load_sample:
        sample = load_repository_data(
            repository,
            "table_sample",
            loading_label=f"Loading a small sample from {selected_table}…",
            table_name=selected_table,
            limit=sample_rows,
        )
        if sample is not None:
            if sample.empty:
                st.info("This table returned no sample rows.")
            else:
                st.dataframe(sample, width="stretch", hide_index=True)
    else:
        st.caption("Sample query is paused until the checkbox is selected.")

    with st.expander("Full warehouse catalogue"):
        st.caption("Row counts in this catalogue are estimates when the source reports them.")
        st.dataframe(
            catalog,
            width="stretch",
            hide_index=True,
            column_config={
                "table_name": "Table",
                "kind": "Kind",
                "description": "Purpose",
                "row_count_estimate": st.column_config.NumberColumn(
                    "Estimated rows",
                    format="%d",
                ),
            },
        )
