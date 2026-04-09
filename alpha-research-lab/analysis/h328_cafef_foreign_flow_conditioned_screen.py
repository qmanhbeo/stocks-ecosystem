"""
H328: constrained conditioned screen for CafeF foreign-flow features.

Question:
    H327 passed the source-quality gate but simple full-universe foreign-flow
    ranks failed confirmation. Does the signal only exist when foreign trading
    participation or foreign-room scarcity is high?

Design:
    - reuse the H327 raw feature builder
    - add two predeclared state families:
      1) high foreign participation by rolling buy+sell volume share
      2) high room scarcity by the H327 room-scarcity rank
    - test a small set of net/buy/sell flow ranks inside those states
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
    FEATURE_COLS,
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
    build_feature_panel,
    load_flow,
    load_stock_panel,
    phase_mask,
    rank_by_day,
    summarize_years,
)


OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
SCREEN_FEATURES = [
    "xs_ff_net_vol_share_1d_rank",
    "xs_ff_net_vol_share_1d_lag1_rank",
    "xs_ff_net_vol_share_5d_rank",
    "xs_ff_net_vol_share_5d_lag1_rank",
    "xs_ff_buy_share_5d_rank",
    "xs_ff_sell_share_5d_rank",
]
STATE_SPECS = [
    ("foreign_participation_top30", "xs_ff_participation_20d_rank", 0.70),
    ("foreign_participation_top20", "xs_ff_participation_20d_rank", 0.80),
    ("room_scarcity_top30", "xs_ff_room_scarcity_rank", 0.70),
    ("room_scarcity_top20", "xs_ff_room_scarcity_rank", 0.80),
]


def build_state_panel(flow: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    merged = stock.merge(flow, on=["time", "ticker"], how="inner", suffixes=("", "_flow"))
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)
    merged["ff_participation_volume"] = merged["foreign_buy_volume"] + merged["foreign_sell_volume"]
    grouped = merged.groupby("ticker", group_keys=False)
    merged["ff_participation_volume_20d"] = (
        grouped["ff_participation_volume"].rolling(20, min_periods=10).sum().reset_index(level=0, drop=True)
    )
    merged["volume_20d"] = grouped["volume"].rolling(20, min_periods=10).sum().reset_index(level=0, drop=True)
    merged["ff_participation_20d"] = merged["ff_participation_volume_20d"] / merged["volume_20d"].replace(0, np.nan)
    return rank_by_day(merged, "ff_participation_20d", "xs_ff_participation_20d_rank", ascending=True)


def ic_for_frame(frame: pd.DataFrame, feature_col: str) -> dict[str, object]:
    clean = frame[[feature_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_YEARLY_OBS:
        return {"n": int(len(clean)), "avg_ic": None, "p_value": None}
    stat = spearmanr(clean[feature_col], clean["actual"])
    return {
        "n": int(len(clean)),
        "avg_ic": float(np.asarray(stat.statistic).flat[0]),
        "p_value": float(np.asarray(stat.pvalue).flat[0]),
    }


def yearly_ic(frame: pd.DataFrame, feature_col: str, phase: str, state_name: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby(frame["time"].dt.year):
        clean = group[[feature_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_YEARLY_OBS:
            continue
        stat = spearmanr(clean[feature_col], clean["actual"])
        rows.append(
            {
                "state": state_name,
                "phase": phase,
                "feature": feature_col,
                "year": int(year),
                "n": int(len(clean)),
                "ic": float(np.asarray(stat.statistic).flat[0]),
                "p_value": float(np.asarray(stat.pvalue).flat[0]),
            }
        )
    return rows


def evaluate_conditioned(merged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    result_rows: list[dict[str, object]] = []
    yearly_rows: list[dict[str, object]] = []
    phase_specs = {
        "dev_2015_2022": (DEV_START, DEV_END),
        "validation_2023_2024": (VALIDATION_START, VALIDATION_END),
        "confirmation_2025": (CONFIRMATION_START, CONFIRMATION_END),
        "full_2015_2025": (PREDICTIVE_START, PREDICTIVE_END),
    }

    for state_name, state_col, threshold in STATE_SPECS:
        state_frame = merged.loc[merged[state_col] >= threshold].copy()
        for feature_col in SCREEN_FEATURES:
            phase_stats: dict[str, dict[str, object]] = {}
            phase_years: dict[str, list[dict[str, object]]] = {}
            for phase, (start, end) in phase_specs.items():
                phase_frame = state_frame.loc[phase_mask(state_frame, start, end)].copy()
                stats = ic_for_frame(phase_frame, feature_col)
                years = yearly_ic(phase_frame, feature_col, phase, state_name)
                phase_stats[phase] = stats
                phase_years[phase] = years
                yearly_rows.extend(years)

            dev_ic = phase_stats["dev_2015_2022"].get("avg_ic")
            direction = 1 if (dev_ic or 0) >= 0 else -1
            dev_year_summary = summarize_years(phase_years["dev_2015_2022"], direction=direction)
            validation_ic = phase_stats["validation_2023_2024"].get("avg_ic")
            confirmation_ic = phase_stats["confirmation_2025"].get("avg_ic")
            full_ic = phase_stats["full_2015_2025"].get("avg_ic")
            corr_s1 = spearman_stat(state_frame[feature_col], state_frame["xs_proba"])
            dev_gate = (
                abs(dev_ic or 0) >= PASS_IC
                and (dev_year_summary.get("pct_directional_years") or 0) >= PASS_PCT_YEARS
            )
            validation_gate = validation_ic is not None and direction * validation_ic >= VALIDATION_MIN_ABS_IC
            confirmation_ok = confirmation_ic is not None and direction * confirmation_ic > 0
            corr_gate = abs(corr_s1) < PASS_CORR
            candidate_gate = bool(dev_gate and validation_gate and confirmation_ok and corr_gate)
            result_rows.append(
                {
                    "state": state_name,
                    "state_col": state_col,
                    "threshold": threshold,
                    "feature": feature_col,
                    "direction": "positive" if direction > 0 else "negative",
                    "state_rows": int(len(state_frame)),
                    "coverage": float(state_frame[feature_col].notna().mean()) if len(state_frame) else 0.0,
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
                    "full_avg_ic": full_ic,
                    "full_n": phase_stats["full_2015_2025"].get("n"),
                    "dev_gate": dev_gate,
                    "validation_gate": validation_gate,
                    "confirmation_ok": confirmation_ok,
                    "corr_gate": corr_gate,
                    "candidate_gate": candidate_gate,
                }
            )

    results = pd.DataFrame(result_rows)
    yearly = pd.DataFrame(yearly_rows)
    if not results.empty:
        results["abs_validation_ic"] = results["validation_avg_ic"].abs()
        results["abs_dev_ic"] = results["dev_avg_ic"].abs()
        results = results.sort_values(
            ["candidate_gate", "abs_validation_ic", "abs_dev_ic", "state", "feature"],
            ascending=[False, False, False, True, True],
        ).reset_index(drop=True)
    passing = results.loc[results["candidate_gate"]].copy()
    return results, yearly, {
        "merged_rows": int(len(merged)),
        "states": [name for name, _, _ in STATE_SPECS],
        "features": SCREEN_FEATURES,
        "passing_pairs": passing[["state", "feature"]].to_dict(orient="records") if not passing.empty else [],
        "best_pair": _json_safe(results.iloc[0].to_dict()) if not results.empty else {},
    }


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    flow = load_flow()
    stock = load_stock_panel()
    feature_panel = build_feature_panel(flow, stock)
    state_panel = build_state_panel(flow, stock)
    s1 = load_s1_frame()
    merged = s1.merge(feature_panel[["time", "ticker"] + FEATURE_COLS], on=["time", "ticker"], how="inner")
    merged = merged.merge(state_panel, on=["time", "ticker"], how="inner")
    merged = merged.loc[phase_mask(merged, PREDICTIVE_START, PREDICTIVE_END)].copy()
    results, yearly, screen_summary = evaluate_conditioned(merged)

    results_path = OUT_DIR / f"{ts}_h328_cafef_foreign_flow_conditioned_results.parquet"
    yearly_path = OUT_DIR / f"{ts}_h328_cafef_foreign_flow_conditioned_yearly_ic.parquet"
    details_path = DETAILS_DIR / f"{ts}_h328_cafef_foreign_flow_conditioned_screen_details.json"
    results.to_parquet(results_path, index=False)
    yearly.to_parquet(yearly_path, index=False)

    passing = screen_summary.get("passing_pairs") or []
    if passing:
        verdict = "PASSED"
        branch_decision = (
            "A constrained foreign-participation / room-scarcity state contains "
            "a flow feature that survived dev, validation, confirmation, and S1-correlation gates. "
            "Next: run redundancy versus C4-C14 and a leakage/source-timing audit."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Conditioning on high foreign participation or room scarcity did not rescue "
            "simple CafeF foreign-flow features. Do not promote raw flow ranks; if this branch "
            "continues, it needs a different thesis such as room-change events or ownership-regime transitions."
        )

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "screen": screen_summary,
    }
    details_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "results": _json_safe(results.to_dict(orient="records")),
                "yearly_ic": _json_safe(yearly.to_dict(orient="records")),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_cafef_foreign_flow_conditioned_screen",
        name="h328_cafef_foreign_flow_conditioned_screen",
        summary=summary,
        artifacts={
            "results": results_path,
            "yearly_ic": yearly_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": "Foreign-flow alpha may be state-local to high foreign participation or high room scarcity.",
            "protocol": {
                "dev": f"{DEV_START}..{DEV_END}",
                "validation": f"{VALIDATION_START}..{VALIDATION_END}",
                "confirmation": f"{CONFIRMATION_START}..{CONFIRMATION_END}",
                "no_tuning_window": "2026+",
            },
        },
    )

    print("H328 CafeF foreign-flow conditioned screen")
    print("=" * 72)
    print(f"verdict: {verdict}")
    print(f"merged rows: {screen_summary['merged_rows']:,}")
    print("top rows:")
    display_cols = [
        "state",
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
    print(results[display_cols].head(12).to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
