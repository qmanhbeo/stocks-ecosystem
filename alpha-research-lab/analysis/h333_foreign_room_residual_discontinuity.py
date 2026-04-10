"""
H333: foreign-room residual discontinuity audit.

Question:
    H327/H328 killed raw CafeF foreign buy/sell ranks. Does the useful signal
    instead live in days where foreign room changes cannot be explained by
    ordinary net foreign trading?

Design:
    - compute room mechanics residual:
        room_residual = delta(foreign_room_remaining) + foreign_net_volume
      because ordinary net foreign buying should reduce remaining room
    - split idiosyncratic discontinuities from broad reset days
    - test dense residual ranks and sparse discontinuity states on T+1 and T+5
    - keep 2026 out of the predictive decision
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ANALYSIS_DIR = ROOT / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_s1_frame, spearman_stat  # noqa: E402
from h327_cafef_foreign_flow_source_audit import (  # noqa: E402
    CONFIRMATION_END,
    CONFIRMATION_START,
    DEV_END,
    DEV_START,
    MIN_YEARLY_OBS,
    PASS_CORR,
    PASS_IC,
    PASS_PCT_YEARS,
    PREDICTIVE_END,
    PREDICTIVE_START,
    VALIDATION_END,
    VALIDATION_MIN_ABS_IC,
    VALIDATION_START,
    _json_safe,
    load_flow,
    load_stock_panel,
    phase_mask,
    rank_by_day,
    summarize_years,
)


OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
FWD5_PATH = ROOT / "artifacts" / "cache" / "future_rel_return_5d_hose.parquet"
ADV_WINDOW = 20
EVENT_TOP_PCT = 0.95
SYSTEMIC_TOP_PCT = 0.95
MIN_PHASE_EVENT_DAYS = {
    "dev_2015_2022": 20,
    "validation_2023_2024": 10,
    "confirmation_2025": 5,
}

DENSE_FEATURES = [
    "xs_ff_room_residual_tighten_rank",
    "xs_ff_room_residual_loosen_rank",
    "xs_ff_room_residual_abs_rank",
    "xs_ff_room_residual_tighten_5d_rank",
    "xs_ff_room_residual_loosen_5d_rank",
    "xs_ff_room_residual_abs_5d_rank",
]

EVENT_STATES = [
    "room_residual_idio_abs_top5",
    "room_residual_idio_tighten_top5",
    "room_residual_idio_loosen_top5",
    "room_residual_systemic_abs_top5",
]


def load_fwd5() -> pd.DataFrame:
    if not FWD5_PATH.exists():
        raise FileNotFoundError(f"missing fwd5 cache: {FWD5_PATH}")
    fwd5 = pd.read_parquet(FWD5_PATH)
    fwd5["time"] = pd.to_datetime(fwd5["time"], errors="coerce")
    fwd5["ticker"] = fwd5["ticker"].astype(str).str.upper()
    fwd5["fwd_rel_5d"] = pd.to_numeric(fwd5["fwd_rel_5d"], errors="coerce")
    return fwd5[["time", "ticker", "fwd_rel_5d"]].dropna(subset=["time", "ticker"])


def build_residual_panel(flow: pd.DataFrame, stock: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = stock.merge(flow, on=["time", "ticker"], how="inner", suffixes=("", "_flow"))
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)
    grouped = merged.groupby("ticker", group_keys=False)
    merged["foreign_room_prev"] = grouped["foreign_room_remaining"].shift(1)
    merged["room_delta"] = merged["foreign_room_remaining"] - merged["foreign_room_prev"]
    merged["room_residual"] = merged["room_delta"] + merged["foreign_net_volume"]
    merged["volume_20d"] = grouped["volume"].rolling(ADV_WINDOW, min_periods=10).mean().reset_index(level=0, drop=True)
    merged["residual_share_adv20"] = merged["room_residual"] / merged["volume_20d"].replace(0, np.nan)
    merged["residual_abs_share_adv20"] = merged["residual_share_adv20"].abs()
    merged["residual_tighten_share_adv20"] = -merged["residual_share_adv20"]

    for source_col, output_col in [
        ("room_residual", "room_residual_5d"),
        ("residual_abs_share_adv20", "residual_abs_share_adv20_5d"),
        ("residual_tighten_share_adv20", "residual_tighten_share_adv20_5d"),
        ("residual_share_adv20", "residual_share_adv20_5d"),
    ]:
        merged[output_col] = grouped[source_col].rolling(5, min_periods=3).sum().reset_index(level=0, drop=True)

    valid_residual = merged["room_residual"].replace([np.inf, -np.inf], np.nan).notna()
    mechanically_exact = (merged["room_residual"].abs() <= 1e-9) & valid_residual
    date_stats = (
        merged.loc[valid_residual]
        .groupby("time", as_index=False)
        .agg(
            residual_rows=("ticker", "size"),
            exact_rows=("room_residual", lambda x: int((x.abs() <= 1e-9).sum())),
            nonzero_rows=("room_residual", lambda x: int((x.abs() > 1e-9).sum())),
            median_abs_share=("residual_abs_share_adv20", "median"),
            p95_abs_share=("residual_abs_share_adv20", lambda x: float(np.nanquantile(x, 0.95))),
        )
    )
    date_stats["exact_ratio"] = date_stats["exact_rows"] / date_stats["residual_rows"].replace(0, np.nan)
    date_stats["nonzero_ratio"] = date_stats["nonzero_rows"] / date_stats["residual_rows"].replace(0, np.nan)
    date_stats["systemic_score"] = date_stats["nonzero_ratio"].fillna(0) * date_stats["p95_abs_share"].fillna(0)
    date_stats["systemic_score_rank"] = date_stats["systemic_score"].rank(method="average", pct=True)
    date_stats["is_systemic_reset_day"] = date_stats["systemic_score_rank"] >= SYSTEMIC_TOP_PCT

    merged = merged.merge(
        date_stats[["time", "systemic_score", "systemic_score_rank", "is_systemic_reset_day"]],
        on="time",
        how="left",
    )
    merged["residual_abs_rank"] = merged.groupby("time")["residual_abs_share_adv20"].rank(
        method="average", pct=True, ascending=True
    )
    merged["residual_tighten_rank"] = merged.groupby("time")["residual_tighten_share_adv20"].rank(
        method="average", pct=True, ascending=True
    )
    merged["residual_loosen_rank"] = merged.groupby("time")["residual_share_adv20"].rank(
        method="average", pct=True, ascending=True
    )
    merged["has_nonzero_residual"] = merged["room_residual"].abs() > 1e-9
    idio_mask = ~merged["is_systemic_reset_day"].fillna(False)
    merged["room_residual_idio_abs_top5"] = (
        idio_mask & merged["has_nonzero_residual"] & (merged["residual_abs_rank"] >= EVENT_TOP_PCT)
    ).astype(float)
    merged["room_residual_idio_tighten_top5"] = (
        idio_mask & merged["has_nonzero_residual"] & (merged["residual_tighten_rank"] >= EVENT_TOP_PCT)
    ).astype(float)
    merged["room_residual_idio_loosen_top5"] = (
        idio_mask & merged["has_nonzero_residual"] & (merged["residual_loosen_rank"] >= EVENT_TOP_PCT)
    ).astype(float)
    merged["room_residual_systemic_abs_top5"] = (
        merged["is_systemic_reset_day"].fillna(False)
        & merged["has_nonzero_residual"]
        & (merged["residual_abs_rank"] >= EVENT_TOP_PCT)
    ).astype(float)

    ranked = merged[["time", "ticker", "room_residual"] + EVENT_STATES].copy()
    rank_specs = [
        ("residual_tighten_share_adv20", "xs_ff_room_residual_tighten_rank", True),
        ("residual_share_adv20", "xs_ff_room_residual_loosen_rank", True),
        ("residual_abs_share_adv20", "xs_ff_room_residual_abs_rank", True),
        ("residual_tighten_share_adv20_5d", "xs_ff_room_residual_tighten_5d_rank", True),
        ("residual_share_adv20_5d", "xs_ff_room_residual_loosen_5d_rank", True),
        ("residual_abs_share_adv20_5d", "xs_ff_room_residual_abs_5d_rank", True),
    ]
    for source_col, output_col, ascending in rank_specs:
        ranked = ranked.merge(rank_by_day(merged, source_col, output_col, ascending=ascending), on=["time", "ticker"])
    return ranked, date_stats


def ic_for_frame(frame: pd.DataFrame, feature_col: str, target_col: str) -> dict[str, object]:
    clean = frame[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_YEARLY_OBS:
        return {"n": int(len(clean)), "avg_ic": None, "p_value": None}
    stat = spearmanr(clean[feature_col], clean[target_col])
    return {
        "n": int(len(clean)),
        "avg_ic": float(np.asarray(stat.statistic).flat[0]),
        "p_value": float(np.asarray(stat.pvalue).flat[0]),
    }


def yearly_ic(frame: pd.DataFrame, feature_col: str, phase: str, target_col: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby(frame["time"].dt.year):
        clean = group[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_YEARLY_OBS:
            continue
        stat = spearmanr(clean[feature_col], clean[target_col])
        rows.append(
            {
                "phase": phase,
                "feature": feature_col,
                "target": target_col,
                "year": int(year),
                "n": int(len(clean)),
                "ic": float(np.asarray(stat.statistic).flat[0]),
                "p_value": float(np.asarray(stat.pvalue).flat[0]),
            }
        )
    return rows


def evaluate_dense_features(merged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    result_rows: list[dict[str, object]] = []
    yearly_rows: list[dict[str, object]] = []
    phase_specs = {
        "dev_2015_2022": (DEV_START, DEV_END),
        "validation_2023_2024": (VALIDATION_START, VALIDATION_END),
        "confirmation_2025": (CONFIRMATION_START, CONFIRMATION_END),
        "full_2015_2025": (PREDICTIVE_START, PREDICTIVE_END),
    }
    for feature_col in DENSE_FEATURES:
        phase_stats: dict[str, dict[str, object]] = {}
        phase_years: dict[str, list[dict[str, object]]] = {}
        for phase, (start, end) in phase_specs.items():
            phase_frame = merged.loc[phase_mask(merged, start, end)].copy()
            stats = ic_for_frame(phase_frame, feature_col, "actual")
            years = yearly_ic(phase_frame, feature_col, phase, "actual")
            phase_stats[phase] = stats
            phase_years[phase] = years
            yearly_rows.extend(years)
        dev_ic = phase_stats["dev_2015_2022"].get("avg_ic")
        direction = 1 if (dev_ic or 0) >= 0 else -1
        dev_year_summary = summarize_years(phase_years["dev_2015_2022"], direction=direction)
        validation_ic = phase_stats["validation_2023_2024"].get("avg_ic")
        confirmation_ic = phase_stats["confirmation_2025"].get("avg_ic")
        corr_s1 = spearman_stat(merged[feature_col], merged["xs_proba"])
        dev_gate = (
            abs(dev_ic or 0) >= PASS_IC
            and (dev_year_summary.get("pct_directional_years") or 0) >= PASS_PCT_YEARS
        )
        validation_gate = validation_ic is not None and direction * validation_ic >= VALIDATION_MIN_ABS_IC
        confirmation_ok = confirmation_ic is not None and direction * confirmation_ic > 0
        corr_gate = abs(corr_s1) < PASS_CORR
        result_rows.append(
            {
                "feature": feature_col,
                "direction": "positive" if direction > 0 else "negative",
                "coverage": float(merged[feature_col].notna().mean()),
                "corr_with_s1": corr_s1,
                "dev_avg_ic": dev_ic,
                "dev_n": phase_stats["dev_2015_2022"].get("n"),
                "dev_years": dev_year_summary.get("years"),
                "dev_directional_years": dev_year_summary.get("directional_years"),
                "dev_pct_directional_years": dev_year_summary.get("pct_directional_years"),
                "validation_avg_ic": validation_ic,
                "validation_n": phase_stats["validation_2023_2024"].get("n"),
                "confirmation_avg_ic": confirmation_ic,
                "confirmation_n": phase_stats["confirmation_2025"].get("n"),
                "full_avg_ic": phase_stats["full_2015_2025"].get("avg_ic"),
                "full_n": phase_stats["full_2015_2025"].get("n"),
                "dev_gate": dev_gate,
                "validation_gate": validation_gate,
                "confirmation_ok": confirmation_ok,
                "corr_gate": corr_gate,
                "candidate_gate": bool(dev_gate and validation_gate and confirmation_ok and corr_gate),
            }
        )
    results = pd.DataFrame(result_rows)
    yearly = pd.DataFrame(yearly_rows)
    if not results.empty:
        results["abs_validation_ic"] = results["validation_avg_ic"].abs()
        results["abs_dev_ic"] = results["dev_avg_ic"].abs()
        results = results.sort_values(
            ["candidate_gate", "abs_validation_ic", "abs_dev_ic", "feature"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
    return results, yearly


def phase_event_stats(frame: pd.DataFrame, state_col: str, phase: str) -> dict[str, object]:
    active = frame.loc[frame[state_col] > 0].copy()
    inactive = frame.loc[frame[state_col] <= 0].copy()
    out = {
        "state": state_col,
        "phase": phase,
        "rows": int(len(frame)),
        "active_rows": int(len(active)),
        "active_days": int(active["time"].nunique()) if not active.empty else 0,
        "active_tickers": int(active["ticker"].nunique()) if not active.empty else 0,
        "active_share": float(len(active) / len(frame)) if len(frame) else 0.0,
    }
    for target_col in ["actual", "fwd_rel_5d"]:
        active_mean = float(active[target_col].mean()) if len(active) else None
        inactive_mean = float(inactive[target_col].mean()) if len(inactive) else None
        out[f"{target_col}_active_mean"] = active_mean
        out[f"{target_col}_inactive_mean"] = inactive_mean
        out[f"{target_col}_lift"] = (
            float(active_mean - inactive_mean)
            if active_mean is not None and inactive_mean is not None and not pd.isna(inactive_mean)
            else None
        )
    return out


def evaluate_event_states(merged: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    phase_specs = {
        "dev_2015_2022": (DEV_START, DEV_END),
        "validation_2023_2024": (VALIDATION_START, VALIDATION_END),
        "confirmation_2025": (CONFIRMATION_START, CONFIRMATION_END),
        "full_2015_2025": (PREDICTIVE_START, PREDICTIVE_END),
    }
    for state_col in EVENT_STATES:
        phase_rows: dict[str, dict[str, object]] = {}
        for phase, (start, end) in phase_specs.items():
            phase_frame = merged.loc[phase_mask(merged, start, end)].copy()
            phase_rows[phase] = phase_event_stats(phase_frame, state_col, phase)
            rows.append(phase_rows[phase])

        dev_lift = phase_rows["dev_2015_2022"].get("fwd_rel_5d_lift") or 0.0
        direction = 1 if dev_lift >= 0 else -1
        for phase in phase_specs:
            item = rows[-len(phase_specs) + list(phase_specs.keys()).index(phase)]
            item["direction"] = "positive" if direction > 0 else "negative"
            item["directional_actual_lift"] = (
                direction * item["actual_lift"] if item.get("actual_lift") is not None else None
            )
            item["directional_fwd5_lift"] = (
                direction * item["fwd_rel_5d_lift"] if item.get("fwd_rel_5d_lift") is not None else None
            )
            item["phase_days_gate"] = item["active_days"] >= MIN_PHASE_EVENT_DAYS.get(phase, 1)

    events = pd.DataFrame(rows)
    if events.empty:
        return events
    return events.sort_values(["state", "phase"]).reset_index(drop=True)


def summarize_events(events: pd.DataFrame) -> dict[str, object]:
    if events.empty:
        return {"passing_event_states": [], "mixed_event_states": [], "best_event_state": {}}
    out_rows = []
    for state, group in events.groupby("state"):
        by_phase = {row["phase"]: row for row in group.to_dict(orient="records")}
        validation = by_phase.get("validation_2023_2024", {})
        confirmation = by_phase.get("confirmation_2025", {})
        dev = by_phase.get("dev_2015_2022", {})
        days_gate = (
            bool(dev.get("phase_days_gate"))
            and bool(validation.get("phase_days_gate"))
            and bool(confirmation.get("phase_days_gate"))
        )
        validation_actual_ok = (validation.get("directional_actual_lift") or 0) > 0
        confirmation_actual_ok = (confirmation.get("directional_actual_lift") or 0) > 0
        validation_fwd5_ok = (validation.get("directional_fwd5_lift") or 0) > 0
        confirmation_fwd5_ok = (confirmation.get("directional_fwd5_lift") or 0) > 0
        event_gate = bool(
            days_gate
            and validation_actual_ok
            and confirmation_actual_ok
            and validation_fwd5_ok
            and confirmation_fwd5_ok
        )
        mixed_gate = bool(days_gate and validation_fwd5_ok and confirmation_fwd5_ok)
        out_rows.append(
            {
                "state": state,
                "direction": dev.get("direction"),
                "dev_active_days": dev.get("active_days"),
                "validation_active_days": validation.get("active_days"),
                "confirmation_active_days": confirmation.get("active_days"),
                "validation_actual_lift": validation.get("actual_lift"),
                "confirmation_actual_lift": confirmation.get("actual_lift"),
                "validation_fwd5_lift": validation.get("fwd_rel_5d_lift"),
                "confirmation_fwd5_lift": confirmation.get("fwd_rel_5d_lift"),
                "days_gate": days_gate,
                "event_gate": event_gate,
                "mixed_gate": mixed_gate,
            }
        )
    summary = pd.DataFrame(out_rows)
    summary["score"] = (
        summary["validation_fwd5_lift"].fillna(0).abs()
        + summary["confirmation_fwd5_lift"].fillna(0).abs()
        + summary["validation_actual_lift"].fillna(0).abs()
        + summary["confirmation_actual_lift"].fillna(0).abs()
    )
    summary = summary.sort_values(["event_gate", "mixed_gate", "score"], ascending=[False, False, False])
    return {
        "passing_event_states": summary.loc[summary["event_gate"], "state"].tolist(),
        "mixed_event_states": summary.loc[summary["mixed_gate"] & ~summary["event_gate"], "state"].tolist(),
        "best_event_state": _json_safe(summary.iloc[0].to_dict()) if not summary.empty else {},
        "event_state_summary": _json_safe(summary.to_dict(orient="records")),
    }


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    flow = load_flow()
    stock = load_stock_panel()
    residual_panel, date_stats = build_residual_panel(flow, stock)
    s1 = load_s1_frame()
    fwd5 = load_fwd5()
    merged = s1.merge(residual_panel, on=["time", "ticker"], how="inner")
    merged = merged.merge(fwd5, on=["time", "ticker"], how="left")
    merged = merged.loc[phase_mask(merged, PREDICTIVE_START, PREDICTIVE_END)].copy()

    dense_results, dense_yearly = evaluate_dense_features(merged)
    event_results = evaluate_event_states(merged)
    event_summary = summarize_events(event_results)

    mechanics = {
        "merged_rows": int(len(merged)),
        "merged_tickers": int(merged["ticker"].nunique()) if not merged.empty else 0,
        "merged_dates": int(merged["time"].nunique()) if not merged.empty else 0,
        "residual_nonnull_share": float(merged["room_residual"].notna().mean()) if len(merged) else 0.0,
        "residual_exact_zero_share": float((merged["room_residual"].abs() <= 1e-9).mean()) if len(merged) else 0.0,
        "systemic_reset_days": int(date_stats["is_systemic_reset_day"].sum()) if not date_stats.empty else 0,
        "date_stats_rows": int(len(date_stats)),
    }

    passing_dense = dense_results.loc[dense_results["candidate_gate"], "feature"].tolist() if not dense_results.empty else []
    passing_events = event_summary.get("passing_event_states") or []
    mixed_events = event_summary.get("mixed_event_states") or []
    if passing_dense or passing_events:
        verdict = "PASSED"
        branch_decision = (
            "Foreign-room residual discontinuities survived the first standalone / sparse-state gate. "
            "Next: run a stricter redundancy and source-event audit before publishing any feature."
        )
    elif mixed_events:
        verdict = "MIXED"
        branch_decision = (
            "Foreign-room residual discontinuities show local same-direction follow-through, but the "
            "full T+1/T+5 validation and confirmation gate did not clear. Keep only as sparse offline evidence."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Room residual discontinuities did not beat the H333 gate. Do not continue raw room-residual "
            "thresholding; move to a different foreign-state thesis such as accumulation change-points or "
            "friction interactions."
        )

    dense_path = OUT_DIR / f"{ts}_h333_foreign_room_residual_dense_results.parquet"
    yearly_path = OUT_DIR / f"{ts}_h333_foreign_room_residual_yearly_ic.parquet"
    event_path = OUT_DIR / f"{ts}_h333_foreign_room_residual_event_results.parquet"
    date_stats_path = OUT_DIR / f"{ts}_h333_foreign_room_residual_date_stats.parquet"
    panel_path = OUT_DIR / f"{ts}_h333_foreign_room_residual_panel.parquet"
    details_path = DETAILS_DIR / f"{ts}_h333_foreign_room_residual_discontinuity_details.json"

    dense_results.to_parquet(dense_path, index=False)
    dense_yearly.to_parquet(yearly_path, index=False)
    event_results.to_parquet(event_path, index=False)
    date_stats.to_parquet(date_stats_path, index=False)
    merged.to_parquet(panel_path, index=False)

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "mechanics": mechanics,
        "dense": {
            "features": DENSE_FEATURES,
            "passing_features": passing_dense,
            "best_feature": _json_safe(dense_results.iloc[0].to_dict()) if not dense_results.empty else {},
        },
        "events": event_summary,
    }
    details_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "dense_results": _json_safe(dense_results.to_dict(orient="records")),
                "event_results": _json_safe(event_results.to_dict(orient="records")),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_foreign_room_residual_discontinuity",
        name="h333_foreign_room_residual_discontinuity",
        summary=summary,
        artifacts={
            "dense_results": dense_path,
            "yearly_ic": yearly_path,
            "event_results": event_path,
            "date_stats": date_stats_path,
            "panel": panel_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": "CafeF foreign-flow value may live in residual room discontinuities rather than raw buy/sell ranks.",
            "protocol": {
                "dev": f"{DEV_START}..{DEV_END}",
                "validation": f"{VALIDATION_START}..{VALIDATION_END}",
                "confirmation": f"{CONFIRMATION_START}..{CONFIRMATION_END}",
                "no_tuning_window": "2026+",
                "residual_formula": "delta(foreign_room_remaining) + foreign_net_volume",
            },
        },
    )

    print("H333 foreign-room residual discontinuity")
    print("=" * 72)
    print(f"verdict: {verdict}")
    print(f"merged rows: {mechanics['merged_rows']:,}")
    print(f"residual exact-zero share: {mechanics['residual_exact_zero_share']:.2%}")
    print(f"systemic reset days: {mechanics['systemic_reset_days']}")
    print("top dense rows:")
    dense_display = [
        "feature",
        "direction",
        "dev_avg_ic",
        "dev_directional_years",
        "dev_years",
        "validation_avg_ic",
        "confirmation_avg_ic",
        "corr_with_s1",
        "candidate_gate",
    ]
    print(dense_results[dense_display].head(8).to_string(index=False))
    print("event summary:")
    event_display = pd.DataFrame(event_summary.get("event_state_summary") or [])
    if not event_display.empty:
        cols = [
            "state",
            "direction",
            "validation_actual_lift",
            "confirmation_actual_lift",
            "validation_fwd5_lift",
            "confirmation_fwd5_lift",
            "event_gate",
            "mixed_gate",
        ]
        print(event_display[cols].head(8).to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
