from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.artifact_contract import (
    atomic_write_parquet,
    build_input_fingerprint,
    validate_required_columns,
    validate_unique_keys,
    write_manifest,
)
from src.experiment_contract import (
    ExperimentSpec,
    S1_DEFAULT_PATH,
    load_s1_decision_panel,
)
from src.repo_paths import artifact_path, lab_relative_path
from src.run_summary import write_run_summary


@dataclass(frozen=True)
class FeaturePanelSpec:
    name: str
    path: Path
    columns: tuple[str, ...]
    join_keys: tuple[str, ...] = ("time", "ticker")
    rename: Mapping[str, str] = field(default_factory=dict)
    rank_columns: Mapping[str, str] = field(default_factory=dict)

    def as_metadata(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": lab_relative_path(self.path),
            "columns": list(self.columns),
            "join_keys": list(self.join_keys),
            "rename": dict(self.rename),
            "rank_columns": dict(self.rank_columns),
        }


@dataclass(frozen=True)
class AdditivePanelResult:
    frame: pd.DataFrame
    cache_path: Path
    manifest_path: Path
    source: str
    fingerprint: dict[str, object]


def _panel_cache_paths(cache_name: str) -> tuple[Path, Path]:
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(cache_name)).strip("._")
    if not safe_name:
        safe_name = "additive_research_panel"
    cache_path = artifact_path("cache", f"{safe_name}.parquet")
    manifest_path = artifact_path("cache", f"{safe_name}_manifest.json")
    return cache_path, manifest_path


def _read_manifest(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _fingerprint_matches(manifest_path: Path, fingerprint: Mapping[str, object]) -> bool:
    manifest = _read_manifest(manifest_path)
    if not manifest:
        return False
    expected_digest = str(fingerprint.get("digest"))
    actual = manifest.get("input_fingerprint")
    return isinstance(actual, dict) and str(actual.get("digest")) == expected_digest


def _load_feature_panel(feature: FeaturePanelSpec) -> pd.DataFrame:
    columns = tuple(dict.fromkeys([*feature.join_keys, *feature.columns]))
    frame = pd.read_parquet(feature.path, columns=list(columns)).copy()
    if feature.rename:
        frame = frame.rename(columns=dict(feature.rename))
    validate_required_columns(frame, feature.join_keys, f"{feature.name} feature panel")
    if "time" in frame.columns:
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame = frame.dropna(subset=list(feature.join_keys))
    validate_unique_keys(frame, feature.join_keys, f"{feature.name} feature panel")
    return frame


def rank_by_time(frame: pd.DataFrame, raw_col: str, rank_col: str) -> pd.Series:
    validate_required_columns(frame, ["time", raw_col], f"rank source {raw_col}")
    raw = pd.to_numeric(frame[raw_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return raw.groupby(frame["time"], sort=False).rank(method="average", pct=True)


def add_rank_columns(frame: pd.DataFrame, rank_columns: Mapping[str, str]) -> pd.DataFrame:
    out = frame.copy()
    for raw_col, rank_col in rank_columns.items():
        out[str(rank_col)] = rank_by_time(out, str(raw_col), str(rank_col))
    return out


def load_or_build_additive_research_panel(
    *,
    spec: ExperimentSpec,
    cache_name: str,
    feature_specs: Sequence[FeaturePanelSpec],
    s1_path: str | Path = S1_DEFAULT_PATH,
) -> AdditivePanelResult:
    cache_path, manifest_path = _panel_cache_paths(cache_name)
    fingerprint = build_input_fingerprint(
        {
            "schema_version": 1,
            "experiment": spec.as_metadata(),
            "s1_path": Path(s1_path),
            "features": [feature.as_metadata() for feature in feature_specs],
            "feature_paths": [feature.path for feature in feature_specs],
        }
    )
    if cache_path.exists() and _fingerprint_matches(manifest_path, fingerprint):
        frame = pd.read_parquet(cache_path)
        if "time" in frame.columns:
            frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
        return AdditivePanelResult(
            frame=frame,
            cache_path=cache_path,
            manifest_path=manifest_path,
            source="cache",
            fingerprint=fingerprint,
        )

    panel = load_s1_decision_panel(
        s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    for feature in feature_specs:
        feature_frame = _load_feature_panel(feature)
        panel = panel.merge(feature_frame, on=list(feature.join_keys), how="inner", validate="many_to_one")
        panel = add_rank_columns(panel, feature.rank_columns)

    validate_unique_keys(panel, ["time", "ticker"], f"{spec.name} additive research panel")
    atomic_write_parquet(panel, cache_path)
    write_manifest(
        manifest_path,
        {
            "artifact": lab_relative_path(cache_path),
            "builder": "src.additive_signal_research.load_or_build_additive_research_panel",
            "input_fingerprint": fingerprint,
            "row_count": int(len(panel)),
            "columns": list(panel.columns),
            "experiment": spec.as_metadata(),
        },
    )
    return AdditivePanelResult(
        frame=panel,
        cache_path=cache_path,
        manifest_path=manifest_path,
        source="built",
        fingerprint=fingerprint,
    )


def compute_spearman_ic(
    frame: pd.DataFrame,
    score_col: str,
    target_col: str,
    *,
    min_rows: int = 50,
) -> float:
    validate_required_columns(frame, [score_col, target_col], "Spearman IC frame")
    valid = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < int(min_rows):
        return float("nan")
    rho, _ = spearmanr(valid[score_col], valid[target_col])
    value = float(np.asarray(rho).flat[0])
    return value if np.isfinite(value) else float("nan")


def compute_yearly_spearman_ic(
    frame: pd.DataFrame,
    score_col: str,
    target_col: str,
    *,
    min_rows: int = 50,
) -> dict[int, float]:
    validate_required_columns(frame, ["time", score_col, target_col], f"yearly IC frame {score_col}")
    work = frame.copy()
    work["year"] = pd.to_datetime(work["time"], errors="coerce").dt.year
    out: dict[int, float] = {}
    for year, group in work.dropna(subset=["year"]).groupby("year", sort=True):
        ic = compute_spearman_ic(group, score_col, target_col, min_rows=min_rows)
        if np.isfinite(ic):
            out[int(year)] = float(ic)
    return out


def summarize_ic(
    frame: pd.DataFrame,
    score_col: str,
    target_col: str,
    *,
    min_rows: int = 50,
) -> dict[str, object]:
    yearly = compute_yearly_spearman_ic(frame, score_col, target_col, min_rows=min_rows)
    return {
        "ic": float(compute_spearman_ic(frame, score_col, target_col, min_rows=min_rows)),
        "yearly_ic": {str(year): float(value) for year, value in yearly.items()},
        "positive_years": int(sum(1 for value in yearly.values() if value > 0)),
        "year_count": int(len(yearly)),
    }


def write_additive_run_summary(
    *,
    spec: ExperimentSpec,
    summary: Mapping[str, object],
    artifacts: Mapping[str, object] | None = None,
    metadata: Mapping[str, object] | None = None,
    ts: str | None = None,
) -> str:
    return write_run_summary(
        ts=ts or datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
        mode=spec.mode,
        name=spec.name,
        summary=dict(summary),
        artifacts=dict(artifacts or {}),
        metadata={"protocol": spec.as_metadata(), **dict(metadata or {})},
    )


# Migration note for future H410-H425 cleanup:
# keep branch-specific score construction in the analysis script, but use this
# module for S1 loading, feature joins, rank columns, cached panels, IC helpers,
# and run-summary writing.
