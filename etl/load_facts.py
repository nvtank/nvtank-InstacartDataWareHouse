"""Stream validated Instacart order facts into the warehouse."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from etl.config import Settings, get_engine, get_settings
from etl.quality import DataQualityError, require_resolved_detail_times, require_source_files
from etl.transforms import transform_order_details, transform_orders

DatabaseBind = Engine | Connection
DETAIL_PARTITIONS = ("p0", "p1", "p2", "p3", "p4", "p5", "p6", "p_max")


@contextmanager
def _connection(bind: DatabaseBind) -> Iterator[Connection]:
    if isinstance(bind, Engine):
        with bind.connect() as connection:
            yield connection
        return
    yield bind


@contextmanager
def _chunk_transaction(connection: Connection) -> Iterator[None]:
    """Commit one bounded chunk unless the caller already owns a transaction."""
    if connection.in_transaction():
        yield
        return
    with connection.begin():
        yield


def _append_chunk(
    connection: Connection,
    frame: pd.DataFrame,
    *,
    table_name: str,
    batch_size: int,
) -> None:
    if frame.empty:
        return
    with _chunk_transaction(connection):
        frame.to_sql(
            table_name,
            connection,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=batch_size,
        )


def load_fact_orders(bind: DatabaseBind, settings: Settings | None = None) -> int:
    """Stream orders.csv without materializing the full source in memory."""
    resolved = settings or get_settings()
    require_source_files(resolved.csv_files, ["orders"])
    loaded = 0
    source_rows = 0

    with _connection(bind) as connection:
        for source_chunk in pd.read_csv(
            resolved.csv_files["orders"], chunksize=resolved.chunk_size
        ):
            source_rows += len(source_chunk)
            fact_chunk = transform_orders(source_chunk)
            _append_chunk(
                connection,
                fact_chunk,
                table_name="Fact_Orders",
                batch_size=resolved.batch_size,
            )
            loaded += len(fact_chunk)

    if source_rows == 0:
        raise DataQualityError("orders.csv: source contains no rows")
    if loaded == 0:
        raise DataQualityError("orders.csv: no prior/train orders were loaded")
    return loaded


def resolve_detail_time_ids(
    connection: Connection,
    partitions: tuple[str, ...] = DETAIL_PARTITIONS,
) -> int:
    """Resolve nullable detail time keys from Fact_Orders and verify completeness."""
    unknown = [partition for partition in partitions if partition not in DETAIL_PARTITIONS]
    if unknown:
        raise ValueError(f"Unsupported Fact_Order_Details partitions: {', '.join(unknown)}")

    updated = 0
    for partition in partitions:
        with _chunk_transaction(connection):
            result = connection.execute(
                text(
                    f"""
                    UPDATE Fact_Order_Details PARTITION ({partition}) fod
                    JOIN Fact_Orders fo ON fod.order_id = fo.order_id
                    SET fod.time_id = fo.time_id
                    WHERE fod.time_id IS NULL OR fod.time_id <> fo.time_id
                    """
                )
            )
            if result.rowcount > 0:
                updated += result.rowcount

    require_resolved_detail_times(connection)
    return updated


def load_fact_order_details(bind: DatabaseBind, settings: Settings | None = None) -> int:
    """Stream both order-product sources, then reconcile their nullable time keys."""
    resolved = settings or get_settings()
    source_keys = ["order_products_prior", "order_products_train"]
    require_source_files(resolved.csv_files, source_keys)
    loaded = 0

    with _connection(bind) as connection:
        for source_key in source_keys:
            source_path = resolved.csv_files[source_key]
            file_rows = 0
            for source_chunk in pd.read_csv(source_path, chunksize=resolved.chunk_size):
                detail_chunk = transform_order_details(source_chunk, dataset=source_key)
                _append_chunk(
                    connection,
                    detail_chunk,
                    table_name="Fact_Order_Details",
                    batch_size=resolved.batch_size,
                )
                file_rows += len(detail_chunk)
                loaded += len(detail_chunk)
            if file_rows == 0:
                raise DataQualityError(f"{source_path.name}: source contains no rows")

        resolved_rows = resolve_detail_time_ids(connection)
        print(f"  Fact_Order_Details: resolved {resolved_rows:,} nullable time keys")

    return loaded


def _table_count(connection: Connection, table_name: str) -> int:
    allowed_tables = {"Fact_Orders", "Fact_Order_Details"}
    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported fact table: {table_name}")
    return int(connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())


def main(settings: Settings | None = None, engine: Engine | None = None) -> int:
    """Load facts with bounded chunk transactions; exceptions deliberately propagate."""
    resolved = settings or get_settings()
    require_source_files(
        resolved.csv_files,
        ["orders", "order_products_prior", "order_products_train"],
    )
    warehouse_engine = engine or get_engine(resolved)

    print("ETL: loading fact tables")
    with warehouse_engine.connect() as connection:
        orders_loaded = load_fact_orders(connection, resolved)
        details_loaded = load_fact_order_details(connection, resolved)

    with warehouse_engine.connect() as connection:
        print(
            f"  Fact_Orders: loaded {orders_loaded:,}; "
            f"warehouse total {_table_count(connection, 'Fact_Orders'):,}"
        )
        print(
            f"  Fact_Order_Details: loaded {details_loaded:,}; "
            f"warehouse total {_table_count(connection, 'Fact_Order_Details'):,}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
