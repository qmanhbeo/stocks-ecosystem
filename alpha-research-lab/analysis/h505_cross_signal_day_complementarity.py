"""
BU4: cross_signal_day_complementarity

Hypothesis: C23/C24/C25/C26 fire on different days. Route to whichever fires
that day (C23 OR C24 OR C25 OR C26) vs always-using-best-single.

This is signal complementarity: when C23 doesn't fire but C24 does, use C24.
This is different from D041 (which killed COMBOs) - this is SELECTIVE ROUTING,
not COMBINATION.

First test: signal_day_union (any of C23/C24/C25/C26 fires that day) vs always-C23.
Uses reusable walk-forward validation with random baselines.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

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


BRANCH_NAME = "cross_signal_day_complementarity"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23/C24/C25/C26 fire on different days. Route to whichever fires "
        "that day (C23 OR C24 OR C25 OR C26) vs always-using-best-single. "
        "Different from D041 (COMBO kill) - this is SELECTIVE ROUTING."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BU4: cross_signal_day_complementarity test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_amihud(df):
    if 'close' not in df.columns or 'volume' not in df.columns:
        return df
    df = df.copy()
    if 'ticker' in df.columns:
        df['daily_return'] = df.groupby('ticker')['close'].pct_change()
    else:
        df['daily_return'] = df['close'].pct_change()
    df['daily_return_abs'] = df['daily_return'].abs()
    df['turnover'] = df['close'] * df['volume'] / 1e9
    df['amihud'] = df['daily_return_abs'] / (df['turnover'] + 1e-9)
    return df


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    stock_dir = Path("/home/manh/stocks-ecosystem/data/stock")
    ohlcv_dfs = []
    for f in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            df = pd.read_parquet(f)
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
            df['ticker'] = ticker
            ohlcv_dfs.append(df)
        except Exception:
            continue

    if ohlcv_dfs:
        ohlcv = pd.concat(ohlcv_dfs, ignore_index=True)
        ohlcv = ohlcv[['ticker', 'time', 'close', 'volume']].dropna()
        ohlcv['time'] = pd.to_datetime(ohlcv['time'], errors='coerce').dt.normalize()
        ohlcv = compute_amihud(ohlcv)
        panel = panel.merge(ohlcv, on=['ticker', 'time'], how='left')

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats['date'] = pd.to_datetime(order_stats['date'], errors='coerce').dt.normalize()
    order_stats['ticker'] = order_stats['ticker'].astype(str).str.upper()

    order_stats['volume_daily'] = order_stats['buy_order_volume'] + order_stats['sell_order_volume']

    order_stats['order_volume_ratio'] = (
        order_stats['buy_order_volume'] / (order_stats['sell_order_volume'] + 1e-9)
    )
    order_stats['buy_heavy'] = (order_stats['order_volume_ratio'] > 1.0).astype(int)

    ceiling_cols = [c for c in order_stats.columns if 'ceiling' in c.lower() or 'gia' in c.lower()]
    order_stats['ceiling_count'] = order_stats[ceiling_cols].fillna(0).sum(axis=1)

    order_stats['vol_change'] = order_stats.groupby('ticker')['volume_daily'].pct_change()
    vol_expansion = order_stats.groupby('date')['vol_change'].transform(
        lambda x: x >= x.quantile(0.8)
    )
    order_stats['vol_expansion'] = vol_expansion.astype(int)

    order_stats_renamed = order_stats.rename(columns={'date': 'time'})
    panel = panel.merge(
        order_stats_renamed[['ticker', 'time', 'order_volume_ratio', 'buy_heavy', 'ceiling_count', 'vol_expansion']],
        on=['ticker', 'time'],
        how='left'
    )

    amihud_p80 = panel['amihud'].quantile(0.8)
    panel['high_illiq'] = (panel['amihud'] > amihud_p80).astype(int)

    ceiling_p80 = panel['ceiling_count'].quantile(0.8)
    panel['ceiling_2'] = (panel['ceiling_count'] >= 2).astype(int)

    panel['c23'] = ((panel['high_illiq'] == 1) & (panel['vol_expansion'] == 1)).astype(int)
    panel['c24'] = ((panel['ceiling_2'] == 1) & (panel['vol_expansion'] == 1)).astype(int)
    panel['c25'] = ((panel['buy_heavy'] == 1) & (panel['high_illiq'] == 1) & (panel['vol_expansion'] == 1)).astype(int)
    panel['c26'] = ((panel['buy_heavy'] == 1) & (panel['vol_expansion'] == 1)).astype(int)

    panel['any_signal'] = ((panel['c23'] == 1) | (panel['c24'] == 1) | (panel['c25'] == 1) | (panel['c26'] == 1)).astype(int)
    panel['signal_count'] = panel['c23'] + panel['c24'] + panel['c25'] + panel['c26']
    panel['cofire_2'] = (panel['signal_count'] >= 2).astype(int)

    panel['always_c23'] = panel['c23']
    panel['always_c24'] = panel['c24']

    return panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL])


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("always_c23", "Always use C23 signal (illiq × vol_exp)", family="signal", primary=True),
    StateSpec("always_c24", "Always use C24 signal (ceiling × vol_exp)", family="signal"),
    StateSpec("any_signal", "Use any signal that fires that day (union)", family="routing"),
    StateSpec("cofire_2", "2+ signals fire same day (regime strength)", family="regime"),
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
    c23_ic = results[results["name"] == "always_c23"]["avg_ic"].iloc[0] if not results.empty else 0
    any_sig_ic = results[results["name"] == "any_signal"]["avg_ic"].iloc[0] if not results.empty else 0
    cofire2_ic = results[results["name"] == "cofire_2"]["avg_ic"].iloc[0] if not results.empty else 0

    c23_lift = c23_ic - baseline_ic
    union_lift = any_sig_ic - baseline_ic
    cofire2_lift = cofire2_ic - baseline_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    if union_lift > 0.005 and c23_lift > 0.005:
        decision = "PASSED"
    elif union_lift > c23_lift + 0.005:
        decision = "MIXED"
    elif cofire2_lift > c23_lift + 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "c23_ic": float(c23_ic),
            "c23_lift": float(c23_lift),
            "any_signal_ic": float(any_sig_ic),
            "union_lift": float(union_lift),
            "cofire_2_ic": float(cofire2_ic),
            "cofire_2_lift": float(cofire2_lift),
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": str(results_path),
            "yearly": str(yearly_path),
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"Always C23 IC: {c23_ic:.4f} (lift: {c23_lift:+.4f})")
    print(f"Any signal (union) IC: {any_sig_ic:.4f} (lift: {union_lift:+.4f})")
    print(f"Co-fire 2+ IC: {cofire2_ic:.4f} (lift: {cofire2_lift:+.4f})")
    print(f"\nSummary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()