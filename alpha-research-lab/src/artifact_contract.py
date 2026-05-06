from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def atomic_write_parquet(df: pd.DataFrame, path: str | Path) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    df.to_parquet(tmp_path, index=False)
    os.replace(tmp_path, out_path)


def atomic_write_json(obj: Mapping[str, Any], path: str | Path) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    body = json.dumps(obj, default=_json_default, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp_path.write_text(body, encoding="utf-8")
    os.replace(tmp_path, out_path)


def validate_required_columns(
    df: pd.DataFrame,
    required_cols: Iterable[str],
    artifact_name: str,
) -> None:
    required = [str(col) for col in required_cols]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{artifact_name} is missing required columns: {missing}")


def validate_unique_keys(
    df: pd.DataFrame,
    key_cols: Sequence[str],
    artifact_name: str,
) -> None:
    keys = [str(col) for col in key_cols]
    validate_required_columns(df, keys, artifact_name)
    duplicate_count = int(df.duplicated(keys).sum())
    if duplicate_count:
        examples = df.loc[df.duplicated(keys, keep=False), keys].head(5).to_dict(orient="records")
        raise ValueError(
            f"{artifact_name} has {duplicate_count:,} duplicate key rows for {keys}; "
            f"examples={examples}"
        )


def _fingerprint_path(path_like: str | Path) -> dict[str, object]:
    path = Path(path_like)
    record: dict[str, object] = {
        "type": "path",
        "path": str(path),
        "exists": path.exists(),
    }
    if path.exists():
        stat = path.stat()
        record.update(
            {
                "is_dir": path.is_dir(),
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        )
    return record


def _fingerprint_value(value: object) -> object:
    if isinstance(value, Path):
        return _fingerprint_path(value)
    if isinstance(value, str):
        candidate = Path(value)
        if candidate.exists():
            return _fingerprint_path(candidate)
        return value
    if isinstance(value, Mapping):
        return {str(key): _fingerprint_value(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_fingerprint_value(item) for item in value]
    return _json_default(value)


def build_input_fingerprint(paths_or_metadata: object) -> dict[str, object]:
    items = _fingerprint_value(paths_or_metadata)
    encoded = json.dumps(items, default=_json_default, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "algorithm": "sha256-path-stat-v1",
        "digest": hashlib.sha256(encoded).hexdigest(),
        "items": items,
    }


def write_manifest(path: str | Path, manifest_dict: Mapping[str, Any]) -> None:
    atomic_write_json(dict(manifest_dict), path)


def validate_time_bounds(
    df: pd.DataFrame,
    date_col: str,
    min_date: str | pd.Timestamp | None = None,
    max_date: str | pd.Timestamp | None = None,
) -> None:
    validate_required_columns(df, [date_col], "time-bounds validation frame")
    values = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if values.empty:
        raise ValueError(f"{date_col} has no valid timestamp values")
    actual_min = pd.Timestamp(values.min())
    actual_max = pd.Timestamp(values.max())
    if min_date is not None and actual_min < pd.Timestamp(min_date):
        raise ValueError(f"{date_col} starts at {actual_min.date()}, before required min_date={pd.Timestamp(min_date).date()}")
    if max_date is not None and actual_max > pd.Timestamp(max_date):
        raise ValueError(f"{date_col} ends at {actual_max.date()}, after required max_date={pd.Timestamp(max_date).date()}")
