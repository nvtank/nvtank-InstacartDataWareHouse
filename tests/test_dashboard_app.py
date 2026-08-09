from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from etl.config import reset_settings_cache

EXPECTED_PAGES = {
    "Executive overview": "Executive overview",
    "Products & aisles": "Products & aisles",
    "Shopping rhythm": "Shopping rhythm",
    "Customer segments": "Customer segments",
    "Departments": "Department performance",
    "Warehouse explorer": "Warehouse explorer",
}


def test_demo_app_navigates_all_six_pages_without_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_MODE", "demo")
    reset_settings_cache()
    app_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"

    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    assert len(app.exception) == 0
    assert len(app.error) == 0
    assert app.sidebar.radio[0].label == "Analysis workspace"
    assert app.sidebar.radio[0].options == list(EXPECTED_PAGES)

    for navigation_label, page_title in EXPECTED_PAGES.items():
        app.sidebar.radio[0].set_value(navigation_label)
        app.run()

        assert len(app.exception) == 0, [exception.value for exception in app.exception]
        assert len(app.error) == 0, [error.value for error in app.error]
        assert page_title in [title.value for title in app.title]
        assert app.sidebar.radio[0].value == navigation_label

    reset_settings_cache()


def test_demo_app_identifies_the_source_without_live_database_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_MODE", "demo")
    reset_settings_cache()
    app_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"

    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    assert len(app.exception) == 0
    assert len(app.error) == 0
    assert any("Demo snapshot" in markdown.value for markdown in app.markdown)
    assert any("Representative demo snapshot" in caption.value for caption in app.sidebar.caption)
    reset_settings_cache()
