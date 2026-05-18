"""
H627 - Breadth-Expansion Exit Rule
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h62x_common import build_base_panel  # noqa: E402
from src.experiment_contract import ExperimentSpec, build_experiment_context, write_dataframe_artifact  # noqa: E402
from src.repo_paths import data_path  # noqa: E402

BRANCH_NAME = "h627_breadth_expansion_exit_rule"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="Adaptive exit on breadth expansion (>1.5x entry breadth) may beat fixed 5-day hold for low-breadth composite entries.",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={"event_return": "event-study return"},
    score_columns={"na": "not IC-based"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H627")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--order-stats-path", type=str, default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--max-hold", type=int, default=10)
    parser.add_argument("--fixed-hold", type=int, default=5)
    return parser.parse_args()


def _event_study(panel: pd.DataFrame, max_hold: int, fixed_hold: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    panel = panel.sort_values(["ticker", "time"]).copy()
    panel["entry_flag"] = panel["composite_2plus"] & panel["low_breadth"]
    panel["entry_start"] = panel["entry_flag"] & (~panel.groupby("ticker")["entry_flag"].shift(1).fillna(False))

    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.reset_index(drop=True)
        entry_idx = g.index[g["entry_start"]].tolist()
        for idx in entry_idx:
            entry_close = g.loc[idx, "close"]
            entry_breadth = g.loc[idx, "market_active_fraction"]
            if pd.isna(entry_close) or entry_close <= 0 or pd.isna(entry_breadth):
                continue

            fixed_idx = min(idx + fixed_hold, len(g) - 1)
            fixed_ret = (g.loc[fixed_idx, "close"] / entry_close) - 1.0 if g.loc[fixed_idx, "close"] > 0 else np.nan

            adaptive_idx = min(idx + max_hold, len(g) - 1)
            end = min(idx + max_hold, len(g) - 1)
            for j in range(idx + 1, end + 1):
                cur_breadth = g.loc[j, "market_active_fraction"]
                if pd.notna(cur_breadth) and cur_breadth > (1.5 * entry_breadth):
                    adaptive_idx = j
                    break
            adaptive_ret = (g.loc[adaptive_idx, "close"] / entry_close) - 1.0 if g.loc[adaptive_idx, "close"] > 0 else np.nan

            rows.append(
                {
                    "ticker": ticker,
                    "entry_time": g.loc[idx, "time"],
                    "year": int(g.loc[idx, "year"]),
                    "entry_breadth": float(entry_breadth),
                    "fixed_hold_days": int(fixed_idx - idx),
                    "adaptive_hold_days": int(adaptive_idx - idx),
                    "fixed_ret": float(fixed_ret) if pd.notna(fixed_ret) else np.nan,
                    "adaptive_ret": float(adaptive_ret) if pd.notna(adaptive_ret) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    cache_path = str(ROOT / "artifacts" / "cache" / "h62x_base_panel_2015_2025.parquet")
    panel = build_base_panel(spec.start_year, spec.end_year, args.order_stats_path, cache_path=cache_path)

    events = _event_study(panel, max_hold=int(args.max_hold), fixed_hold=int(args.fixed_hold))
    if events.empty:
        raise RuntimeError("No valid events for H627")

    agg = events[["fixed_ret", "adaptive_ret", "fixed_hold_days", "adaptive_hold_days"]].agg(["mean", "median"])
    yearly = events.groupby("year")[["fixed_ret", "adaptive_ret"]].mean().reset_index()
    yearly["lift"] = yearly["adaptive_ret"] - yearly["fixed_ret"]

    fixed_mean = float(events["fixed_ret"].mean())
    adaptive_mean = float(events["adaptive_ret"].mean())
    lift = adaptive_mean - fixed_mean

    if lift > 0.01:
        decision = "PASSED"
    elif lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    events_path = write_dataframe_artifact(events, context, f"{BRANCH_NAME}_events")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    agg_path = write_dataframe_artifact(agg.reset_index(), context, f"{BRANCH_NAME}_aggregate")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "event_rows": int(len(events)),
            "fixed_mean_return": fixed_mean,
            "adaptive_mean_return": adaptive_mean,
            "lift_adaptive_minus_fixed": lift,
            "fixed_win_rate": float((events["fixed_ret"] > 0).mean()),
            "adaptive_win_rate": float((events["adaptive_ret"] > 0).mean()),
            "mean_fixed_hold_days": float(events["fixed_hold_days"].mean()),
            "mean_adaptive_hold_days": float(events["adaptive_hold_days"].mean()),
        },
        artifacts={"events": events_path, "yearly": yearly_path, "aggregate": agg_path},
        metadata={"hypothesis": SPEC.hypothesis},
    )
    print(agg.to_string())
    print(yearly.to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


if __name__ == "__main__":
    run_branch(parse_args())
