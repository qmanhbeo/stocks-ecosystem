from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True)
class RecommendationRequest:
    profile_name: str
    adapter: "RecommendationModelAdapter"
    universe_source_key: str
    as_of_date: pd.Timestamp | str | None = None
    output_root: str | Path | None = None
    allow_stale_inputs: bool = False
    artifact_overrides: Mapping[str, str | Path] = field(default_factory=dict)
    policies: tuple["RecommendationPolicy", ...] = ()
    model_id: str | None = None
    top_n_summary: int = 10


@dataclass(frozen=True)
class RecommendationContext:
    request: RecommendationRequest
    as_of_date: pd.Timestamp
    resolved_artifacts: Mapping[str, Path]


@dataclass(frozen=True)
class RecommendationResult:
    candidates: pd.DataFrame
    manifest: dict[str, object]
    candidate_path: Path
    manifest_path: Path


@runtime_checkable
class RecommendationModelAdapter(Protocol):
    @property
    def adapter_id(self) -> str:
        ...

    def required_artifacts(self) -> tuple[str, ...]:
        ...

    def default_model_id(self) -> str:
        ...

    def score(
        self,
        universe_frame: pd.DataFrame,
        *,
        context: RecommendationContext,
    ) -> pd.DataFrame:
        ...


@runtime_checkable
class RecommendationPolicy(Protocol):
    @property
    def policy_id(self) -> str:
        ...

    def required_artifacts(self) -> tuple[str, ...]:
        ...

    def apply(
        self,
        candidates: pd.DataFrame,
        *,
        context: RecommendationContext,
    ) -> pd.DataFrame:
        ...
