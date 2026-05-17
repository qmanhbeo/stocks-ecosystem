"""
H545: breadth_adaptive_exit_rules

Hypothesis: H526 found exit timing (fresh vs sustained) makes NO difference overall.
But H525 found high-breadth dates have weaker signal than low-breadth dates.
Now test if exit timing differs BY breadth regime:
- Exit faster on high-breadth dates (signal already weak, decays fast?)
- Hold longer on low-breadth dates (signal stronger, sustains?)

Prior results:
- H525: high_breadth IC=0.1149, low_breadth IC=0.1454 (+0.0305)
- H526: fresh_entry IC=0.1693, sustained IC=0.1712 (-0.002 diff = NO diff)
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import re

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


BRANCH_NAME = "breadth_adaptive_exit_rules"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H526 found exit timing makes NO difference overall. But H525 found high-breadth dates "
        "have weaker signal than low-breadth. Test if exit timing differs BY breadth regime: "
        "exit faster on high-breadth (weak signal decays fast), hold longer on low-breadth."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H545 breadth_adaptive_exit_rules test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
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

    # Load order_stats for vol regime computation (needed for C23 composite)
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
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats = order_stats[order_stats["total_volume"] > 0]

    # Compute vol regime (H446)
    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel.sort_values(["ticker", "time"])

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(lambda x: x.diff())
    panel = panel.dropna(subset=["vol_change"])

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    # Compute C23 (high_illiq × vol_expansion) - need amihud
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

        ohlcv["daily_return"] = ohlcv.groupby("ticker")["close"].pct_change()
        ohlcv["turnover"] = ohlcv["close"] * ohlcv["volume"] / 1e9
        ohlcv["amihud"] = ohlcv["daily_return"].abs() / (ohlcv["turnover"] + 1e-9)

        ohlcv = ohlcv.sort_values(["ticker", "time"])
        ohlcv["amihud_20d"] = ohlcv.groupby("ticker")["amihud"].transform(
            lambda x: x.rolling(20, min_periods=10).mean()
        )

        panel = panel.merge(ohlcv[["time", "ticker", "amihud_20d"]], on=["time", "ticker"], how="left")

    if "amihud_20d" not in panel.columns:
        panel["amihud_20d"] = np.nan

    amihud_rank = panel.groupby("time", sort=False)["amihud_20d"].rank(method="average", pct=True)
    panel["high_illiq"] = amihud_rank >= 0.8

    # C23: high_illiq × vol_expansion
    panel["c23_signal"] = panel["high_illiq"] & panel["vol_expansion"]

    # Compute BREADTH: fraction of tickers with C23 signal per date
    active_per_date = panel[panel["c23_signal"]].groupby("time")["ticker"].nunique().reset_index()
    active_per_date.columns = ["time", "active_tickers"]

    total_per_date = panel.groupby("time")["ticker"].nunique().reset_index()
    total_per_date.columns = ["time", "total_tickers"]

    breadth_df = active_per_date.merge(total_per_date, on="time", how="outer")
    breadth_df["total_tickers"] = breadth_df["total_tickers"].fillna(1)
    breadth_df["active_tickers"] = breadth_df["active_tickers"].fillna(0)
    breadth_df["breadth_fraction"] = breadth_df["active_tickers"] / breadth_df["total_tickers"]

    panel = panel.merge(breadth_df[["time", "breadth_fraction"]], on="time", how="left")
    panel["breadth_fraction"] = panel["breadth_fraction"].fillna(0)

    # Binary low vs high breadth (using date-level ranking)
    date_breadth = panel.groupby("time")["breadth_fraction"].first().reset_index()
    date_breadth["breadth_rank"] = date_breadth["breadth_fraction"].rank(method="average", pct=True)
    date_breadth["low_breadth"] = date_breadth["breadth_rank"] <= 0.2
    date_breadth["high_breadth"] = date_breadth["breadth_rank"] >= 0.8

    panel = panel.merge(date_breadth[["time", "low_breadth", "high_breadth"]], on="time", how="left")

    # Compute holding duration: days since first C23 signal in current streak
    panel = panel.sort_values(["ticker", "time"])
    panel["c23_active_lag"] = panel.groupby("ticker")["c23_signal"].shift(1)
    panel["c23_active_lag"] = panel["c23_active_lag"].fillna(False).astype(bool)

    panel["new_c23_streak"] = (panel["c23_signal"]) & (~panel["c23_active_lag"])
    panel["c23_streak_id"] = panel.groupby("ticker")["new_c23_streak"].cumsum()
    panel.loc[~panel["c23_signal"], "c23_streak_id"] = 0

    panel["days_since_c23_entry"] = panel.groupby(["ticker", "c23_streak_id"]).cumcount()
    panel.loc[~panel["c23_signal"], "days_since_c23_entry"] = 0

    # Exit timing: fresh (first day in signal) vs sustained (2+ days)
    # Similar to H526 but now split by breadth regime
    panel["c23_fresh"] = (panel["c23_signal"]) & (panel["days_since_c23_entry"] == 0)
    panel["c23_sustained"] = (panel["c23_signal"]) & (panel["days_since_c23_entry"] >= 1)

    # Compute state columns: breadth × exit timing (coarser buckets)
    panel["low_breadth_fresh"] = panel["low_breadth"].fillna(False) & panel["c23_fresh"]
    panel["low_breadth_sustained"] = panel["low_breadth"].fillna(False) & panel["c23_sustained"]

    panel["high_breadth_fresh"] = panel["high_breadth"].fillna(False) & panel["c23_fresh"]
    panel["high_breadth_sustained"] = panel["high_breadth"].fillna(False) & panel["c23_sustained"]

    panel["low_breadth_any"] = panel["low_breadth"].fillna(False) & panel["c23_signal"]
    panel["high_breadth_any"] = panel["high_breadth"].fillna(False) & panel["c23_signal"]

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Entry breadth × exit timing combinations (coarser)
    # Low breadth entry + fresh/sustained
    StateSpec("low_breadth_fresh", "Low breadth entry, fresh (same day)", family="breadth_exit", primary=True),
    StateSpec("low_breadth_sustained", "Low breadth entry, sustained (2d+)", family="breadth_exit"),
    # High breadth entry + fresh/sustained
    StateSpec("high_breadth_fresh", "High breadth entry, fresh (same day)", family="breadth_exit", primary=True),
    StateSpec("high_breadth_sustained", "High breadth entry, sustained (2d+)", family="breadth_exit"),
    # Overall breadth (for reference)
    StateSpec("low_breadth_any", "Low breadth any entry", family="breadth"),
    StateSpec("high_breadth_any", "High breadth any entry", family="breadth"),
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

    # Extract key metrics
    def get_ic(name):
        row = results[results["name"] == name]
        return row["avg_ic"].iloc[0] if not row.empty else np.nan

    def get_lift(name):
        ic = get_ic(name)
        return ic - baseline_ic if not np.isnan(ic) else np.nan

    low_fresh_ic = get_ic("low_breadth_fresh")
    low_sustained_ic = get_ic("low_breadth_sustained")

    high_fresh_ic = get_ic("high_breadth_fresh")
    high_sustained_ic = get_ic("high_breadth_sustained")

    low_any_ic = get_ic("low_breadth_any")
    high_any_ic = get_ic("high_breadth_any")

    # Hypothesis: exit timing differs by breadth
    # Low breadth: sustained = stronger? or fresh = stronger?
    # High breadth: fresh = stronger? or sustained = stronger?
    low_exit_spread = abs(low_fresh_ic - low_sustained_ic) if not (np.isnan(low_fresh_ic) or np.isnan(low_sustained_ic)) else 0
    high_exit_spread = abs(high_fresh_ic - high_sustained_ic) if not (np.isnan(high_fresh_ic) or np.isnan(high_sustained_ic)) else 0

    # Best exit per breadth regime
    best_low_exit = max(low_fresh_ic, low_sustained_ic) if not (np.isnan(low_fresh_ic) and np.isnan(low_sustained_ic)) else 0
    best_high_exit = max(high_fresh_ic, high_sustained_ic) if not (np.isnan(high_fresh_ic) and np.isnan(high_sustained_ic)) else 0

    # Decision: Does exit timing differ by breadth?
    # If there's a meaningful spread within each regime (> 0.01)
    if low_exit_spread > 0.01 or high_exit_spread > 0.01:
        # Find the best combo
        if best_low_exit > low_any_ic + 0.01 and best_high_exit > high_any_ic + 0.01:
            decision = "PASSED"
        elif best_low_exit > low_any_ic + 0.005 or best_high_exit > high_any_ic + 0.005:
            decision = "MIXED"
        else:
            decision = "FAILED"
    else:
        # No meaningful difference - exit timing doesn't vary by breadth
        decision = "FAILED"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # Low breadth exits
            "low_breadth_fresh_ic": float(low_fresh_ic) if not np.isnan(low_fresh_ic) else None,
            "low_breadth_sustained_ic": float(low_sustained_ic) if not np.isnan(low_sustained_ic) else None,
            # High breadth exits
            "high_breadth_fresh_ic": float(high_fresh_ic) if not np.isnan(high_fresh_ic) else None,
            "high_breadth_sustained_ic": float(high_sustained_ic) if not np.isnan(high_sustained_ic) else None,
            # Overall
            "low_breadth_any_ic": float(low_any_ic) if not np.isnan(low_any_ic) else None,
            "high_breadth_any_ic": float(high_any_ic) if not np.isnan(high_any_ic) else None,
            # Spreads
            "low_exit_spread": float(low_exit_spread),
            "high_exit_spread": float(high_exit_spread),
            "best_low_exit": float(best_low_exit),
            "best_high_exit": float(best_high_exit),
            "best_state_by_avg_year_ic": best_row.get("name"),
            "best_avg_year_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
            "best_years": best_row.get("years"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\nLow breadth entry + exit timing:")
    print(f"  fresh: {low_fresh_ic:.4f}, sustained: {low_sustained_ic:.4f}")
    print(f"  spread: {low_exit_spread:.4f}")
    print(f"\nHigh breadth entry + exit timing:")
    print(f"  fresh: {high_fresh_ic:.4f}, sustained: {high_sustained_ic:.4f}")
    print(f"  spread: {high_exit_spread:.4f}")
    print(f"\nOverall breadth (reference):")
    print(f"  low_breadth_any: {low_any_ic:.4f}")
    print(f"  high_breadth_any: {high_any_ic:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()