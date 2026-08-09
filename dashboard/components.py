"""Reusable, accessible Streamlit components for analytics pages."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from html import escape
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.data import AnalyticsRepository, SourceMetadata

LOGGER = logging.getLogger(__name__)
PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}


def page_header(title: str, summary: str, *, eyebrow: str) -> None:
    """Render one semantic page heading and its concise purpose statement."""

    st.markdown(f'<p class="id-eyebrow">{escape(eyebrow)}</p>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(
        f'<p class="id-page-summary">{escape(summary)}</p>',
        unsafe_allow_html=True,
    )


def render_source_status(metadata: SourceMetadata) -> None:
    """Make demo/live provenance visible without exposing connection details."""

    badge_class = "live" if metadata.is_live else "demo"
    badge_label = "Live warehouse" if metadata.is_live else "Demo snapshot"
    safe_note = escape(metadata.dataset_note)
    st.markdown(
        (
            '<div class="id-source-row" role="status" aria-live="polite">'
            f'<span class="id-source-badge {badge_class}">'
            '<span class="id-source-dot" aria-hidden="true"></span>'
            f"{escape(badge_label)}</span>"
            f'<span class="id-source-note">{safe_note}</span>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    if metadata.fallback_reason:
        st.info(
            "The live warehouse did not pass its readiness check. "
            "This session is using deterministic representative aggregates."
        )


def source_cache_key(metadata: SourceMetadata) -> str:
    """Build a credential-free cache key that changes with repository health."""

    return "|".join(
        (
            metadata.mode,
            metadata.requested_mode,
            metadata.label,
            metadata.checked_at.isoformat(),
            str(metadata.healthy),
        )
    )


@st.cache_data(ttl=900, max_entries=128, show_spinner=False)
def _cached_repository_call(
    _repository: AnalyticsRepository,
    source_key: str,
    method_name: str,
    parameters: tuple[tuple[str, Any], ...],
) -> Any:
    del source_key  # Its value participates in Streamlit's cache key.
    method = getattr(_repository, method_name)
    return method(**dict(parameters))


def load_repository_data(
    repository: AnalyticsRepository,
    method_name: str,
    *,
    loading_label: str,
    **parameters: Any,
) -> Any | None:
    """Load cached repository data and present a sanitized failure state."""

    cache_parameters = tuple(sorted(parameters.items()))
    try:
        with st.spinner(loading_label):
            return _cached_repository_call(
                repository,
                source_cache_key(repository.source_metadata),
                method_name,
                cache_parameters,
            )
    except Exception:
        LOGGER.exception("Dashboard repository method %s failed", method_name)
        st.warning(
            "This view could not load from the selected data source. "
            "Retry the session or verify the warehouse readiness check."
        )
        return None


def clear_data_cache() -> None:
    """Clear only cached repository results, leaving the connection resource intact."""

    _cached_repository_call.clear()


def plotly_chart(figure: go.Figure, *, key: str) -> None:
    """Render a responsive chart with a stable identity and compact controls."""

    st.plotly_chart(
        figure,
        width="stretch",
        key=key,
        config=PLOTLY_CONFIG,
    )


def insight_card(title: str, body: str) -> None:
    """Render a short textual insight that remains useful without chart color."""

    st.markdown(
        (
            '<div class="id-insight">'
            f"<strong>{escape(title)}</strong>"
            f"<span>{escape(body)}</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def format_compact_number(value: Any) -> str:
    """Format large values for KPI cards without hiding their magnitude."""

    if value is None or pd.isna(value):
        return "—"
    number = float(value)
    absolute = abs(number)
    if absolute >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:,.0f}"


def format_integer(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{int(round(float(value))):,}"


def format_decimal(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.{digits}f}"


def format_percent(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}%"


def download_frame(
    frame: pd.DataFrame,
    *,
    label: str,
    file_name: str,
    key: str,
) -> None:
    """Offer the exact aggregate behind a chart as an accessible CSV fallback."""

    st.download_button(
        label,
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
        key=key,
    )


def require_columns(
    frame: pd.DataFrame | None,
    columns: Iterable[str],
    *,
    context: str,
) -> bool:
    """Guard page rendering against incomplete source contracts."""

    if frame is None:
        return False
    missing = [column for column in columns if column not in frame.columns]
    if frame.empty or missing:
        LOGGER.warning("Incomplete %s frame; missing=%s", context, missing)
        st.info(f"No {context.lower()} data is available for this snapshot.")
        return False
    return True
