"""
H263: pooled family-aware reduced-shape intraday router.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.continuation_exit_research import (
    BASE_CONTINUATION_FEATURES,
    ContinuationModelSpec,
    fit_continuation_model,
)
from src.intraday_exit_research import (
    INTRADAY_SHAPE_ATOM_COLUMNS,
    REDUCED_SHAPE_FEATURE_COLUMNS,
    add_intraday_shape_atoms,
    build_family_aware_router_scores,
    summarize_continuation_probability_frame,
)
from src.run_summary import write_run_summary


H262_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_exit_intraday_family_contradiction_audit.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


BENCHMARK_SPECS = (
    ContinuationModelSpec(name="path_core_observed", feature_columns=tuple(BASE_CONTINUATION_FEATURES)),
    ContinuationModelSpec(name="intraday_shape_core", feature_columns=tuple(REDUCED_SHAPE_FEATURE_COLUMNS)),
    ContinuationModelSpec(name="intraday_shape_atoms", feature_columns=tuple(INTRADAY_SHAPE_ATOM_COLUMNS)),
    ContinuationModelSpec(
        name="intraday_shape_plus_path",
        feature_columns=tuple(list(BASE_CONTINUATION_FEATURES) + list(REDUCED_SHAPE_FEATURE_COLUMNS)),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H263: pooled family-aware reduced-shape intraday router")
    parser.add_argument("--h262-summary", type=str, default=str(H262_SUMMARY_PATH))
    parser.add_argument("--family-column", type=str, default="entry_thesis_family")
    return parser.parse_args()


def _summary_row_from_probabilities(frame: pd.DataFrame, *, model_name: str, prob_column: str) -> dict[str, object]:
    phase_metrics = summarize_continuation_probability_frame(frame, prob_column=prob_column)
    row: dict[str, object] = {
        "model_name": model_name,
        "feature_columns": [prob_column],
    }
    for phase in ("dev", "validation", "confirmation"):
        metrics = phase_metrics[phase]
        for key, value in metrics.items():
            row[f"{phase}_{key}"] = value
    return row


def main() -> None:
    args = parse_args()
    h262_summary_path = Path(args.h262_summary)
    h262_payload = load_summary_payload(h262_summary_path)
    if not bool(h262_payload.get("summary", {}).get("advance_to_h263", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_intraday_family_aware_router",
            name="h263_pooled_family_aware_intraday_router",
            summary={
                "skipped": True,
                "reason": "H262 did not clear the family-scoped contradiction gate",
            },
            artifacts={},
            metadata={},
        )
        return

    family_summary = pd.read_parquet(resolve_summary_artifact(h262_summary_path, "family_summary"))
    scored_panel = pd.read_parquet(resolve_summary_artifact(h262_summary_path, "scored_panel"))
    scored_panel["time"] = pd.to_datetime(scored_panel["time"], errors="coerce").dt.normalize()
    scored_panel = add_intraday_shape_atoms(scored_panel)

    routed_panel = build_family_aware_router_scores(
        scored_panel,
        family_summary,
        family_column=str(args.family_column),
        out_column="family_router_prob",
    )

    benchmark_rows: list[dict[str, object]] = []
    for spec in BENCHMARK_SPECS:
        fit = fit_continuation_model(routed_panel, spec=spec)
        benchmark_rows.append(dict(fit.summary_row))
        routed_panel.loc[fit.scored_dataset.index, f"benchmark_score__{spec.name}"] = pd.to_numeric(
            fit.scored_dataset["continuation_prob"],
            errors="coerce",
        ).to_numpy(dtype=float)

    benchmark_results = pd.DataFrame(benchmark_rows).sort_values(
        by=[
            "promoted",
            "validation_auc",
            "validation_top_quintile_hold_advantage",
            "confirmation_auc",
            "model_name",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    baseline_row = benchmark_results.loc[benchmark_results["model_name"] == "path_core_observed"].iloc[0]
    intraday_rows = benchmark_results.loc[benchmark_results["model_name"] != "path_core_observed"].reset_index(drop=True)
    best_intraday_row = intraday_rows.iloc[0]

    family_router_row = _summary_row_from_probabilities(
        routed_panel,
        model_name="family_aware_router",
        prob_column="family_router_prob",
    )
    family_router_row["feature_columns"] = [
        f"{row[str(args.family_column)]}:{row['router_model_name']}"
        for row in family_summary.to_dict(orient="records")
    ]
    family_router_row["router_intraday_family_count"] = int(pd.to_numeric(family_summary["router_uses_intraday"], errors="coerce").fillna(0).sum())
    family_router_row["router_intraday_families"] = sorted(
        str(value) for value in family_summary.loc[family_summary["router_uses_intraday"].fillna(False).astype(bool), str(args.family_column)].tolist()
    )

    family_router_val_auc = pd.to_numeric(family_router_row.get("validation_auc"), errors="coerce")
    family_router_val_tq = pd.to_numeric(
        family_router_row.get("validation_top_quintile_hold_advantage"),
        errors="coerce",
    )
    family_router_conf_tq = pd.to_numeric(
        family_router_row.get("confirmation_top_quintile_hold_advantage"),
        errors="coerce",
    )
    baseline_val_auc = pd.to_numeric(baseline_row.get("validation_auc"), errors="coerce")
    baseline_val_tq = pd.to_numeric(baseline_row.get("validation_top_quintile_hold_advantage"), errors="coerce")
    baseline_conf_tq = pd.to_numeric(baseline_row.get("confirmation_top_quintile_hold_advantage"), errors="coerce")
    best_intraday_val_auc = pd.to_numeric(best_intraday_row.get("validation_auc"), errors="coerce")
    best_intraday_val_tq = pd.to_numeric(best_intraday_row.get("validation_top_quintile_hold_advantage"), errors="coerce")

    passed = bool(
        pd.notna(family_router_val_auc)
        and pd.notna(family_router_val_tq)
        and pd.notna(family_router_conf_tq)
        and float(family_router_val_auc) > float(baseline_val_auc)
        and float(family_router_val_tq) > float(baseline_val_tq)
        and float(family_router_conf_tq) >= float(baseline_conf_tq)
    )
    mixed = bool(
        not passed
        and pd.notna(family_router_val_auc)
        and pd.notna(family_router_val_tq)
        and float(family_router_val_auc) > float(best_intraday_val_auc)
        and float(family_router_val_tq) > float(best_intraday_val_tq)
    )
    verdict = "PASSED" if passed else "MIXED" if mixed else "FAILED"

    family_router_row["validation_auc_delta_vs_path_core"] = (
        None if pd.isna(family_router_val_auc) or pd.isna(baseline_val_auc) else float(family_router_val_auc - baseline_val_auc)
    )
    family_router_row["validation_top_quintile_delta_vs_path_core"] = (
        None if pd.isna(family_router_val_tq) or pd.isna(baseline_val_tq) else float(family_router_val_tq - baseline_val_tq)
    )
    family_router_row["confirmation_top_quintile_delta_vs_path_core"] = (
        None if pd.isna(family_router_conf_tq) or pd.isna(baseline_conf_tq) else float(family_router_conf_tq - baseline_conf_tq)
    )
    family_router_row["decision"] = verdict

    results = pd.concat([benchmark_results, pd.DataFrame([family_router_row])], ignore_index=True)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h263_pooled_family_aware_intraday_router_results.parquet"
    routed_panel_path = OUT_DIR / f"{ts}_h263_pooled_family_aware_intraday_router_scored_panel.parquet"

    results.to_parquet(results_path, index=False)
    routed_panel.to_parquet(routed_panel_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_exit_intraday_family_aware_router",
        name="h263_pooled_family_aware_intraday_router",
        summary={
            "decision": verdict,
            "baseline_model": baseline_row.to_dict(),
            "best_intraday_model": best_intraday_row.to_dict(),
            "family_router": family_router_row,
            "family_router_choices": family_summary.to_dict(orient="records"),
        },
        artifacts={
            "results": str(results_path),
            "scored_panel": str(routed_panel_path),
        },
        metadata={
            "branch_contract": "Pooled family-aware router on the H262 family-scoped continuation branch",
            "h262_summary": str(h262_summary_path),
        },
    )


if __name__ == "__main__":
    main()
