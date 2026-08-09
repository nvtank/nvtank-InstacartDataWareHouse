import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from etl import etl_pipeline
from etl.etl_pipeline import PipelineError, StageReport
from etl.quality import WarehouseCheckResult


def scalar_result(value: int) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def test_check_schema_accepts_case_insensitive_names(monkeypatch: pytest.MonkeyPatch) -> None:
    inspector = MagicMock()
    inspector.get_table_names.return_value = [name.lower() for name in etl_pipeline.REQUIRED_TABLES]
    monkeypatch.setattr(etl_pipeline, "inspect", MagicMock(return_value=inspector))

    etl_pipeline.check_schema(MagicMock())


def test_check_schema_reports_every_missing_table(monkeypatch: pytest.MonkeyPatch) -> None:
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["Dim_Time"]
    monkeypatch.setattr(etl_pipeline, "inspect", MagicMock(return_value=inspector))

    with pytest.raises(PipelineError) as error:
        etl_pipeline.check_schema(MagicMock())

    assert "Dim_Department" in str(error.value)
    assert "Fact_Order_Details" in str(error.value)


def test_table_counts_uses_only_static_required_tables() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [
        scalar_result(index) for index, _ in enumerate(etl_pipeline.REQUIRED_TABLES, start=1)
    ]

    counts = etl_pipeline.table_counts(connection)

    assert counts == {
        table: index for index, table in enumerate(etl_pipeline.REQUIRED_TABLES, start=1)
    }
    assert connection.execute.call_count == len(etl_pipeline.REQUIRED_TABLES)


def test_empty_target_guard_accepts_empty_and_summarizes_populated_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_counts = {table: 0 for table in etl_pipeline.REQUIRED_TABLES}
    empty_counts["Dim_Time"] = 168
    monkeypatch.setattr(etl_pipeline, "table_counts", MagicMock(return_value=empty_counts))
    etl_pipeline.ensure_empty_load_target(MagicMock())

    populated_counts = empty_counts | {"Fact_Orders": 12, "Dim_Product": 3}
    monkeypatch.setattr(etl_pipeline, "table_counts", MagicMock(return_value=populated_counts))

    with pytest.raises(PipelineError) as error:
        etl_pipeline.ensure_empty_load_target(MagicMock())

    assert "Fact_Orders=12" in str(error.value)
    assert "Dim_Product=3" in str(error.value)
    assert "--reset-data --yes" in str(error.value)


def test_reset_load_data_disables_and_restores_foreign_key_checks() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value

    etl_pipeline.reset_load_data(engine)

    statements = [call.args[0] for call in connection.exec_driver_sql.call_args_list]
    assert statements[0] == "SET FOREIGN_KEY_CHECKS=0"
    assert statements[-1] == "SET FOREIGN_KEY_CHECKS=1"
    assert statements[1:-1] == [
        f"TRUNCATE TABLE {table}" for table in etl_pipeline.MUTABLE_TABLES
    ]


def test_reset_load_data_restores_foreign_keys_after_truncate_failure() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value

    def execute(statement: str) -> None:
        if statement.startswith("TRUNCATE"):
            raise RuntimeError("database unavailable")

    connection.exec_driver_sql.side_effect = execute

    with pytest.raises(RuntimeError, match="database unavailable"):
        etl_pipeline.reset_load_data(engine)

    connection.exec_driver_sql.assert_called_with("SET FOREIGN_KEY_CHECKS=1")


def test_timed_stage_returns_integer_rows_and_elapsed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(etl_pipeline.time, "perf_counter", MagicMock(side_effect=[5.0, 6.25]))

    report = etl_pipeline._timed_stage("fixture", lambda: 7)

    assert report == StageReport(name="fixture", rows=7, elapsed_seconds=1.25)


def test_run_pipeline_validate_only_skips_source_and_load_steps(
    monkeypatch: pytest.MonkeyPatch, settings_factory
) -> None:
    settings = settings_factory()
    engine = MagicMock()
    check = WarehouseCheckResult("time_dimension_rows", actual=168, expected=168)
    monkeypatch.setattr(etl_pipeline, "get_engine", MagicMock(return_value=engine))
    check_schema = MagicMock()
    monkeypatch.setattr(etl_pipeline, "check_schema", check_schema)
    warehouse_checks = MagicMock(return_value=(check,))
    monkeypatch.setattr(etl_pipeline, "run_warehouse_checks", warehouse_checks)
    monkeypatch.setattr(
        etl_pipeline,
        "table_counts",
        MagicMock(return_value={"Dim_Time": 168}),
    )
    source_check = MagicMock()
    monkeypatch.setattr(etl_pipeline, "require_source_files", source_check)

    stages, counts, checks = etl_pipeline.run_pipeline(settings, validate_only=True)

    assert stages == []
    assert counts == {"Dim_Time": 168}
    assert checks == [
        {"name": "time_dimension_rows", "actual": 168, "expected": 168, "passed": True}
    ]
    check_schema.assert_called_once_with(engine)
    source_check.assert_not_called()


def test_run_pipeline_orchestrates_all_stages_and_quality_gate(
    monkeypatch: pytest.MonkeyPatch, settings_factory
) -> None:
    settings = settings_factory()
    engine = MagicMock()
    dimension_connection = engine.begin.return_value.__enter__.return_value
    monkeypatch.setattr(etl_pipeline, "get_engine", MagicMock(return_value=engine))
    monkeypatch.setattr(etl_pipeline, "check_schema", MagicMock())
    monkeypatch.setattr(etl_pipeline, "require_source_files", MagicMock())
    reset = MagicMock()
    monkeypatch.setattr(etl_pipeline, "reset_load_data", reset)
    monkeypatch.setattr(etl_pipeline, "ensure_empty_load_target", MagicMock())
    department_load = MagicMock(return_value=2)
    aisle_load = MagicMock(return_value=3)
    product_load = MagicMock(return_value=4)
    order_load = MagicMock(return_value=5)
    detail_load = MagicMock(return_value=6)
    monkeypatch.setattr(etl_pipeline.load_dimensions, "load_dim_department", department_load)
    monkeypatch.setattr(etl_pipeline.load_dimensions, "load_dim_aisle", aisle_load)
    monkeypatch.setattr(etl_pipeline.load_dimensions, "load_dim_product", product_load)
    monkeypatch.setattr(etl_pipeline.load_facts, "load_fact_orders", order_load)
    monkeypatch.setattr(etl_pipeline.load_facts, "load_fact_order_details", detail_load)
    monkeypatch.setattr(
        etl_pipeline,
        "update_all_metrics",
        MagicMock(
            return_value=SimpleNamespace(
                orders_updated=5,
                users_upserted=2,
                elapsed_seconds=0.5,
            )
        ),
    )
    check = WarehouseCheckResult("duplicate_orders", actual=0, expected=0)
    monkeypatch.setattr(etl_pipeline, "run_warehouse_checks", MagicMock(return_value=(check,)))
    monkeypatch.setattr(
        etl_pipeline,
        "table_counts",
        MagicMock(return_value={"Fact_Orders": 5, "Fact_Order_Details": 6}),
    )

    stages, counts, checks = etl_pipeline.run_pipeline(settings, reset_data=True)

    assert [(stage.name, stage.rows) for stage in stages] == [
        ("dimensions", 9),
        ("orders", 5),
        ("order_details", 6),
        ("derived_metrics", 7),
    ]
    assert counts == {"Fact_Orders": 5, "Fact_Order_Details": 6}
    assert checks[0]["passed"] is True
    reset.assert_called_once_with(engine)
    department_load.assert_called_once_with(dimension_connection, settings)
    order_load.assert_called_once_with(engine, settings)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--reset-data"],
        ["--reset-data", "--yes", "--validate-only"],
    ],
)
def test_cli_rejects_unsafe_argument_combinations(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        etl_pipeline.cli(arguments)

    assert error.value.code == 2


def test_cli_dry_run_checks_files_without_connecting(
    monkeypatch: pytest.MonkeyPatch, settings_factory, capsys
) -> None:
    settings = settings_factory(db_password="must-not-print")
    settings.data_path.mkdir()
    for path in settings.csv_files.values():
        path.touch()
    monkeypatch.setattr(etl_pipeline, "get_settings", MagicMock(return_value=settings))
    pipeline = MagicMock()
    monkeypatch.setattr(etl_pipeline, "run_pipeline", pipeline)

    exit_code = etl_pipeline.cli(["--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "All required source files are present" in output
    assert "must-not-print" not in output
    assert "***" in output
    pipeline.assert_not_called()


def test_cli_writes_deterministic_success_report(
    monkeypatch: pytest.MonkeyPatch, settings_factory, tmp_path: Path
) -> None:
    settings = settings_factory(db_password="must-not-leak")
    report_path = tmp_path / "reports" / "success.json"
    stage = StageReport("orders", rows=2, elapsed_seconds=0.25)
    monkeypatch.setattr(etl_pipeline, "get_settings", MagicMock(return_value=settings))
    monkeypatch.setattr(
        etl_pipeline,
        "run_pipeline",
        MagicMock(
            return_value=(
                [stage],
                {"Fact_Orders": 2},
                [{"name": "duplicate_orders", "actual": 0, "expected": 0, "passed": True}],
            )
        ),
    )
    monkeypatch.setattr(
        etl_pipeline.uuid,
        "uuid4",
        MagicMock(return_value=uuid.UUID("00000000-0000-0000-0000-000000000042")),
    )
    monkeypatch.setattr(
        etl_pipeline,
        "_utc_now",
        MagicMock(side_effect=["2026-08-06T00:00:00+00:00", "2026-08-06T00:00:02+00:00"]),
    )
    monkeypatch.setattr(
        etl_pipeline.time,
        "perf_counter",
        MagicMock(side_effect=[100.0, 102.345]),
    )

    exit_code = etl_pipeline.cli(["--report", str(report_path)])
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "succeeded"
    assert payload["run_id"] == "00000000-0000-0000-0000-000000000042"
    assert payload["elapsed_seconds"] == 2.345
    assert payload["stages"] == [{"name": "orders", "rows": 2, "elapsed_seconds": 0.25}]
    assert payload["table_counts"] == {"Fact_Orders": 2}
    assert "must-not-leak" not in report_path.read_text(encoding="utf-8")


def test_cli_converts_pipeline_failure_to_nonzero_report(
    monkeypatch: pytest.MonkeyPatch, settings_factory, tmp_path: Path, capsys
) -> None:
    settings = settings_factory()
    report_path = tmp_path / "failure.json"
    monkeypatch.setattr(etl_pipeline, "get_settings", MagicMock(return_value=settings))
    monkeypatch.setattr(
        etl_pipeline,
        "run_pipeline",
        MagicMock(side_effect=PipelineError("fixture warehouse is invalid")),
    )

    exit_code = etl_pipeline.cli(["--validate-only", "--report", str(report_path)])
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["mode"] == "validate"
    assert payload["error_type"] == "PipelineError"
    assert payload["error"] == "fixture warehouse is invalid"
    assert "ETL failed: PipelineError" in capsys.readouterr().err
