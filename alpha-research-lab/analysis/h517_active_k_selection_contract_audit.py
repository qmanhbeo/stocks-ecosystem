"""
H517: active_k_selection_contract_audit

Protocol audit to freeze active-k selection discipline after H514-H516.
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


BRANCH_NAME = "active_k_selection_contract_audit"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "A constrained axis-aware active-k selection rule should avoid silhouette-only "
        "drift while preserving strict dev-only model-selection discipline."
    ),
    start_year=2015,
    end_year=2025,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H517 active-k selection contract audit")
    parser.add_argument(
        "--h512-summary",
        type=str,
        default=str(ROOT / "artifacts" / "run_summaries" / "20260517_132235_active_manifold_disentangling_research_branch.json"),
    )
    parser.add_argument(
        "--h514-summary",
        type=str,
        default=str(ROOT / "artifacts" / "run_summaries" / "20260517_133731_amplified_axis_refinement_research_branch.json"),
    )
    parser.add_argument("--min_amplified_jaccard", type=float, default=0.06)
    parser.add_argument("--min_mean_disentangle", type=float, default=0.10)
    parser.add_argument("--min_lift_gap", type=float, default=0.01)
    parser.add_argument("--min_strong_clusters", type=int, default=2)
    return parser.parse_args()


def _load_table(summary_path: str) -> tuple[dict, pd.DataFrame]:
    with open(summary_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    rel = payload["artifacts"]["active_k_discipline"]
    path = Path(rel)
    if not path.is_absolute():
        path = ROOT / rel
    df = pd.read_parquet(path)
    return payload, df


def _rule_silhouette(df: pd.DataFrame) -> int:
    row = df.sort_values(["silhouette_dev", "active_k"], ascending=[False, True]).iloc[0]
    return int(row["active_k"])


def _rule_axis_guarded(
    df: pd.DataFrame,
    *,
    min_amp: float,
    min_mean: float,
    min_gap: float,
    min_strong: int,
) -> int | None:
    gate = df[
        (df["max_jaccard_amplified"] >= float(min_amp))
        & (df["mean_disentangle_jaccard"] >= float(min_mean))
        & (df["active_lift_minus_random_lift"] >= float(min_gap))
        & (df["strong_non_sparse_clusters"] >= int(min_strong))
    ].copy()
    if gate.empty:
        return None
    row = gate.sort_values(["silhouette_dev", "active_k"], ascending=[False, True]).iloc[0]
    return int(row["active_k"])


def _collect(run_name: str, df: pd.DataFrame, sil_k: int, guard_k: int | None) -> dict[str, object]:
    out = {"run": run_name, "silhouette_k": sil_k, "guarded_k": guard_k}
    for label, k in [("silhouette", sil_k), ("guarded", guard_k)]:
        if k is None:
            continue
        row = df[df["active_k"] == int(k)].iloc[0]
        out[f"{label}_amplified"] = float(row["max_jaccard_amplified"])
        out[f"{label}_mean_disentangle"] = float(row["mean_disentangle_jaccard"])
        out[f"{label}_lift_gap"] = float(row["active_lift_minus_random_lift"])
        out[f"{label}_strong_clusters"] = int(row["strong_non_sparse_clusters"])
        out[f"{label}_silhouette_dev"] = float(row["silhouette_dev"])
    return out


def run_audit(args: argparse.Namespace) -> str:
    context = build_experiment_context(replace(SPEC), artifact_subdir="research_branches")

    h512_payload, h512_df = _load_table(args.h512_summary)
    h514_payload, h514_df = _load_table(args.h514_summary)

    h512_sil = _rule_silhouette(h512_df)
    h514_sil = _rule_silhouette(h514_df)

    h512_guard = _rule_axis_guarded(
        h512_df,
        min_amp=args.min_amplified_jaccard,
        min_mean=args.min_mean_disentangle,
        min_gap=args.min_lift_gap,
        min_strong=args.min_strong_clusters,
    )
    h514_guard = _rule_axis_guarded(
        h514_df,
        min_amp=args.min_amplified_jaccard,
        min_mean=args.min_mean_disentangle,
        min_gap=args.min_lift_gap,
        min_strong=args.min_strong_clusters,
    )

    rows = [
        _collect("h512", h512_df, h512_sil, h512_guard),
        _collect("h514", h514_df, h514_sil, h514_guard),
    ]
    out = pd.DataFrame(rows)

    # pass condition: guarded rule exists for both and improves amplified axis on h514
    h514_row = out[out["run"] == "h514"].iloc[0]
    guarded_exists = pd.notna(h514_row.get("guarded_k"))
    h514_improves_amp = (
        guarded_exists
        and float(h514_row["guarded_amplified"]) > float(h514_row["silhouette_amplified"])
    )
    h514_guard_preserves_lift = (
        guarded_exists and float(h514_row["guarded_lift_gap"]) >= float(args.min_lift_gap)
    )
    decision = (
        "SUPPORTS guarded selection contract"
        if guarded_exists and h514_improves_amp and h514_guard_preserves_lift
        else "MIXED"
    )

    out_path = write_dataframe_artifact(out, context, f"{BRANCH_NAME}_comparison")
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "h512_silhouette_k": int(h512_sil),
            "h512_guarded_k": int(h512_guard) if h512_guard is not None else None,
            "h514_silhouette_k": int(h514_sil),
            "h514_guarded_k": int(h514_guard) if h514_guard is not None else None,
            "h514_silhouette_amplified": float(h514_row["silhouette_amplified"]),
            "h514_guarded_amplified": float(h514_row["guarded_amplified"]) if guarded_exists else None,
            "h514_guarded_lift_gap": float(h514_row["guarded_lift_gap"]) if guarded_exists else None,
            "flag_guarded_exists": bool(guarded_exists),
            "flag_h514_guarded_improves_amplified": bool(h514_improves_amp),
            "flag_h514_guarded_preserves_lift_gap": bool(h514_guard_preserves_lift),
        },
        artifacts={
            "comparison": out_path,
            "source_h512_summary": args.h512_summary,
            "source_h514_summary": args.h514_summary,
        },
        metadata={
            "guardrails": {
                "min_amplified_jaccard": float(args.min_amplified_jaccard),
                "min_mean_disentangle": float(args.min_mean_disentangle),
                "min_lift_gap": float(args.min_lift_gap),
                "min_strong_clusters": int(args.min_strong_clusters),
            }
        },
    )

    print(out.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_audit(parse_args())


if __name__ == "__main__":
    main()
