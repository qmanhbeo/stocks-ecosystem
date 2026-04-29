"""
H363 - Vietnam Holiday Timing Payoff Audit.

Question:
- Do Vietnam's legally major public holidays matter as sparse before/after
  market states under the current full-library selector contract, rather than
  as dense calendar model features?

Design:
- Build a dated 2015-2025 holiday-state calendar from the legal major holiday
  set and infer actual exchange closure clusters from VNINDEX trading dates.
- Mark only sparse trading-day states: pre_1/pre_2/pre_3/pre_5 and
  post_1/post_2/post_3/post_5.
- Audit payoff before portfolio integration:
    * 1d and 5d relative return,
    * S1 actual,
    * full-library top-book 5d relative return,
    * tradability/liquidity flags.
- Match active rows to non-holiday controls by research phase, S1 score bucket,
  and full-library score bucket.
- Exclude 2026+ entirely.
- Only if a holiday state passes the payoff gate, run one fixed sparse
  portfolio audit with a single 0.015 bonus/veto on buyable top-quintile names.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_market_rules import required_holding_age_for_sell  # noqa: E402

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes  # noqa: E402
from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns  # noqa: E402
from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.research_protocol import DEFAULT_PROTOCOL, phase_mask  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.tradability_conditioned_research import load_research_bundle, run_selector_candidate  # noqa: E402
from src.vietnam_holiday_calendar import (  # noqa: E402
    build_vietnam_major_holiday_states,
    holiday_state_data_checks,
    load_vnindex_trading_dates,
)

from h358_order_pressure_portfolio_tradability_audit import (  # noqa: E402
    _execution_health_flags,
    _flatten_phase_rows,
    _phase_execution_summary,
)


MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
FWD_REL_5D_PATH = artifact_path("cache/future_rel_return_5d_hose.parquet")
FWD_REL_1D_PATH = artifact_path("cache/future_rel_return_1d_hose.parquet")
OUT_DIR = artifact_path("portfolio_baselines")
TIMING_DIR = artifact_path("timing_data")
RUN_SUMMARY_DIR = artifact_path("run_summaries")

START_YEAR = 2015
END_YEAR = 2025
MATCH_BUCKETS = 5
PRIMARY_METRIC = "top_book_fwd_rel_5d"
BAD_TAIL_THRESHOLD_1D = -0.02
BAD_TAIL_THRESHOLD_5D = -0.03
MEAN_MIN_LIFT = 0.002
Q10_MAX_WORSENING = -0.0025
BAD_TAIL_MAX_WORSENING = 0.010
HIT_RATE_MAX_WORSENING = -0.020
MIN_VALIDATION_TOPBOOK_ROWS = 20
MIN_VALIDATION_DATES = 4
MIN_CONFIRMATION_TOPBOOK_ROWS = 10
MIN_CONFIRMATION_DATES = 2
MIN_MATCHED_ROW_RATE = 0.90
MAX_SINGLE_YEAR_POSITIVE_LIFT_SHARE = 0.80
MIN_POSITIVE_YEARS = 2

HOLIDAY_BONUS = 0.015
BASE_RANK_FLOOR = 0.80
Q10_PORTFOLIO_MAX_WORSENING = -0.0025
BAD_TAIL_PORTFOLIO_MAX_WORSENING = 0.010
STRATEGY_NAME = "holiday_sparse_clock"

METRIC_SPECS = (
    {
        "metric": "fwd_rel_1d",
        "value_col": "fwd_rel_1d",
        "metric_note": "All-row 1 trading-day forward relative return.",
        "bad_threshold": BAD_TAIL_THRESHOLD_1D,
        "top_book_only": False,
    },
    {
        "metric": "fwd_rel_5d",
        "value_col": "fwd_rel_5d",
        "metric_note": "All-row 5 trading-day forward relative return.",
        "bad_threshold": BAD_TAIL_THRESHOLD_5D,
        "top_book_only": False,
    },
    {
        "metric": "s1_actual",
        "value_col": "actual",
        "metric_note": "S1 binary actual target.",
        "bad_threshold": 0.0,
        "top_book_only": False,
    },
    {
        "metric": PRIMARY_METRIC,
        "value_col": "fwd_rel_5d",
        "metric_note": "Full-library top-5 book rows, 5 trading-day forward relative return.",
        "bad_threshold": BAD_TAIL_THRESHOLD_5D,
        "top_book_only": True,
    },
    {
        "metric": "can_buy_next_open",
        "value_col": "can_buy_next_open",
        "metric_note": "Shared execution flag: buyable at next open.",
        "bad_threshold": None,
        "top_book_only": False,
    },
    {
        "metric": "can_sell_next_open",
        "value_col": "can_sell_next_open",
        "metric_note": "Shared execution flag: sellable at next open.",
        "bad_threshold": None,
        "top_book_only": False,
    },
    {
        "metric": "has_volume",
        "value_col": "has_volume",
        "metric_note": "Shared execution flag: same-day volume present.",
        "bad_threshold": None,
        "top_book_only": False,
    },
    {
        "metric": "is_ceiling",
        "value_col": "is_ceiling",
        "metric_note": "Shared execution flag: same-day close at ceiling.",
        "bad_threshold": None,
        "top_book_only": False,
    },
    {
        "metric": "is_floor",
        "value_col": "is_floor",
        "metric_note": "Shared execution flag: same-day close at floor.",
        "bad_threshold": None,
        "top_book_only": False,
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--fwd-rel-5d", type=str, default=str(FWD_REL_5D_PATH))
    parser.add_argument("--fwd-rel-1d-cache", type=str, default=str(FWD_REL_1D_PATH))
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--skip-portfolio", action="store_true")
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _daily_rank(series: pd.Series, time_index: pd.Series, *, ascending: bool = True) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=ascending,
    )


def _score_bucket(rank: pd.Series) -> pd.Series:
    return (
        np.ceil(pd.to_numeric(rank, errors="coerce") * MATCH_BUCKETS)
        .clip(lower=1, upper=MATCH_BUCKETS)
        .astype("Int64")
    )


def _build_future_rel_1d(stock_dir: Path, benchmark_path: Path) -> pd.DataFrame:
    index = pd.read_parquet(benchmark_path, columns=["time", "close"]).rename(columns={"close": "_idx_close"})
    index["time"] = pd.to_datetime(index["time"], errors="coerce").dt.normalize()
    index = index.sort_values("time").drop_duplicates("time")

    parts: list[pd.DataFrame] = []
    for path in sorted(glob.glob(str(stock_dir / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(path).name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        if ticker in {"VNINDEX", "VN30"}:
            continue
        frame = pd.read_parquet(path, columns=["time", "close"]).copy()
        if len(frame) < 100:
            continue
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
        frame = frame.sort_values("time").drop_duplicates("time")
        frame = frame.merge(index, on="time", how="left", validate="one_to_one")
        frame["_idx_close"] = pd.to_numeric(frame["_idx_close"], errors="coerce").ffill()
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        stock_ret = frame["close"].shift(-1).div(frame["close"]) - 1.0
        idx_ret = frame["_idx_close"].shift(-1).div(frame["_idx_close"]) - 1.0
        frame["fwd_rel_1d"] = (stock_ret - idx_ret).replace([np.inf, -np.inf], np.nan)
        part = frame.loc[frame["fwd_rel_1d"].notna(), ["time", "fwd_rel_1d"]].copy()
        part = part.loc[part["fwd_rel_1d"].abs() <= 0.5]
        if not part.empty:
            part["ticker"] = ticker
            parts.append(part)
    if not parts:
        return pd.DataFrame(columns=["time", "ticker", "fwd_rel_1d"])
    return pd.concat(parts, ignore_index=True).sort_values(["time", "ticker"]).reset_index(drop=True)


def _load_future_rel_1d(cache_path: Path, stock_dir: Path, benchmark_path: Path) -> pd.DataFrame:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        frame = pd.read_parquet(cache_path).copy()
    else:
        frame = _build_future_rel_1d(stock_dir, benchmark_path)
        frame.to_parquet(cache_path, index=False)
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["fwd_rel_1d"] = pd.to_numeric(frame["fwd_rel_1d"], errors="coerce")
    return frame.dropna(subset=["time", "ticker", "fwd_rel_1d"]).drop_duplicates(["time", "ticker"])


def _load_future_rel_5d(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["time", "ticker", "fwd_rel_5d"]).copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["fwd_rel_5d"] = pd.to_numeric(frame["fwd_rel_5d"], errors="coerce")
    return frame.dropna(subset=["time", "ticker", "fwd_rel_5d"]).drop_duplicates(["time", "ticker"])


def _load_base_panel(
    *,
    matrix_path: Path,
    tradability_path: Path,
    fwd_rel_5d_path: Path,
    fwd_rel_1d_path: Path,
    stock_dir: Path,
    benchmark_path: Path,
    start_year: int,
    end_year: int,
) -> tuple[pd.DataFrame, list[str]]:
    matrix = pd.read_parquet(matrix_path).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    matrix = matrix.loc[matrix["time"].dt.year.between(int(start_year), int(end_year))].dropna(subset=["time", "ticker"])

    full_library_columns = resolve_strategy_columns(matrix.columns.tolist(), "full_library")
    score_col = "score__full_library_baseline"
    score_frame = compute_strategy_scores(matrix, {"full_library_baseline": list(full_library_columns)})
    scored = matrix[["time", "ticker", "actual", "s1_proba"]].merge(
        score_frame[["time", "ticker", score_col]],
        on=["time", "ticker"],
        how="inner",
        validate="one_to_one",
    )
    scored["s1_rank"] = _daily_rank(scored["s1_proba"], scored["time"], ascending=True)
    scored["full_library_rank"] = _daily_rank(scored[score_col], scored["time"], ascending=True)
    scored["s1_bucket"] = _score_bucket(scored["s1_rank"])
    scored["full_library_bucket"] = _score_bucket(scored["full_library_rank"])
    scored = scored.sort_values(["time", score_col, "ticker"], ascending=[True, False, True]).reset_index(drop=True)
    scored["_book_rank"] = scored.groupby("time", sort=False)[score_col].rank(method="first", ascending=False)
    scored["full_library_top_book"] = scored["_book_rank"] <= 5
    scored = scored.drop(columns=["_book_rank"])

    fwd1 = _load_future_rel_1d(fwd_rel_1d_path, stock_dir, benchmark_path)
    fwd5 = _load_future_rel_5d(fwd_rel_5d_path)
    tradability = pd.read_parquet(
        tradability_path,
        columns=[
            "time",
            "ticker",
            "has_volume",
            "is_ceiling",
            "is_floor",
            "can_buy_next_open",
            "can_sell_next_open",
        ],
    ).copy()
    tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce").dt.normalize()
    tradability["ticker"] = tradability["ticker"].astype(str).str.upper()
    tradability = tradability.loc[tradability["time"].dt.year.between(int(start_year), int(end_year))]

    panel = scored.merge(fwd1, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(fwd5, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(tradability, on=["time", "ticker"], how="left", validate="one_to_one")
    for column in ("actual", "s1_proba", score_col, "fwd_rel_1d", "fwd_rel_5d"):
        panel[column] = pd.to_numeric(panel[column], errors="coerce")
    for column in ("has_volume", "is_ceiling", "is_floor", "can_buy_next_open", "can_sell_next_open"):
        panel[column] = panel[column].fillna(False).astype(bool)
    panel["research_phase"] = panel["time"].dt.year.map(DEFAULT_PROTOCOL.phase_for_year)
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True), list(full_library_columns)


def _state_label(subject: str, holiday_state: str) -> str:
    return f"{subject}__{holiday_state}"


def _expand_audit_states(family_states: pd.DataFrame) -> pd.DataFrame:
    if family_states.empty:
        return family_states.copy()

    pieces: list[pd.DataFrame] = []
    family = family_states.copy()
    family["state_scope"] = "family"
    family["state_subject"] = family["holiday_family"].astype(str)
    family["state_label"] = [
        _state_label(subject, state)
        for subject, state in zip(family["state_subject"], family["holiday_state"], strict=False)
    ]
    family["state_note"] = family["holiday_family_label"].astype(str)
    pieces.append(family)

    group_specs = (
        ("group", "tet", family_states["holiday_family"].eq("tet"), "Tet grouped family state."),
        (
            "group",
            "civil_holidays",
            family_states["holiday_family"].ne("tet"),
            "All non-Tet legal major holiday families.",
        ),
        ("group", "all_holidays", pd.Series(True, index=family_states.index), "All legal major holiday families."),
        (
            "closure",
            "long_closure_ge5",
            pd.to_numeric(family_states["closure_length"], errors="coerce").fillna(0) >= 5,
            "Diagnostic closure-length state: calendar closure length >= 5 days.",
        ),
        (
            "closure",
            "short_closure_lt5",
            pd.to_numeric(family_states["closure_length"], errors="coerce").fillna(0) < 5,
            "Diagnostic closure-length state: calendar closure length < 5 days.",
        ),
    )
    for scope, subject, mask, note in group_specs:
        group = family_states.loc[mask].copy()
        if group.empty:
            continue
        group["state_scope"] = scope
        group["state_subject"] = subject
        group["state_label"] = [_state_label(subject, state) for state in group["holiday_state"]]
        group["state_note"] = note
        group = (
            group.sort_values(["time", "holiday_state", "closure_length"], ascending=[True, True, False])
            .drop_duplicates(["time", "holiday_state", "state_scope", "state_subject"])
            .reset_index(drop=True)
        )
        pieces.append(group)

    out = pd.concat(pieces, ignore_index=True)
    return out.sort_values(["state_scope", "state_subject", "holiday_state", "time"]).reset_index(drop=True)


def _reference_table(frame: pd.DataFrame, keys: list[str], metric_col: str, bad_threshold: float | None) -> pd.DataFrame:
    columns = [
        *keys,
        "matched_mean",
        "matched_median",
        "matched_q10",
        "matched_q90",
        "matched_hit_rate",
        "matched_bad_tail_rate",
        "matched_control_rows",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    work = frame.copy()
    metric = pd.to_numeric(work[metric_col], errors="coerce").astype(float)
    work[metric_col] = metric
    work["_hit"] = (metric > 0.0).astype(float)
    work["_bad_tail"] = (metric <= float(bad_threshold)).astype(float) if bad_threshold is not None else np.nan
    grouped = work.groupby(keys, dropna=False) if keys else work.groupby(lambda _: 0)
    refs = grouped.agg(
        matched_mean=(metric_col, "mean"),
        matched_median=(metric_col, "median"),
        matched_hit_rate=("_hit", "mean"),
        matched_bad_tail_rate=("_bad_tail", "mean"),
        matched_control_rows=(metric_col, "count"),
    ).reset_index()
    quantiles = (
        grouped[metric_col]
        .quantile([0.10, 0.90])
        .unstack(level=-1)
        .rename(columns={0.10: "matched_q10", 0.90: "matched_q90"})
        .reset_index()
    )
    out = refs.merge(quantiles, on=keys, how="left", validate="one_to_one") if keys else refs.join(
        quantiles[["matched_q10", "matched_q90"]]
    )
    return out[columns]


def _metric_spec(metric: str) -> dict[str, object]:
    for spec in METRIC_SPECS:
        if spec["metric"] == metric:
            return dict(spec)
    raise KeyError(metric)


def _build_ref_cache(panel: pd.DataFrame) -> dict[tuple[str, str, str], pd.DataFrame]:
    cache: dict[tuple[str, str, str], pd.DataFrame] = {}
    levels = (
        ("s1_full", ["research_phase", "s1_bucket", "full_library_bucket"]),
        ("full_only", ["research_phase", "full_library_bucket"]),
        ("phase", ["research_phase"]),
    )
    for phase in ("dev", "validation", "confirmation"):
        phase_frame = panel.loc[phase_mask(panel, phase, protocol=DEFAULT_PROTOCOL)].copy()
        for spec in METRIC_SPECS:
            metric = str(spec["metric"])
            value_col = str(spec["value_col"])
            controls = phase_frame.loc[
                ~phase_frame["holiday_any_state"].fillna(False).astype(bool)
                & pd.to_numeric(phase_frame[value_col], errors="coerce").notna()
                & phase_frame["s1_bucket"].notna()
                & phase_frame["full_library_bucket"].notna()
            ].copy()
            if bool(spec["top_book_only"]):
                controls = controls.loc[controls["full_library_top_book"]].copy()
            for level_name, keys in levels:
                cache[(phase, metric, level_name)] = _reference_table(
                    controls,
                    keys,
                    value_col,
                    spec["bad_threshold"],
                )
    return cache


def _match_active_rows(
    active: pd.DataFrame,
    *,
    phase: str,
    metric: str,
    value_col: str,
    ref_cache: dict[tuple[str, str, str], pd.DataFrame],
) -> pd.DataFrame:
    if active.empty:
        return pd.DataFrame()
    current = active[
        [
            "time",
            "ticker",
            "research_phase",
            "s1_bucket",
            "full_library_bucket",
            "full_library_rank",
            "full_library_top_book",
            value_col,
        ]
    ].copy()
    current["_row_id"] = np.arange(len(current))
    remaining = current.copy()
    matched_parts: list[pd.DataFrame] = []
    for level_name, keys in (
        ("s1_full", ["research_phase", "s1_bucket", "full_library_bucket"]),
        ("full_only", ["research_phase", "full_library_bucket"]),
        ("phase", ["research_phase"]),
    ):
        if remaining.empty:
            break
        refs = ref_cache[(phase, metric, level_name)]
        joined = remaining.merge(refs, on=keys, how="left", validate="many_to_one")
        got = joined.loc[joined["matched_mean"].notna()].copy()
        if not got.empty:
            got["match_level"] = level_name
            matched_parts.append(got)
            remaining = remaining.loc[~remaining["_row_id"].isin(got["_row_id"])].copy()
    if not remaining.empty:
        remaining = remaining.copy()
        for col in (
            "matched_mean",
            "matched_median",
            "matched_q10",
            "matched_q90",
            "matched_hit_rate",
            "matched_bad_tail_rate",
            "matched_control_rows",
        ):
            remaining[col] = np.nan
        remaining["match_level"] = "unmatched"
        matched_parts.append(remaining)
    return pd.concat(matched_parts, ignore_index=True) if matched_parts else pd.DataFrame()


def _phase_metric_summary(
    panel: pd.DataFrame,
    state_def: pd.Series,
    active_dates: set[pd.Timestamp],
    *,
    phase: str,
    spec: dict[str, object],
    ref_cache: dict[tuple[str, str, str], pd.DataFrame],
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    metric = str(spec["metric"])
    value_col = str(spec["value_col"])
    phase_frame = panel.loc[
        phase_mask(panel, phase, protocol=DEFAULT_PROTOCOL)
        & panel["time"].isin(active_dates)
        & pd.to_numeric(panel[value_col], errors="coerce").notna()
    ].copy()
    if bool(spec["top_book_only"]):
        phase_frame = phase_frame.loc[phase_frame["full_library_top_book"]].copy()
    matches = _match_active_rows(
        phase_frame,
        phase=phase,
        metric=metric,
        value_col=value_col,
        ref_cache=ref_cache,
    )
    matched = matches.loc[matches["match_level"].ne("unmatched")].copy() if not matches.empty else pd.DataFrame()
    active_metric = pd.to_numeric(phase_frame[value_col], errors="coerce").astype(float)
    phase_frame[value_col] = active_metric
    active_rows = int(len(phase_frame))
    matched_rows = int(len(matched))

    active_mean = _safe_float(active_metric.mean()) if active_rows else None
    matched_mean = _safe_float(matched["matched_mean"].mean()) if matched_rows else None
    active_q10 = _safe_float(active_metric.quantile(0.10)) if active_rows else None
    matched_q10 = _safe_float(matched["matched_q10"].mean()) if matched_rows else None
    active_q90 = _safe_float(active_metric.quantile(0.90)) if active_rows else None
    matched_q90 = _safe_float(matched["matched_q90"].mean()) if matched_rows else None
    active_hit_rate = _safe_float((active_metric > 0.0).mean()) if active_rows else None
    matched_hit_rate = _safe_float(matched["matched_hit_rate"].mean()) if matched_rows else None
    bad_threshold = spec["bad_threshold"]
    active_bad_tail_rate = (
        _safe_float((active_metric <= float(bad_threshold)).mean()) if active_rows and bad_threshold is not None else None
    )
    matched_bad_tail_rate = (
        _safe_float(matched["matched_bad_tail_rate"].mean()) if matched_rows and bad_threshold is not None else None
    )

    yearly = pd.DataFrame()
    if matched_rows:
        yearly = matched.assign(
            lift=pd.to_numeric(matched[value_col], errors="coerce") - pd.to_numeric(matched["matched_mean"], errors="coerce"),
            year=pd.to_datetime(matched["time"]).dt.year,
        )
        yearly = (
            yearly.groupby("year", as_index=False)
            .agg(mean_lift=("lift", "mean"), active_rows=("_row_id", "count"), active_dates=("time", "nunique"))
        )
    positive = yearly.loc[pd.to_numeric(yearly.get("mean_lift"), errors="coerce") > 0.0].copy() if not yearly.empty else pd.DataFrame()
    positive_sum = float(positive["mean_lift"].sum()) if not positive.empty else 0.0
    max_positive_share = (
        float(positive["mean_lift"].max() / positive_sum) if positive_sum > 0 and not positive.empty else None
    )

    summary = {
        "state_label": state_def["state_label"],
        "state_scope": state_def["state_scope"],
        "state_subject": state_def["state_subject"],
        "holiday_state": state_def["holiday_state"],
        "holiday_side": state_def["holiday_side"],
        "holiday_offset": int(state_def["holiday_offset"]),
        "state_note": state_def["state_note"],
        "phase": phase,
        "metric": metric,
        "metric_note": spec["metric_note"],
        "top_book_only": bool(spec["top_book_only"]),
        "active_rows": active_rows,
        "active_dates": int(phase_frame["time"].nunique()) if active_rows else 0,
        "active_tickers": int(phase_frame["ticker"].nunique()) if active_rows else 0,
        "matched_rows": matched_rows,
        "matched_row_rate": float(matched_rows / active_rows) if active_rows else 0.0,
        "avg_matched_control_rows": _safe_float(matched["matched_control_rows"].mean()) if matched_rows else None,
        "active_mean": active_mean,
        "matched_mean": matched_mean,
        "mean_lift": None if active_mean is None or matched_mean is None else active_mean - matched_mean,
        "active_q10": active_q10,
        "matched_q10": matched_q10,
        "q10_lift": None if active_q10 is None or matched_q10 is None else active_q10 - matched_q10,
        "active_q90": active_q90,
        "matched_q90": matched_q90,
        "q90_lift": None if active_q90 is None or matched_q90 is None else active_q90 - matched_q90,
        "active_hit_rate": active_hit_rate,
        "matched_hit_rate": matched_hit_rate,
        "hit_rate_lift": None if active_hit_rate is None or matched_hit_rate is None else active_hit_rate - matched_hit_rate,
        "active_bad_tail_rate": active_bad_tail_rate,
        "matched_bad_tail_rate": matched_bad_tail_rate,
        "bad_tail_rate_lift": None
        if active_bad_tail_rate is None or matched_bad_tail_rate is None
        else active_bad_tail_rate - matched_bad_tail_rate,
        "year_count": int(len(yearly)),
        "positive_lift_years": int(len(positive)),
        "max_positive_lift_year_share": max_positive_share,
        "s1_full_match_rows": int((matches["match_level"] == "s1_full").sum()) if not matches.empty else 0,
        "full_only_match_rows": int((matches["match_level"] == "full_only").sum()) if not matches.empty else 0,
        "phase_match_rows": int((matches["match_level"] == "phase").sum()) if not matches.empty else 0,
        "unmatched_rows": int((matches["match_level"] == "unmatched").sum()) if not matches.empty else 0,
    }
    if not matches.empty:
        matches["state_label"] = state_def["state_label"]
        matches["phase"] = phase
        matches["metric"] = metric
    if not yearly.empty:
        yearly["state_label"] = state_def["state_label"]
        yearly["phase"] = phase
        yearly["metric"] = metric
    return summary, matches, yearly


def _evaluate(panel: pd.DataFrame, audit_states: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ref_cache = _build_ref_cache(panel)
    state_defs = (
        audit_states[
            [
                "state_label",
                "state_scope",
                "state_subject",
                "holiday_state",
                "holiday_side",
                "holiday_offset",
                "state_note",
            ]
        ]
        .drop_duplicates()
        .sort_values(["state_scope", "state_subject", "holiday_state"])
        .reset_index(drop=True)
    )
    dates_by_state = {
        str(label): set(pd.to_datetime(group["time"], errors="coerce").dt.normalize().dropna().tolist())
        for label, group in audit_states.groupby("state_label")
    }
    summaries: list[dict[str, object]] = []
    match_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    for state_def in state_defs.itertuples(index=False):
        state_series = pd.Series(state_def._asdict())
        active_dates = dates_by_state[str(state_series["state_label"])]
        for phase in ("dev", "validation", "confirmation"):
            for spec in METRIC_SPECS:
                summary, matches, yearly = _phase_metric_summary(
                    panel,
                    state_series,
                    active_dates,
                    phase=phase,
                    spec=dict(spec),
                    ref_cache=ref_cache,
                )
                summaries.append(summary)
                if not matches.empty:
                    match_frames.append(matches)
                if not yearly.empty:
                    yearly_frames.append(yearly)
    results = pd.DataFrame(summaries)
    active_matches = pd.concat(match_frames, ignore_index=True) if match_frames else pd.DataFrame()
    yearly = pd.concat(yearly_frames, ignore_index=True) if yearly_frames else pd.DataFrame()
    return results, active_matches, yearly


def _result(results: pd.DataFrame, state_label: str, phase: str, metric: str) -> pd.Series:
    match = results.loc[
        (results["state_label"] == state_label)
        & (results["phase"] == phase)
        & (results["metric"] == metric)
    ]
    if match.empty:
        raise ValueError(f"Missing result for {state_label} / {phase} / {metric}")
    return match.iloc[0]


def _num(row: pd.Series, key: str, default: float = 0.0) -> float:
    value = pd.to_numeric(row.get(key), errors="coerce")
    return default if pd.isna(value) else float(value)


def _phase_viable(row: pd.Series, *, phase: str) -> bool:
    min_rows = MIN_VALIDATION_TOPBOOK_ROWS if phase == "validation" else MIN_CONFIRMATION_TOPBOOK_ROWS
    min_dates = MIN_VALIDATION_DATES if phase == "validation" else MIN_CONFIRMATION_DATES
    return (
        int(row["active_rows"]) >= min_rows
        and int(row["active_dates"]) >= min_dates
        and _num(row, "matched_row_rate", 0.0) >= MIN_MATCHED_ROW_RATE
    )


def _phase_payoff_clean(row: pd.Series) -> bool:
    return (
        _num(row, "mean_lift", -9.0) >= MEAN_MIN_LIFT
        and _num(row, "q10_lift", -9.0) >= Q10_MAX_WORSENING
        and _num(row, "bad_tail_rate_lift", 9.0) <= BAD_TAIL_MAX_WORSENING
        and _num(row, "hit_rate_lift", -9.0) >= HIT_RATE_MAX_WORSENING
    )


def _year_consistency(yearly: pd.DataFrame, state_label: str) -> dict[str, object]:
    scoped = yearly.loc[
        (yearly["state_label"] == state_label)
        & (yearly["metric"] == PRIMARY_METRIC)
        & yearly["phase"].isin(["validation", "confirmation"])
    ].copy()
    if scoped.empty:
        return {
            "val_conf_year_count": 0,
            "val_conf_positive_years": 0,
            "val_conf_max_positive_lift_year_share": None,
            "passes_year_consistency": False,
        }
    positive = scoped.loc[pd.to_numeric(scoped["mean_lift"], errors="coerce") > 0.0].copy()
    positive_sum = float(positive["mean_lift"].sum()) if not positive.empty else 0.0
    max_share = float(positive["mean_lift"].max() / positive_sum) if positive_sum > 0 and not positive.empty else None
    return {
        "val_conf_year_count": int(scoped["year"].nunique()),
        "val_conf_positive_years": int(positive["year"].nunique()) if not positive.empty else 0,
        "val_conf_max_positive_lift_year_share": max_share,
        "passes_year_consistency": bool(
            int(positive["year"].nunique()) >= MIN_POSITIVE_YEARS
            and (max_share is not None and max_share <= MAX_SINGLE_YEAR_POSITIVE_LIFT_SHARE)
        ),
    }


def _decide(results: pd.DataFrame, yearly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    rows: list[dict[str, object]] = []
    state_defs = results[["state_label", "state_scope", "state_subject", "holiday_state", "state_note"]].drop_duplicates()
    for state in state_defs.itertuples(index=False):
        state_label = str(state.state_label)
        row: dict[str, object] = {
            "state_label": state_label,
            "state_scope": str(state.state_scope),
            "state_subject": str(state.state_subject),
            "holiday_state": str(state.holiday_state),
            "state_note": str(state.state_note),
        }
        phase_flags: dict[str, dict[str, bool]] = {}
        for phase in ("dev", "validation", "confirmation"):
            primary = _result(results, state_label, phase, PRIMARY_METRIC)
            viable = True if phase == "dev" else _phase_viable(primary, phase=phase)
            clean = viable and _phase_payoff_clean(primary)
            phase_flags[phase] = {"viable": viable, "clean": clean}
            for key in (
                "active_rows",
                "active_dates",
                "mean_lift",
                "q10_lift",
                "q90_lift",
                "bad_tail_rate_lift",
                "hit_rate_lift",
                "matched_row_rate",
            ):
                row[f"{phase}_{PRIMARY_METRIC}_{key}"] = _safe_float(primary[key])

            for metric in ("fwd_rel_1d", "fwd_rel_5d", "s1_actual", "can_buy_next_open", "has_volume", "is_ceiling", "is_floor"):
                metric_row = _result(results, state_label, phase, metric)
                row[f"{phase}_{metric}_mean_lift"] = _safe_float(metric_row["mean_lift"])

        year_flags = _year_consistency(yearly, state_label)
        row.update(year_flags)
        if str(state.state_scope) == "closure":
            decision = "DIAGNOSTIC"
            reason = "closure_length_diagnostic_not_portfolio_candidate"
        elif not (phase_flags["validation"]["viable"] and phase_flags["confirmation"]["viable"]):
            decision = "SKIPPED"
            reason = "insufficient_validation_or_confirmation_top_book_rows_or_dates"
        elif phase_flags["validation"]["clean"] and phase_flags["confirmation"]["clean"] and year_flags["passes_year_consistency"]:
            decision = "PASSED"
            reason = "validation_and_confirmation_top_book_payoff_clean_with_multi_year_support"
        elif (
            _num(_result(results, state_label, "validation", PRIMARY_METRIC), "mean_lift", -9.0) > 0.0
            and _num(_result(results, state_label, "confirmation", PRIMARY_METRIC), "mean_lift", -9.0) > 0.0
        ):
            decision = "MIXED"
            reason = "positive_validation_and_confirmation_mean_lift_but_gate_or_year_consistency_not_clean"
        elif max(
            _num(_result(results, state_label, "validation", PRIMARY_METRIC), "mean_lift", -9.0),
            _num(_result(results, state_label, "confirmation", PRIMARY_METRIC), "mean_lift", -9.0),
        ) > MEAN_MIN_LIFT:
            decision = "MIXED"
            reason = "one_phase_holiday_timing_hint_only"
        else:
            decision = "FAILED"
            reason = "no_clean_two_phase_holiday_timing_payoff"
        row["decision"] = decision
        row["reason"] = reason
        row["score"] = (
            _num(pd.Series(row), f"validation_{PRIMARY_METRIC}_mean_lift", -9.0)
            + _num(pd.Series(row), f"confirmation_{PRIMARY_METRIC}_mean_lift", -9.0)
            + _num(pd.Series(row), f"validation_{PRIMARY_METRIC}_q10_lift", -9.0)
            + _num(pd.Series(row), f"confirmation_{PRIMARY_METRIC}_q10_lift", -9.0)
            - _num(pd.Series(row), f"validation_{PRIMARY_METRIC}_bad_tail_rate_lift", 9.0)
            - _num(pd.Series(row), f"confirmation_{PRIMARY_METRIC}_bad_tail_rate_lift", 9.0)
        )
        rows.append(row)

    state_results = pd.DataFrame(rows)
    candidates = state_results.loc[state_results["state_scope"].isin(["family", "group"])].copy()
    decision_rank = {"PASSED": 0, "MIXED": 1, "FAILED": 2, "SKIPPED": 3, "DIAGNOSTIC": 9}
    candidates["_decision_rank"] = candidates["decision"].map(decision_rank).fillna(9)
    best = candidates.sort_values(["_decision_rank", "score"], ascending=[True, False]).iloc[0]
    passed = candidates.loc[candidates["decision"].eq("PASSED")].copy()

    if not passed.empty:
        verdict = "PASSED"
        branch_decision = (
            "At least one sparse holiday state passed the matched top-book payoff gate. "
            "Run exactly one fixed sparse portfolio audit with a 0.015 bonus/veto."
        )
    elif (candidates["decision"] == "MIXED").any():
        verdict = "MIXED"
        branch_decision = (
            "Holiday states have payoff hints, but none passed validation, confirmation, risk, and year-consistency gates. "
            "Keep the branch as offline evidence only."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "No sparse holiday state produced a clean matched top-book payoff. Do not run a holiday sparse portfolio overlay."
        )
    summary = {
        "verdict": verdict,
        "best_state": _json_safe(best.drop(labels=["_decision_rank"], errors="ignore").to_dict()),
        "passed_state_count": int(len(passed)),
        "branch_decision": branch_decision,
        "state_decisions": _json_safe(
            state_results[["state_label", "state_scope", "state_subject", "holiday_state", "decision", "reason", "score"]]
            .sort_values(["decision", "score"], ascending=[True, False])
            .to_dict(orient="records")
        ),
    }
    return state_results, summary


def _risk_rows(daily_by_strategy: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for strategy, daily in daily_by_strategy.items():
        work = daily.copy()
        work["execution_date"] = pd.to_datetime(work["execution_date"])
        for phase in ("dev", "validation", "confirmation"):
            scoped = work.loc[phase_mask(work, phase, date_column="execution_date", protocol=DEFAULT_PROTOCOL)]
            rel = pd.to_numeric(scoped["relative_return"], errors="coerce").dropna()
            rows.append(
                {
                    "strategy_name": strategy,
                    "phase": phase,
                    "daily_relative_q10": _safe_float(rel.quantile(0.10)) if not rel.empty else None,
                    "daily_relative_bad_tail_rate": _safe_float((rel <= BAD_TAIL_THRESHOLD_5D).mean()) if not rel.empty else None,
                }
            )
    return pd.DataFrame(rows)


def _risk_gate(risk: pd.DataFrame) -> dict[str, object]:
    baseline = risk.loc[risk["strategy_name"] == "full_library_baseline"].set_index("phase")
    candidate = risk.loc[risk["strategy_name"] == STRATEGY_NAME].set_index("phase")
    out: dict[str, object] = {}
    passes = True
    for phase in ("validation", "confirmation"):
        q10_delta = (_safe_float(candidate.loc[phase, "daily_relative_q10"]) or 0.0) - (
            _safe_float(baseline.loc[phase, "daily_relative_q10"]) or 0.0
        )
        bad_tail_delta = (_safe_float(candidate.loc[phase, "daily_relative_bad_tail_rate"]) or 0.0) - (
            _safe_float(baseline.loc[phase, "daily_relative_bad_tail_rate"]) or 0.0
        )
        out[f"{phase}_daily_relative_q10_delta"] = q10_delta
        out[f"{phase}_bad_tail_rate_delta"] = bad_tail_delta
        passes = passes and q10_delta >= Q10_PORTFOLIO_MAX_WORSENING and bad_tail_delta <= BAD_TAIL_PORTFOLIO_MAX_WORSENING
    out["passes_downside_tail_gate"] = bool(passes)
    return out


def _run_sparse_portfolio(
    *,
    args: argparse.Namespace,
    ts: str,
    audit_states: pd.DataFrame,
    passed_state: pd.Series,
    full_library_columns: list[str],
) -> dict[str, object]:
    state_label = str(passed_state["state_label"])
    active_dates = set(
        pd.to_datetime(
            audit_states.loc[audit_states["state_label"].eq(state_label), "time"],
            errors="coerce",
        )
        .dt.normalize()
        .dropna()
        .tolist()
    )
    val_lift = _num(passed_state, f"validation_{PRIMARY_METRIC}_mean_lift", 0.0)
    conf_lift = _num(passed_state, f"confirmation_{PRIMARY_METRIC}_mean_lift", 0.0)
    direction = "bonus" if (val_lift + conf_lift) >= 0.0 else "veto"
    signed_bonus = HOLIDAY_BONUS if direction == "bonus" else -HOLIDAY_BONUS

    fee_leg = float(args.round_trip_cost) / 2.0
    required_holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    matrix = bundle.matrix.copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    scored = compute_strategy_scores(matrix, {"full_library_baseline": list(full_library_columns)})
    base = scored["score__full_library_baseline"].astype(float)
    base_rank = base.groupby(scored["time"], sort=False).rank(method="average", pct=True)
    tradability = bundle.tradability[["time", "ticker", "can_buy_next_open"]].copy()
    tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce").dt.normalize()
    tradability["ticker"] = tradability["ticker"].astype(str).str.upper()
    scored = scored.merge(tradability, on=["time", "ticker"], how="left", validate="one_to_one")
    scored["can_buy_next_open"] = scored["can_buy_next_open"].fillna(False).astype(bool)
    scored["holiday_sparse_clock_active"] = scored["time"].isin(active_dates)
    eligible = scored["holiday_sparse_clock_active"] & scored["can_buy_next_open"] & (base_rank >= BASE_RANK_FLOOR)
    scored[f"score__{STRATEGY_NAME}"] = base + signed_bonus * eligible.astype(float)

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for strategy_name, signal_columns in {
        "full_library_baseline": list(full_library_columns),
        STRATEGY_NAME: [f"{state_label}_{direction}"],
    }.items():
        result = run_selector_candidate(
            scored_frame=scored[["time", "ticker", "actual", f"score__{strategy_name}"]],
            bundle=bundle,
            strategy_name=strategy_name,
            signal_columns=signal_columns,
            start_year=int(args.start_year),
            end_year=int(args.end_year),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            required_holding_age=int(required_holding_age),
        )
        row = _flatten_phase_rows(strategy_name, signal_columns, _phase_execution_summary(result.daily), result.summary)
        rows.append(row)
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    candidate_idx = results.index[results["strategy_name"] == STRATEGY_NAME][0]
    candidate = results.loc[candidate_idx].copy()
    for key, value in {**additive_candidate_deltas(candidate, baseline), **_execution_health_flags(candidate, baseline)}.items():
        results.loc[candidate_idx, key] = value
        candidate[key] = value
    results.loc[candidate_idx, "portfolio_gate_pass"] = bool(additive_candidate_passes(candidate, baseline))
    risk = _risk_rows(daily_outputs)
    tail_gate = _risk_gate(risk)
    for key, value in tail_gate.items():
        results.loc[candidate_idx, key] = value
    contract_pass = bool(
        results.loc[candidate_idx, "portfolio_gate_pass"]
        and results.loc[candidate_idx, "passes_execution_health"]
        and tail_gate["passes_downside_tail_gate"]
    )
    results.loc[candidate_idx, "verdict"] = "PASSED" if contract_pass else "FAILED"
    results.loc[results["strategy_name"] == "full_library_baseline", "portfolio_gate_pass"] = False
    results.loc[results["strategy_name"] == "full_library_baseline", "passes_execution_health"] = True
    results.loc[results["strategy_name"] == "full_library_baseline", "passes_downside_tail_gate"] = True
    results.loc[results["strategy_name"] == "full_library_baseline", "verdict"] = "BASELINE"

    results_path = OUT_DIR / f"{ts}_h363_vietnam_holiday_sparse_clock_portfolio_results.parquet"
    risk_path = OUT_DIR / f"{ts}_h363_vietnam_holiday_sparse_clock_portfolio_risk.parquet"
    candidate_daily_path = OUT_DIR / f"{ts}_h363_vietnam_holiday_sparse_clock_portfolio_candidate_daily.parquet"
    results.to_parquet(results_path, index=False)
    risk.to_parquet(risk_path, index=False)
    daily_outputs[STRATEGY_NAME].to_parquet(candidate_daily_path, index=False)
    candidate_row = results.loc[results["strategy_name"] == STRATEGY_NAME].iloc[0]
    return {
        "portfolio_run": True,
        "portfolio_verdict": "PASSED" if contract_pass else "FAILED",
        "portfolio_state_label": state_label,
        "portfolio_direction": direction,
        "eligible_bonus_rows": int(eligible.sum()),
        "active_dates": int(len(active_dates)),
        "portfolio_gate_pass": bool(candidate_row.get("portfolio_gate_pass")),
        "passes_execution_health": bool(candidate_row.get("passes_execution_health")),
        "passes_downside_tail_gate": bool(candidate_row.get("passes_downside_tail_gate")),
        "validation_relative_delta": _safe_float(candidate_row.get("validation_relative_delta")),
        "confirmation_relative_delta": _safe_float(candidate_row.get("confirmation_relative_delta")),
        "validation_daily_relative_q10_delta": _safe_float(candidate_row.get("validation_daily_relative_q10_delta")),
        "confirmation_daily_relative_q10_delta": _safe_float(candidate_row.get("confirmation_daily_relative_q10_delta")),
        "artifacts": {
            "portfolio_results": results_path,
            "portfolio_risk": risk_path,
            "portfolio_candidate_daily": candidate_daily_path,
        },
    }


def main() -> None:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TIMING_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    print("H363: building Vietnam major-holiday calendar...", flush=True)
    trading_dates = load_vnindex_trading_dates(Path(args.benchmark))
    holiday_states, holiday_clusters = build_vietnam_major_holiday_states(
        trading_dates,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    data_checks = holiday_state_data_checks(
        holiday_states,
        trading_dates,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    if not data_checks["all_state_dates_in_trading_calendar"]:
        raise RuntimeError(f"Holiday state data check failed: {data_checks}")
    if int(data_checks["state_rows_with_2026_or_later"]) > 0 or int(data_checks["state_rows_outside_requested_years"]) > 0:
        raise RuntimeError(f"Holiday state year-range check failed: {data_checks}")

    calendar_path = TIMING_DIR / f"{ts}_h363_vietnam_holiday_timing_calendar.parquet"
    clusters_path = TIMING_DIR / f"{ts}_h363_vietnam_holiday_timing_clusters.parquet"
    holiday_states.to_parquet(calendar_path, index=False)
    holiday_clusters.to_parquet(clusters_path, index=False)
    print(
        f"H363: calendar ok ({len(holiday_states):,} state rows, {len(holiday_clusters):,} clusters); loading payoff panel...",
        flush=True,
    )

    audit_states = _expand_audit_states(holiday_states)
    audit_states_path = TIMING_DIR / f"{ts}_h363_vietnam_holiday_timing_audit_states.parquet"
    audit_states.to_parquet(audit_states_path, index=False)

    panel, full_library_columns = _load_base_panel(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        fwd_rel_5d_path=Path(args.fwd_rel_5d),
        fwd_rel_1d_path=Path(args.fwd_rel_1d_cache),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    holiday_dates = set(pd.to_datetime(holiday_states["time"], errors="coerce").dt.normalize().dropna().tolist())
    panel["holiday_any_state"] = panel["time"].isin(holiday_dates)

    print(
        f"H363: evaluating {audit_states['state_label'].nunique():,} sparse states across {len(METRIC_SPECS):,} metrics...",
        flush=True,
    )
    results, active_matches, yearly = _evaluate(panel, audit_states)
    state_results, decision_summary = _decide(results, yearly)

    passed = state_results.loc[state_results["decision"].eq("PASSED") & state_results["state_scope"].isin(["family", "group"])].copy()
    portfolio_summary: dict[str, object] = {"portfolio_run": False, "portfolio_reason": "payoff_gate_not_passed"}
    if not passed.empty and not args.skip_portfolio:
        passed = passed.sort_values(["score"], ascending=False).reset_index(drop=True)
        print(f"H363: payoff passed for {passed.iloc[0]['state_label']}; running fixed sparse portfolio audit...", flush=True)
        portfolio_summary = _run_sparse_portfolio(
            args=args,
            ts=ts,
            audit_states=audit_states,
            passed_state=passed.iloc[0],
            full_library_columns=full_library_columns,
        )
    elif not passed.empty and args.skip_portfolio:
        portfolio_summary = {"portfolio_run": False, "portfolio_reason": "skip_portfolio_flag"}

    results_path = OUT_DIR / f"{ts}_h363_vietnam_holiday_timing_payoff_results.parquet"
    state_results_path = OUT_DIR / f"{ts}_h363_vietnam_holiday_timing_state_results.parquet"
    active_matches_path = OUT_DIR / f"{ts}_h363_vietnam_holiday_timing_active_matches.parquet"
    yearly_path = OUT_DIR / f"{ts}_h363_vietnam_holiday_timing_yearly_lifts.parquet"
    details_path = RUN_SUMMARY_DIR / f"{ts}_h363_vietnam_holiday_timing_details.json"

    results.to_parquet(results_path, index=False)
    state_results.to_parquet(state_results_path, index=False)
    active_matches.to_parquet(active_matches_path, index=False)
    yearly.to_parquet(yearly_path, index=False)

    summary = {
        **decision_summary,
        "portfolio": _json_safe(portfolio_summary),
        "protocol": DEFAULT_PROTOCOL.describe(),
        "calendar": {
            "state_rows": int(len(holiday_states)),
            "state_dates": int(pd.to_datetime(holiday_states["time"]).nunique()) if not holiday_states.empty else 0,
            "clusters": int(len(holiday_clusters)),
            "families": sorted(holiday_states["holiday_family"].dropna().unique().tolist()) if not holiday_states.empty else [],
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "data_checks": data_checks,
        },
        "panel": {
            "rows": int(len(panel)),
            "dates": int(panel["time"].nunique()),
            "tickers": int(panel["ticker"].nunique()),
            "holiday_any_state_rows": int(panel["holiday_any_state"].sum()),
            "holiday_any_state_dates": int(panel.loc[panel["holiday_any_state"], "time"].nunique()),
            "top_book_rows": int(panel["full_library_top_book"].sum()),
        },
        "thresholds": {
            "primary_metric": PRIMARY_METRIC,
            "mean_min_lift": MEAN_MIN_LIFT,
            "q10_max_worsening": Q10_MAX_WORSENING,
            "bad_tail_max_worsening": BAD_TAIL_MAX_WORSENING,
            "hit_rate_max_worsening": HIT_RATE_MAX_WORSENING,
            "min_validation_topbook_rows": MIN_VALIDATION_TOPBOOK_ROWS,
            "min_validation_dates": MIN_VALIDATION_DATES,
            "min_confirmation_topbook_rows": MIN_CONFIRMATION_TOPBOOK_ROWS,
            "min_confirmation_dates": MIN_CONFIRMATION_DATES,
            "min_positive_years": MIN_POSITIVE_YEARS,
            "max_single_year_positive_lift_share": MAX_SINGLE_YEAR_POSITIVE_LIFT_SHARE,
            "holiday_bonus_or_veto": HOLIDAY_BONUS,
            "base_rank_floor": BASE_RANK_FLOOR,
        },
        "source_notes": {
            "legal_major_set": (
                "Labor Code Article 112 major public holidays: New Year, Tet, Hung Kings, "
                "Reunification Day, Labor Day, and National Day plus adjacent official day."
            ),
            "closure_inference": "Closure clusters are inferred from missing VNINDEX trading dates around legal anchors.",
            "research_split": "2015-2022 dev, 2023-2024 validation, 2025 confirmation, 2026+ excluded.",
        },
    }
    details = {
        "summary": _json_safe(summary),
        "state_results": _json_safe(state_results.to_dict(orient="records")),
        "phase_metric_results_head": _json_safe(results.head(500).to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(details, indent=2, default=str), encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_vietnam_holiday_timing_payoff",
        name="h363_vietnam_holiday_timing_payoff",
        summary=summary,
        artifacts={
            "holiday_calendar": calendar_path,
            "holiday_clusters": clusters_path,
            "audit_states": audit_states_path,
            "results": results_path,
            "state_results": state_results_path,
            "active_matches": active_matches_path,
            "yearly_lifts": yearly_path,
            "details": details_path,
            **_json_safe(portfolio_summary.get("artifacts", {})),
        },
        metadata={
            "inputs": {
                "matrix": Path(args.matrix),
                "tradability": Path(args.tradability),
                "stock_dir": Path(args.stock_dir),
                "benchmark": Path(args.benchmark),
                "fwd_rel_5d": Path(args.fwd_rel_5d),
                "fwd_rel_1d_cache": Path(args.fwd_rel_1d_cache),
            },
            "notes": "2026+ rows excluded; controls are non-holiday rows matched by phase, S1 bucket, and full-library bucket.",
        },
    )

    print("\nH363: VIETNAM HOLIDAY TIMING PAYOFF")
    print(f"  payoff verdict: {summary['verdict']}")
    print(f"  best state: {summary['best_state']['state_label']} ({summary['best_state']['decision']})")
    print(f"  passed states: {summary['passed_state_count']}")
    print(f"  portfolio run: {bool(portfolio_summary.get('portfolio_run'))}")
    if portfolio_summary.get("portfolio_run"):
        print(f"  portfolio verdict: {portfolio_summary.get('portfolio_verdict')}")
        print(f"  portfolio state: {portfolio_summary.get('portfolio_state_label')} / {portfolio_summary.get('portfolio_direction')}")
        print(f"  validation rel delta: {(_safe_float(portfolio_summary.get('validation_relative_delta')) or 0.0) * 100:+.2f}%")
        print(f"  confirmation rel delta: {(_safe_float(portfolio_summary.get('confirmation_relative_delta')) or 0.0) * 100:+.2f}%")
    print(f"  calendar rows/dates: {summary['calendar']['state_rows']:,} / {summary['calendar']['state_dates']:,}")
    print(f"  summary: {summary_path}")


if __name__ == "__main__":
    main()
