"""
H513: h512_phase_stability_audit

Robustness follow-through for H512:
- verify that recovered active-manifold structure is not a one-pocket artifact
- check phase/year stability of strong active clusters
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

from src.experiment_contract import (
    ExperimentSpec,
    build_experiment_context,
    write_dataframe_artifact,
)


BRANCH_NAME = "h512_phase_stability_audit"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H512 recovered active-manifold separation should remain phase/year "
        "stable across multiple strong non-sparse clusters, not one sparse pocket."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H513 H512 phase/year stability audit")
    parser.add_argument(
        "--h512-summary-path",
        type=str,
        default=str(
            ROOT
            / "artifacts"
            / "run_summaries"
            / "20260517_132235_active_manifold_disentangling_research_branch.json"
        ),
    )
    parser.add_argument("--min_cluster_rows", type=int, default=5000)
    parser.add_argument("--max_single_cluster_share", type=float, default=0.80)
    return parser.parse_args()


def _resolve_artifact(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT / path


def run_audit(args: argparse.Namespace) -> str:
    spec = replace(SPEC)
    context = build_experiment_context(spec, artifact_subdir="research_branches")

    with open(args.h512_summary_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    artifacts = payload.get("artifacts", {})
    active_results_path = _resolve_artifact(artifacts["active_results"])
    active_yearly_path = _resolve_artifact(artifacts["active_yearly"])
    chosen_panel_rel = artifacts.get("chosen_active_panel")

    results = pd.read_parquet(active_results_path)
    yearly = pd.read_parquet(active_yearly_path)
    panel = pd.read_parquet(_resolve_artifact(chosen_panel_rel)) if chosen_panel_rel else None

    summary = payload.get("summary", {})
    if "selected_active_k_dev_silhouette" in summary:
        selected_active_k = int(summary["selected_active_k_dev_silhouette"])
    elif "selected_active_k" in summary:
        selected_active_k = int(summary["selected_active_k"])
    else:
        raise KeyError("Summary missing selected active k field.")
    k_results = results.loc[results["active_k"] == selected_active_k].copy()
    k_yearly = yearly.loc[yearly["active_k"] == selected_active_k].copy()

    base_row = k_results.loc[k_results["name"] == "all_rows"].iloc[0]
    base_ic = float(base_row["avg_ic"])

    strong = k_results.loc[
        (k_results["family"] == "active_latent")
        & (k_results["pooled_rows"] >= int(args.min_cluster_rows))
        & (k_results["avg_ic"] > base_ic)
    ].copy()
    strong = strong.sort_values("avg_ic", ascending=False)

    yearly_rows: list[dict[str, object]] = []
    for _, row in strong.iterrows():
        name = str(row["name"])
        y = k_yearly.loc[k_yearly["state"] == name].copy()
        valid_ic = y.loc[pd.notna(y["ic"]), "ic"].astype(float)
        yearly_rows.append(
            {
                "cluster": name,
                "avg_ic": float(row["avg_ic"]),
                "pooled_rows": int(row["pooled_rows"]),
                "years_with_ic": int(len(valid_ic)),
                "positive_years": int((valid_ic > 0).sum()),
                "min_year_ic": float(valid_ic.min()) if len(valid_ic) else np.nan,
                "max_year_ic": float(valid_ic.max()) if len(valid_ic) else np.nan,
                "dev_ic": float(row["dev_ic"]) if pd.notna(row["dev_ic"]) else np.nan,
                "validation_ic": float(row["validation_ic"]) if pd.notna(row["validation_ic"]) else np.nan,
                "confirmation_ic": float(row["confirmation_ic"]) if pd.notna(row["confirmation_ic"]) else np.nan,
                "validation_rows": int(row["validation_rows"]),
                "confirmation_rows": int(row["confirmation_rows"]),
            }
        )
    strong_stability = pd.DataFrame(yearly_rows)

    if panel is not None and "h511_active_cluster_id" in panel.columns:
        share = panel["h511_active_cluster_id"].value_counts(normalize=True).sort_values(ascending=False)
        share_table = share.rename_axis("cluster_id").reset_index(name="share")
        dominant_share = float(share.iloc[0]) if len(share) else np.nan
    else:
        # Fallback for summaries that did not publish a chosen panel:
        # estimate concentration from pooled cluster rows in active_results.
        pool = k_results.loc[k_results["family"] == "active_latent", ["name", "pooled_rows"]].copy()
        total = float(pool["pooled_rows"].sum())
        if total > 0:
            pool["share"] = pool["pooled_rows"] / total
            pool = pool.sort_values("share", ascending=False).reset_index(drop=True)
            pool["cluster_id"] = pool["name"].str.extract(r"cluster_(\d+)$").fillna("-1")
            share_table = pool[["cluster_id", "share", "pooled_rows"]]
            dominant_share = float(pool["share"].iloc[0])
        else:
            share_table = pd.DataFrame(columns=["cluster_id", "share", "pooled_rows"])
            dominant_share = np.nan

    flag_multi_cluster = int(len(strong_stability)) >= 2
    flag_phase_positive = bool(
        not strong_stability.empty
        and (strong_stability["validation_ic"] > 0).all()
        and (strong_stability["confirmation_ic"] > 0).all()
    )
    flag_not_single_pocket = bool(
        pd.notna(dominant_share) and dominant_share <= float(args.max_single_cluster_share)
    )

    decision = (
        "SUPPORTS H512 robustness"
        if flag_multi_cluster and flag_phase_positive and flag_not_single_pocket
        else "MIXED"
    )

    strong_path = write_dataframe_artifact(
        strong_stability,
        context,
        f"{BRANCH_NAME}_strong_cluster_stability",
    )
    share_path = write_dataframe_artifact(
        share_table,
        context,
        f"{BRANCH_NAME}_cluster_share",
    )

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "selected_active_k": selected_active_k,
            "active_base_ic": base_ic,
            "strong_cluster_count": int(len(strong_stability)),
            "dominant_cluster_share": dominant_share,
            "flag_multi_cluster_strength": bool(flag_multi_cluster),
            "flag_phase_positive": bool(flag_phase_positive),
            "flag_not_single_pocket": bool(flag_not_single_pocket),
            "max_single_cluster_share_gate": float(args.max_single_cluster_share),
        },
        artifacts={
            "source_h512_summary": args.h512_summary_path,
            "strong_cluster_stability": strong_path,
            "cluster_share": share_path,
        },
        metadata={
            "selected_h512_ts": payload.get("ts"),
            "gate_min_cluster_rows": int(args.min_cluster_rows),
        },
    )

    print(strong_stability.to_string(index=False))
    print(share_table.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_audit(parse_args())


if __name__ == "__main__":
    main()
