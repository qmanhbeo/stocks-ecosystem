"""
H354: dividend-clock payoff audit.

Question:
    Did the old dividend-calendar branch fail because it was used as a broad
    model input, while the useful effect, if any, is only a sparse pre/post
    ex-dividend payoff or risk-filter clock?

Design:
    - do not retrain the XS model or tune dividend-calendar features
    - use the existing dense dividend calendar as the only state source
    - restrict controls to the same dividend-calendar ticker universe
    - match active rows to non-dividend-window controls by date and S1 bucket,
      with date-only fallback
    - evaluate fwd_rel_5d payoff shape, S1 actual lift, and tradability
    - exclude 2026 entirely
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_protocol import ResearchProtocol, phase_mask  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


DIVIDEND_PATH = data_path("features/xs_dividend_calendar.parquet")
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
FUTURE_REL_5D_PATH = ROOT / "artifacts" / "cache" / "future_rel_return_5d_hose.parquet"
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2015,
    dev_end_year=2022,
    validation_start_year=2023,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

MATCH_BUCKETS = 5
MIN_ACTIVE_ROWS = 80
MIN_ACTIVE_DATES = 40
MEAN_MIN_LIFT = 0.002
DEV_MEAN_MIN_LIFT = -0.001
Q10_MAX_WORSENING = -0.0025
BAD_TAIL_MAX_WORSENING = 0.010
HIT_RATE_MAX_WORSENING = -0.020
CAN_BUY_MAX_WORSENING = -0.050
BAD_TAIL_THRESHOLD = -0.03

STATE_SPECS = (
    {
        "state_name": "pre_ex_20d",
        "state_note": "Dividend calendar pre-ex window, up to 20 trading days before ex date.",
        "state_kind": "candidate",
        "control_exclude_col": "any_dividend_window",
    },
    {
        "state_name": "pre_ex_10d",
        "state_note": "Dividend calendar 1-10 trading days before ex date.",
        "state_kind": "candidate",
        "control_exclude_col": "any_dividend_window",
    },
    {
        "state_name": "pre_ex_5d",
        "state_note": "Dividend calendar 1-5 trading days before ex date.",
        "state_kind": "candidate",
        "control_exclude_col": "any_dividend_window",
    },
    {
        "state_name": "post_ex_5d",
        "state_note": "Dividend calendar 0-5 trading days after ex date.",
        "state_kind": "candidate",
        "control_exclude_col": "any_dividend_window",
    },
    {
        "state_name": "post_ex_20d",
        "state_note": "Dividend calendar post-ex window, up to 20 trading days after ex date.",
        "state_kind": "candidate",
        "control_exclude_col": "any_dividend_window",
    },
    {
        "state_name": "clustered_div_count_30d",
        "state_note": "At least two dividend events inside the trailing/nearby 30-day calendar field.",
        "state_kind": "candidate",
        "control_exclude_col": "any_dividend_window",
    },
    {
        "state_name": "any_dividend_window",
        "state_note": "Diagnostic union of pre/post dividend windows.",
        "state_kind": "diagnostic",
        "control_exclude_col": "any_dividend_window",
    },
)

METRIC_SPECS = (
    ("fwd_rel_5d", "forward 5d relative return", BAD_TAIL_THRESHOLD),
    ("actual", "binary S1 target", 0.0),
)


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _daily_rank(series: pd.Series, time_index: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=True,
    )


def _load_panel() -> pd.DataFrame:
    s1 = pd.read_parquet(S1_PATH, columns=["time", "ticker", "xs_proba", "actual"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()
    s1 = s1.loc[s1["time"].dt.year.between(2015, 2025)].copy()
    s1["s1_rank_full"] = _daily_rank(s1["xs_proba"], s1["time"])
    s1["s1_bucket"] = (
        np.ceil(pd.to_numeric(s1["s1_rank_full"], errors="coerce") * MATCH_BUCKETS)
        .clip(lower=1, upper=MATCH_BUCKETS)
        .astype("Int64")
    )

    dividend = pd.read_parquet(DIVIDEND_PATH).copy()
    dividend["time"] = pd.to_datetime(dividend["time"], errors="coerce").dt.normalize()
    dividend["ticker"] = dividend["ticker"].astype(str).str.upper()
    dividend = dividend.loc[dividend["time"].dt.year.between(2015, 2025)].copy()

    future_rel = pd.read_parquet(FUTURE_REL_5D_PATH).copy()
    future_rel["time"] = pd.to_datetime(future_rel["time"], errors="coerce").dt.normalize()
    future_rel["ticker"] = future_rel["ticker"].astype(str).str.upper()
    future_rel = future_rel.loc[future_rel["time"].dt.year.between(2015, 2025)].copy()
    future_rel = future_rel[["time", "ticker", "fwd_rel_5d"]]

    tradability = pd.read_parquet(
        TRADABILITY_PATH,
        columns=["time", "ticker", "can_buy_next_open", "can_sell_next_open"],
    ).copy()
    tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce").dt.normalize()
    tradability["ticker"] = tradability["ticker"].astype(str).str.upper()
    tradability = tradability.loc[tradability["time"].dt.year.between(2015, 2025)].copy()

    panel = dividend.merge(s1, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(future_rel, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(tradability, on=["time", "ticker"], how="left", validate="one_to_one")

    numeric_cols = [
        "days_to_ex_div",
        "days_since_ex_div",
        "pre_div_window",
        "post_div_window",
        "div_count_30d",
        "xs_proba",
        "actual",
        "fwd_rel_5d",
    ]
    for column in numeric_cols:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")
    for column in ("can_buy_next_open", "can_sell_next_open"):
        panel[column] = panel[column].fillna(False).astype(bool)

    panel["pre_ex_20d"] = panel["pre_div_window"].fillna(0.0) > 0.0
    panel["pre_ex_10d"] = panel["days_to_ex_div"].between(1, 10, inclusive="both")
    panel["pre_ex_5d"] = panel["days_to_ex_div"].between(1, 5, inclusive="both")
    panel["post_ex_5d"] = panel["days_since_ex_div"].between(0, 5, inclusive="both")
    panel["post_ex_20d"] = panel["post_div_window"].fillna(0.0) > 0.0
    panel["clustered_div_count_30d"] = panel["div_count_30d"].fillna(0.0) >= 2.0
    panel["any_dividend_window"] = panel["pre_ex_20d"] | panel["post_ex_20d"]
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _reference_table(frame: pd.DataFrame, keys: list[str], metric_col: str, bad_threshold: float) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                *keys,
                "matched_mean",
                "matched_median",
                "matched_q10",
                "matched_q90",
                "matched_hit_rate",
                "matched_bad_tail_rate",
                "matched_can_buy_rate",
                "matched_can_sell_rate",
                "matched_control_rows",
            ]
        )
    work = frame.copy()
    work["_hit"] = (pd.to_numeric(work[metric_col], errors="coerce") > 0.0).astype(float)
    work["_bad_tail"] = (pd.to_numeric(work[metric_col], errors="coerce") <= bad_threshold).astype(float)
    work["_can_buy"] = work["can_buy_next_open"].astype(float)
    work["_can_sell"] = work["can_sell_next_open"].astype(float)
    grouped = work.groupby(keys, dropna=False)
    refs = grouped.agg(
        matched_mean=(metric_col, "mean"),
        matched_median=(metric_col, "median"),
        matched_hit_rate=("_hit", "mean"),
        matched_bad_tail_rate=("_bad_tail", "mean"),
        matched_can_buy_rate=("_can_buy", "mean"),
        matched_can_sell_rate=("_can_sell", "mean"),
        matched_control_rows=(metric_col, "count"),
    ).reset_index()
    quantiles = (
        grouped[metric_col]
        .quantile([0.10, 0.90])
        .unstack(level=-1)
        .rename(columns={0.10: "matched_q10", 0.90: "matched_q90"})
        .reset_index()
    )
    return refs.merge(quantiles, on=keys, how="left", validate="one_to_one")


def _build_ref_cache(panel: pd.DataFrame) -> dict[tuple[str, str, str, str], pd.DataFrame]:
    cache: dict[tuple[str, str, str, str], pd.DataFrame] = {}
    levels = (
        ("date_s1", ["time", "s1_bucket"]),
        ("date", ["time"]),
    )
    exclude_cols = sorted({str(spec["control_exclude_col"]) for spec in STATE_SPECS})
    for phase in ("dev", "validation", "confirmation"):
        phase_frame = panel.loc[phase_mask(panel, phase, protocol=PROTOCOL)].copy()
        for exclude_col in exclude_cols:
            for metric_col, _metric_note, bad_threshold in METRIC_SPECS:
                metric = pd.to_numeric(phase_frame[metric_col], errors="coerce")
                controls = phase_frame.loc[
                    ~phase_frame[exclude_col].fillna(False).astype(bool)
                    & metric.notna()
                    & phase_frame["s1_bucket"].notna()
                ].copy()
                for level_name, keys in levels:
                    cache[(phase, exclude_col, metric_col, level_name)] = _reference_table(
                        controls, keys, metric_col, float(bad_threshold)
                    )
    return cache


def _match_active_rows(
    active: pd.DataFrame,
    *,
    phase: str,
    exclude_col: str,
    metric_col: str,
    ref_cache: dict[tuple[str, str, str, str], pd.DataFrame],
) -> pd.DataFrame:
    if active.empty:
        return pd.DataFrame()
    current = active[
        [
            "time",
            "ticker",
            "s1_bucket",
            metric_col,
            "can_buy_next_open",
            "can_sell_next_open",
        ]
    ].copy()
    current["_row_id"] = np.arange(len(current))
    remaining = current.copy()
    matched_parts: list[pd.DataFrame] = []
    for level_name, keys in (("date_s1", ["time", "s1_bucket"]), ("date", ["time"])):
        if remaining.empty:
            break
        refs = ref_cache[(phase, exclude_col, metric_col, level_name)]
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
            "matched_can_buy_rate",
            "matched_can_sell_rate",
            "matched_control_rows",
        ):
            remaining[col] = np.nan
        remaining["match_level"] = "unmatched"
        matched_parts.append(remaining)
    return pd.concat(matched_parts, ignore_index=True) if matched_parts else pd.DataFrame()


def _phase_metric_summary(
    panel: pd.DataFrame,
    *,
    state_spec: dict[str, str],
    phase: str,
    metric_col: str,
    metric_note: str,
    bad_threshold: float,
    ref_cache: dict[tuple[str, str, str, str], pd.DataFrame],
) -> tuple[dict[str, object], pd.DataFrame]:
    phase_frame = panel.loc[phase_mask(panel, phase, protocol=PROTOCOL)].copy()
    state = phase_frame[state_spec["state_name"]].fillna(False).astype(bool)
    active = phase_frame.loc[state & pd.to_numeric(phase_frame[metric_col], errors="coerce").notna()].copy()
    matches = _match_active_rows(
        active,
        phase=phase,
        exclude_col=str(state_spec["control_exclude_col"]),
        metric_col=metric_col,
        ref_cache=ref_cache,
    )
    matched = matches.loc[matches["match_level"].ne("unmatched")].copy() if not matches.empty else pd.DataFrame()

    active_metric = pd.to_numeric(active[metric_col], errors="coerce")
    active_rows = int(len(active))
    matched_rows = int(len(matched))
    active_mean = _safe_float(active_metric.mean()) if active_rows else None
    matched_mean = _safe_float(matched["matched_mean"].mean()) if matched_rows else None
    active_median = _safe_float(active_metric.median()) if active_rows else None
    matched_median = _safe_float(matched["matched_median"].mean()) if matched_rows else None
    active_q10 = _safe_float(active_metric.quantile(0.10)) if active_rows else None
    matched_q10 = _safe_float(matched["matched_q10"].mean()) if matched_rows else None
    active_q90 = _safe_float(active_metric.quantile(0.90)) if active_rows else None
    matched_q90 = _safe_float(matched["matched_q90"].mean()) if matched_rows else None
    active_hit_rate = _safe_float((active_metric > 0.0).mean()) if active_rows else None
    matched_hit_rate = _safe_float(matched["matched_hit_rate"].mean()) if matched_rows else None
    active_bad_tail_rate = _safe_float((active_metric <= bad_threshold).mean()) if active_rows else None
    matched_bad_tail_rate = _safe_float(matched["matched_bad_tail_rate"].mean()) if matched_rows else None
    active_can_buy_rate = _safe_float(active["can_buy_next_open"].mean()) if active_rows else None
    matched_can_buy_rate = _safe_float(matched["matched_can_buy_rate"].mean()) if matched_rows else None
    active_can_sell_rate = _safe_float(active["can_sell_next_open"].mean()) if active_rows else None
    matched_can_sell_rate = _safe_float(matched["matched_can_sell_rate"].mean()) if matched_rows else None

    daily = pd.DataFrame()
    if matched_rows:
        daily = (
            matched.assign(mean_lift=pd.to_numeric(matched[metric_col], errors="coerce") - matched["matched_mean"])
            .groupby("time", as_index=False)
            .agg(mean_lift=("mean_lift", "mean"), active_rows=("_row_id", "count"))
        )

    summary = {
        "state": state_spec["state_name"],
        "state_note": state_spec["state_note"],
        "state_kind": state_spec["state_kind"],
        "phase": phase,
        "metric": metric_col,
        "metric_note": metric_note,
        "active_rows": active_rows,
        "active_dates": int(active["time"].nunique()) if active_rows else 0,
        "active_tickers": int(active["ticker"].nunique()) if active_rows else 0,
        "matched_rows": matched_rows,
        "matched_row_rate": float(matched_rows / active_rows) if active_rows else 0.0,
        "avg_matched_control_rows": _safe_float(matched["matched_control_rows"].mean()) if matched_rows else None,
        "active_mean": active_mean,
        "matched_mean": matched_mean,
        "mean_lift": None if active_mean is None or matched_mean is None else active_mean - matched_mean,
        "active_median": active_median,
        "matched_median": matched_median,
        "median_lift": None if active_median is None or matched_median is None else active_median - matched_median,
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
        "bad_tail_rate_lift": (
            None
            if active_bad_tail_rate is None or matched_bad_tail_rate is None
            else active_bad_tail_rate - matched_bad_tail_rate
        ),
        "active_can_buy_rate": active_can_buy_rate,
        "matched_can_buy_rate": matched_can_buy_rate,
        "can_buy_rate_lift": None
        if active_can_buy_rate is None or matched_can_buy_rate is None
        else active_can_buy_rate - matched_can_buy_rate,
        "active_can_sell_rate": active_can_sell_rate,
        "matched_can_sell_rate": matched_can_sell_rate,
        "can_sell_rate_lift": None
        if active_can_sell_rate is None or matched_can_sell_rate is None
        else active_can_sell_rate - matched_can_sell_rate,
        "daily_mean_lift_days": int(len(daily)),
        "daily_mean_lift_hit_rate": _safe_float((daily["mean_lift"] > 0.0).mean()) if not daily.empty else None,
        "date_s1_match_rows": int((matches["match_level"] == "date_s1").sum()) if not matches.empty else 0,
        "date_match_rows": int((matches["match_level"] == "date").sum()) if not matches.empty else 0,
        "unmatched_rows": int((matches["match_level"] == "unmatched").sum()) if not matches.empty else 0,
    }
    if not matches.empty:
        matches["state"] = state_spec["state_name"]
        matches["phase"] = phase
        matches["metric"] = metric_col
    return summary, matches


def _evaluate(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ref_cache = _build_ref_cache(panel)
    summaries: list[dict[str, object]] = []
    match_frames: list[pd.DataFrame] = []
    for state_spec in STATE_SPECS:
        for phase in ("dev", "validation", "confirmation"):
            for metric_col, metric_note, bad_threshold in METRIC_SPECS:
                summary, matches = _phase_metric_summary(
                    panel,
                    state_spec=state_spec,
                    phase=phase,
                    metric_col=metric_col,
                    metric_note=metric_note,
                    bad_threshold=float(bad_threshold),
                    ref_cache=ref_cache,
                )
                summaries.append(summary)
                if not matches.empty:
                    match_frames.append(matches)
    results = pd.DataFrame(summaries)
    active_matches = pd.concat(match_frames, ignore_index=True) if match_frames else pd.DataFrame()
    return results, active_matches


def _row(results: pd.DataFrame, state: str, phase: str, metric: str) -> pd.Series:
    match = results.loc[(results["state"] == state) & (results["phase"] == phase) & (results["metric"] == metric)]
    if match.empty:
        raise ValueError(f"Missing result for {state} / {phase} / {metric}")
    return match.iloc[0]


def _num(row: pd.Series, key: str, default: float = 0.0) -> float:
    value = pd.to_numeric(row.get(key), errors="coerce")
    return default if pd.isna(value) else float(value)


def _phase_viable(row: pd.Series) -> bool:
    return (
        int(row["active_rows"]) >= MIN_ACTIVE_ROWS
        and int(row["active_dates"]) >= MIN_ACTIVE_DATES
        and _num(row, "matched_row_rate", 0.0) >= 0.95
    )


def _phase_payoff_clean(row: pd.Series, *, require_mean: bool) -> bool:
    mean_floor = MEAN_MIN_LIFT if require_mean else DEV_MEAN_MIN_LIFT
    return (
        _num(row, "mean_lift", -9.0) >= mean_floor
        and _num(row, "q10_lift", -9.0) >= Q10_MAX_WORSENING
        and _num(row, "bad_tail_rate_lift", 9.0) <= BAD_TAIL_MAX_WORSENING
        and _num(row, "hit_rate_lift", -9.0) >= HIT_RATE_MAX_WORSENING
        and _num(row, "can_buy_rate_lift", -9.0) >= CAN_BUY_MAX_WORSENING
    )


def _decide(results: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    state_rows: list[dict[str, object]] = []
    for state_spec in STATE_SPECS:
        state = state_spec["state_name"]
        row: dict[str, object] = {
            "state": state,
            "state_note": state_spec["state_note"],
            "state_kind": state_spec["state_kind"],
        }
        phase_flags: dict[str, dict[str, bool]] = {}
        for phase in ("dev", "validation", "confirmation"):
            fwd = _row(results, state, phase, "fwd_rel_5d")
            actual = _row(results, state, phase, "actual")
            viable = _phase_viable(fwd)
            clean = viable and _phase_payoff_clean(fwd, require_mean=phase != "dev")
            phase_flags[phase] = {"viable": viable, "clean": clean}
            for key in (
                "active_rows",
                "active_dates",
                "mean_lift",
                "q10_lift",
                "q90_lift",
                "bad_tail_rate_lift",
                "hit_rate_lift",
                "can_buy_rate_lift",
                "daily_mean_lift_hit_rate",
            ):
                row[f"{phase}_fwd_{key}"] = _safe_float(fwd[key])
            row[f"{phase}_actual_mean_lift"] = _safe_float(actual["mean_lift"])
            row[f"{phase}_actual_hit_rate_lift"] = _safe_float(actual["hit_rate_lift"])

        if state_spec["state_kind"] != "candidate":
            decision = "DIAGNOSTIC"
            reason = "diagnostic_union_state"
        elif not (phase_flags["validation"]["viable"] and phase_flags["confirmation"]["viable"]):
            decision = "SKIPPED"
            reason = "insufficient_validation_or_confirmation_active_rows"
        elif phase_flags["validation"]["clean"] and phase_flags["confirmation"]["clean"]:
            decision = "PASSED"
            reason = "positive_matched_return_lift_without_worse_tail_or_tradability_in_validation_and_confirmation"
        elif (
            _num(_row(results, state, "validation", "fwd_rel_5d"), "mean_lift", -9.0) > 0.0
            and _num(_row(results, state, "confirmation", "fwd_rel_5d"), "mean_lift", -9.0) > 0.0
        ):
            decision = "MIXED"
            reason = "positive_mean_lift_in_validation_and_confirmation_but_risk_or_gate_not_clean"
        elif max(
            _num(_row(results, state, "validation", "fwd_rel_5d"), "mean_lift", -9.0),
            _num(_row(results, state, "confirmation", "fwd_rel_5d"), "mean_lift", -9.0),
        ) > MEAN_MIN_LIFT:
            decision = "MIXED"
            reason = "one_phase_payoff_hint_only"
        else:
            decision = "FAILED"
            reason = "no_clean_two_phase_matched_dividend_clock_payoff"
        row["decision"] = decision
        row["reason"] = reason
        row["score"] = (
            _num(pd.Series(row), "validation_fwd_mean_lift", -9.0)
            + _num(pd.Series(row), "confirmation_fwd_mean_lift", -9.0)
            + 0.25 * _num(pd.Series(row), "validation_fwd_q90_lift", -9.0)
            + 0.25 * _num(pd.Series(row), "confirmation_fwd_q90_lift", -9.0)
            + _num(pd.Series(row), "validation_fwd_q10_lift", -9.0)
            + _num(pd.Series(row), "confirmation_fwd_q10_lift", -9.0)
            - _num(pd.Series(row), "validation_fwd_bad_tail_rate_lift", 9.0)
            - _num(pd.Series(row), "confirmation_fwd_bad_tail_rate_lift", 9.0)
        )
        state_rows.append(row)

    state_results = pd.DataFrame(state_rows)
    candidates = state_results.loc[state_results["state_kind"].eq("candidate")].copy()
    decision_rank = {"PASSED": 0, "MIXED": 1, "FAILED": 2, "SKIPPED": 3, "DIAGNOSTIC": 9}
    candidates["decision_rank"] = candidates["decision"].map(decision_rank).fillna(9)
    best = candidates.sort_values(["decision_rank", "score"], ascending=[True, False]).iloc[0]

    if (candidates["decision"] == "PASSED").any():
        verdict = "PASSED"
        branch_decision = (
            "A dividend-clock state survives matched payoff testing. Advance only to a narrow sparse "
            "risk-filter or portfolio-sizing audit; do not reopen dividend-calendar model features."
        )
    elif (candidates["decision"] == "MIXED").any():
        verdict = "MIXED"
        branch_decision = (
            "Dividend-clock states have at most local payoff hints. Keep as offline calendar evidence "
            "unless a stricter portfolio-level contract needs a sparse clock."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The dividend clock does not produce a clean matched payoff state. Keep the old H31 "
            "dividend-calendar branch closed under current data."
        )

    summary = {
        "decision": verdict,
        "best_state": _json_safe(best.to_dict()),
        "branch_decision": branch_decision,
        "candidate_state_count": int(len(candidates)),
        "state_decisions": _json_safe(
            state_results[["state", "state_kind", "decision", "reason", "score"]].to_dict(orient="records")
        ),
    }
    return state_results.drop(columns=["decision_rank"], errors="ignore"), summary


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel = _load_panel()
    results, active_matches = _evaluate(panel)
    state_results, decision_summary = _decide(results)

    artifact_stem = f"{ts}_h354_dividend_clock_payoff"
    results_path = OUT_DIR / f"{artifact_stem}_results.parquet"
    state_results_path = OUT_DIR / f"{artifact_stem}_state_results.parquet"
    active_matches_path = OUT_DIR / f"{artifact_stem}_active_matches.parquet"
    details_path = DETAILS_DIR / f"{artifact_stem}_details.json"

    results.to_parquet(results_path, index=False)
    state_results.to_parquet(state_results_path, index=False)
    active_matches.to_parquet(active_matches_path, index=False)

    summary = {
        **decision_summary,
        "protocol": PROTOCOL.describe(),
        "panel": {
            "rows": int(len(panel)),
            "tickers": int(panel["ticker"].nunique()),
            "dates": int(panel["time"].nunique()),
            "start": panel["time"].min().isoformat() if not panel.empty else None,
            "end": panel["time"].max().isoformat() if not panel.empty else None,
            "any_dividend_window_rows": int(panel["any_dividend_window"].sum()),
            "any_dividend_window_dates": int(panel.loc[panel["any_dividend_window"], "time"].nunique()),
        },
        "candidate_definitions": _json_safe(
            {spec["state_name"]: spec["state_note"] for spec in STATE_SPECS}
        ),
        "thresholds": {
            "min_active_rows": MIN_ACTIVE_ROWS,
            "min_active_dates": MIN_ACTIVE_DATES,
            "mean_min_lift": MEAN_MIN_LIFT,
            "dev_mean_min_lift": DEV_MEAN_MIN_LIFT,
            "q10_max_worsening": Q10_MAX_WORSENING,
            "bad_tail_max_worsening": BAD_TAIL_MAX_WORSENING,
            "hit_rate_max_worsening": HIT_RATE_MAX_WORSENING,
            "can_buy_max_worsening": CAN_BUY_MAX_WORSENING,
            "bad_tail_threshold": BAD_TAIL_THRESHOLD,
        },
    }
    details = {
        "summary": _json_safe(summary),
        "state_results": _json_safe(state_results.to_dict(orient="records")),
        "phase_metric_results": _json_safe(results.to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(details, indent=2), encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_dividend_clock_payoff",
        name="h354_dividend_clock_payoff",
        summary=summary,
        artifacts={
            "results": results_path,
            "state_results": state_results_path,
            "active_matches": active_matches_path,
            "details": details_path,
        },
        metadata={
            "inputs": {
                "dividend_calendar": DIVIDEND_PATH,
                "s1": S1_PATH,
                "future_rel_5d": FUTURE_REL_5D_PATH,
                "tradability": TRADABILITY_PATH,
            },
            "notes": "2026 rows excluded; controls restricted to same dividend-calendar ticker universe.",
        },
    )
    print(summary_path)
    print(pd.DataFrame(state_results).sort_values(["decision", "score"], ascending=[True, False]).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
