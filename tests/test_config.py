from pathlib import Path
from unittest.mock import MagicMock

import pytest

from etl import config
from etl.config import ConfigurationError, Settings


def test_settings_defaults_are_normalized_and_repo_relative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    settings = Settings.from_env({"DB_PASSWORD": "secret"})

    assert settings.db_host == "localhost"
    assert settings.db_port == 3307
    assert settings.db_user == "instacart"
    assert settings.data_path == (tmp_path / "data").resolve()
    assert settings.dashboard_mode == "auto"
    assert settings.batch_size == 1_000
    assert settings.chunk_size == 50_000


def test_settings_reads_explicit_values_and_builds_csv_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    environment = {
        "DB_HOST": "  db.internal  ",
        "DB_PORT": "4406",
        "DB_USER": "  analyst  ",
        "DB_PASSWORD": "p@ss:/word",
        "DB_NAME": "  warehouse  ",
        "DATA_PATH": "fixtures/source",
        "BATCH_SIZE": "25",
        "CHUNK_SIZE": "250",
        "DASHBOARD_MODE": " LIVE ",
        "DASHBOARD_CACHE_TTL": "90",
        "MINING_RANDOM_STATE": "7",
        "MINING_ORDER_LIMIT": "500",
    }

    settings = Settings.from_env(environment)

    assert settings.db_host == "db.internal"
    assert settings.db_port == 4406
    assert settings.dashboard_mode == "live"
    assert settings.mining_random_state == 7
    assert settings.csv_files["orders"] == tmp_path / "fixtures/source/orders.csv"
    assert settings.database_url.password == "p@ss:/word"
    assert settings.database_url.drivername == "mysql+pymysql"
    assert "p@ss:/word" not in settings.safe_summary()
    assert "***" in settings.safe_summary()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("DB_PORT", "not-a-number", "must be an integer"),
        ("BATCH_SIZE", "0", "must be greater than zero"),
        ("CHUNK_SIZE", "-1", "must be greater than zero"),
    ],
)
def test_settings_rejects_invalid_positive_integers(name: str, value: str, message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        Settings.from_env({name: value})


def test_settings_rejects_unknown_dashboard_mode() -> None:
    with pytest.raises(ConfigurationError, match="DASHBOARD_MODE must be one of"):
        Settings.from_env({"DASHBOARD_MODE": "sometimes"})


def test_validate_database_lists_missing_required_values(settings_factory) -> None:
    settings = settings_factory(db_host="", db_password="", db_name="")

    with pytest.raises(ConfigurationError) as error:
        settings.validate_database()

    assert "DB_HOST" in str(error.value)
    assert "DB_PASSWORD" in str(error.value)
    assert "DB_NAME" in str(error.value)


def test_missing_source_files_reports_only_absent_files(settings_factory) -> None:
    settings = settings_factory()
    settings.data_path.mkdir()
    settings.csv_files["orders"].touch()

    missing = settings.missing_source_files()

    assert settings.csv_files["orders"] not in missing
    assert set(missing) == set(settings.csv_files.values()) - {settings.csv_files["orders"]}


def test_get_engine_validates_settings_and_uses_safe_sqlalchemy_url(
    monkeypatch: pytest.MonkeyPatch, settings_factory
) -> None:
    settings = settings_factory(db_password="p@ss:/word")
    created_engine = object()
    create_engine = MagicMock(return_value=created_engine)
    monkeypatch.setattr(config, "create_engine", create_engine)

    result = config.get_engine(settings)

    assert result is created_engine
    url = create_engine.call_args.args[0]
    assert url.password == "p@ss:/word"
    create_engine.assert_called_once_with(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def test_database_healthcheck_returns_version_without_exposing_exceptions() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = "11.4.5-MariaDB"

    assert config.database_healthcheck(engine) == (True, "11.4.5-MariaDB")

    engine.connect.side_effect = RuntimeError("password=do-not-leak")
    assert config.database_healthcheck(engine) == (False, "RuntimeError")


def test_settings_cache_can_be_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    config.reset_settings_cache()
    monkeypatch.setenv("DB_HOST", "cached-host")
    first = config.get_settings()
    monkeypatch.setenv("DB_HOST", "new-host")

    assert config.get_settings() is first
    assert config.get_settings().db_host == "cached-host"

    config.reset_settings_cache()
    assert config.get_settings().db_host == "new-host"
    config.reset_settings_cache()
