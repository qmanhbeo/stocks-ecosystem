"""
BR4: breadth_illiq_regime_interaction

Hypothesis: H481 found narrow > broad. C23 is strongest signal. Test illiq × vol_exp ×
narrow_breadth combo. H481 tested breadth ALONE, not COMBO. Mechanism: regime interaction
boost - narrow amplifies illiq effect.

First test: high_illiq × vol_expansion × narrow_breadth vs controls (each component alone,
each pair, combo).
Compare with C23 (illiq × exp) and breadth × vol_expansion controls.
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


BRANCH_NAME = "breadth_illiq_regime_interaction"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H481 found narrow > broad. C23 is strongest signal. Test illiq × vol_exp × "
        "narrow_breadth combo. H481 tested breadth ALONE, not COMBO. "
        "Mechanism: regime interaction boost - narrow amplifies illiq effect."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR4 breadth_illiq_regime_interaction test")
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
    order_stats["advancing"] = order_stats["pct_change"] > 0
    order_stats["declining"] = order_stats["pct_change"] < 0

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "advancing", "declining"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    panel = panel.sort_values(["ticker", "time"])

    breadth = (
        panel.groupby("time")["advancing"]
        .mean()
        .rename("breadth")
        .reset_index()
    )
    breadth["narrow_breadth"] = breadth["breadth"] <= 0.20
    breadth["broad_breadth"] = breadth["breadth"] >= 0.80
    panel = panel.merge(breadth[["time", "narrow_breadth", "broad_breadth"]], on="time", how="left")
    panel["narrow_breadth"] = panel["narrow_breadth"].fillna(False)
    panel["broad_breadth"] = panel["broad_breadth"].fillna(False)

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    if "amihud_20d_avg" in panel.columns and panel["amihud_20d_avg"].notna().any():
        amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
        panel["high_illiq"] = amihud_rank >= 0.8
    else:
        panel["high_illiq"] = False

    panel["high_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["illiq_narrow"] = panel["high_illiq"] & panel["narrow_breadth"]
    panel["illiq_broad"] = panel["high_illiq"] & panel["broad_breadth"]
    panel["vol_narrow"] = panel["vol_expansion"] & panel["narrow_breadth"]
    panel["high_illiq_expansion_narrow"] = panel["high_illiq"] & panel["vol_expansion"] & panel["narrow_breadth"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("high_illiq_expansion", "C23: illiq × vol expansion", family="component", primary=True),
    StateSpec("narrow_breadth", "Narrow market (breadth <= 20%)", family="breadth"),
    StateSpec("vol_expansion", "Vol expansion (top 20%)", family="vol"),
    StateSpec("high_illiq", "High illiquidity alone", family="illiq"),
    StateSpec("illiq_narrow", "illiq × narrow breadth", family="combo"),
    StateSpec("illiq_broad", "illiq × broad breadth", family="combo"),
    StateSpec("vol_narrow", "vol expansion × narrow breadth", family="combo"),
    StateSpec("high_illiq_expansion_narrow", "Triple: illiq × vol × narrow breadth", family="combo", primary=True),
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

    c23_ic = results[results["name"] == "high_illiq_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c23_lift = c23_ic - baseline_ic

    triple_ic = results[results["name"] == "high_illiq_expansion_narrow"]["avg_ic"].iloc[0] if not results.empty else 0
    triple_lift = triple_ic - baseline_ic

    narrow_ic = results[results["name"] == "narrow_breadth"]["avg_ic"].iloc[0] if not results.empty else 0
    narrow_lift = narrow_ic - baseline_ic

    vol_narrow_ic = results[results["name"] == "vol_narrow"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_narrow_lift = vol_narrow_ic - baseline_ic

    illiq_narrow_ic = results[results["name"] == "illiq_narrow"]["avg_ic"].iloc[0] if not results.empty else 0
    illiq_narrow_lift = illiq_narrow_ic - baseline_ic

    illiq_broad_ic = results[results["name"] == "illiq_broad"]["avg_ic"].iloc[0] if not results.empty else 0
    illiq_broad_lift = illiq_broad_ic - baseline_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    incremental = triple_lift - c23_lift

    if triple_lift > c23_lift + 0.01:
        decision = "PASSED"
    elif triple_lift > c23_lift:
        decision = "MIXED"
    elif triple_lift > 0.01:
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
            "triple_ic": float(triple_ic),
            "triple_lift": float(triple_lift),
            "narrow_lift": float(narrow_lift),
            "vol_narrow_lift": float(vol_narrow_lift),
            "illiq_narrow_lift": float(illiq_narrow_lift),
            "illiq_broad_lift": float(illiq_broad_lift),
            "incremental_vs_c23": float(incremental),
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
    print(f"C23 (illiq × exp): IC={c23_ic:.4f}, lift={c23_lift:+.4f}")
    print(f"Triple (illiq × exp × narrow): IC={triple_ic:.4f}, lift={triple_lift:+.4f}, incremental={incremental:+.4f}")
    print(f"narrow_breadth alone: IC={narrow_ic:.4f}, lift={narrow_lift:+.4f}")
    print(f"vol_narrow: IC={vol_narrow_ic:.4f}, lift={vol_narrow_lift:+.4f}")
    print(f"illiq × narrow: IC={illiq_narrow_ic:.4f}, lift={illiq_narrow_lift:+.4f}")
    print(f"illiq × broad: IC={illiq_broad_ic:.4f}, lift={illiq_broad_lift:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
