from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.repo_paths import artifact_path, data_path
from src.run_summary import write_run_summary


MAX_RESEARCH_YEAR = 2025
S1_RAW_SCORE_COL = "xs_proba"
S1_RAW_TARGET_COL = "actual"
S1_SCORE_COL = "s1_xs_proba"
S1_TARGET_COL = "s1_barrier_hit_1d"
S1_DEFAULT_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")

DEFAULT_FORBIDDEN_STATE_COLUMNS = (S1_RAW_TARGET_COL, S1_TARGET_COL)


@dataclass(frozen=True)
class YearSplit:
    name: str
    years: tuple[int, ...]

    def as_metadata(self) -> dict[str, object]:
        return {"name": self.name, "years": list(self.years)}


DEFAULT_PHASES = (
    YearSplit("dev", tuple(range(2015, 2023))),
    YearSplit("validation", (2023, 2024)),
    YearSplit("confirmation", (2025,)),
)


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    family: str = "candidate"
    baseline: str | None = None
    peer: str | None = None
    primary: bool = False

    def as_metadata(self) -> dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "family": self.family,
            "baseline": self.baseline,
            "peer": self.peer,
            "primary": self.primary,
        }


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    mode: str
    hypothesis: str
    start_year: int = 2015
    end_year: int = MAX_RESEARCH_YEAR
    min_train_years: int = 2
    min_year_rows: int = 500
    min_phase_rows: int = 500
    target_columns: Mapping[str, str] = field(default_factory=dict)
    score_columns: Mapping[str, str] = field(default_factory=dict)
    forbidden_state_columns: tuple[str, ...] = DEFAULT_FORBIDDEN_STATE_COLUMNS
    phases: tuple[YearSplit, ...] = DEFAULT_PHASES

    def __post_init__(self) -> None:
        if int(self.end_year) > MAX_RESEARCH_YEAR:
            raise ValueError(
                f"{self.name} end_year={self.end_year} would include 2026+; "
                f"research scaffolds must use <= {MAX_RESEARCH_YEAR} unless a "
                "branch has an explicit forward-only protocol."
            )
        targets = {str(key): str(value) for key, value in self.target_columns.items()}
        scores = {str(key): str(value) for key, value in self.score_columns.items()}
        forbidden = tuple(
            dict.fromkeys(
                [
                    *DEFAULT_FORBIDDEN_STATE_COLUMNS,
                    *[str(col) for col in self.forbidden_state_columns],
                    *targets.keys(),
                ]
            )
        )
        object.__setattr__(self, "target_columns", targets)
        object.__setattr__(self, "score_columns", scores)
        object.__setattr__(self, "forbidden_state_columns", forbidden)

    def as_metadata(self) -> dict[str, object]:
        return {
            "name": self.name,
            "mode": self.mode,
            "hypothesis": self.hypothesis,
            "start_year": int(self.start_year),
            "end_year": int(self.end_year),
            "min_train_years": int(self.min_train_years),
            "min_year_rows": int(self.min_year_rows),
            "min_phase_rows": int(self.min_phase_rows),
            "target_columns": dict(self.target_columns),
            "score_columns": dict(self.score_columns),
            "forbidden_state_columns": list(self.forbidden_state_columns),
            "phases": [phase.as_metadata() for phase in self.phases],
        }


@dataclass(frozen=True)
class ExperimentContext:
    spec: ExperimentSpec
    ts: str
    output_dir: Path

    def write_summary(
        self,
        *,
        summary: Mapping[str, object],
        artifacts: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload_metadata = {"protocol": self.spec.as_metadata()}
        if metadata:
            payload_metadata.update(dict(metadata))
        return write_run_summary(
            ts=self.ts,
            mode=self.spec.mode,
            name=self.spec.name,
            summary=dict(summary),
            artifacts=dict(artifacts or {}),
            metadata=payload_metadata,
        )


def build_experiment_context(
    spec: ExperimentSpec,
    *,
    artifact_subdir: str | Path | None = None,
    ts: str | None = None,
) -> ExperimentContext:
    run_ts = ts or datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = artifact_path(artifact_subdir or spec.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    return ExperimentContext(spec=spec, ts=run_ts, output_dir=out_dir)


def normalize_time_ticker(
    frame: pd.DataFrame,
    *,
    time_col: str = "time",
    ticker_col: str = "ticker",
    source: str = "frame",
) -> pd.DataFrame:
    require_columns(frame, [time_col, ticker_col], context=source)
    out = frame.copy()
    out[time_col] = pd.to_datetime(out[time_col], errors="coerce").dt.normalize()
    out = out.dropna(subset=[time_col, ticker_col])
    out[ticker_col] = out[ticker_col].astype(str).str.upper()
    return out


def restrict_years(
    frame: pd.DataFrame,
    *,
    start_year: int,
    end_year: int,
    time_col: str = "time",
    source: str = "frame",
) -> pd.DataFrame:
    if int(end_year) > MAX_RESEARCH_YEAR:
        raise ValueError(f"{source} requested end_year={end_year}; 2026+ is blocked by default")
    require_columns(frame, [time_col], context=source)
    years = pd.to_datetime(frame[time_col], errors="coerce").dt.year
    out = frame.loc[years.between(int(start_year), int(end_year))].copy()
    out[time_col] = pd.to_datetime(out[time_col], errors="coerce").dt.normalize()
    guard_no_future_years(out, time_col=time_col, max_year=MAX_RESEARCH_YEAR, source=source)
    return out


def guard_no_future_years(
    frame: pd.DataFrame,
    *,
    time_col: str = "time",
    max_year: int = MAX_RESEARCH_YEAR,
    source: str = "frame",
) -> None:
    require_columns(frame, [time_col], context=source)
    years = pd.to_datetime(frame[time_col], errors="coerce").dt.year
    bad_years = sorted(int(year) for year in years.dropna().unique() if int(year) > int(max_year))
    if bad_years:
        raise ValueError(f"{source} contains forbidden future years: {bad_years}")


def require_columns(frame: pd.DataFrame, columns: Sequence[str], *, context: str) -> None:
    missing = [str(col) for col in columns if str(col) not in frame.columns]
    if missing:
        raise ValueError(f"{context} is missing required columns: {missing}")


def load_s1_decision_panel(
    path: str | Path = S1_DEFAULT_PATH,
    *,
    start_year: int = 2015,
    end_year: int = MAX_RESEARCH_YEAR,
    extra_columns: Sequence[str] = (),
) -> pd.DataFrame:
    """
    Load the canonical S1 panel with explicit role-safe names.

    The source parquet calls the future 1d barrier label `actual`. This loader
    always renames it to `s1_barrier_hit_1d` so scripts do not accidentally
    treat it as a signed return or observable market-state input.
    """
    columns = list(dict.fromkeys(["time", "ticker", S1_RAW_SCORE_COL, S1_RAW_TARGET_COL, *extra_columns]))
    frame = pd.read_parquet(path, columns=columns)
    frame = normalize_time_ticker(frame, source="S1 decision panel")
    frame = frame.rename(columns={S1_RAW_SCORE_COL: S1_SCORE_COL, S1_RAW_TARGET_COL: S1_TARGET_COL})
    frame[S1_SCORE_COL] = pd.to_numeric(frame[S1_SCORE_COL], errors="coerce")
    frame[S1_TARGET_COL] = pd.to_numeric(frame[S1_TARGET_COL], errors="coerce")
    return restrict_years(
        frame,
        start_year=int(start_year),
        end_year=int(end_year),
        source="S1 decision panel",
    )


def validate_state_columns(
    frame: pd.DataFrame,
    state_columns: Sequence[str],
    spec: ExperimentSpec,
    *,
    context: str = "state columns",
) -> None:
    state_names = [str(col) for col in state_columns]
    missing = [col for col in state_names if col != "all_rows" and col not in frame.columns]
    if missing:
        raise ValueError(f"{context} are missing from the panel: {missing}")
    forbidden = set(spec.forbidden_state_columns)
    overlap = sorted(set(state_names).intersection(forbidden))
    if overlap:
        raise ValueError(
            f"{context} include target/future-derived columns {overlap}. "
            "Define states only from decision-time observables."
        )


def state_mask(frame: pd.DataFrame, state_col: str) -> pd.Series:
    if state_col == "all_rows" and state_col not in frame.columns:
        return pd.Series(True, index=frame.index, dtype=bool)
    require_columns(frame, [state_col], context="state mask")
    return frame[state_col].fillna(False).astype(bool)


def safe_spearman(
    frame: pd.DataFrame,
    score_col: str,
    target_col: str,
    *,
    min_rows: int,
    min_score_unique: int = 3,
    min_target_unique: int = 2,
) -> dict[str, object]:
    require_columns(frame, [score_col, target_col], context="safe_spearman")
    clean = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if (
        len(clean) < int(min_rows)
        or clean[score_col].nunique() < int(min_score_unique)
        or clean[target_col].nunique() < int(min_target_unique)
    ):
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    rho, p_value = spearmanr(clean[score_col], clean[target_col])
    rho_value = float(np.asarray(rho).flat[0])
    p_value_value = float(np.asarray(p_value).flat[0])
    if not np.isfinite(rho_value):
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    return {
        "rows": int(len(clean)),
        "ic": rho_value,
        "p_value": p_value_value if np.isfinite(p_value_value) else None,
    }


def yearly_ic(
    frame: pd.DataFrame,
    score_col: str,
    target_col: str,
    *,
    min_year_rows: int,
) -> list[dict[str, object]]:
    require_columns(frame, ["time", score_col, target_col], context="yearly_ic")
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby(pd.to_datetime(frame["time"], errors="coerce").dt.year, sort=True):
        stat = safe_spearman(group, score_col, target_col, min_rows=int(min_year_rows))
        rows.append({"year": int(year), **stat})
    return rows


def summarize_ic_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    valid = [float(row["ic"]) for row in rows if row.get("ic") is not None and np.isfinite(float(row["ic"]))]
    if not valid:
        return {
            "avg_ic": None,
            "positive_years": 0,
            "years": 0,
            "pct_positive_years": None,
            "min_year_ic": None,
            "max_year_ic": None,
        }
    positive = sum(1 for value in valid if value > 0)
    return {
        "avg_ic": float(np.mean(valid)),
        "positive_years": int(positive),
        "years": int(len(valid)),
        "pct_positive_years": float(positive / len(valid)),
        "min_year_ic": float(np.min(valid)),
        "max_year_ic": float(np.max(valid)),
    }


def phase_ic(
    frame: pd.DataFrame,
    score_col: str,
    target_col: str,
    spec: ExperimentSpec,
) -> dict[str, object]:
    out: dict[str, object] = {}
    years = pd.to_datetime(frame["time"], errors="coerce").dt.year
    for phase in spec.phases:
        group = frame.loc[years.isin(phase.years)]
        stat = safe_spearman(group, score_col, target_col, min_rows=int(spec.min_phase_rows))
        out[f"{phase.name}_rows"] = stat["rows"]
        out[f"{phase.name}_ic"] = stat["ic"]
        out[f"{phase.name}_p_value"] = stat["p_value"]
    return out


def evaluate_state_specs(
    frame: pd.DataFrame,
    states: Sequence[StateSpec],
    *,
    score_col: str,
    target_col: str,
    spec: ExperimentSpec,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_state_columns(frame, [state.name for state in states], spec)
    require_columns(frame, ["time", score_col, target_col], context="state evaluation panel")

    result_rows: list[dict[str, object]] = []
    yearly_rows: list[dict[str, object]] = []
    for state in states:
        subset = frame.loc[state_mask(frame, state.name)].copy()
        pooled = safe_spearman(subset, score_col, target_col, min_rows=int(spec.min_year_rows))
        years = yearly_ic(subset, score_col, target_col, min_year_rows=int(spec.min_year_rows))
        for row in years:
            yearly_rows.append({"state": state.name, "target": target_col, "score": score_col, **row})
        summary = summarize_ic_rows(years)
        result_rows.append(
            {
                **state.as_metadata(),
                "target": target_col,
                "score": score_col,
                "pooled_rows": pooled["rows"],
                "pooled_ic": pooled["ic"],
                "pooled_p_value": pooled["p_value"],
                **summary,
                **phase_ic(subset, score_col, target_col, spec),
            }
        )
    return pd.DataFrame(result_rows), pd.DataFrame(yearly_rows)


def classify_signal_tier(
    *,
    avg_ic: float | None,
    pct_positive_years: float | None,
    corr_with_parent: float | None = None,
    strong_ic: float = 0.05,
    weak_ic: float = 0.01,
    max_abs_corr: float = 0.30,
    min_positive_year_share: float = 0.60,
) -> str:
    if avg_ic is None or not np.isfinite(float(avg_ic)):
        return "NO_VALID_IC"
    if pct_positive_years is None or float(pct_positive_years) < float(min_positive_year_share):
        return "UNSTABLE"
    if corr_with_parent is not None and abs(float(corr_with_parent)) >= float(max_abs_corr):
        return "PARENT_ECHO"
    if float(avg_ic) > float(strong_ic):
        return "STRONG_STANDALONE_CANDIDATE"
    if float(avg_ic) > float(weak_ic):
        return "WEAK_CANDIDATE_CONTEXT"
    return "NO_EDGE"


def rolling_train_test_years(
    *,
    start_year: int,
    end_year: int,
    min_train_years: int,
) -> list[dict[str, object]]:
    if int(end_year) > MAX_RESEARCH_YEAR:
        raise ValueError("rolling_train_test_years blocks 2026+ by default")
    folds: list[dict[str, object]] = []
    for test_year in range(int(start_year) + int(min_train_years), int(end_year) + 1):
        folds.append(
            {
                "test_year": int(test_year),
                "train_years": tuple(range(int(start_year), int(test_year))),
            }
        )
    return folds


def write_dataframe_artifact(
    frame: pd.DataFrame,
    context: ExperimentContext,
    stem: str,
    *,
    index: bool = False,
) -> Path:
    context.output_dir.mkdir(parents=True, exist_ok=True)
    path = context.output_dir / f"{context.ts}_{stem}.parquet"
    frame.to_parquet(path, index=index)
    return path
