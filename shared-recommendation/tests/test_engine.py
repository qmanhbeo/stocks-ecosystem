from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from shared_recommendation import (
    ArtifactKey,
    RecommendationContext,
    RecommendationEngine,
    RecommendationRequest,
    TradabilityPolicy,
)


@dataclass(frozen=True)
class StubAdapter:
    @property
    def adapter_id(self) -> str:
        return "stub"

    def required_artifacts(self) -> tuple[str, ...]:
        return ()

    def default_model_id(self) -> str:
        return "stub_model"

    def score(self, universe_frame: pd.DataFrame, *, context: RecommendationContext) -> pd.DataFrame:
        return universe_frame[["time", "ticker"]].assign(score_raw=[0.9, 0.2])


def test_engine_generates_candidates_and_applies_tradability_gate(tmp_path):
    data_root = tmp_path / "data"
    matrix_path = data_root / "features" / "xs_rl_signal_matrix.parquet"
    tradability_path = data_root / "features" / "execution" / "tradability_daily.parquet"
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    tradability_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-27", "2026-03-27"]),
            "ticker": ["AAA", "BBB"],
            "actual": [1.0, 0.0],
        }
    ).to_parquet(matrix_path, index=False)
    pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-27", "2026-03-27"]),
            "ticker": ["AAA", "BBB"],
            "can_buy_next_open": [True, False],
        }
    ).to_parquet(tradability_path, index=False)

    engine = RecommendationEngine()
    result = engine.generate(
        RecommendationRequest(
            profile_name="unit_test_profile",
            adapter=StubAdapter(),
            universe_source_key=ArtifactKey.LAB_SIGNAL_MATRIX,
            as_of_date="2026-03-27",
            output_root=data_root / "features" / "recommendations",
            artifact_overrides={
                ArtifactKey.LAB_SIGNAL_MATRIX: matrix_path,
                ArtifactKey.TRADABILITY_DAILY: tradability_path,
            },
            policies=(TradabilityPolicy(),),
        )
    )

    assert result.manifest["eligible_count"] == 1
    assert result.candidate_path.exists()
    assert result.manifest_path.exists()

    saved = pd.read_parquet(result.candidate_path).sort_values("ticker").reset_index(drop=True)
    assert saved["ticker"].tolist() == ["AAA", "BBB"]
    assert saved["eligible"].tolist() == [True, False]
    assert json.loads(saved.loc[1, "blocked_reasons_json"]) == ["cannot_buy_next_open"]


def test_engine_rejects_duplicate_scored_rows(tmp_path):
    data_root = tmp_path / "data"
    matrix_path = data_root / "features" / "xs_rl_signal_matrix.parquet"
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-27", "2026-03-27"]),
            "ticker": ["AAA", "AAA"],
        }
    ).to_parquet(matrix_path, index=False)

    engine = RecommendationEngine()
    try:
        engine.generate(
            RecommendationRequest(
                profile_name="duplicate_test",
                adapter=StubAdapter(),
                universe_source_key=ArtifactKey.LAB_SIGNAL_MATRIX,
                as_of_date="2026-03-27",
                output_root=data_root / "features" / "recommendations",
                artifact_overrides={ArtifactKey.LAB_SIGNAL_MATRIX: matrix_path},
            )
        )
    except ValueError as exc:
        assert "duplicate" in str(exc).lower()
    else:
        raise AssertionError("Expected duplicate universe rows to fail")
