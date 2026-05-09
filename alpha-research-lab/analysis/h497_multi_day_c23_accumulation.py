"""
BU3: multi_day_c23_accumulation

Test if C23 (high_illiq × vol_expansion) works better when it fires on
consecutive days vs single day.

Hypothesis: Sustained illiq × vol_expansion across 2-3 days represents a stronger
regime than one-off C23 firing. Analogous to C24 (multi-day ceiling) mechanism.

Compare:
- single_day_C23: C23 fires on T only
- consecutive_2d: C23 fires on T-1 AND T
- consecutive_3d: C23 fires on T-2 AND T-1 AND T

Note: D046 tested LAGGED signals (C23 at T+2 forward), which failed.
       BU3 tests RECURRENCE (C23 firing on consecutive days), which is different.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

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


BRANCH_NAME = "multi_day_c23_accumulation"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23 (high_illiq × vol_expansion) on consecutive days works better than "
        "single-day C23. Sustained illiq × vol expansion represents stronger regime."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BU3: multi-day C23 accumulation test"
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


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


def load_ohlcv_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Load OHLCV and compute Amihud illiquidity inline."""
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

    if not ohlcv_dfs:
        panel["amihud_20d_avg"] = np.nan
        return panel

    ohlcv = pd.concat(ohlcv_dfs, ignore_index=True)
    ohlcv = ohlcv.rename(columns={"date": "time"})
    ohlcv["time"] = pd.to_datetime(ohlcv["time"])
    ohlcv = ohlcv[ohlcv["time"].dt.year <= 2025]

    ohlcv["daily_return"] = ohlcv.groupby("ticker")["close"].pct_change()
    ohlcv["daily_return_abs"] = ohlcv["daily_return"].abs()
    ohlcv["turnover"] = ohlcv["close"] * ohlcv["volume"] / 1e9
    ohlcv["amihud"] = ohlcv["daily_return_abs"] / (ohlcv["turnover"] + 1e-9)
    ohlcv["amihud_20d_avg"] = ohlcv.groupby("ticker")["amihud"].transform(
        lambda x: x.rolling(window=20, min_periods=10).mean()
    )

    panel = panel.merge(
        ohlcv[["time", "ticker", "amihud_20d_avg"]],
        on=["time", "ticker"],
        how="left",
    )
    return panel


def load_order_stats_features(panel: pd.DataFrame, order_stats_path: str) -> pd.DataFrame:
    """Load order_stats and compute vol_expansion."""
    order_stats = pd.read_parquet(order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]

    order_stats["vol_change_5d"] = order_stats.groupby("ticker")["total_volume"].pct_change(periods=5)

    panel = panel.merge(
        order_stats[["time", "ticker", "vol_change_5d"]],
        on=["time", "ticker"],
        how="left",
    )
    return panel


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    """Load S1 panel + compute C23 features."""
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    panel = load_ohlcv_features(panel)
    panel = load_order_stats_features(panel, args.order_stats_path)

    panel["amihud_rank"] = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(pct=True, method="average")
    panel["vol_expansion_rank"] = panel.groupby("time", sort=False)["vol_change_5d"].rank(pct=True, method="average")

    panel["high_illiq"] = panel["amihud_rank"] >= 0.80
    panel["vol_expansion"] = panel["vol_expansion_rank"] >= 0.80
    panel["c23_signal"] = panel["high_illiq"] & panel["vol_expansion"]

    panel["c23_t_1"] = panel.groupby("ticker", sort=False)["c23_signal"].shift(1).fillna(False).astype(bool)
    panel["c23_t_2"] = panel.groupby("ticker", sort=False)["c23_signal"].shift(2).fillna(False).astype(bool)

    panel["single_day_c23"] = panel["c23_signal"] & ~panel["c23_t_1"]
    panel["consecutive_2d_c23"] = panel["c23_signal"] & panel["c23_t_1"]
    panel["consecutive_3d_c23"] = panel["c23_signal"] & panel["c23_t_1"] & panel["c23_t_2"]

    panel["all_rows"] = True
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "single_day_c23",
        "C23 fires on T only (not fired on T-1)",
        family="c23_accumulation",
        baseline="all_rows",
    ),
    StateSpec(
        "consecutive_2d_c23",
        "C23 fires on T-1 AND T (2 consecutive days)",
        family="c23_accumulation",
        baseline="all_rows",
    ),
    StateSpec(
        "consecutive_3d_c23",
        "C23 fires on T-2 AND T-1 AND T (3 consecutive days)",
        family="c23_accumulation",
        baseline="all_rows",
    ),
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

    baseline_row = results[results["name"] == "all_rows"].iloc[0]
    baseline_ic = baseline_row["avg_ic"]

    single_day = results[results["name"] == "single_day_c23"].iloc[0]
    cons_2d = results[results["name"] == "consecutive_2d_c23"].iloc[0]
    cons_3d = results[results["name"] == "consecutive_3d_c23"].iloc[0]

    best_state = results.sort_values("avg_ic", ascending=False).iloc[0]
    best_name = best_state["name"]
    best_ic = best_state["avg_ic"]
    best_lift = best_ic - baseline_ic

    if cons_2d["avg_ic"] > single_day["avg_ic"] + 0.005 and cons_3d["avg_ic"] > single_day["avg_ic"] + 0.005:
        decision = "PASSED"
    elif best_lift > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_all_rows_ic": float(baseline_ic),
            "single_day_c23_ic": float(single_day["avg_ic"]),
            "single_day_c23_lift": float(single_day["avg_ic"] - baseline_ic),
            "single_day_c23_rows": int(single_day["pooled_rows"]),
            "consecutive_2d_c23_ic": float(cons_2d["avg_ic"]),
            "consecutive_2d_c23_lift": float(cons_2d["avg_ic"] - baseline_ic),
            "consecutive_2d_c23_rows": int(cons_2d["pooled_rows"]),
            "consecutive_3d_c23_ic": float(cons_3d["avg_ic"]),
            "consecutive_3d_c23_lift": float(cons_3d["avg_ic"] - baseline_ic),
            "consecutive_3d_c23_rows": int(cons_3d["pooled_rows"]),
            "best_state": best_name,
            "best_ic": float(best_ic),
            "best_lift": float(best_lift),
            "best_positive_years": int(best_state["positive_years"]),
            "best_years": best_state["years"],
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

    print("\n=== Results ===")
    print(results.sort_values("avg_ic", ascending=False).to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Best: {best_name} IC={best_ic:.4f} lift={best_lift:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()