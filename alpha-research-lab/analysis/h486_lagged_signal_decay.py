"""
H486 / BJ: lagged_signal_decay

Hypothesis: C23 works at 1d (IC 0.26), C24 multi-day works. Test if signal
effectiveness DECAYS or IMPROVES at longer horizons. C24 multi-day showed
temporal structure works. Mechanism: signals have natural holding periods.

Test:
- Compute C23 (high_illiq × vol_expansion) and C24 (ceiling_count >= 2 × vol_expansion)
- Evaluate at 1d, 2d, 3d barrier labels
- Does signal effectiveness decay or improve at longer horizons?

Decision rule:
- PASSED: best horizon has IC > baseline (1d) by +0.01+
- MIXED: 2d/3d similar to 1d
- FAILED: 1d is best, decay consistent
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from pathlib import Path
import re

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "lagged_signal_decay"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23 works at 1d (IC 0.26), C24 multi-day works. Test if signal "
        "effectiveness DECAYS or IMPROVES at longer horizons. C24 multi-day showed "
        "temporal structure works. Mechanism: signals have natural holding periods."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={"s1_barrier_hit_1d": "1d barrier", "s1_barrier_hit_2d": "2d barrier", "s1_barrier_hit_3d": "3d barrier"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H486 lagged_signal_decay")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--stock-path", type=str,
                        default=str(data_path("stock/")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_amihud(panel: pd.DataFrame, stock_path: str) -> pd.DataFrame:
    """Compute Amihud illiquidity from raw OHLCV files (gia_lich_su_TICKER_1D.parquet format)."""
    stock_dir = Path(stock_path)
    if not stock_dir.exists():
        return panel

    stock_files = list(stock_dir.glob("gia_lich_su_*_1D.parquet"))
    if not stock_files:
        return panel

    amihud_list = []
    for sf in stock_files:
        ticker = sf.stem.replace("gia_lich_su_", "").replace("_1D", "")
        try:
            df = pd.read_parquet(sf)
            if "time" not in df.columns or "close" not in df.columns:
                continue
            df = df.copy()
            df["ticker"] = ticker
            df = df.sort_values("time")

            if "volume" in df.columns and "close" in df.columns:
                df["daily_return"] = df["close"].pct_change().abs()
                df["turnover"] = df["close"] * df["volume"] / 1e9
                df["amihud"] = df["daily_return"] / (df["turnover"] + 1e-9)
                df["amihud_20d"] = df["amihud"].rolling(20, min_periods=10).mean()
                amihud_list.append(df[["time", "ticker", "amihud_20d"]])
        except Exception:
            continue

    if amihud_list:
        amihud_df = pd.concat(amihud_list, ignore_index=True)
        panel = panel.merge(amihud_df, on=["time", "ticker"], how="left")
    return panel


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    s1_path = Path(args.s1_path)
    s1_files = list(s1_path.glob("*.parquet")) if s1_path.is_dir() else [s1_path]

    dfs = []
    for sf in s1_files:
        df = pd.read_parquet(sf)
        dfs.append(df)

    panel = pd.concat(dfs, ignore_index=True)

    if "actual" in panel.columns and "s1_barrier_hit_1d" not in panel.columns:
        panel = panel.rename(columns={"actual": "s1_barrier_hit_1d"})
    if "xs_proba" in panel.columns and S1_SCORE_COL not in panel.columns:
        panel = panel.rename(columns={"xs_proba": S1_SCORE_COL})

    panel = panel[panel[S1_SCORE_COL].notna()]
    panel["time"] = pd.to_datetime(panel["time"])
    panel = panel[(panel["time"].dt.year >= spec.start_year) & (panel["time"].dt.year <= spec.end_year)]

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

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

    panel = compute_amihud(panel, args.stock_path)

    panel = panel.sort_values(["ticker", "time"])

    panel["at_ceiling"] = (panel["pct_change"] >= 6.5).astype(bool)
    panel["ceiling_count_3d"] = panel.groupby("ticker")["at_ceiling"].transform(
        lambda x: x.rolling(window=3, min_periods=2).sum()
    )
    panel["ceiling_2_of_3"] = (panel["ceiling_count_3d"] >= 2).astype(bool)

    pct_change_vol = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    vol_change = pct_change_vol.diff()
    panel["vol_change"] = vol_change
    panel = panel.dropna(subset=["vol_change"])

    vol_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = (vol_rank >= 0.8).astype(bool)

    if "amihud_20d" in panel.columns:
        illiq_rank = panel.groupby("time", sort=False)["amihud_20d"].rank(method="average", pct=True, ascending=False)
        panel["high_illiq"] = (illiq_rank >= 0.8).astype(bool)
    else:
        panel["high_illiq"] = False

    panel["c23_high_illiq_exp"] = (panel["high_illiq"] & panel["vol_expansion"]).astype(bool)
    panel["c24_ceiling_2_exp"] = (panel["ceiling_2_of_3"] & panel["vol_expansion"]).astype(bool)

    panel["c23_alone"] = panel["high_illiq"].astype(bool)
    panel["c24_alone"] = panel["ceiling_2_of_3"].astype(bool)
    panel["vol_exp_alone"] = panel["vol_expansion"].astype(bool)

    panel["all_rows"] = True

    panel = panel.dropna(subset=[S1_SCORE_COL, "s1_barrier_hit_1d"])

    panel = panel.sort_values(["ticker", "time"])
    panel["s1_barrier_hit_2d"] = panel.groupby("ticker")["s1_barrier_hit_1d"].shift(-1).fillna(0).astype(int)
    panel["s1_barrier_hit_3d"] = panel.groupby("ticker")["s1_barrier_hit_1d"].shift(-2).fillna(0).astype(int)

    return panel


def evaluate_at_horizon(panel: pd.DataFrame, state_name: str, target_col: str) -> dict:
    """Evaluate a state's IC at a specific horizon."""
    if state_name == "all_rows":
        mask = panel[target_col].notna()
    elif state_name == "c23_high_illiq_exp":
        mask = panel["c23_high_illiq_exp"] & panel[target_col].notna()
    elif state_name == "c24_ceiling_2_exp":
        mask = panel["c24_ceiling_2_exp"] & panel[target_col].notna()
    elif state_name == "c23_alone":
        mask = panel["c23_alone"] & panel[target_col].notna()
    elif state_name == "c24_alone":
        mask = panel["c24_alone"] & panel[target_col].notna()
    elif state_name == "vol_exp_alone":
        mask = panel["vol_exp_alone"] & panel[target_col].notna()
    else:
        return {"ic": np.nan, "rows": 0}

    if mask.sum() < 100:
        return {"ic": np.nan, "rows": int(mask.sum())}

    scores = panel.loc[mask, S1_SCORE_COL]
    targets = panel.loc[mask, target_col]

    if len(scores) < 100:
        return {"ic": np.nan, "rows": int(len(scores))}

    ic = np.corrcoef(scores, targets)[0, 1]
    return {"ic": ic, "rows": int(len(scores))}


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

    print(f"Panel loaded: {len(panel)} rows")

    states = ["all_rows", "c23_high_illiq_exp", "c24_ceiling_2_exp", "c23_alone", "c24_alone", "vol_exp_alone"]
    horizons = ["s1_barrier_hit_1d", "s1_barrier_hit_2d", "s1_barrier_hit_3d"]

    results = []
    for state in states:
        for horizon in horizons:
            result = evaluate_at_horizon(panel, state, horizon)
            results.append({
                "state": state,
                "horizon": horizon,
                "ic": result["ic"],
                "rows": result["rows"],
            })

    results_df = pd.DataFrame(results)

    baseline_1d = results_df[(results_df["state"] == "all_rows") & (results_df["horizon"] == "s1_barrier_hit_1d")]["ic"].iloc[0]
    baseline_2d = results_df[(results_df["state"] == "all_rows") & (results_df["horizon"] == "s1_barrier_hit_2d")]["ic"].iloc[0]
    baseline_3d = results_df[(results_df["state"] == "all_rows") & (results_df["horizon"] == "s1_barrier_hit_3d")]["ic"].iloc[0]

    c23_exp_1d = results_df[(results_df["state"] == "c23_high_illiq_exp") & (results_df["horizon"] == "s1_barrier_hit_1d")]["ic"].iloc[0]
    c23_exp_2d = results_df[(results_df["state"] == "c23_high_illiq_exp") & (results_df["horizon"] == "s1_barrier_hit_2d")]["ic"].iloc[0]
    c23_exp_3d = results_df[(results_df["state"] == "c23_high_illiq_exp") & (results_df["horizon"] == "s1_barrier_hit_3d")]["ic"].iloc[0]

    c24_exp_1d = results_df[(results_df["state"] == "c24_ceiling_2_exp") & (results_df["horizon"] == "s1_barrier_hit_1d")]["ic"].iloc[0]
    c24_exp_2d = results_df[(results_df["state"] == "c24_ceiling_2_exp") & (results_df["horizon"] == "s1_barrier_hit_2d")]["ic"].iloc[0]
    c24_exp_3d = results_df[(results_df["state"] == "c24_ceiling_2_exp") & (results_df["horizon"] == "s1_barrier_hit_3d")]["ic"].iloc[0]

    c23_lift_2d = c23_exp_2d - c23_exp_1d if not np.isnan(c23_exp_2d) else np.nan
    c23_lift_3d = c23_exp_3d - c23_exp_1d if not np.isnan(c23_exp_3d) else np.nan
    c24_lift_2d = c24_exp_2d - c24_exp_1d if not np.isnan(c24_exp_2d) else np.nan
    c24_lift_3d = c24_exp_3d - c24_exp_1d if not np.isnan(c24_exp_3d) else np.nan

    best_horizon_c23 = max([(1, c23_exp_1d), (2, c23_exp_2d), (3, c23_exp_3d)], key=lambda x: x[1] if not np.isnan(x[1]) else -1)
    best_horizon_c24 = max([(1, c24_exp_1d), (2, c24_exp_2d), (3, c24_exp_3d)], key=lambda x: x[1] if not np.isnan(x[1]) else -1)

    decision = "FAILED"
    if (c23_lift_2d > 0.01 or c23_lift_3d > 0.01 or c24_lift_2d > 0.01 or c24_lift_3d > 0.01):
        decision = "PASSED"
    elif (abs(c23_lift_2d) < 0.005 and abs(c23_lift_3d) < 0.005 and abs(c24_lift_2d) < 0.005 and abs(c24_lift_3d) < 0.005):
        decision = "MIXED"

    results_path = write_dataframe_artifact(results_df, context, f"{BRANCH_NAME}_results")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "baseline_1d": float(baseline_1d),
            "baseline_2d": float(baseline_2d),
            "baseline_3d": float(baseline_3d),
            "c23_exp_1d": float(c23_exp_1d),
            "c23_exp_2d": float(c23_exp_2d),
            "c23_exp_3d": float(c23_exp_3d),
            "c23_lift_2d": float(c23_lift_2d),
            "c23_lift_3d": float(c23_lift_3d),
            "c24_exp_1d": float(c24_exp_1d),
            "c24_exp_2d": float(c24_exp_2d),
            "c24_exp_3d": float(c24_exp_3d),
            "c24_lift_2d": float(c24_lift_2d),
            "c24_lift_3d": float(c24_lift_3d),
            "best_horizon_c23": int(best_horizon_c23[0]),
            "best_horizon_c24": int(best_horizon_c24[0]),
        },
        artifacts={"results": results_path},
        metadata={"hypothesis": SPEC.hypothesis},
    )

    print("\n=== LAGGED SIGNAL DECAY TEST ===")
    print(f"\nBaseline (all rows):")
    print(f"  1d: {baseline_1d:.4f}")
    print(f"  2d: {baseline_2d:.4f}")
    print(f"  3d: {baseline_3d:.4f}")

    print(f"\nC23 (high_illiq × vol_expansion):")
    print(f"  1d: {c23_exp_1d:.4f}")
    print(f"  2d: {c23_exp_2d:.4f} (lift: {c23_lift_2d:+.4f})")
    print(f"  3d: {c23_exp_3d:.4f} (lift: {c23_lift_3d:+.4f})")

    print(f"\nC24 (ceiling_2 × vol_expansion):")
    print(f"  1d: {c24_exp_1d:.4f}")
    print(f"  2d: {c24_exp_2d:.4f} (lift: {c24_lift_2d:+.4f})")
    print(f"  3d: {c24_exp_3d:.4f} (lift: {c24_lift_3d:+.4f})")

    print(f"\nBest horizon: C23=d{best_horizon_c23[0]}, C24=d{best_horizon_c24[0]}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")

    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()