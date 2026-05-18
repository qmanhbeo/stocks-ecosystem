"""
H611 - Implementation Pain as Position Sizing

Hypothesis:
Blocked names (implementation pain) may work better as a size multiplier rather
than a hard filter.

Test:
- baseline score: s1_xs_proba
- sized score: s1_xs_proba * 1.5 for blocked_either else * 1.0
- compare IC on all rows

Decision:
- PASSED: sized IC > baseline IC by +0.01
- MIXED: sized IC > baseline IC
- FAILED: otherwise
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (  # noqa: E402
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    load_s1_decision_panel,
    normalize_time_ticker,
    restrict_years,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402


BRANCH_NAME = "h611_implementation_pain_position_sizing"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Use blocked state as score-size modifier (1.5x) instead of hard filter; "
        "compare sized score IC vs baseline score IC on same panel."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        "s1_xs_proba_blocked_150": "S1 score with 1.5x multiplier on blocked_either names",
    },
)

ALL_ROWS_SPEC = [StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H611: Implementation pain position sizing")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        S1_DEFAULT_PATH,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    tradability_path = data_path("features/execution/tradability_daily.parquet")
    trad_df = pd.read_parquet(tradability_path)
    trad_df = normalize_time_ticker(trad_df, source="tradability")
    trad_df = restrict_years(
        trad_df,
        start_year=spec.start_year,
        end_year=spec.end_year,
        source="tradability",
    )
    panel = panel.merge(
        trad_df[["time", "ticker", "can_buy_next_open", "can_sell_next_open"]],
        on=["time", "ticker"],
        how="left",
    )
    panel["blocked_buy"] = ~(panel["can_buy_next_open"].fillna(True))
    panel["blocked_sell"] = ~(panel["can_sell_next_open"].fillna(True))
    panel["blocked_either"] = panel["blocked_buy"] | panel["blocked_sell"]
    panel["s1_xs_proba_blocked_150"] = panel[S1_SCORE_COL] * (
        1.5 * panel["blocked_either"].astype(float) + 1.0 * (~panel["blocked_either"]).astype(float)
    )
    panel["all_rows"] = True
    return panel


def _extract_single_ic(results: pd.DataFrame) -> tuple[float, int]:
    row = results.iloc[0]
    return float(row["avg_ic"]), int(row["pooled_rows"])


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    validate_state_columns(panel, ["all_rows"], spec)

    baseline_results, baseline_yearly = evaluate_state_specs(
        panel,
        ALL_ROWS_SPEC,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )
    sized_results, sized_yearly = evaluate_state_specs(
        panel,
        ALL_ROWS_SPEC,
        score_col="s1_xs_proba_blocked_150",
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    baseline_ic, pooled_rows = _extract_single_ic(baseline_results)
    sized_ic, _ = _extract_single_ic(sized_results)
    lift = sized_ic - baseline_ic

    compare = pd.DataFrame(
        [
            {
                "name": "baseline_score",
                "avg_ic": baseline_ic,
                "pooled_rows": pooled_rows,
                "score_col": S1_SCORE_COL,
            },
            {
                "name": "blocked_multiplier_150",
                "avg_ic": sized_ic,
                "pooled_rows": pooled_rows,
                "score_col": "s1_xs_proba_blocked_150",
            },
        ]
    )
    key_col = "state" if "state" in baseline_yearly.columns else "name"
    yearly_compare = baseline_yearly.copy()
    yearly_compare = yearly_compare.rename(columns={"ic": "baseline_ic"})
    yearly_compare = yearly_compare[[key_col, "year", "baseline_ic", "rows"]]
    sized_yearly_min = sized_yearly[[key_col, "year", "ic"]].rename(columns={"ic": "sized_ic"})
    yearly_compare = yearly_compare.merge(sized_yearly_min, on=[key_col, "year"], how="left")
    yearly_compare["ic_lift"] = yearly_compare["sized_ic"] - yearly_compare["baseline_ic"]

    results_path = write_dataframe_artifact(compare, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly_compare, context, f"{BRANCH_NAME}_yearly")

    if lift > 0.01:
        decision = "PASSED"
    elif lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "baseline_ic": baseline_ic,
            "blocked_multiplier_150_ic": sized_ic,
            "lift_vs_baseline": lift,
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={
            "state_specs": [state.as_metadata() for state in ALL_ROWS_SPEC],
            "hypothesis": SPEC.hypothesis,
        },
    )
    print(compare.to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
