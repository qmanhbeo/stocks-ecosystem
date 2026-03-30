from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from shared_recommendation.artifacts import (
    ArtifactKey,
    artifact_spec,
    assert_artifact_current,
    default_recommendation_candidates_path,
    default_recommendation_manifest_path,
    resolve_artifact_path,
)
from shared_recommendation.contracts import (
    RecommendationContext,
    RecommendationRequest,
    RecommendationResult,
)
from shared_recommendation.io import write_recommendation_artifacts
from shared_recommendation.policies import (
    compute_cross_sectional_rank,
    ensure_candidate_columns,
    finalize_block_reasons,
)


class RecommendationEngine:
    def generate(self, request: RecommendationRequest) -> RecommendationResult:
        universe_path = self._resolve_artifact_path(
            request.universe_source_key,
            request.artifact_overrides,
        )
        universe_spec = artifact_spec(request.universe_source_key)
        universe = pd.read_parquet(universe_path)
        missing_columns = sorted(set(universe_spec.required_columns) - set(universe.columns))
        if missing_columns:
            raise ValueError(
                f"Universe source is missing required columns {missing_columns}: {universe_path}"
            )
        universe["time"] = pd.to_datetime(universe["time"], errors="coerce")
        if universe["time"].isna().any():
            raise ValueError(f"Universe source contains invalid 'time' values: {universe_path}")

        as_of_date = (
            pd.Timestamp(request.as_of_date)
            if request.as_of_date is not None
            else pd.Timestamp(universe["time"].max())
        ).normalize()
        universe = universe.loc[universe["time"].dt.normalize() == as_of_date].copy()
        if universe.empty:
            raise ValueError(f"No universe rows remain for as_of_date {as_of_date.date()}")
        if universe.duplicated(subset=["time", "ticker"]).any():
            raise ValueError("Universe source contains duplicate (time, ticker) rows")

        resolved_artifacts = {
            request.universe_source_key: universe_path,
        }
        required_artifacts = set(request.adapter.required_artifacts())
        for policy in request.policies:
            required_artifacts.update(policy.required_artifacts())
        for key in sorted(required_artifacts):
            path = self._resolve_artifact_path(key, request.artifact_overrides)
            resolved_artifacts[key] = path
            if not request.allow_stale_inputs:
                assert_artifact_current(path, artifact_spec(key), as_of_date)

        context = RecommendationContext(
            request=request,
            as_of_date=as_of_date,
            resolved_artifacts=resolved_artifacts,
        )
        scored = request.adapter.score(universe, context=context)
        self._validate_scored_frame(scored)
        candidates = scored.copy()
        candidates["time"] = pd.to_datetime(candidates["time"])
        candidates["adapter_id"] = request.adapter.adapter_id
        candidates["model_id"] = request.model_id or request.adapter.default_model_id()
        candidates["score_rank_pct"] = compute_cross_sectional_rank(candidates)
        candidates["score_final"] = pd.to_numeric(candidates["score_rank_pct"], errors="coerce").fillna(0.0)
        candidates = ensure_candidate_columns(candidates)
        for policy in request.policies:
            candidates = policy.apply(candidates, context=context)
            candidates = ensure_candidate_columns(candidates)

        candidates["candidate_rank"] = (
            pd.to_numeric(candidates["score_final"], errors="coerce")
            .groupby(candidates["time"], sort=False)
            .rank(method="first", ascending=False)
        )
        eligible_rank = (
            pd.to_numeric(candidates["score_final"], errors="coerce")
            .where(candidates["eligible"].astype(bool))
            .groupby(candidates["time"], sort=False)
            .rank(method="first", ascending=False)
        )
        candidates["eligible_rank"] = eligible_rank
        manifest_payload = {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "profile_name": request.profile_name,
            "adapter_id": request.adapter.adapter_id,
            "model_id": request.model_id or request.adapter.default_model_id(),
            "as_of_date": str(as_of_date.date()),
            "candidate_count": int(len(candidates)),
            "eligible_count": int(candidates["eligible"].astype(bool).sum()),
            "source_artifacts": {key: str(path) for key, path in sorted(resolved_artifacts.items())},
            "policies": [policy.policy_id for policy in request.policies],
            "top_eligible_tickers": (
                candidates.loc[candidates["eligible"].astype(bool)]
                .sort_values(["time", "eligible_rank", "ticker"])
                .head(max(int(request.top_n_summary), 1))["ticker"]
                .astype(str)
                .tolist()
            ),
        }
        candidates["artifact_manifest_json"] = json.dumps(
            {
                "profile_name": manifest_payload["profile_name"],
                "adapter_id": manifest_payload["adapter_id"],
                "model_id": manifest_payload["model_id"],
                "as_of_date": manifest_payload["as_of_date"],
                "source_artifacts": manifest_payload["source_artifacts"],
            },
            sort_keys=True,
        )
        candidates = finalize_block_reasons(candidates)

        if request.output_root is None:
            candidate_path = default_recommendation_candidates_path(request.profile_name)
            manifest_path = default_recommendation_manifest_path(request.profile_name)
        else:
            output_root = Path(request.output_root).expanduser().resolve()
            candidate_path = output_root / request.profile_name / "latest_candidates.parquet"
            manifest_path = output_root / request.profile_name / "manifest.json"

        write_recommendation_artifacts(
            candidates=candidates,
            manifest=manifest_payload,
            candidate_path=candidate_path,
            manifest_path=manifest_path,
        )
        return RecommendationResult(
            candidates=candidates,
            manifest=manifest_payload,
            candidate_path=candidate_path,
            manifest_path=manifest_path,
        )

    @staticmethod
    def _resolve_artifact_path(
        artifact_key: str,
        overrides: dict[str, str | Path] | None,
    ) -> Path:
        if overrides and artifact_key in overrides:
            return Path(overrides[artifact_key]).expanduser().resolve()
        return resolve_artifact_path(artifact_key)

    @staticmethod
    def _validate_scored_frame(frame: pd.DataFrame) -> None:
        required = {"time", "ticker", "score_raw"}
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"Adapter output is missing required columns: {missing}")
        if frame.duplicated(subset=["time", "ticker"]).any():
            raise ValueError("Adapter output contains duplicate (time, ticker) rows")
