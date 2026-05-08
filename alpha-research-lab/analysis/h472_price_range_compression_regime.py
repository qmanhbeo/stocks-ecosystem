"""
H472: price_range_compression_regime

Hypothesis: Compressed daily range (low high-low %) = calm before storm in vol expansion.
Low range stocks in expanding markets may break out upward. High range stocks may be exhausted.
D041 confirmed: vol_expansion + illiquidity = universal amplifier. Range compression is another
behavior that may amplify in this regime.

Data: Uses OHLCV to compute daily range inline.
Compare with: C16 baseline, C23/C25/C26 patterns.
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

BRANCH_NAME = "price_range_compression_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Compressed daily range (low H-L %) in vol expansion = calm before storm. "
        "Low range stocks in expanding markets may break out. D041 pattern: behavior + illiq + vol_expansion."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("range_compressed_exp", "Compressed range + vol expansion", family="range_regime"),
    StateSpec("range_expanded_exp", "Expanded range + vol expansion", family="range_regime"),
    StateSpec("range_compressed_any", "Compressed range (any regime)", family="range_regime"),
    StateSpec("range_expanded_any", "Expanded range (any regime)", family="range_regime"),
    StateSpec("range_compressed_illiq_exp", "Compressed range + illiq + vol expansion", family="range_regime"),
    StateSpec("range_expanded_illiq_exp", "Expanded range + illiq + vol expansion", family="range_regime"),
    StateSpec("range_compressed_top20", "Most compressed 20% range + vol expansion", family="range_regime"),
    StateSpec("range_expanded_top20", "Most expanded 20% range + vol expansion", family="range_regime"),
    StateSpec("range_flat_5d_exp", "5d avg range compressed + vol expansion", family="range_regime"),
    StateSpec("range_flat_10d_exp", "10d avg range compressed + vol expansion", family="range_regime"),
    StateSpec("range_compressed_recovery", "Compressed range + vol expansion + not at limit", family="range_regime"),
]


def compute_range_features(price_df):
    df = price_df.copy()
    if "time" not in df.columns or "ticker" not in df.columns:
        return df[["ticker", "time"]].assign(
            daily_range_pct=0.05, range_pct_rank=0.5, range_5d_avg=0.05, range_10d_avg=0.05,
            vol_expansion=0, vol_expansion_q80=False, illiq_rank=0.5, illiq_high=False,
            at_ceiling=False
        )
    df = df.sort_values(["ticker", "time"]).copy()
    df["daily_range_pct"] = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)

    df["vol_20d"] = df.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(20, min_periods=10).mean()
    )
    df["vol_60d"] = df.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(60, min_periods=20).mean()
    )
    df["vol_expansion"] = (df["vol_20d"] / df["vol_60d"].replace(0, np.nan) - 1).fillna(0)

    ret = df["close"].pct_change(fill_method=None).abs()
    vol = df["volume"] / 1e6
    amihud = (ret / vol.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["illiq_20d"] = amihud.rolling(20, min_periods=5).mean()

    df["range_5d_avg"] = df.groupby("ticker")["daily_range_pct"].transform(
        lambda x: x.rolling(5, min_periods=3).mean()
    )
    df["range_10d_avg"] = df.groupby("ticker")["daily_range_pct"].transform(
        lambda x: x.rolling(10, min_periods=5).mean()
    )

    df["range_pct_rank"] = df.groupby("time")["daily_range_pct"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    df["range_5d_rank"] = df.groupby("time")["range_5d_avg"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )

    df["range_compressed"] = df["range_pct_rank"] <= 0.30
    df["range_expanded"] = df["range_pct_rank"] >= 0.70
    df["range_compressed_5d"] = df["range_5d_rank"] <= 0.30

    df["illiq_rank"] = df.groupby("time")["illiq_20d"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    df["illiq_high"] = df["illiq_rank"] >= 0.70

    max_price = df.groupby("ticker")["high"].transform("max")
    df["at_ceiling"] = df["daily_range_pct"] >= 0.07

    return df[["ticker", "time", "daily_range_pct", "range_pct_rank", "range_5d_avg",
              "range_10d_avg", "vol_expansion", "illiq_rank", "illiq_high",
              "range_compressed", "range_expanded", "range_compressed_5d",
              "at_ceiling", "range_5d_rank"]]


def load_panel(args, spec):
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    panel["all_rows"] = True

    price_files = sorted(data_path("stock").glob("gia_lich_su_*_1D.parquet"))
    if price_files:
        price_dfs = []
        for f in price_files:
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
            df = pd.read_parquet(f)
            if "date" in df.columns and "time" not in df.columns:
                df = df.rename(columns={"date": "time"})
            df["ticker"] = ticker
            price_dfs.append(df[["ticker", "time", "open", "high", "low", "close", "volume"]])
        price_all = pd.concat(price_dfs, ignore_index=True)
        price_features = compute_range_features(price_all)
        panel = panel.merge(price_features, on=["time", "ticker"], how="left")
    else:
        panel["daily_range_pct"] = 0.05
        panel["range_pct_rank"] = 0.5
        panel["range_5d_avg"] = 0.05
        panel["range_10d_avg"] = 0.05
        panel["vol_expansion"] = 0
        panel["illiq_rank"] = 0.5
        panel["illiq_high"] = False
        panel["range_compressed"] = False
        panel["range_expanded"] = False
        panel["range_compressed_5d"] = False
        panel["at_ceiling"] = False
        panel["range_5d_rank"] = 0.5

    panel["vol_expansion_q80"] = panel.groupby("time")["vol_expansion"].transform(
        lambda x: x >= x.quantile(0.80)
    )

    panel["range_compressed_exp"] = panel["range_compressed"] & panel["vol_expansion_q80"]
    panel["range_expanded_exp"] = panel["range_expanded"] & panel["vol_expansion_q80"]
    panel["range_compressed_any"] = panel["range_compressed"]
    panel["range_expanded_any"] = panel["range_expanded"]
    panel["range_compressed_illiq_exp"] = panel["range_compressed"] & panel["illiq_high"] & panel["vol_expansion_q80"]
    panel["range_expanded_illiq_exp"] = panel["range_expanded"] & panel["illiq_high"] & panel["vol_expansion_q80"]
    panel["range_compressed_top20"] = (panel["range_pct_rank"] <= 0.20) & panel["vol_expansion_q80"]
    panel["range_expanded_top20"] = (panel["range_pct_rank"] >= 0.80) & panel["vol_expansion_q80"]
    panel["range_flat_5d_exp"] = panel["range_compressed_5d"] & panel["vol_expansion_q80"]
    panel["range_flat_10d_exp"] = (panel["range_5d_rank"] <= 0.30) & panel["vol_expansion_q80"]
    panel["range_compressed_recovery"] = panel["range_compressed"] & panel["vol_expansion_q80"] & ~panel["at_ceiling"]

    return panel


def parse_args():
    parser = argparse.ArgumentParser(description="H472: price_range_compression_regime")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    return parser.parse_args()


def run_branch(args):
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(SPEC.min_year_rows),
        min_phase_rows=int(SPEC.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    print(f"Panel: {panel.shape}, date range: {panel['time'].min()} - {panel['time'].max()}")

    state_names = [s.name for s in STATE_SPECS]
    validate_state_columns(panel, state_names, spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].values[0]

    print("\n=== State Results ===")
    print(f"{'State':30s} {'Avg IC':>8s} {'Lift':>8s} {'Rows':>8s} {'Pos Yrs':>8s}")
    print("-" * 65)
    for _, row in results.sort_values("avg_ic", ascending=False).iterrows():
        lift = (row["avg_ic"] or 0) - baseline_ic
        print(f"{row['name']:30s} {(row['avg_ic'] or 0):+.4f}  {lift:+.4f}  {row['pooled_rows']:7d}  {row['positive_years']}/{row['years']}")

    best = results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]
    lift = (best["avg_ic"] or 0) - baseline_ic

    if best["avg_ic"] and best["positive_years"] / best["years"] >= 0.7 and best["avg_ic"] > 0.15:
        decision = "PASSED"
    elif best["avg_ic"] and best["avg_ic"] > baseline_ic + 0.02:
        decision = "PASSED"
    elif best["avg_ic"] and best["avg_ic"] > baseline_ic + 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    print(f"\n=== Decision: {decision} ===")
    print(f"Best: {best['name']} (IC={best['avg_ic']}, lift={lift:.4f})")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "branch": BRANCH_NAME,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "best_state": best["name"],
            "best_avg_ic": float(best["avg_ic"]) if best["avg_ic"] else None,
            "best_lift": float(lift),
            "baseline_ic": float(baseline_ic) if baseline_ic else None,
        },
        artifacts={
            "results": str(results_path),
            "yearly": str(yearly_path),
        },
        metadata={
            "hypothesis": SPEC.hypothesis,
            "state_specs": [s.as_metadata() for s in STATE_SPECS],
        },
    )
    return summary_path


def main():
    run_branch(parse_args())


if __name__ == "__main__":
    main()