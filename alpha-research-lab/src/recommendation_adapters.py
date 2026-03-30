from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_RECOMMENDATION_ROOT = WORKSPACE_ROOT / "shared-recommendation"
if str(SHARED_RECOMMENDATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_RECOMMENDATION_ROOT))

from shared_recommendation.artifacts import ArtifactKey
from shared_recommendation.contracts import RecommendationContext

from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns


@dataclass(frozen=True)
class SignalBlendAdapter:
    strategy_name: str = "full_library"

    @property
    def adapter_id(self) -> str:
        return "signal_blend"

    def required_artifacts(self) -> tuple[str, ...]:
        return (ArtifactKey.LAB_SIGNAL_MATRIX,)

    def default_model_id(self) -> str:
        return f"signal_blend__{self.strategy_name}"

    def score(
        self,
        universe_frame: pd.DataFrame,
        *,
        context: RecommendationContext,
    ) -> pd.DataFrame:
        columns = resolve_strategy_columns(universe_frame.columns.tolist(), self.strategy_name)
        scored = compute_strategy_scores(universe_frame.copy(), {self.strategy_name: columns})
        return (
            scored[["time", "ticker", f"score__{self.strategy_name}"]]
            .rename(columns={f"score__{self.strategy_name}": "score_raw"})
            .reset_index(drop=True)
        )


@dataclass(frozen=True)
class PrecomputedScoreAdapter:
    score_column: str
    model_name: str = "precomputed_score"

    @property
    def adapter_id(self) -> str:
        return "precomputed_score"

    def required_artifacts(self) -> tuple[str, ...]:
        return ()

    def default_model_id(self) -> str:
        return f"{self.model_name}__{self.score_column}"

    def score(
        self,
        universe_frame: pd.DataFrame,
        *,
        context: RecommendationContext,
    ) -> pd.DataFrame:
        if self.score_column not in universe_frame.columns:
            raise ValueError(
                f"Precomputed score column {self.score_column!r} is missing from the universe frame"
            )
        return (
            universe_frame[["time", "ticker", self.score_column]]
            .rename(columns={self.score_column: "score_raw"})
            .reset_index(drop=True)
        )


@dataclass(frozen=True)
class BinaryProbaAdapter:
    estimator: object
    feature_columns: tuple[str, ...]
    model_name: str = "binary_proba"

    @property
    def adapter_id(self) -> str:
        return "binary_proba"

    def required_artifacts(self) -> tuple[str, ...]:
        return ()

    def default_model_id(self) -> str:
        return self.model_name

    def score(
        self,
        universe_frame: pd.DataFrame,
        *,
        context: RecommendationContext,
    ) -> pd.DataFrame:
        missing = [column for column in self.feature_columns if column not in universe_frame.columns]
        if missing:
            raise ValueError(f"BinaryProbaAdapter missing feature columns: {missing}")
        if not hasattr(self.estimator, "predict_proba"):
            raise TypeError("BinaryProbaAdapter requires an estimator with predict_proba()")
        features = (
            universe_frame.loc[:, list(self.feature_columns)]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
        )
        probabilities = self.estimator.predict_proba(features)
        if probabilities.ndim != 2 or probabilities.shape[1] < 2:
            raise ValueError("predict_proba() must return a 2D array with at least 2 columns")
        return universe_frame[["time", "ticker"]].assign(score_raw=probabilities[:, 1])
