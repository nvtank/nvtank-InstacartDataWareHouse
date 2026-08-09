from collections.abc import Callable
from pathlib import Path

import pytest

from etl.config import Settings


@pytest.fixture
def settings_factory(tmp_path: Path) -> Callable[..., Settings]:
    def build_settings(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "db_host": "database.test",
            "db_port": 3307,
            "db_user": "instacart",
            "db_password": "local-password",
            "db_name": "instacart_dwh",
            "data_path": tmp_path / "data",
            "batch_size": 100,
            "chunk_size": 10,
            "dashboard_mode": "demo",
            "dashboard_cache_ttl": 60,
            "mining_random_state": 42,
            "mining_order_limit": 1_000,
        }
        values.update(overrides)
        return Settings(**values)

    return build_settings
