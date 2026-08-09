"""Instacart Decision Intelligence Streamlit entry point."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Instacart Decision Intelligence",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "Instacart Decision Intelligence explores a batch-loaded public "
            "market-basket dataset through a reproducible analytics contract."
        )
    },
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components import clear_data_cache, render_source_status
from dashboard.data import (
    AnalyticsRepository,
    RepositoryConfigurationError,
    RepositoryUnavailableError,
    create_repository,
)
from dashboard.pages import customers, departments, overview, products, tables, time_analysis
from dashboard.styles import inject_global_styles
from etl.config import ConfigurationError, get_settings

PageRenderer = Callable[[AnalyticsRepository], None]
PAGES: dict[str, PageRenderer] = {
    "Executive overview": overview.show,
    "Products & aisles": products.show,
    "Shopping rhythm": time_analysis.show,
    "Customer segments": customers.show,
    "Departments": departments.show,
    "Warehouse explorer": tables.show,
}


@st.cache_resource(show_spinner=False)
def initialize_repository() -> AnalyticsRepository:
    """Create one checked repository resource for the Streamlit server process."""

    return create_repository(get_settings())


def render_sidebar(repository: AnalyticsRepository) -> str:
    st.sidebar.title("Instacart Intelligence")
    st.sidebar.caption("Decision cockpit · warehouse snapshot")
    st.sidebar.divider()
    selected_page = st.sidebar.radio(
        "Analysis workspace",
        tuple(PAGES),
        index=0,
    )
    st.sidebar.divider()
    metadata = repository.source_metadata
    st.sidebar.markdown("**Data source**")
    st.sidebar.caption(
        "Live MariaDB warehouse" if metadata.is_live else "Representative demo snapshot"
    )
    st.sidebar.caption(f"Source policy: {metadata.requested_mode.upper()}")
    if st.sidebar.button("Refresh snapshot", width="stretch"):
        clear_data_cache()
        initialize_repository.clear()
        st.rerun()
    st.sidebar.caption(
        "Instacart's source data contains day-of-week and hour fields, not calendar dates."
    )
    return selected_page


def main() -> None:
    inject_global_styles()
    try:
        repository = initialize_repository()
    except (ConfigurationError, RepositoryConfigurationError):
        st.error(
            "Dashboard configuration is invalid. Check DASHBOARD_MODE and the "
            "documented environment variables, then restart the app."
        )
        st.stop()
    except RepositoryUnavailableError:
        st.error(
            "Live mode was requested, but the warehouse did not pass its readiness "
            "check. Use DASHBOARD_MODE=auto for safe demo fallback or repair the "
            "database connection."
        )
        st.stop()
    except Exception:
        st.error(
            "The analytics source could not be initialized. No credentials or raw "
            "connection details are displayed in this interface."
        )
        st.stop()

    selected_page = render_sidebar(repository)
    render_source_status(repository.source_metadata)
    PAGES[selected_page](repository)
    st.divider()
    st.caption(
        "Instacart Decision Intelligence · aggregate analytics over an anonymized "
        "public market-basket dataset."
    )


if __name__ == "__main__":
    main()
