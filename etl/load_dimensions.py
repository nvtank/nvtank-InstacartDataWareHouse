"""Stream validated Instacart dimensions into the warehouse."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from etl.config import Settings, get_engine, get_settings
from etl.quality import DataQualityError, require_source_files
from etl.transforms import transform_aisles, transform_departments, transform_products

DatabaseBind = Engine | Connection
FrameTransform = Callable[[pd.DataFrame], pd.DataFrame]


@contextmanager
def _transaction(bind: DatabaseBind) -> Iterator[Connection]:
    if isinstance(bind, Engine):
        with bind.begin() as connection:
            yield connection
        return
    yield bind


def _load_dimension(
    bind: DatabaseBind,
    *,
    source_path: Path,
    table_name: str,
    transform: FrameTransform,
    settings: Settings,
) -> int:
    loaded = 0
    with _transaction(bind) as connection:
        for source_chunk in pd.read_csv(source_path, chunksize=settings.chunk_size):
            dimension_chunk = transform(source_chunk)
            dimension_chunk.to_sql(
                table_name,
                connection,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=settings.batch_size,
            )
            loaded += len(dimension_chunk)

    if loaded == 0:
        raise DataQualityError(f"{source_path.name}: no dimension rows were loaded")
    return loaded


def load_dim_department(bind: DatabaseBind, settings: Settings | None = None) -> int:
    resolved = settings or get_settings()
    require_source_files(resolved.csv_files, ["departments"])
    return _load_dimension(
        bind,
        source_path=resolved.csv_files["departments"],
        table_name="Dim_Department",
        transform=transform_departments,
        settings=resolved,
    )


def load_dim_aisle(bind: DatabaseBind, settings: Settings | None = None) -> int:
    resolved = settings or get_settings()
    require_source_files(resolved.csv_files, ["aisles"])
    return _load_dimension(
        bind,
        source_path=resolved.csv_files["aisles"],
        table_name="Dim_Aisle",
        transform=transform_aisles,
        settings=resolved,
    )


def load_dim_product(bind: DatabaseBind, settings: Settings | None = None) -> int:
    resolved = settings or get_settings()
    require_source_files(resolved.csv_files, ["products"])
    return _load_dimension(
        bind,
        source_path=resolved.csv_files["products"],
        table_name="Dim_Product",
        transform=transform_products,
        settings=resolved,
    )


def _table_count(connection: Connection, table_name: str) -> int:
    allowed_tables = {"Dim_Department", "Dim_Aisle", "Dim_Product"}
    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported dimension table: {table_name}")
    return int(connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())


def main(settings: Settings | None = None, engine: Engine | None = None) -> int:
    """Load all dimensions atomically; exceptions deliberately propagate."""
    resolved = settings or get_settings()
    require_source_files(resolved.csv_files, ["departments", "aisles", "products"])
    warehouse_engine = engine or get_engine(resolved)

    print("ETL: loading dimension tables")
    with warehouse_engine.begin() as connection:
        loaded = {
            "Dim_Department": load_dim_department(connection, resolved),
            "Dim_Aisle": load_dim_aisle(connection, resolved),
            "Dim_Product": load_dim_product(connection, resolved),
        }

    with warehouse_engine.connect() as connection:
        for table_name, rows in loaded.items():
            total = _table_count(connection, table_name)
            print(f"  {table_name}: loaded {rows:,}; warehouse total {total:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
