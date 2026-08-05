"""Stable artifact paths and serialization helpers for mining jobs."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

MINING_ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = MINING_ROOT / "results"


def ensure_results_dir(path: Path | str | None = None) -> Path:
    output_dir = Path(path) if path is not None else DEFAULT_RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def itemset_to_json(items: Iterable[object]) -> str:
    """Serialize an itemset without ambiguous comma-delimited parsing."""
    normalized = sorted((str(item) for item in items), key=str.casefold)
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def itemset_from_json(value: str) -> frozenset[str]:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid itemset JSON: {value!r}") from exc
    if not isinstance(decoded, list) or not all(
        isinstance(item, str) or (isinstance(item, int) and not isinstance(item, bool))
        for item in decoded
    ):
        raise ValueError("Itemset JSON must be an array of string or integer identifiers")
    return frozenset(str(item) for item in decoded)


def write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def dump_joblib(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(value, path)
    return path
