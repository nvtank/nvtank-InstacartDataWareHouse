"""Fail-fast command line orchestrator for the Instacart warehouse load."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from . import load_dimensions, load_facts
from .config import PROJECT_ROOT, Settings, get_engine, get_settings
from .quality import require_source_files, run_warehouse_checks
from .update_fact_metrics import update_all_metrics

REQUIRED_TABLES = (
    "Dim_Time",
    "Dim_Department",
    "Dim_Aisle",
    "Dim_Product",
    "Dim_User",
    "Fact_Orders",
    "Fact_Order_Details",
)
MUTABLE_TABLES = (
    "Fact_Order_Details",
    "Fact_Orders",
    "Dim_User",
    "Dim_Product",
    "Dim_Aisle",
    "Dim_Department",
)
DEFAULT_REPORT_PATH = PROJECT_ROOT / "artifacts" / "etl" / "latest.json"


class PipelineError(RuntimeError):
    """Raised for an unsafe or incomplete ETL precondition."""


@dataclass(frozen=True, slots=True)
class StageReport:
    name: str
    rows: int
    elapsed_seconds: float


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def check_schema(engine: Engine) -> None:
    discovered = {name.casefold(): name for name in inspect(engine).get_table_names()}
    missing = [table for table in REQUIRED_TABLES if table.casefold() not in discovered]
    if missing:
        raise PipelineError(
            f"Missing warehouse tables: {', '.join(missing)}. Run `make schema` first."
        )


def table_counts(bind: Engine | Connection) -> dict[str, int]:
    owns_connection = isinstance(bind, Engine)
    connection = bind.connect() if owns_connection else bind
    try:
        return {
            table: int(connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
            for table in REQUIRED_TABLES
        }
    finally:
        if owns_connection:
            connection.close()


def ensure_empty_load_target(engine: Engine) -> None:
    populated = {
        table: count
        for table, count in table_counts(engine).items()
        if table in MUTABLE_TABLES and count > 0
    }
    if populated:
        summary = ", ".join(f"{table}={count:,}" for table, count in populated.items())
        raise PipelineError(
            "Warehouse already contains load data "
            f"({summary}). Refusing to append duplicate facts; use --reset-data --yes explicitly."
        )


def reset_load_data(engine: Engine) -> None:
    """Clear only ETL-owned rows; Dim_Time and the database itself are preserved."""
    with engine.connect() as connection:
        connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        try:
            for table in MUTABLE_TABLES:
                connection.exec_driver_sql(f"TRUNCATE TABLE {table}")
        finally:
            connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")


def _timed_stage(name: str, operation: Any) -> StageReport:
    started = time.perf_counter()
    rows = int(operation())
    result = StageReport(name=name, rows=rows, elapsed_seconds=time.perf_counter() - started)
    print(f"[{name}] {rows:,} rows in {result.elapsed_seconds:.1f}s")
    return result


def run_pipeline(
    settings: Settings,
    *,
    reset_data: bool = False,
    validate_only: bool = False,
) -> tuple[list[StageReport], dict[str, int], list[dict[str, Any]]]:
    engine = get_engine(settings)
    check_schema(engine)

    if validate_only:
        checks = run_warehouse_checks(engine)
        return [], table_counts(engine), [asdict(check) | {"passed": check.passed} for check in checks]

    require_source_files(settings.csv_files, settings.csv_files.keys())
    if reset_data:
        reset_load_data(engine)
    ensure_empty_load_target(engine)

    stages: list[StageReport] = []

    def load_all_dimensions() -> int:
        with engine.begin() as connection:
            return sum(
                (
                    load_dimensions.load_dim_department(connection, settings),
                    load_dimensions.load_dim_aisle(connection, settings),
                    load_dimensions.load_dim_product(connection, settings),
                )
            )

    stages.append(_timed_stage("dimensions", load_all_dimensions))
    stages.append(
        _timed_stage("orders", lambda: load_facts.load_fact_orders(engine, settings))
    )
    stages.append(
        _timed_stage(
            "order_details", lambda: load_facts.load_fact_order_details(engine, settings)
        )
    )

    metric_result = update_all_metrics(engine)
    stages.append(
        StageReport(
            name="derived_metrics",
            rows=metric_result.orders_updated + metric_result.users_upserted,
            elapsed_seconds=metric_result.elapsed_seconds,
        )
    )
    print(
        "[derived_metrics] "
        f"{metric_result.orders_updated:,} order rows and "
        f"{metric_result.users_upserted:,} user rows affected "
        f"in {metric_result.elapsed_seconds:.1f}s"
    )

    checks = run_warehouse_checks(engine)
    quality_results = [asdict(check) | {"passed": check.passed} for check in checks]
    return stages, table_counts(engine), quality_results


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load, reconcile, and validate the Instacart MariaDB warehouse."
    )
    parser.add_argument(
        "--reset-data",
        action="store_true",
        help="truncate ETL-owned tables before loading (requires --yes)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm the destructive --reset-data operation",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="run warehouse contracts without loading source files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate configuration and source-file presence without connecting",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="machine-readable ETL report path",
    )
    return parser


def cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.reset_data and not args.yes:
        parser.error("--reset-data is destructive and requires --yes")
    if args.reset_data and args.validate_only:
        parser.error("--reset-data cannot be combined with --validate-only")

    settings = get_settings()
    if args.dry_run:
        require_source_files(settings.csv_files, settings.csv_files.keys())
        print(f"Configuration valid: {settings.safe_summary()}")
        print("All required source files are present.")
        return 0

    run_id = str(uuid.uuid4())
    started_at = _utc_now()
    started = time.perf_counter()
    payload: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at,
        "configuration": settings.safe_summary(),
        "mode": "validate" if args.validate_only else "load",
    }

    try:
        stages, counts, checks = run_pipeline(
            settings,
            reset_data=args.reset_data,
            validate_only=args.validate_only,
        )
        payload.update(
            {
                "status": "succeeded",
                "stages": [asdict(stage) for stage in stages],
                "table_counts": counts,
                "quality_checks": checks,
            }
        )
        exit_code = 0
    except Exception as exc:  # CLI boundary: report failure, then return non-zero.
        payload.update(
            {
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            }
        )
        print(f"ETL failed: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        exit_code = 1

    payload["finished_at"] = _utc_now()
    payload["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    _write_report(args.report, payload)
    print(f"ETL report: {args.report}")
    return exit_code


def main() -> int:
    return cli()


if __name__ == "__main__":
    raise SystemExit(cli())
