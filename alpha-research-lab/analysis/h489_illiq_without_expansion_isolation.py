"""
BR3: illiq_without_expansion_isolation

Hypothesis: C23 = illiq × vol_exp together (IC +0.1318). But illiq ALONE (high_illiq
without vol_exp) = IC +0.0731 (+0.0731 vs baseline 0.1298). Test high_illiq WITHOUT
vol_exp as standalone signal. If positive, illiq alone is independent signal, not
dependent on vol regime.

First test: high_illiq alone vs high_illiq × vol_expansion vs random baseline.
Compare with C23 (combo) and illiq × vol_contraction.
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


BRANCH_NAME = "illiq_without_expansion_isolation"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23 = illiq × vol_exp together (IC +0.1318). But illiq ALONE (high_illiq "
        "without vol_exp) = IC +0.0731. Test high_illiq WITHOUT vol_exp as standalone. "
        "If positive, illiq alone is independent signal, not dependent on vol regime."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR3 illiq_without_expansion_isolation test")
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
            df["ticker"] = ticker
            ohlcv_dfs.append(df)
        except:
            continue

    if ohlcv_dfs:
        ohlcv = pd.concat(ohlcv_dfs, ignore_index=True)
        ohlcv = ohlcv.rename(columns={"date": "time"})
        ohlcv["time"] = pd.to_datetime(ohlcv["time"])
        ohlcv = ohlcv[ohlcv["time"].dt.year <= 2025]
        ohlcv = compute_amihud(ohlcv)
        ohlcv = ohlcv.sort_values(["ticker", "time"])
        ohlcv["amihud_20d_avg"] = ohlcv.groupby("ticker")["amihud"].transform(
            lambda x: x.rolling(window=20, min_periods=10).mean()
        )
        panel = panel.merge(
            ohlcv[["time", "ticker", "amihud_20d_avg"]],
            on=["time", "ticker"],
            how="left",
        )
    else:
        panel["amihud_20d_avg"] = np.nan

    order_stats = pd.read_parquet(args.order_stats_path)
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
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    panel = panel.sort_values(["ticker", "time"])

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8
    panel["vol_contraction"] = vol_change_rank <= 0.2

    if "amihud_20d_avg" in panel.columns and panel["amihud_20d_avg"].notna().any():
        amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
        panel["high_illiq"] = amihud_rank >= 0.8
        panel["mid_illiq"] = (amihud_rank > 0.3) & (amihud_rank < 0.7)
        panel["low_illiq"] = amihud_rank <= 0.2
    else:
        panel["high_illiq"] = False
        panel["mid_illiq"] = False
        panel["low_illiq"] = False

    panel["high_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["high_illiq_alone"] = panel["high_illiq"] & ~panel["vol_expansion"]
    panel["high_illiq_contraction"] = panel["high_illiq"] & panel["vol_contraction"]
    panel["low_illiq_expansion"] = panel["low_illiq"] & panel["vol_expansion"]
    panel["low_illiq_contraction"] = panel["low_illiq"] & panel["vol_contraction"]
    panel["mid_illiq_expansion"] = panel["mid_illiq"] & panel["vol_expansion"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("high_illiq", "High illiquidity alone (top 20%)", family="illiq"),
    StateSpec("mid_illiq", "Mid illiquidity (40-60%)", family="illiq"),
    StateSpec("low_illiq", "Low illiquidity (bottom 20%)", family="illiq"),
    StateSpec("high_illiq_expansion", "C23: High illiq + Vol expansion", family="illiq_vol", primary=True),
    StateSpec("high_illiq_alone", "High illiq WITHOUT vol expansion", family="illiq_vol"),
    StateSpec("high_illiq_contraction", "High illiq + Vol contraction", family="illiq_vol"),
    StateSpec("low_illiq_expansion", "Low illiq + Vol expansion", family="illiq_vol"),
    StateSpec("low_illiq_contraction", "Low illiq + Vol contraction", family="illiq_vol"),
    StateSpec("mid_illiq_expansion", "Mid illiq + Vol expansion", family="illiq_vol"),
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

    high_illiq_ic = results[results["name"] == "high_illiq"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_lift = high_illiq_ic - baseline_ic

    high_illiq_exp_ic = results[results["name"] == "high_illiq_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_exp_lift = high_illiq_exp_ic - baseline_ic

    high_illiq_alone_ic = results[results["name"] == "high_illiq_alone"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_alone_lift = high_illiq_alone_ic - baseline_ic

    high_illiq_cont_ic = results[results["name"] == "high_illiq_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_cont_lift = high_illiq_cont_ic - baseline_ic

    low_illiq_ic = results[results["name"] == "low_illiq"]["avg_ic"].iloc[0] if not results.empty else 0
    low_illiq_lift = low_illiq_ic - baseline_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    illiq_in_expansion = panel["high_illiq_expansion"].sum()
    illiq_alone = panel["high_illiq_alone"].sum()
    illiq_in_contraction = panel["high_illiq_contraction"].sum()

    if high_illiq_alone_lift > 0.01 and high_illiq_alone_lift > 0.005 * high_illiq_exp_lift:
        decision = "PASSED"
    elif high_illiq_alone_lift > 0.01:
        decision = "PASSED"
    elif high_illiq_lift > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "high_illiq_ic": float(high_illiq_ic),
            "high_illiq_lift": float(high_illiq_lift),
            "high_illiq_expansion_ic": float(high_illiq_exp_ic),
            "high_illiq_expansion_lift": float(high_illiq_exp_lift),
            "high_illiq_alone_ic": float(high_illiq_alone_ic),
            "high_illiq_alone_lift": float(high_illiq_alone_lift),
            "high_illiq_contraction_ic": float(high_illiq_cont_ic),
            "high_illiq_contraction_lift": float(high_illiq_cont_lift),
            "low_illiq_ic": float(low_illiq_ic),
            "low_illiq_lift": float(low_illiq_lift),
            "illiq_in_expansion_rows": int(illiq_in_expansion),
            "illiq_alone_rows": int(illiq_alone),
            "illiq_in_contraction_rows": int(illiq_in_contraction),
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
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
    print(f"\nIlliq alone:")
    print(f"  high_illiq: IC={high_illiq_ic:.4f}, lift={high_illiq_lift:+.4f}")
    print(f"  mid_illiq: IC={results[results['name']=='mid_illiq']['avg_ic'].iloc[0]:.4f}")
    print(f"  low_illiq: IC={low_illiq_ic:.4f}, lift={low_illiq_lift:+.4f}")
    print(f"\nIlliq × Vol regime:")
    print(f"  high_illiq_expansion (C23): IC={high_illiq_exp_ic:.4f}, lift={high_illiq_exp_lift:+.4f}")
    print(f"  high_illiq_alone: IC={high_illiq_alone_ic:.4f}, lift={high_illiq_alone_lift:+.4f}")
    print(f"  high_illiq_contraction: IC={high_illiq_cont_ic:.4f}, lift={high_illiq_cont_lift:+.4f}")
    print(f"\nRows breakdown:")
    print(f"  high_illiq in expansion: {illiq_in_expansion}")
    print(f"  high_illiq ALONE (no vol): {illiq_alone}")
    print(f"  high_illiq in contraction: {illiq_in_contraction}")
    print(f"\nSummary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
