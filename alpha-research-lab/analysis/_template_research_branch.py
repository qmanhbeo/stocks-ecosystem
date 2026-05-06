"""
Copy this file to `analysis/hNNN_branch_name.py` for a new lightweight
research branch.

The template is intentionally runnable as-is. It performs a small S1 smoke
audit so future agents can verify the scaffold before replacing the TODO
sections with a real branch.

Required edits for a real branch:
1. Rename BRANCH_NAME, MODE, and SPEC.hypothesis.
2. Add decision-time features in `load_panel`.
3. Replace STATE_SPECS with fixed, predeclared states and controls.
4. Replace `decision` with the branch's actual pass/mixed/fail ladder.

Do not define state columns from `s1_barrier_hit_1d`, raw `actual`, future
returns, or any same-date target-derived aggregate.
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
    validate_state_columns,
    write_dataframe_artifact,
)


BRANCH_NAME = "template_research_branch"
MODE = "research_branch_template"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Template smoke branch: demonstrates role-safe S1 loading, fixed "
        "state definitions, yearly IC summaries, and run-summary artifacts."
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
    StateSpec(
        "example_high_s1",
        "Example only: top S1 score-rank bucket",
        family="example",
        baseline="all_rows",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reusable research-branch template. Copy this file before editing; "
            "running it unchanged performs a small S1 scaffold smoke audit."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    parser.add_argument("--example-high-s1-rank-threshold", type=float, default=0.80)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    # TODO: merge only decision-time observable branch features here.
    # Keep target/future columns out of state definitions. The contract helper
    # already renamed S1's raw `actual` column to `s1_barrier_hit_1d` to make
    # that role explicit.
    panel["all_rows"] = True
    s1_rank = panel[S1_SCORE_COL].groupby(panel["time"], sort=False).rank(method="average", pct=True)
    panel["example_high_s1"] = s1_rank >= float(args.example_high_s1_rank_threshold)
    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_templates")
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

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    # TODO: replace TEMPLATE_ONLY with PASSED / MIXED / FAILED / PARKED using
    # the branch's predeclared ladder.
    decision = "TEMPLATE_ONLY"
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "best_state_by_avg_year_ic": best_row.get("name"),
            "best_avg_year_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
            "best_years": best_row.get("years"),
            "template_note": "Copy this file before using it for a real branch.",
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "template": True,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
