"""
H468: market_breadth_regime_signal

Hypothesis: Market breadth (how many stocks are up vs down) is a regime indicator
that changes signal efficacy. C3 tested dispersion AS FEATURE, not as REGIME GATE.
Test: gate signals by breadth regime.

Also test: breadth ACCELERATION (breadth getting better/worse) as signal.

Data: derived from S1 panel — compute daily up/down ratio.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "market_breadth_regime_signal"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Market breadth (up vs down ratio) is a regime indicator. "
        "Test breadth as regime gate for S1/C16 signals. Also test breadth ACCELERATION. "
        "C3 tested dispersion as FEATURE, not as REGIME GATE."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H468 market_breadth_regime_signal")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    dt = panel["time"]

    breadth_daily = panel.groupby("time").agg(
        count_up=("s1_barrier_hit_1d", "sum"),
        count_total=("s1_barrier_hit_1d", "count"),
    ).reset_index()
    breadth_daily["breadth_ratio"] = breadth_daily["count_up"] / breadth_daily["count_total"]
    breadth_daily["breadth_rank"] = breadth_daily["breadth_ratio"].rank(pct=True, method="average")

    breadth_daily["breadth_5d_avg"] = breadth_daily["breadth_ratio"].rolling(5, min_periods=3).mean()
    breadth_daily["breadth_change"] = breadth_daily["breadth_ratio"].diff()
    breadth_daily["breadth_change_5d"] = breadth_daily["breadth_ratio"].diff(5)
    breadth_daily["breadth_accel"] = breadth_daily["breadth_change"].diff()

    breadth_daily["breadth_rank_5d"] = breadth_daily["breadth_5d_avg"].rank(pct=True, method="average")

    panel = panel.merge(
        breadth_daily[["time", "breadth_ratio", "breadth_rank", "breadth_5d_avg",
                        "breadth_change", "breadth_change_5d", "breadth_accel", "breadth_rank_5d"]],
        on="time",
        how="left",
    )

    panel["breadth_top20"] = (panel["breadth_rank"] >= 0.8).astype(bool)
    panel["breadth_bottom20"] = (panel["breadth_rank"] <= 0.2).astype(bool)
    panel["breadth_top40"] = (panel["breadth_rank"] >= 0.6).astype(bool)
    panel["breadth_bottom40"] = (panel["breadth_rank"] <= 0.4).astype(bool)

    breadth_change_rank = panel.groupby("time", sort=False)["breadth_change"].rank(method="average", pct=True)
    panel["breadth_widening"] = (breadth_change_rank >= 0.8).astype(bool)
    panel["breadth_narrowing"] = (breadth_change_rank <= 0.2).astype(bool)

    panel["c16_rank"] = panel.groupby("time", sort=False)["s1_xs_proba"].rank(method="average", pct=True)
    panel["c16_top20"] = (panel["c16_rank"] >= 0.8).astype(bool)

    order_stats = pd.read_parquet(data_path("order_stats/cafef/order_stats_daily.parquet"))
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    import re
    def parse_price_change(s):
        if pd.isna(s):
            return np.nan
        try:
            match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
            if match:
                return float(match.group(1).replace(',', '.'))
            return np.nan
        except:
            return np.nan

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change"]],
        on=["time", "ticker"],
        how="left",
    )

    pct_change_vol = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    vol_change = pct_change_vol.diff()
    panel["vol_change"] = vol_change
    panel = panel.dropna(subset=["vol_change"])

    vol_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = (vol_rank >= 0.8).astype(bool)

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("breadth_top20", "Broad market (breadth rank top 20%)", family="breadth"),
    StateSpec("breadth_bottom20", "Narrow market (breadth rank bottom 20%)", family="breadth"),
    StateSpec("breadth_widening", "Breadth improving (breadth_change rank top 20%)", family="breadth"),
    StateSpec("breadth_narrowing", "Breadth deteriorating (breadth_change rank bottom 20%)", family="breadth"),
    StateSpec("c16_top20_in_breadth_top20", "High C16 in broad market", family="combo"),
    StateSpec("c16_top20_in_breadth_bottom20", "High C16 in narrow market", family="combo"),
    StateSpec("vol_expansion_in_breadth_top20", "Vol expansion in broad market", family="combo"),
    StateSpec("vol_expansion_in_breadth_bottom20", "Vol expansion in narrow market", family="combo"),
]


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)

    panel["c16_top20_in_breadth_top20"] = (panel["c16_top20"] & panel["breadth_top20"]).astype(bool)
    panel["c16_top20_in_breadth_bottom20"] = (panel["c16_top20"] & panel["breadth_bottom20"]).astype(bool)
    panel["vol_expansion_in_breadth_top20"] = (panel["vol_expansion"] & panel["breadth_top20"]).astype(bool)
    panel["vol_expansion_in_breadth_bottom20"] = (panel["vol_expansion"] & panel["breadth_bottom20"]).astype(bool)

    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0

    best = results[results["name"] != "all_rows"].sort_values("avg_ic", ascending=False).iloc[0] if not results.empty else {}
    best_name = best.get("name", "none")
    best_ic = best.get("avg_ic", 0)
    best_lift = best_ic - baseline_ic

    decision = "FAILED"
    if best_lift > 0.010:
        decision = "PASSED"
    elif best_lift > 0.003:
        decision = "MIXED"

    breadth_top_ic = results[results["name"] == "breadth_top20"]["avg_ic"].iloc[0] if not results.empty else 0
    breadth_bot_ic = results[results["name"] == "breadth_bottom20"]["avg_ic"].iloc[0] if not results.empty else 0
    breadth_wide_ic = results[results["name"] == "breadth_widening"]["avg_ic"].iloc[0] if not results.empty else 0
    breadth_narrow_ic = results[results["name"] == "breadth_narrowing"]["avg_ic"].iloc[0] if not results.empty else 0

    c16_top_breadth_top_ic = results[results["name"] == "c16_top20_in_breadth_top20"]["avg_ic"].iloc[0] if not results.empty else 0
    c16_top_breadth_bot_ic = results[results["name"] == "c16_top20_in_breadth_bottom20"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_breadth_top_ic = results[results["name"] == "vol_expansion_in_breadth_top20"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_breadth_bot_ic = results[results["name"] == "vol_expansion_in_breadth_bottom20"]["avg_ic"].iloc[0] if not results.empty else 0

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "breadth_top20_ic": float(breadth_top_ic),
            "breadth_bottom20_ic": float(breadth_bot_ic),
            "breadth_widening_ic": float(breadth_wide_ic),
            "breadth_narrowing_ic": float(breadth_narrow_ic),
            "c16_top_breadth_top_ic": float(c16_top_breadth_top_ic),
            "c16_top_breadth_bot_ic": float(c16_top_breadth_bot_ic),
            "vol_breadth_top_ic": float(vol_breadth_top_ic),
            "vol_breadth_bot_ic": float(vol_breadth_bot_ic),
            "best_state": best_name,
            "best_lift": float(best_lift),
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"state_specs": [state.as_metadata() for state in STATE_SPECS], "hypothesis": SPEC.hypothesis},
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"  breadth_top20: {breadth_top_ic:.4f} (lift: {breadth_top_ic - baseline_ic:+.4f})")
    print(f"  breadth_bottom20: {breadth_bot_ic:.4f} (lift: {breadth_bot_ic - baseline_ic:+.4f})")
    print(f"  breadth_widening: {breadth_wide_ic:.4f} (lift: {breadth_wide_ic - baseline_ic:+.4f})")
    print(f"  breadth_narrowing: {breadth_narrow_ic:.4f} (lift: {breadth_narrow_ic - baseline_ic:+.4f})")
    print(f"  c16_top20_in_breadth_top20: {c16_top_breadth_top_ic:.4f}")
    print(f"  c16_top20_in_breadth_bottom20: {c16_top_breadth_bot_ic:.4f}")
    print(f"  vol_expansion_in_breadth_top20: {vol_breadth_top_ic:.4f}")
    print(f"  vol_expansion_in_breadth_bottom20: {vol_breadth_bot_ic:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()