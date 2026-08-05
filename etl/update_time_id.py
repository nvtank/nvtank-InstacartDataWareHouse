"""Recovery CLI for reconciling nullable detail time keys."""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from .config import get_engine
from .load_facts import DETAIL_PARTITIONS
from .load_facts import resolve_detail_time_ids as _resolve_detail_time_ids


@dataclass(frozen=True, slots=True)
class TimeResolutionResult:
    rows_updated: int
    partitions_processed: int
    elapsed_seconds: float


def resolve_detail_time_ids(engine: Engine) -> TimeResolutionResult:
    """Delegate to the ETL resolver so load and recovery use one invariant."""
    started = time.perf_counter()
    with engine.connect() as connection:
        rows_updated = _resolve_detail_time_ids(connection)
    return TimeResolutionResult(
        rows_updated=rows_updated,
        partitions_processed=len(DETAIL_PARTITIONS),
        elapsed_seconds=time.perf_counter() - started,
    )


def main() -> int:
    result = resolve_detail_time_ids(get_engine())
    print(
        f"Resolved {result.rows_updated:,} rows across {result.partitions_processed} "
        f"partitions in {result.elapsed_seconds:.1f}s."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
