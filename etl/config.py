"""Typed, environment-driven configuration shared by every project component."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

SOURCE_FILES: Mapping[str, str] = {
    "aisles": "aisles.csv",
    "departments": "departments.csv",
    "products": "products.csv",
    "orders": "orders.csv",
    "order_products_prior": "order_products__prior.csv",
    "order_products_train": "order_products__train.csv",
}
VALID_DASHBOARD_MODES = frozenset({"auto", "live", "demo"})


class ConfigurationError(ValueError):
    """Raised when environment configuration is invalid or incomplete."""


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environment.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, received {raw_value!r}") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings loaded from environment variables."""

    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    data_path: Path
    batch_size: int
    chunk_size: int
    dashboard_mode: str
    dashboard_cache_ttl: int
    mining_random_state: int
    mining_order_limit: int

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environment is None else environment
        dashboard_mode = env.get("DASHBOARD_MODE", "auto").strip().lower()
        if dashboard_mode not in VALID_DASHBOARD_MODES:
            allowed = ", ".join(sorted(VALID_DASHBOARD_MODES))
            raise ConfigurationError(f"DASHBOARD_MODE must be one of: {allowed}")

        return cls(
            db_host=env.get("DB_HOST", "localhost").strip(),
            db_port=_positive_int(env, "DB_PORT", 3307),
            db_user=env.get("DB_USER", "instacart").strip(),
            db_password=env.get("DB_PASSWORD", ""),
            db_name=env.get("DB_NAME", "instacart_dwh").strip(),
            data_path=_resolve_path(env.get("DATA_PATH", "data")),
            batch_size=_positive_int(env, "BATCH_SIZE", 1000),
            chunk_size=_positive_int(env, "CHUNK_SIZE", 50_000),
            dashboard_mode=dashboard_mode,
            dashboard_cache_ttl=_positive_int(env, "DASHBOARD_CACHE_TTL", 3600),
            mining_random_state=int(env.get("MINING_RANDOM_STATE", "42")),
            mining_order_limit=_positive_int(env, "MINING_ORDER_LIMIT", 100_000),
        )

    @property
    def csv_files(self) -> dict[str, Path]:
        return {key: self.data_path / filename for key, filename in SOURCE_FILES.items()}

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )

    def validate_database(self) -> None:
        missing = [
            name
            for name, value in {
                "DB_HOST": self.db_host,
                "DB_USER": self.db_user,
                "DB_PASSWORD": self.db_password,
                "DB_NAME": self.db_name,
            }.items()
            if not value
        ]
        if missing:
            raise ConfigurationError(
                f"Missing database configuration: {', '.join(missing)}. "
                "Copy .env.example to .env and set local credentials."
            )

    def missing_source_files(self) -> list[Path]:
        return [path for path in self.csv_files.values() if not path.is_file()]

    def safe_summary(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:***@{self.db_host}:{self.db_port}/{self.db_name} "
            f"(data={self.data_path})"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def reset_settings_cache() -> None:
    """Clear cached settings; primarily useful for tests and local tooling."""
    get_settings.cache_clear()


def get_engine(settings: Settings | None = None) -> Engine:
    """Create a pooled SQLAlchemy engine without interpolating credentials."""
    resolved = settings or get_settings()
    resolved.validate_database()
    return create_engine(
        resolved.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def database_healthcheck(engine: Engine) -> tuple[bool, str]:
    """Return a safe connection status for CLIs and the dashboard."""
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT VERSION()"))
            return True, str(version.scalar_one())
    except Exception as exc:  # Boundary: convert driver failures to a UI-safe status.
        return False, exc.__class__.__name__


# Compatibility exports for the original scripts while they migrate to Settings.
_SETTINGS = get_settings()
DB_CONFIG = {
    "host": _SETTINGS.db_host,
    "port": _SETTINGS.db_port,
    "user": _SETTINGS.db_user,
    "password": _SETTINGS.db_password,
    "database": _SETTINGS.db_name,
}
DATA_PATH = str(_SETTINGS.data_path)
CSV_FILES = {key: str(path) for key, path in _SETTINGS.csv_files.items()}
BATCH_SIZE = _SETTINGS.batch_size
CHUNK_SIZE = _SETTINGS.chunk_size


if __name__ == "__main__":
    settings = get_settings()
    print(f"Configuration: {settings.safe_summary()}")
    engine = get_engine(settings)
    healthy, detail = database_healthcheck(engine)
    print(f"Database: {'connected' if healthy else 'unavailable'} ({detail})")
