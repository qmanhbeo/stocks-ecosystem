"""
BR1: signal_cofire_regime

Hypothesis: C23/C24/C25/C26 fire on different days but share vol_expansion.
They capture DIFFERENT behavioral angles on the SAME regime.
Test if co-fire COUNT (0-4 signals firing same day) predicts regime STRENGTH.
Mechanism: when multiple independent signals fire together, market regime is stronger.

First test: cofire buckets (0, 1, 2, 3, 4) vs forward S1 IC.
Compare with random baseline (all rows).
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


BRANCH_NAME = "signal_cofire_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23/C24/C25/C26 fire on different days but share vol_expansion. "
        "Test if co-fire COUNT (0-4 signals firing same day) predicts regime STRENGTH. "
        "Mechanism: when multiple independent signals fire together, market regime is stronger."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR1 signal_cofire_regime test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--ohlcv-path", type=str,
                        default=str(data_path("stock/gia_lich_su_hose_1D.parquet")))
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
    order_stats["buy_sell_volume_imbalance"] = (
        (order_stats["buy_volume"] - order_stats["sell_volume"]) /
        (order_stats["buy_volume"] + order_stats["sell_volume"] + 1)
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_sell_volume_imbalance"]],
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

    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8

    panel["near_ceiling"] = (panel["pct_change"] >= 5.0) & (panel["pct_change"] <= 7.0)
    panel["at_limit"] = panel["pct_change"] >= 6.5

    panel = panel.sort_values(["ticker", "time"])
    panel["limit_1_of_3"] = (
        panel.groupby("ticker")["at_limit"].transform(lambda x: x.rolling(3, min_periods=3).sum())
    )
    panel["limit_2_of_3"] = panel["limit_1_of_3"] >= 2

    panel["vol_expansion_global"] = panel.groupby("time")["vol_expansion"].transform("max")

    panel["vwap_below_10"] = False
    panel["high_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["ceiling_2_expansion"] = panel["limit_2_of_3"] & panel["vol_expansion"]
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]

    cofire_count = pd.Series(0, index=panel.index, dtype=int)
    if "high_illiq_expansion" in panel.columns:
        cofire_count += panel["high_illiq_expansion"].fillna(False).astype(int)
    if "ceiling_2_expansion" in panel.columns:
        cofire_count += panel["ceiling_2_expansion"].fillna(False).astype(int)
    if "buy_heavy_expansion" in panel.columns:
        cofire_count += panel["buy_heavy_expansion"].fillna(False).astype(int)
    if "vwap_below_10" in panel.columns:
        cofire_count += panel["vwap_below_10"].fillna(False).astype(int)

    panel["cofire_count"] = cofire_count

    panel["cofire_0"] = panel["cofire_count"] == 0
    panel["cofire_1"] = panel["cofire_count"] == 1
    panel["cofire_2"] = panel["cofire_count"] == 2
    panel["cofire_3"] = panel["cofire_count"] == 3
    panel["cofire_4"] = panel["cofire_count"] == 4
    panel["cofire_ge2"] = panel["cofire_count"] >= 2
    panel["cofire_ge3"] = panel["cofire_count"] >= 3

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("cofire_0", "Co-fire count = 0 (no signals)", family="cofire"),
    StateSpec("cofire_1", "Co-fire count = 1", family="cofire"),
    StateSpec("cofire_2", "Co-fire count = 2", family="cofire"),
    StateSpec("cofire_3", "Co-fire count = 3", family="cofire"),
    StateSpec("cofire_4", "Co-fire count = 4", family="cofire"),
    StateSpec("cofire_ge2", "Co-fire count >= 2", family="cofire"),
    StateSpec("cofire_ge3", "Co-fire count >= 3", family="cofire"),
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

    cofire_results = {}
    for n in range(5):
        row = results[results["name"] == f"cofire_{n}"]
        if not row.empty:
            cofire_results[n] = {
                "ic": row["avg_ic"].iloc[0],
                "lift": row["avg_ic"].iloc[0] - baseline_ic,
                "rows": row["pooled_rows"].iloc[0],
                "pos_years": row["positive_years"].iloc[0],
                "years": row["years"].iloc[0],
            }

    ge2_row = results[results["name"] == "cofire_ge2"]
    ge3_row = results[results["name"] == "cofire_ge3"]
    cofire_ge2_ic = ge2_row["avg_ic"].iloc[0] if not ge2_row.empty else 0
    cofire_ge3_ic = ge3_row["avg_ic"].iloc[0] if not ge3_row.empty else 0
    cofire_ge2_lift = cofire_ge2_ic - baseline_ic
    cofire_ge3_lift = cofire_ge3_ic - baseline_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    cofire_0_ic = cofire_results.get(0, {}).get("ic", 0)
    cofire_1_ic = cofire_results.get(1, {}).get("ic", 0)
    cofire_2_ic = cofire_results.get(2, {}).get("ic", 0)
    cofire_3_ic = cofire_results.get(3, {}).get("ic", 0)
    cofire_4_ic = cofire_results.get(4, {}).get("ic", 0)

    monotonic = (cofire_1_ic >= cofire_0_ic and cofire_2_ic >= cofire_1_ic and
                cofire_3_ic >= cofire_2_ic and cofire_4_ic >= cofire_3_ic)
    cofire_ge2_positive = cofire_ge2_lift > 0.005

    if cofire_ge2_positive and cofire_ge2_lift > cofire_ge3_lift + 0.005:
        decision = "PASSED"
    elif cofire_ge2_positive and cofire_ge3_lift > 0.01:
        decision = "PASSED"
    elif cofire_ge2_positive and monotonic:
        decision = "PASSED"
    elif cofire_ge2_positive:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "cofire_ge2_ic": float(cofire_ge2_ic),
            "cofire_ge2_lift": float(cofire_ge2_lift),
            "cofire_ge3_ic": float(cofire_ge3_ic),
            "cofire_ge3_lift": float(cofire_ge3_lift),
            "cofire_0_ic": float(cofire_0_ic),
            "cofire_1_ic": float(cofire_1_ic),
            "cofire_2_ic": float(cofire_2_ic),
            "cofire_3_ic": float(cofire_3_ic),
            "cofire_4_ic": float(cofire_4_ic),
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
    print(f"Co-fire >=2: IC={cofire_ge2_ic:.4f}, lift={cofire_ge2_lift:+.4f}")
    print(f"Co-fire >=3: IC={cofire_ge3_ic:.4f}, lift={cofire_ge3_lift:+.4f}")
    print(f"\nCo-fire by count:")
    for n in range(5):
        ic = cofire_results.get(n, {}).get("ic", 0)
        lift = cofire_results.get(n, {}).get("lift", 0)
        rows = cofire_results.get(n, {}).get("rows", 0)
        pos = cofire_results.get(n, {}).get("pos_years", 0)
        yrs = cofire_results.get(n, {}).get("years", 0)
        print(f"  cofire_{n}: IC={ic:.4f}, lift={lift:+.4f}, rows={rows}, pos_years={pos}/{yrs}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
