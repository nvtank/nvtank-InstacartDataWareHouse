"""Clear Streamlit's local data and resource caches."""

from __future__ import annotations

import streamlit as st


def clear_all_caches() -> None:
    """Clear both cache stores and report the completed action."""

    st.cache_data.clear()
    st.cache_resource.clear()
    print("Streamlit data and resource caches cleared.")


if __name__ == "__main__":
    clear_all_caches()
