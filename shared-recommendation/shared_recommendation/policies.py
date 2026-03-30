from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from shared_recommendation.artifacts import ArtifactKey, artifact_spec
from shared_recommendation.contracts import RecommendationContext


def ensure_candidate_columns(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    if "eligible" not in work.columns:
        work["eligible"] = True
    else:
        work["eligible"] = work["eligible"].fillna(False).astype(bool)
    if "_blocked_reasons" not in work.columns:
        work["_blocked_reasons"] = [[] for _ in range(len(work))]
    if "activation_state" not in work.columns:
        work["activation_state"] = "not_applied"
    if "tradability_source" not in work.columns:
        work["tradability_source"] = "not_applied"
    return work


def append_block_reason(frame: pd.DataFrame, mask: pd.Series, reason: str) -> pd.DataFrame:
    work = frame.copy()
    if not bool(mask.any()):
        return work
    for idx in work.index[mask]:
        existing = work.at[idx, "_blocked_reasons"]
        if isinstance(existing, str):
            reasons = [existing]
        elif isinstance(existing, tuple):
            reasons = list(existing)
        elif isinstance(existing, list):
            reasons = list(existing)
        else:
            reasons = []
        reasons.append(reason)
        work.at[idx, "_blocked_reasons"] = reasons
        work.at[idx, "eligible"] = False
    return work


def compute_cross_sectional_rank(frame: pd.DataFrame, score_column: str = "score_raw") -> pd.Series:
    numeric = pd.to_numeric(frame[score_column], errors="coerce")
    return numeric.groupby(frame["time"], sort=False).rank(method="average", pct=True)


def finalize_block_reasons(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["blocked_reasons_json"] = work["_blocked_reasons"].map(
        lambda values: json.dumps(
            list(values)
            if isinstance(values, (list, tuple))
            else ([values] if isinstance(values, str) and values else [])
        )
    )
    return work.drop(columns=["_blocked_reasons"])


@dataclass(frozen=True)
class TradabilityPolicy:
    artifact_key: str = ArtifactKey.TRADABILITY_DAILY
    missing_row_reason: str = "missing_tradability_row"
    blocked_reason: str = "cannot_buy_next_open"

    @property
    def policy_id(self) -> str:
        return "tradability_daily"

    def required_artifacts(self) -> tuple[str, ...]:
        return (self.artifact_key,)

    def apply(
        self,
        candidates: pd.DataFrame,
        *,
        context: RecommendationContext,
    ) -> pd.DataFrame:
        work = ensure_candidate_columns(candidates)
        path = Path(context.resolved_artifacts[self.artifact_key])
        spec = artifact_spec(self.artifact_key)
        tradability = pd.read_parquet(path, columns=list(spec.required_columns))
        tradability["time"] = pd.to_datetime(tradability["time"])

        merged = work.merge(
            tradability,
            on=["time", "ticker"],
            how="left",
            validate="one_to_one",
            suffixes=("", "_tradability"),
        )
        missing_row = merged["can_buy_next_open"].isna()
        merged["can_buy_next_open"] = merged["can_buy_next_open"].fillna(False).astype(bool)
        merged["tradability_source"] = str(path)
        merged = append_block_reason(merged, missing_row, self.missing_row_reason)
        merged = append_block_reason(merged, ~merged["can_buy_next_open"], self.blocked_reason)
        return merged
