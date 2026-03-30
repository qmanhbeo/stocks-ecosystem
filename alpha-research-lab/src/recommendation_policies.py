from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_RECOMMENDATION_ROOT = WORKSPACE_ROOT / "shared-recommendation"
if str(SHARED_RECOMMENDATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_RECOMMENDATION_ROOT))

from shared_recommendation.contracts import RecommendationContext
from shared_recommendation.policies import append_block_reason, ensure_candidate_columns


LATEST_LIVE_OVERLAY_SUMMARY = Path("artifacts/run_summaries/latest_portfolio_live_activation_overlay.json")


@dataclass(frozen=True)
class LatestLiveOverlayPolicy:
    summary_path: Path = LATEST_LIVE_OVERLAY_SUMMARY
    fail_on_stale_signal_matrix: bool = True
    fail_on_signal_date_mismatch: bool = True
    expected_selector: str | None = None

    @property
    def policy_id(self) -> str:
        return "alpha_latest_live_overlay"

    def required_artifacts(self) -> tuple[str, ...]:
        return ()

    def apply(
        self,
        candidates: pd.DataFrame,
        *,
        context: RecommendationContext,
    ) -> pd.DataFrame:
        work = ensure_candidate_columns(candidates)
        if not self.summary_path.exists():
            work["activation_state"] = "missing_overlay"
            return append_block_reason(work, pd.Series([True] * len(work), index=work.index), "missing_live_overlay")

        payload = json.loads(self.summary_path.read_text(encoding="utf-8"))
        summary = payload.get("summary", {})
        selector = summary.get("selector")
        next_open = summary.get("next_open_recommendation") or {}
        activation_on = next_open.get("activation_on")
        signal_date_text = next_open.get("signal_date")
        stale = bool(summary.get("stale_signal_matrix", False))

        if activation_on is None:
            work["activation_state"] = "unknown"
            work = append_block_reason(work, pd.Series([True] * len(work), index=work.index), "missing_activation_state")
        else:
            work["activation_state"] = "on" if bool(activation_on) else "off"
            if not bool(activation_on):
                work = append_block_reason(work, pd.Series([True] * len(work), index=work.index), "activation_off")

        if self.expected_selector is not None and selector != self.expected_selector:
            work["activation_state"] = "selector_mismatch"
            work = append_block_reason(
                work,
                pd.Series([True] * len(work), index=work.index),
                "overlay_selector_mismatch",
            )

        if stale and self.fail_on_stale_signal_matrix:
            work["activation_state"] = "stale_overlay"
            work = append_block_reason(
                work,
                pd.Series([True] * len(work), index=work.index),
                "stale_live_overlay",
            )

        if signal_date_text and self.fail_on_signal_date_mismatch:
            expected = pd.Timestamp(signal_date_text).normalize()
            actual = pd.Timestamp(context.as_of_date).normalize()
            if expected != actual:
                work["activation_state"] = "signal_date_mismatch"
                work = append_block_reason(
                    work,
                    pd.Series([True] * len(work), index=work.index),
                    "overlay_signal_date_mismatch",
                )
        return work
