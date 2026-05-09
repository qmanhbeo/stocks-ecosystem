"""
BU5: sector_vol_regime

Hypothesis: Sector-level vol expansion (sector >50% stocks hitting vol_expansion) as regime gate.
D038 killed sector MOMENTUM gate; sector VOL regime is different mechanism.
Test: sector_vol_exp × C23 vs C23 alone vs random baseline.
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


BRANCH_NAME = "sector_vol_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Sector-level vol expansion as regime gate. D038 killed sector MOMENTUM, "
        "test sector VOL regime (sector >50% stocks hitting vol_expansion) × C23 vs C23 alone."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BU5: sector_vol_regime test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--sector-path", type=str,
                        default=str(data_path("features/sector_classification.parquet")))
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

    sector = pd.read_parquet(args.sector_path)
    sector = sector.rename(columns={'symbol': 'ticker'})
    sector['ticker'] = sector['ticker'].astype(str).str.upper()
    panel = panel.merge(sector[['ticker', 'icb_name2']], on='ticker', how='left')
    panel = panel.rename(columns={'icb_name2': 'sector'})

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

    order_stats['vol_change'] = order_stats.groupby('ticker')['volume_daily'].pct_change()
    vol_expansion = order_stats.groupby('date')['vol_change'].transform(
        lambda x: x >= x.quantile(0.8)
    )
    order_stats['vol_expansion'] = vol_expansion.astype(int)

    order_stats_renamed = order_stats.rename(columns={'date': 'time'})
    panel = panel.merge(
        order_stats_renamed[['ticker', 'time', 'buy_heavy', 'vol_expansion']],
        on=['ticker', 'time'],
        how='left'
    )

    amihud_p80 = panel['amihud'].quantile(0.8)
    panel['high_illiq'] = (panel['amihud'] > amihud_p80).astype(int)

    panel['c23'] = ((panel['high_illiq'] == 1) & (panel['vol_expansion'] == 1)).astype(int)

    sector_vol = panel[panel['vol_expansion'] == 1].groupby(['time', 'sector']).size().reset_index(name='sector_vol_count')
    sector_total = panel.groupby(['time', 'sector']).size().reset_index(name='sector_total_count')
    sector_vol = sector_vol.merge(sector_total, on=['time', 'sector'])
    sector_vol['sector_vol_pct'] = sector_vol['sector_vol_count'] / sector_vol['sector_total_count']
    sector_vol['sector_vol_exp'] = (sector_vol['sector_vol_pct'] > 0.5).astype(int)

    panel = panel.merge(sector_vol[['time', 'sector', 'sector_vol_exp']], on=['time', 'sector'], how='left')
    panel['sector_vol_exp'] = panel['sector_vol_exp'].fillna(0).astype(int)

    panel['sector_c23'] = ((panel['sector_vol_exp'] == 1) & (panel['c23'] == 1)).astype(int)
    panel['always_c23'] = panel['c23']

    return panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL, 'sector'])


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("always_c23", "Always use C23 signal (illiq × vol_exp)", family="signal", primary=True),
    StateSpec("sector_vol_exp", "Sector in vol expansion regime (>50% stocks)", family="sector_regime"),
    StateSpec("sector_c23", "C23 within sector in vol expansion regime", family="sector_regime"),
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
    sector_vol_ic = results[results["name"] == "sector_vol_exp"]["avg_ic"].iloc[0] if not results.empty else 0
    sector_c23_ic = results[results["name"] == "sector_c23"]["avg_ic"].iloc[0] if not results.empty else 0

    c23_lift = c23_ic - baseline_ic
    sector_c23_lift = sector_c23_ic - baseline_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    if sector_c23_lift > 0.01 and c23_lift > 0.01:
        decision = "PASSED"
    elif sector_c23_lift > c23_lift + 0.005:
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
            "sector_vol_exp_ic": float(sector_vol_ic),
            "sector_c23_ic": float(sector_c23_ic),
            "sector_c23_lift": float(sector_c23_lift),
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
    print(f"Sector vol expansion IC: {sector_vol_ic:.4f}")
    print(f"Sector × C23 IC: {sector_c23_ic:.4f} (lift: {sector_c23_lift:+.4f})")
    print(f"\nSummary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()