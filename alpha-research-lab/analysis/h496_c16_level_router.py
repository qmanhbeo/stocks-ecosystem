"""
BR10: c16_level_router

Hypothesis: H120 found C16 works at IC 0.077. C23 works at IC 0.26. Test: use C16
LEVEL (high vs low) as ROUTER — when C16 is HIGH, use C23; when C16 is LOW, use C16
alone. Different regimes need different signals. Mechanism: high C16 regime = strong
order pressure, low C16 regime = weak order pressure — route signals accordingly.

First test: C23 × C16_level_high vs C23 × C16_level_low vs C16_high alone vs random baseline.
C16 from order_stats buy/sell volume ratio.
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


BRANCH_NAME = "c16_level_router"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H120 found C16 works at IC 0.077. C23 works at IC 0.26. "
        "Test: use C16 LEVEL (high vs low) as ROUTER — when C16 HIGH use C23, "
        "when C16 LOW use C16 alone. Different regimes need different signals."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR10 c16_level_router test")
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
    order_stats["buy_volume"] = order_stats["buy_order_volume"]
    order_stats["sell_volume"] = order_stats["sell_order_volume"]
    order_stats["c16_proxy"] = (order_stats["buy_volume"] - order_stats["sell_volume"]) / (
        order_stats["buy_volume"] + order_stats["sell_volume"] + 1
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "c16_proxy"]],
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

    if "amihud_20d_avg" in panel.columns and panel["amihud_20d_avg"].notna().any():
        amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
        panel["high_illiq"] = amihud_rank >= 0.8
    else:
        panel["high_illiq"] = False

    panel["high_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]

    if "c16_proxy" in panel.columns and panel["c16_proxy"].notna().any():
        c16_rank = panel.groupby("time", sort=False)["c16_proxy"].rank(method="average", pct=True)
        panel["c16_high"] = c16_rank >= 0.80
        panel["c16_low"] = c16_rank <= 0.20
        panel["c16_mid"] = (c16_rank > 0.20) & (c16_rank < 0.80)
    else:
        panel["c16_high"] = False
        panel["c16_low"] = False
        panel["c16_mid"] = False

    panel["c16_high_illiq_exp"] = panel["c16_high"] & panel["high_illiq_expansion"]
    panel["c16_low_illiq_exp"] = panel["c16_low"] & panel["high_illiq_expansion"]
    panel["c16_high_alone"] = panel["c16_high"]
    panel["c16_low_alone"] = panel["c16_low"]

    panel["near_ceiling"] = (panel["pct_change"] >= 5.0) & (panel["pct_change"] <= 7.0)
    panel["at_limit"] = panel["pct_change"] >= 6.5
    panel["limit_1_of_3"] = (
        panel.groupby("ticker")["at_limit"].transform(lambda x: x.rolling(3, min_periods=3).sum())
    )
    panel["limit_2_of_3"] = panel["limit_1_of_3"] >= 2
    panel["ceiling_2_expansion"] = panel["limit_2_of_3"] & panel["vol_expansion"]

    panel["c16_high_ceiling_2"] = panel["c16_high"] & panel["limit_2_of_3"]
    panel["c16_low_ceiling_2"] = panel["c16_low"] & panel["limit_2_of_3"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("high_illiq_expansion", "C23: illiq × vol expansion", family="signal", primary=True),
    StateSpec("ceiling_2_expansion", "C24: ceiling 2/3 × vol expansion", family="signal"),
    StateSpec("c16_high", "C16 level HIGH (top 20%)", family="c16_regime"),
    StateSpec("c16_low", "C16 level LOW (bottom 20%)", family="c16_regime"),
    StateSpec("c16_mid", "C16 level MID (40-60%)", family="c16_regime"),
    StateSpec("c16_high_illiq_exp", "C16 HIGH × C23", family="router", primary=True),
    StateSpec("c16_low_illiq_exp", "C16 LOW × C23", family="router"),
    StateSpec("c16_high_alone", "C16 HIGH alone", family="c16_regime"),
    StateSpec("c16_low_alone", "C16 LOW alone", family="c16_regime"),
    StateSpec("c16_high_ceiling_2", "C16 HIGH × C24", family="router"),
    StateSpec("c16_low_ceiling_2", "C16 LOW × C24", family="router"),
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

    c24_ic = results[results["name"] == "ceiling_2_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c24_lift = c24_ic - baseline_ic

    c16_high_ic = results[results["name"] == "c16_high"]["avg_ic"].iloc[0] if not results.empty else 0
    c16_low_ic = results[results["name"] == "c16_low"]["avg_ic"].iloc[0] if not results.empty else 0
    c16_high_lift = c16_high_ic - baseline_ic
    c16_low_lift = c16_low_ic - baseline_ic

    high_c23_ic = results[results["name"] == "c16_high_illiq_exp"]["avg_ic"].iloc[0] if not results.empty else 0
    low_c23_ic = results[results["name"] == "c16_low_illiq_exp"]["avg_ic"].iloc[0] if not results.empty else 0
    high_c23_lift = high_c23_ic - baseline_ic
    low_c23_lift = low_c23_ic - baseline_ic

    high_c24_ic = results[results["name"] == "c16_high_ceiling_2"]["avg_ic"].iloc[0] if not results.empty else 0
    low_c24_ic = results[results["name"] == "c16_low_ceiling_2"]["avg_ic"].iloc[0] if not results.empty else 0

    c16_high_alone_ic = results[results["name"] == "c16_high_alone"]["avg_ic"].iloc[0] if not results.empty else 0
    c16_low_alone_ic = results[results["name"] == "c16_low_alone"]["avg_ic"].iloc[0] if not results.empty else 0

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    high_vs_low = high_c23_lift - low_c23_lift
    c16_routing_benefit = max(high_c23_lift, low_c23_lift) - c23_lift

    if c16_routing_benefit > 0.01:
        decision = "PASSED"
    elif high_vs_low > 0.01:
        decision = "MIXED"
    elif c16_high_lift > 0.005 or c16_low_lift > 0.005:
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
            "c24_ic": float(c24_ic),
            "c24_lift": float(c24_lift),
            "c16_high_ic": float(c16_high_ic),
            "c16_low_ic": float(c16_low_ic),
            "c16_high_lift": float(c16_high_lift),
            "c16_low_lift": float(c16_low_lift),
            "c16_high_c23_ic": float(high_c23_ic),
            "c16_low_c23_ic": float(low_c23_ic),
            "c16_high_c23_lift": float(high_c23_lift),
            "c16_low_c23_lift": float(low_c23_lift),
            "c16_high_ceiling_2_ic": float(high_c24_ic),
            "c16_low_ceiling_2_ic": float(low_c24_ic),
            "c16_high_alone_ic": float(c16_high_alone_ic),
            "c16_low_alone_ic": float(c16_low_alone_ic),
            "high_vs_low_benefit": float(high_vs_low),
            "routing_benefit": float(c16_routing_benefit),
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
    print(f"C23 (illiq × exp): IC={c23_ic:.4f}, lift={c23_lift:+.4f}")
    print(f"C24 (ceiling × exp): IC={c24_ic:.4f}, lift={c24_lift:+.4f}")
    print(f"\nC16 level alone:")
    print(f"  c16_high: IC={c16_high_ic:.4f}, lift={c16_high_lift:+.4f}")
    print(f"  c16_low: IC={c16_low_ic:.4f}, lift={c16_low_lift:+.4f}")
    print(f"\nC16 × signals:")
    print(f"  c16_high × C23: IC={high_c23_ic:.4f}, lift={high_c23_lift:+.4f}")
    print(f"  c16_low × C23: IC={low_c23_ic:.4f}, lift={low_c23_lift:+.4f}")
    print(f"  c16_high × C24: IC={high_c24_ic:.4f}")
    print(f"  c16_low × C24: IC={low_c24_ic:.4f}")
    print(f"\nRouting benefit (high_vs_low): {high_vs_low:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
