"""
H565: Capacity-Breadth Direction Combo

H474: tight_capacity +0.055 lift
H546: tight_contracting > expanding

Hypothesis: Test capacity_direction × breadth interaction. Is there a hidden 
state where both signals amplify? tight + low_breadth combo might be stronger.

Pass criterion: tight_contracting × low_breadth beats either single by > +0.01
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

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
    validate_state_columns,
    write_dataframe_artifact,
    normalize_time_ticker,
    restrict_years,
)
from src.repo_paths import data_path


BRANCH_NAME = "capacity_breadth_direction_combo"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H565: Capacity-Breadth Direction Combo Test")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def load_panel(args: argparse.Namespace) -> pd.DataFrame:
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=args.start_year, end_year=args.end_year, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_xs_proba", "actual": "s1_barrier_hit_1d"})

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=args.start_year, end_year=args.end_year, source="C16 panel")

    panel = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(panel)} rows")

    date_breadth = panel.groupby("time")["ticker"].nunique().reset_index()
    date_breadth.columns = ["time", "active_count"]
    breadth_20 = date_breadth["active_count"].quantile(0.20)
    date_breadth["low_breadth"] = date_breadth["active_count"] <= breadth_20
    panel = panel.merge(date_breadth[["time", "low_breadth"]], on="time", how="left")

    if "order_count" in panel.columns:
        panel["order_count_rank"] = panel.groupby("time", sort=False)["order_count"].rank(pct=True)
        panel["tight_capacity"] = panel["order_count_rank"] <= 0.2

        order_count_by_ticker = panel.groupby("ticker")["order_count"].transform(lambda x: x.pct_change(5))
        panel["capacity_change"] = order_count_by_ticker
        panel["capacity_change_rank"] = panel.groupby("time", sort=False)["capacity_change"].rank(pct=True)
        panel["tight_contracting"] = panel["tight_capacity"] & (panel["capacity_change_rank"] <= 0.3)
        panel["tight_expanding"] = panel["tight_capacity"] & (panel["capacity_change_rank"] >= 0.7)
    else:
        panel["tight_capacity"] = panel["order_volume_ratio_rank"] <= 0.2

    panel["tight_low_breadth"] = panel["tight_capacity"] & panel["low_breadth"]

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test capacity × breadth interaction. "
            "tight_capacity + low_breadth combo might amplify both signals."
        ),
        start_year=2015,
        end_year=2025,
        min_year_rows=500,
        min_phase_rows=500,
        target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
        score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_panel(args)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("tight_capacity", "Tight capacity (low order count)", family="capacity"),
        StateSpec("low_breadth", "Low breadth dates", family="breadth"),
        StateSpec("tight_low_breadth", "Tight capacity + Low breadth", family="combo"),
    ]

    available_cols = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS = [s for s in STATE_SPECS if s.name in available_cols]

    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col="s1_xs_proba",
        target_col="s1_barrier_hit_1d",
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    print("=== H565: Capacity-Breadth Direction Combo Test ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    tight = results[results["name"] == "tight_capacity"]["avg_ic"].iloc[0] if "tight_capacity" in results["name"].values else 0.0
    low_br = results[results["name"] == "low_breadth"]["avg_ic"].iloc[0] if "low_breadth" in results["name"].values else 0.0
    combo = results[results["name"] == "tight_low_breadth"]["avg_ic"].iloc[0] if "tight_low_breadth" in results["name"].values else 0.0

    combo_vs_tight = combo - tight
    combo_vs_lowbreadth = combo - low_br

    if combo_vs_tight > 0.01 and combo_vs_lowbreadth > 0.01:
        decision = "PASSED"
    elif combo_vs_tight > 0.005 or combo_vs_lowbreadth > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": baseline,
            "tight_capacity_ic": tight,
            "low_breadth_ic": low_br,
            "combo_ic": combo,
            "combo_vs_tight": combo_vs_tight,
            "combo_vs_lowbreadth": combo_vs_lowbreadth,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "capacity × breadth combo",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Tight Capacity IC: {tight:.4f}")
    print(f"Low Breadth IC: {low_br:.4f}")
    print(f"Tight + Low Breadth IC: {combo:.4f}")
    print(f"Combo vs Tight: {combo_vs_tight:.4f}")
    print(f"Combo vs Low Breadth: {combo_vs_lowbreadth:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()