"""
H262: family-scoped reduced-shape intraday contradiction audit.
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
from src.intraday_exit_research import (
    FAMILY_CONTRADICTION_MODEL_SPECS,
    add_intraday_shape_atoms,
    annotate_family_contradiction_results,
    fit_family_scoped_continuation_models,
    summarize_family_router_choices,
)
from src.run_summary import write_run_summary


H259_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_exit_intraday_reduced_shape_predictive_screen.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H262: family-scoped reduced-shape intraday contradiction audit")
    parser.add_argument("--h259-summary", type=str, default=str(H259_SUMMARY_PATH))
    parser.add_argument("--family-column", type=str, default="entry_thesis_family")
    return parser.parse_args()


def _family_names(frame: pd.DataFrame, family_column: str, decision: str) -> list[str]:
    if frame.empty or "best_candidate_decision" not in frame.columns:
        return []
    mask = frame["best_candidate_decision"].astype(str) == str(decision)
    return sorted(str(value) for value in frame.loc[mask, family_column].tolist())


def main() -> None:
    args = parse_args()
    h259_summary_path = Path(args.h259_summary)
    h259_payload = load_summary_payload(h259_summary_path)
    if bool(h259_payload.get("summary", {}).get("skipped", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_intraday_family_contradiction_audit",
            name="h262_intraday_family_contradiction_audit",
            summary={
                "skipped": True,
                "reason": "H259 was skipped, so there is no observed reduced-shape continuation panel to audit",
            },
            artifacts={},
            metadata={},
        )
        return

    observed_path = resolve_summary_artifact(h259_summary_path, "observed_panel")
    observed = pd.read_parquet(observed_path)
    observed["time"] = pd.to_datetime(observed["time"], errors="coerce").dt.normalize()
    observed = add_intraday_shape_atoms(observed)

    bundle = fit_family_scoped_continuation_models(
        observed,
        family_column=str(args.family_column),
        specs=FAMILY_CONTRADICTION_MODEL_SPECS,
    )
    results = annotate_family_contradiction_results(
        bundle.results,
        family_column=str(args.family_column),
    )
    family_summary = summarize_family_router_choices(
        results,
        family_column=str(args.family_column),
    )

    passed_families = _family_names(family_summary, str(args.family_column), "PASSED")
    mixed_families = _family_names(family_summary, str(args.family_column), "MIXED")
    verdict = "PASSED" if passed_families else "MIXED" if mixed_families else "FAILED"
    advance_to_h263 = verdict in {"PASSED", "MIXED"}

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h262_intraday_family_contradiction_audit_results.parquet"
    family_summary_path = OUT_DIR / f"{ts}_h262_intraday_family_contradiction_audit_family_summary.parquet"
    scored_path = OUT_DIR / f"{ts}_h262_intraday_family_contradiction_audit_scored_panel.parquet"

    results.to_parquet(results_path, index=False)
    family_summary.to_parquet(family_summary_path, index=False)
    bundle.scored_panel.to_parquet(scored_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_exit_intraday_family_contradiction_audit",
        name="h262_intraday_family_contradiction_audit",
        summary={
            "decision": verdict,
            "advance_to_h263": advance_to_h263,
            "protocol": h259_payload.get("summary", {}).get("protocol"),
            "family_count": int(family_summary[str(args.family_column)].nunique()) if not family_summary.empty else 0,
            "observed_row_count": int(len(observed)),
            "passed_families": passed_families,
            "mixed_families": mixed_families,
            "best_family": None if family_summary.empty else family_summary.iloc[0].to_dict(),
            "family_decisions": [] if family_summary.empty else family_summary.to_dict(orient="records"),
        },
        artifacts={
            "results": str(results_path),
            "family_summary": str(family_summary_path),
            "scored_panel": str(scored_path),
        },
        metadata={
            "branch_contract": "Family-scoped reduced-shape contradiction audit on the H259 observed panel only",
            "h259_summary": str(h259_summary_path),
        },
    )


if __name__ == "__main__":
    main()
