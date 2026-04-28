"""
H352: event-v2 optionality payoff audit.

Question:
    Did the event-v2 states fail additive promotion because they are sparse
    tail-payoff / risk-filter states rather than mean-rank overlays?

Design:
    - reuse the saved H321 cascade panel; do not refit event thresholds
    - exclude 2026+ rows completely
    - compare active event rows against matched non-event controls by date,
      S1 bucket, and sector, with date/S1 and date fallbacks
    - evaluate payoff shape, downside tail, hit rate, and tradability rather
      than another additive score overlay
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

from src.additive_selector_research import resolve_summary_artifact  # noqa: E402
from src.research_protocol import ResearchProtocol, phase_mask  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


H321_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_hawkes_disclosure_cascade.json"
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

MATCH_BUCKETS = 5
MIN_ACTIVE_ROWS = 80
MIN_ACTIVE_DATES = 40
UPSIDE_TAIL_MIN_LIFT = 0.005
DOWNSIDE_TAIL_MAX_WORSENING = -0.0025
BAD_TAIL_MAX_WORSENING = 0.010
MEAN_MIN_LIFT = -0.001
HIT_RATE_MAX_WORSENING = -0.020
CAN_BUY_MAX_WORSENING = -0.050
BAD_TAIL_THRESHOLD = -0.03

METRIC_SPECS = (
    ("fwd_rel_5d", "relative forward 5d return", BAD_TAIL_THRESHOLD),
    ("actual", "binary S1 target", 0.0),
)

STATE_SPECS = (
    {
        "state_name": "event_today_novel20",
        "state_note": "H310 same-day first-public event state",
        "state_kind": "candidate",
        "state_group": "same_day",
        "control_exclude_col": "event_today_any_v2",
    },
    {
        "state_name": "today_self_accel_high",
        "state_note": "H321 same-day fast self-excitation cascade state",
        "state_kind": "candidate",
        "state_group": "same_day",
        "control_exclude_col": "event_today_any_v2",
    },
    {
        "state_name": "today_high_sector_low_self",
        "state_note": "H321 high sector cascade / low own-prior state",
        "state_kind": "candidate",
        "state_group": "same_day",
        "control_exclude_col": "event_today_any_v2",
    },
    {
        "state_name": "recent5_low_self_no_today",
        "state_note": "H321 recent low self-intensity state, no same-day event",
        "state_kind": "candidate",
        "state_group": "recent_window",
        "control_exclude_col": "recent5_any_v2_event",
    },
    {
        "state_name": "recent5_high_self_no_today",
        "state_note": "H321 recent high self-intensity state, no same-day event",
        "state_kind": "candidate",
        "state_group": "recent_window",
        "control_exclude_col": "recent5_any_v2_event",
    },
    {
        "state_name": "event_today_follow20",
        "state_note": "H310 same-day follow-up diagnostic state",
        "state_kind": "diagnostic",
        "state_group": "same_day",
        "control_exclude_col": "event_today_any_v2",
    },
    {
        "state_name": "v1_proxy_5d",
        "state_note": "Broad v1 company-event proxy diagnostic",
        "state_kind": "diagnostic",
        "state_group": "broad_event",
        "control_exclude_col": "v1_proxy_5d",
    },
)


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


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _daily_rank(series: pd.Series, time_index: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=True,
    )


def _load_panel() -> pd.DataFrame:
    panel_path = resolve_summary_artifact(H321_SUMMARY_PATH, "panel")
    state_cols = sorted({spec["state_name"] for spec in STATE_SPECS} | {spec["control_exclude_col"] for spec in STATE_SPECS})
    panel_cols = [
        "time",
        "ticker",
        "xs_proba",
        "actual",
        "fwd_rel_5d",
        "sector_label",
        *state_cols,
    ]
    panel = pd.read_parquet(panel_path, columns=panel_cols).copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel["ticker"] = panel["ticker"].astype(str).str.upper()
    panel = panel.loc[panel["time"].dt.year.between(2023, 2025)].copy()

    tradability = pd.read_parquet(
        TRADABILITY_PATH,
        columns=["time", "ticker", "can_buy_next_open", "can_sell_next_open"],
    ).copy()
    tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce").dt.normalize()
    tradability["ticker"] = tradability["ticker"].astype(str).str.upper()
    tradability = tradability.loc[tradability["time"].dt.year.between(2023, 2025)].copy()

    panel = panel.merge(tradability, on=["time", "ticker"], how="left", validate="one_to_one")
    for col in state_cols:
        panel[col] = panel[col].fillna(False).astype(bool)
    for col in ("xs_proba", "actual", "fwd_rel_5d"):
        panel[col] = pd.to_numeric(panel[col], errors="coerce")
    for col in ("can_buy_next_open", "can_sell_next_open"):
        panel[col] = panel[col].fillna(False).astype(bool)
    panel["sector_label"] = panel["sector_label"].fillna("Unknown").astype(str)
    panel["s1_rank"] = _daily_rank(panel["xs_proba"], panel["time"])
    panel["s1_bucket"] = (
        np.ceil(pd.to_numeric(panel["s1_rank"], errors="coerce") * MATCH_BUCKETS)
        .clip(lower=1, upper=MATCH_BUCKETS)
        .astype("Int64")
    )
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
    refs = refs.merge(quantiles, on=keys, how="left", validate="one_to_one")
    return refs


def _build_ref_cache(panel: pd.DataFrame) -> dict[tuple[str, str, str, str], pd.DataFrame]:
    cache: dict[tuple[str, str, str, str], pd.DataFrame] = {}
    levels = (
        ("date_sector_s1", ["time", "sector_label", "s1_bucket"]),
        ("date_s1", ["time", "s1_bucket"]),
        ("date", ["time"]),
    )
    exclude_cols = sorted({str(spec["control_exclude_col"]) for spec in STATE_SPECS})
    for phase in ("dev", "validation", "confirmation"):
        phase_frame = panel.loc[phase_mask(panel, phase, protocol=PROTOCOL)].copy()
        for exclude_col in exclude_cols:
            for metric_col, _metric_note, bad_threshold in METRIC_SPECS:
                metric = pd.to_numeric(phase_frame[metric_col], errors="coerce")
                control_mask = (
                    ~phase_frame[exclude_col].fillna(False).astype(bool)
                    & metric.notna()
                    & phase_frame["s1_bucket"].notna()
                )
                controls = phase_frame.loc[
                    control_mask,
                    [
                        "time",
                        "sector_label",
                        "s1_bucket",
                        metric_col,
                        "can_buy_next_open",
                        "can_sell_next_open",
                    ],
                ].copy()
                for level_name, keys in levels:
                    cache[(phase, exclude_col, metric_col, level_name)] = _reference_table(
                        controls,
                        keys,
                        metric_col,
                        float(bad_threshold),
                    )
    return cache


def _matched_active_rows(
    frame: pd.DataFrame,
    *,
    state_col: str,
    control_exclude_col: str,
    metric_col: str,
    bad_threshold: float,
    phase: str,
    ref_cache: dict[tuple[str, str, str, str], pd.DataFrame],
) -> pd.DataFrame:
    metric = pd.to_numeric(frame[metric_col], errors="coerce")
    active_mask = frame[state_col].fillna(False).astype(bool) & metric.notna() & frame["s1_bucket"].notna()
    active = frame.loc[
        active_mask,
        [
            "time",
            "ticker",
            "sector_label",
            "s1_bucket",
            metric_col,
            "can_buy_next_open",
            "can_sell_next_open",
        ],
    ].copy()
    active = active.rename(columns={metric_col: "active_metric"})
    active["_row_id"] = np.arange(len(active), dtype=int)
    active["match_level"] = "unmatched"
    ref_cols = [
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
    for col in ref_cols:
        active[col] = np.nan

    if active.empty:
        return active

    levels = (
        ("date_sector_s1", ["time", "sector_label", "s1_bucket"]),
        ("date_s1", ["time", "s1_bucket"]),
        ("date", ["time"]),
    )
    remaining = active["_row_id"].to_numpy()
    for level_name, keys in levels:
        if len(remaining) == 0:
            break
        refs = ref_cache[(phase, control_exclude_col, metric_col, level_name)]
        if refs.empty:
            continue
        candidate = active.loc[active["_row_id"].isin(remaining), ["_row_id", *keys]].merge(
            refs,
            on=keys,
            how="left",
            validate="many_to_one",
        )
        matched = candidate.loc[candidate["matched_mean"].notna()].copy()
        if matched.empty:
            continue
        matched_ids = matched["_row_id"].astype(int).to_numpy()
        active_index = active.set_index("_row_id").index
        for col in ref_cols:
            values = matched.set_index("_row_id")[col]
            active.loc[active_index.isin(matched_ids), col] = active.loc[
                active_index.isin(matched_ids), "_row_id"
            ].map(values)
        active.loc[active_index.isin(matched_ids), "match_level"] = level_name
        remaining = np.setdiff1d(remaining, matched_ids, assume_unique=False)

    return active


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
    matches = _matched_active_rows(
        phase_frame,
        state_col=state_spec["state_name"],
        control_exclude_col=state_spec["control_exclude_col"],
        metric_col=metric_col,
        bad_threshold=bad_threshold,
        phase=phase,
        ref_cache=ref_cache,
    )
    matched = matches.loc[matches["matched_mean"].notna()].copy()
    active_metric = pd.to_numeric(matches["active_metric"], errors="coerce")
    matched_metric = pd.to_numeric(matched["active_metric"], errors="coerce")

    active_rows = int(len(matches))
    matched_rows = int(len(matched))
    active_dates = int(matches["time"].nunique()) if not matches.empty else 0
    active_tickers = int(matches["ticker"].nunique()) if not matches.empty else 0

    active_mean = _safe_float(active_metric.mean()) if not active_metric.empty else None
    matched_mean = _safe_float(matched["matched_mean"].mean()) if not matched.empty else None
    active_median = _safe_float(active_metric.median()) if not active_metric.empty else None
    matched_median = _safe_float(matched["matched_median"].mean()) if not matched.empty else None
    active_q10 = _safe_float(active_metric.quantile(0.10)) if not active_metric.empty else None
    matched_q10 = _safe_float(matched["matched_q10"].mean()) if not matched.empty else None
    active_q90 = _safe_float(active_metric.quantile(0.90)) if not active_metric.empty else None
    matched_q90 = _safe_float(matched["matched_q90"].mean()) if not matched.empty else None
    active_hit_rate = _safe_float((active_metric > 0.0).mean()) if not active_metric.empty else None
    matched_hit_rate = _safe_float(matched["matched_hit_rate"].mean()) if not matched.empty else None
    active_bad_tail_rate = _safe_float((active_metric <= bad_threshold).mean()) if not active_metric.empty else None
    matched_bad_tail_rate = _safe_float(matched["matched_bad_tail_rate"].mean()) if not matched.empty else None
    active_can_buy_rate = _safe_float(matches["can_buy_next_open"].mean()) if not matches.empty else None
    matched_can_buy_rate = _safe_float(matched["matched_can_buy_rate"].mean()) if not matched.empty else None
    active_can_sell_rate = _safe_float(matches["can_sell_next_open"].mean()) if not matches.empty else None
    matched_can_sell_rate = _safe_float(matched["matched_can_sell_rate"].mean()) if not matched.empty else None

    daily = pd.DataFrame()
    if not matched.empty:
        daily = (
            matched.assign(row_lift=matched_metric - pd.to_numeric(matched["matched_mean"], errors="coerce"))
            .groupby("time", as_index=False)
            .agg(active_rows=("ticker", "count"), mean_lift=("row_lift", "mean"))
        )

    summary = {
        "state": state_spec["state_name"],
        "state_note": state_spec["state_note"],
        "state_kind": state_spec["state_kind"],
        "state_group": state_spec["state_group"],
        "phase": phase,
        "metric": metric_col,
        "metric_note": metric_note,
        "control_exclude_col": state_spec["control_exclude_col"],
        "phase_rows": int(len(phase_frame)),
        "phase_dates": int(phase_frame["time"].nunique()) if not phase_frame.empty else 0,
        "active_rows": active_rows,
        "active_dates": active_dates,
        "active_tickers": active_tickers,
        "matched_rows": matched_rows,
        "matched_row_rate": float(matched_rows / active_rows) if active_rows else 0.0,
        "avg_matched_control_rows": _safe_float(matched["matched_control_rows"].mean()) if not matched.empty else None,
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
            None if active_bad_tail_rate is None or matched_bad_tail_rate is None else active_bad_tail_rate - matched_bad_tail_rate
        ),
        "active_can_buy_rate": active_can_buy_rate,
        "matched_can_buy_rate": matched_can_buy_rate,
        "can_buy_rate_lift": None if active_can_buy_rate is None or matched_can_buy_rate is None else active_can_buy_rate - matched_can_buy_rate,
        "active_can_sell_rate": active_can_sell_rate,
        "matched_can_sell_rate": matched_can_sell_rate,
        "can_sell_rate_lift": None
        if active_can_sell_rate is None or matched_can_sell_rate is None
        else active_can_sell_rate - matched_can_sell_rate,
        "daily_mean_lift_days": int(len(daily)),
        "daily_mean_lift_hit_rate": _safe_float((daily["mean_lift"] > 0.0).mean()) if not daily.empty else None,
        "date_sector_s1_match_rows": int((matches["match_level"] == "date_sector_s1").sum()) if not matches.empty else 0,
        "date_s1_match_rows": int((matches["match_level"] == "date_s1").sum()) if not matches.empty else 0,
        "date_match_rows": int((matches["match_level"] == "date").sum()) if not matches.empty else 0,
        "unmatched_rows": int((matches["match_level"] == "unmatched").sum()) if not matches.empty else 0,
    }

    matches["state"] = state_spec["state_name"]
    matches["phase"] = phase
    matches["metric"] = metric_col
    return summary, matches


def _evaluate(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries: list[dict[str, object]] = []
    match_frames: list[pd.DataFrame] = []
    ref_cache = _build_ref_cache(panel)
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
                match_frames.append(matches)
    results = pd.DataFrame(summaries)
    active_matches = pd.concat(match_frames, ignore_index=True) if match_frames else pd.DataFrame()
    return results, active_matches


def _result(results: pd.DataFrame, state: str, phase: str, metric: str) -> pd.Series:
    match = results.loc[(results["state"] == state) & (results["phase"] == phase) & (results["metric"] == metric)]
    if match.empty:
        raise ValueError(f"Missing result for {state} / {phase} / {metric}")
    return match.iloc[0]


def _num(row: pd.Series, key: str, default: float = 0.0) -> float:
    value = pd.to_numeric(row.get(key), errors="coerce")
    return default if pd.isna(value) else float(value)


def _phase_tail_good(row: pd.Series) -> bool:
    return (
        _num(row, "q90_lift", -9.0) >= UPSIDE_TAIL_MIN_LIFT
        and _num(row, "q10_lift", -9.0) >= DOWNSIDE_TAIL_MAX_WORSENING
        and _num(row, "bad_tail_rate_lift", 9.0) <= BAD_TAIL_MAX_WORSENING
    )


def _phase_viable(row: pd.Series) -> bool:
    return (
        int(row["active_rows"]) >= MIN_ACTIVE_ROWS
        and int(row["active_dates"]) >= MIN_ACTIVE_DATES
        and _num(row, "matched_row_rate", 0.0) >= 0.95
    )


def _phase_payoff_clean(row: pd.Series) -> bool:
    return (
        _num(row, "mean_lift", -9.0) >= MEAN_MIN_LIFT
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
            "state_group": state_spec["state_group"],
        }
        phase_flags: dict[str, dict[str, bool]] = {}
        for phase in ("dev", "validation", "confirmation"):
            fwd = _result(results, state, phase, "fwd_rel_5d")
            actual = _result(results, state, phase, "actual")
            viable = _phase_viable(fwd)
            tail_good = viable and _phase_tail_good(fwd)
            payoff_clean = viable and _phase_payoff_clean(fwd)
            phase_flags[phase] = {
                "viable": viable,
                "tail_good": tail_good,
                "payoff_clean": payoff_clean,
            }
            for key in (
                "active_rows",
                "active_dates",
                "mean_lift",
                "q90_lift",
                "q10_lift",
                "bad_tail_rate_lift",
                "hit_rate_lift",
                "can_buy_rate_lift",
            ):
                row[f"{phase}_fwd_{key}"] = _safe_float(fwd[key])
            row[f"{phase}_actual_hit_rate_lift"] = _safe_float(actual["hit_rate_lift"])
            row[f"{phase}_actual_mean_lift"] = _safe_float(actual["mean_lift"])

        if state_spec["state_kind"] != "candidate":
            decision = "DIAGNOSTIC"
            reason = "diagnostic_control_state"
        elif not (phase_flags["validation"]["viable"] and phase_flags["confirmation"]["viable"]):
            decision = "SKIPPED"
            reason = "insufficient_validation_or_confirmation_active_rows"
        elif (
            phase_flags["validation"]["tail_good"]
            and phase_flags["confirmation"]["tail_good"]
            and phase_flags["validation"]["payoff_clean"]
            and phase_flags["confirmation"]["payoff_clean"]
        ):
            decision = "PASSED"
            reason = "positive_upside_tail_without_worse_downside_or_tradability_in_validation_and_confirmation"
        elif phase_flags["validation"]["tail_good"] and phase_flags["confirmation"]["tail_good"]:
            decision = "MIXED"
            reason = "tail_lift_in_both_phases_but_mean_hit_rate_or_tradability_not_clean"
        elif phase_flags["validation"]["tail_good"] and (
            _num(_result(results, state, "confirmation", "fwd_rel_5d"), "q90_lift", -9.0) > 0.0
            and _num(_result(results, state, "confirmation", "fwd_rel_5d"), "q10_lift", -9.0)
            >= DOWNSIDE_TAIL_MAX_WORSENING
        ):
            decision = "MIXED"
            reason = "validation_tail_lift_with_partial_confirmation_tail_support"
        else:
            validation_q90 = _num(_result(results, state, "validation", "fwd_rel_5d"), "q90_lift", -9.0)
            confirmation_q90 = _num(_result(results, state, "confirmation", "fwd_rel_5d"), "q90_lift", -9.0)
            if max(validation_q90, confirmation_q90) > 0.0 and min(validation_q90, confirmation_q90) >= -0.002:
                decision = "MIXED"
                reason = "weak_tail_hint_but_not_a_clean_two_phase_optionality_state"
            else:
                decision = "FAILED"
                reason = "no_clean_validation_and_confirmation_tail_payoff_lift"
        row["decision"] = decision
        row["reason"] = reason
        row["score"] = (
            _num(pd.Series(row), "validation_fwd_q90_lift", -9.0)
            + _num(pd.Series(row), "confirmation_fwd_q90_lift", -9.0)
            + _num(pd.Series(row), "validation_fwd_q10_lift", -9.0)
            + _num(pd.Series(row), "confirmation_fwd_q10_lift", -9.0)
            + 0.5 * _num(pd.Series(row), "validation_fwd_mean_lift", -9.0)
            + 0.5 * _num(pd.Series(row), "confirmation_fwd_mean_lift", -9.0)
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
            "At least one event-v2 state survives as a payoff-shape state against matched non-event controls. "
            "Advance only to a narrow sparse-sizing or risk-filter integration audit, not an additive rank overlay."
        )
    elif (candidates["decision"] == "MIXED").any():
        verdict = "MIXED"
        branch_decision = (
            "Event-v2 states show partial tail-payoff evidence, but not a clean two-phase deployable payoff shape. "
            "Keep as offline timing evidence; do not integrate without a stricter portfolio-level follow-up."
        )
    elif (candidates["decision"] == "SKIPPED").all():
        verdict = "SKIPPED"
        branch_decision = "Candidate event states were too sparse for the predeclared validation/confirmation tail audit."
    else:
        verdict = "FAILED"
        branch_decision = (
            "The event-v2 states do not deliver a clean validation and confirmation upside-tail / downside-risk advantage "
            "against matched non-event controls. Do not reopen event-v2 integration under this payoff-shape contract."
        )

    decision = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "best_state": best["state"],
        "best_state_decision": best["decision"],
        "best_state_reason": best["reason"],
        "best_validation_fwd_mean_lift": _safe_float(best["validation_fwd_mean_lift"]),
        "best_validation_fwd_q90_lift": _safe_float(best["validation_fwd_q90_lift"]),
        "best_validation_fwd_q10_lift": _safe_float(best["validation_fwd_q10_lift"]),
        "best_validation_fwd_bad_tail_rate_lift": _safe_float(best["validation_fwd_bad_tail_rate_lift"]),
        "best_confirmation_fwd_mean_lift": _safe_float(best["confirmation_fwd_mean_lift"]),
        "best_confirmation_fwd_q90_lift": _safe_float(best["confirmation_fwd_q90_lift"]),
        "best_confirmation_fwd_q10_lift": _safe_float(best["confirmation_fwd_q10_lift"]),
        "best_confirmation_fwd_bad_tail_rate_lift": _safe_float(best["confirmation_fwd_bad_tail_rate_lift"]),
    }
    return state_results, decision


def _print_results(state_results: pd.DataFrame, decision: dict[str, object]) -> None:
    cols = [
        "state",
        "decision",
        "validation_fwd_active_rows",
        "validation_fwd_mean_lift",
        "validation_fwd_q90_lift",
        "validation_fwd_q10_lift",
        "validation_fwd_bad_tail_rate_lift",
        "confirmation_fwd_active_rows",
        "confirmation_fwd_mean_lift",
        "confirmation_fwd_q90_lift",
        "confirmation_fwd_q10_lift",
        "confirmation_fwd_bad_tail_rate_lift",
    ]
    print("\nH352: EVENT-V2 OPTIONALITY PAYOFF AUDIT")
    print(state_results.loc[:, cols].to_string(index=False))
    print(f"\nverdict={decision['verdict']} | best_state={decision['best_state']} | best_decision={decision['best_state_decision']}")


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel = _load_panel()
    if (panel["time"].dt.year >= 2026).any():
        raise ValueError("H352 predictive panel unexpectedly includes 2026+ rows")

    results, active_matches = _evaluate(panel)
    state_results, decision = _decide(results)

    results_out = OUT_DIR / f"{ts}_h352_event_v2_optionality_payoff_results.parquet"
    state_results_out = OUT_DIR / f"{ts}_h352_event_v2_optionality_payoff_state_results.parquet"
    matches_out = OUT_DIR / f"{ts}_h352_event_v2_optionality_payoff_active_matches.parquet"
    details_out = DETAILS_DIR / f"{ts}_h352_event_v2_optionality_payoff_details.json"
    results.to_parquet(results_out, index=False)
    state_results.to_parquet(state_results_out, index=False)
    active_matches.to_parquet(matches_out, index=False)

    summary = {
        **decision,
        "protocol": PROTOCOL.describe(),
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "candidate_states": [spec["state_name"] for spec in STATE_SPECS if spec["state_kind"] == "candidate"],
        "diagnostic_states": [spec["state_name"] for spec in STATE_SPECS if spec["state_kind"] != "candidate"],
    }
    details = {
        "summary": summary,
        "state_specs": STATE_SPECS,
        "metric_specs": [
            {"metric": metric, "note": note, "bad_tail_threshold": threshold}
            for metric, note, threshold in METRIC_SPECS
        ],
        "decision_rules": {
            "minimum_active_rows_per_validation_phase": MIN_ACTIVE_ROWS,
            "minimum_active_dates_per_validation_phase": MIN_ACTIVE_DATES,
            "minimum_matched_row_rate": 0.95,
            "pass": (
                "validation and confirmation fwd_rel_5d q90 lift >= 0.005, q10 lift >= -0.0025, "
                "bad-tail-rate lift <= 0.010, mean lift >= -0.001, hit-rate lift >= -0.020, "
                "and can-buy-rate lift >= -0.050"
            ),
            "mixed": "two-phase tail lift with weaker payoff/tradability, or weak two-phase tail hints",
            "failed": "no clean validation and confirmation payoff-shape lift",
            "skipped": "insufficient validation or confirmation active rows/dates",
        },
        "matching": "active rows matched to non-event controls by date+sector+S1 bucket, falling back to date+S1 bucket and then date",
    }
    details_out.write_text(json.dumps(_json_safe(details), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_event_v2_optionality_payoff",
        name="h352_event_v2_optionality_payoff",
        summary=summary,
        artifacts={
            "results": str(results_out),
            "state_results": str(state_results_out),
            "active_matches": str(matches_out),
            "details": str(details_out),
        },
        metadata={
            "h321_summary": str(H321_SUMMARY_PATH),
            "tradability": str(TRADABILITY_PATH),
            "source_limited_protocol": "2023 dev / 2024 validation / 2025 confirmation; 2026 excluded",
            "matching": "non-event controls by date+sector+S1 bucket with fallback",
        },
    )

    _print_results(state_results, decision)
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
