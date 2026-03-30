from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _atomic_write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(body, encoding="utf-8")
    temp_path.replace(path)


def _atomic_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temp_path, index=False)
    temp_path.replace(path)


def write_recommendation_artifacts(
    *,
    candidates: pd.DataFrame,
    manifest: dict[str, object],
    candidate_path: Path,
    manifest_path: Path,
) -> None:
    _atomic_write_parquet(candidate_path, candidates)
    _atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
