"""
H518: carry_axis_bottleneck_audit

Diagnostic-only pass to quantify carry-axis bottlenecks under the
H515 guarded active-k contract.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import ExperimentSpec, build_experiment_context, write_dataframe_artifact


BRANCH_NAME = "carry_axis_bottleneck_audit"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Under the H515 guarded contract, carry-axis weakness should be "
        "traceable to coverage/sparsity and overlap imbalance rather than "
        "global latent collapse."
    ),
    start_year=2015,
    end_year=2025,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H518 carry-axis bottleneck audit")
    parser.add_argument(
        "--summary-path",
        type=str,
        default=str(ROOT / "artifacts" / "run_summaries" / "20260517_133818_amplified_axis_refinement_research_branch.json"),
    )
    return parser.parse_args()


def run_audit(args: argparse.Namespace) -> str:
    context = build_experiment_context(replace(SPEC), artifact_subdir="research_branches")
    with open(args.summary_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    artifacts = payload["artifacts"]

    overlap_path = ROOT / artifacts["active_overlap"]
    results_path = ROOT / artifacts["active_results"]
    yearly_path = ROOT / artifacts["active_yearly"]

    overlap = pd.read_parquet(overlap_path)
    results = pd.read_parquet(results_path)
    yearly = pd.read_parquet(yearly_path)
    selected_k = int(payload["summary"]["selected_active_k"])

    ov = overlap[overlap["active_k"] == selected_k].copy()
    rs = results[(results["active_k"] == selected_k) & (results["family"] == "active_latent")].copy()
    yr = yearly[yearly["active_k"] == selected_k].copy()

    # best cluster by each symbolic axis
    axis_rows: list[dict[str, object]] = []
    for sym in ["c23_fresh_not_yesterday", "cofire_2", "c23_yesterday_carry"]:
        sub = ov[ov["symbolic_col"] == sym].sort_values("jaccard", ascending=False)
        best = sub.iloc[0]
        cname = str(best["cluster_col"])
        r = rs[rs["name"] == cname].iloc[0] if not rs[rs["name"] == cname].empty else None
        axis_rows.append(
            {
                "axis": sym,
                "cluster": cname,
                "jaccard": float(best["jaccard"]),
                "contain_symbolic_in_cluster": float(best["contain_symbolic_in_cluster"]),
                "contain_cluster_in_symbolic": float(best["contain_cluster_in_symbolic"]),
                "cluster_rows": int(r["pooled_rows"]) if r is not None else None,
                "cluster_avg_ic": float(r["avg_ic"]) if r is not None else None,
            }
        )
    axis_table = pd.DataFrame(axis_rows)

    carry_row = axis_table[axis_table["axis"] == "c23_yesterday_carry"].iloc[0]
    amp_row = axis_table[axis_table["axis"] == "cofire_2"].iloc[0]
    onset_row = axis_table[axis_table["axis"] == "c23_fresh_not_yesterday"].iloc[0]

    # year spread for carry best cluster
    carry_cluster = str(carry_row["cluster"])
    carry_year = yr[yr["state"] == carry_cluster].copy().sort_values("year")
    carry_valid = carry_year[pd.notna(carry_year["ic"])]

    year_volatility = (
        float(carry_valid["ic"].max() - carry_valid["ic"].min()) if not carry_valid.empty else np.nan
    )
    carry_pos_years = int((carry_valid["ic"] > 0).sum()) if not carry_valid.empty else 0
    carry_years = int(len(carry_valid))

    # bottleneck classification
    carry_j = float(carry_row["jaccard"])
    amp_j = float(amp_row["jaccard"])
    onset_j = float(onset_row["jaccard"])
    carry_gap_vs_amp = carry_j - amp_j
    carry_gap_vs_onset = carry_j - onset_j

    if carry_j < 0.10 and carry_pos_years >= max(1, carry_years - 1):
        bottleneck = "representation_overlap_bottleneck"
    elif carry_pos_years < max(1, int(0.7 * carry_years)):
        bottleneck = "phase_instability_bottleneck"
    else:
        bottleneck = "mixed_bottleneck"

    decision = "MIXED"
    if bottleneck == "representation_overlap_bottleneck":
        decision = "SUPPORTS carry-overlap bottleneck"

    axis_path = write_dataframe_artifact(axis_table, context, f"{BRANCH_NAME}_axis_table")
    carry_path = write_dataframe_artifact(carry_year, context, f"{BRANCH_NAME}_carry_yearly")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "selected_active_k": selected_k,
            "carry_best_cluster": carry_cluster,
            "carry_jaccard": carry_j,
            "amplified_jaccard": amp_j,
            "onset_jaccard": onset_j,
            "carry_gap_vs_amplified": carry_gap_vs_amp,
            "carry_gap_vs_onset": carry_gap_vs_onset,
            "carry_positive_years": carry_pos_years,
            "carry_years_with_ic": carry_years,
            "carry_year_ic_spread": year_volatility,
            "bottleneck_class": bottleneck,
        },
        artifacts={
            "axis_table": axis_path,
            "carry_yearly": carry_path,
            "source_summary": args.summary_path,
        },
    )

    print(axis_table.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_audit(parse_args())


if __name__ == "__main__":
    main()
