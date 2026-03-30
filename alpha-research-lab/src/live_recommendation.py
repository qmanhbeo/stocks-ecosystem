from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_RECOMMENDATION_ROOT = WORKSPACE_ROOT / "shared-recommendation"
if str(SHARED_RECOMMENDATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_RECOMMENDATION_ROOT))

from shared_recommendation import (
    ArtifactKey,
    RecommendationEngine,
    RecommendationRequest,
    TradabilityPolicy,
)

from src.recommendation_adapters import SignalBlendAdapter
from src.recommendation_policies import LatestLiveOverlayPolicy


def build_live_recommendation(
    *,
    profile_name: str,
    strategy: str,
    matrix_path: Path,
    tradability_path: Path,
    as_of_date: str | None,
    output_root: Path | None,
    apply_live_overlay_gate: bool,
    overlay_summary_path: Path,
    allow_stale_inputs: bool,
    allow_stale_overlay: bool,
    allow_overlay_signal_date_mismatch: bool,
):
    policies = [TradabilityPolicy()]
    if apply_live_overlay_gate:
        policies.append(
            LatestLiveOverlayPolicy(
                summary_path=overlay_summary_path,
                fail_on_stale_signal_matrix=not allow_stale_overlay,
                fail_on_signal_date_mismatch=not allow_overlay_signal_date_mismatch,
                expected_selector=strategy,
            )
        )
    engine = RecommendationEngine()
    return engine.generate(
        RecommendationRequest(
            profile_name=profile_name,
            adapter=SignalBlendAdapter(strategy_name=strategy),
            universe_source_key=ArtifactKey.LAB_SIGNAL_MATRIX,
            as_of_date=as_of_date,
            output_root=output_root,
            allow_stale_inputs=allow_stale_inputs,
            artifact_overrides={
                ArtifactKey.LAB_SIGNAL_MATRIX: matrix_path,
                ArtifactKey.TRADABILITY_DAILY: tradability_path,
            },
            policies=tuple(policies),
            model_id=f"signal_blend__{strategy}",
        )
    )


def summarize_live_recommendation(result, *, top_n: int = 10) -> dict[str, object]:
    candidates = result.candidates.copy()
    eligible = candidates.loc[candidates["eligible"].astype(bool)].copy()
    eligible = eligible.sort_values(["time", "eligible_rank", "ticker"]).head(max(int(top_n), 1))
    blocked = candidates.loc[~candidates["eligible"].astype(bool)].copy()
    return {
        "as_of_date": result.manifest["as_of_date"],
        "profile_name": result.manifest["profile_name"],
        "adapter_id": result.manifest["adapter_id"],
        "model_id": result.manifest["model_id"],
        "candidate_count": int(result.manifest["candidate_count"]),
        "eligible_count": int(result.manifest["eligible_count"]),
        "top_eligible": json.loads(eligible.to_json(orient="records", date_format="iso")) if not eligible.empty else [],
        "blocked_count": int(len(blocked)),
        "candidate_path": str(result.candidate_path),
        "manifest_path": str(result.manifest_path),
    }
