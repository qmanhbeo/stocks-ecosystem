from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ExitRuleSpec:
    family: str
    params: dict[str, object]

    @property
    def variant_name(self) -> str:
        parts = [self.family]
        for key in sorted(self.params):
            value = self.params[key]
            if isinstance(value, float):
                token = str(value).replace(".", "p").replace("-", "m")
            else:
                token = str(value).replace(".", "p").replace("-", "m")
            parts.append(f"{key}_{token}")
        return "__".join(parts)


def build_exit_state_panel(blotter: pd.DataFrame) -> pd.DataFrame:
    if blotter.empty:
        return pd.DataFrame(
            columns=[
                "signal_date",
                "execution_date",
                "ticker",
                "holding_age_before",
                "signal_score",
                "score_rank",
                "entry_score",
                "entry_rank",
                "score_change_since_entry",
                "return_since_entry",
                "peak_return_since_entry",
                "underwater_days_since_entry",
                "blocked_sell_streak",
                "entry_thesis_family",
                "entry_thesis_score",
                "current_thesis_score",
                "thesis_score_change_since_entry",
                "can_sell_next_open",
                "sell_blocked",
                "exit_signal",
                "requested_action",
                "executed_action",
            ]
        )

    work = blotter.copy()
    keep = [
        "signal_date",
        "execution_date",
        "ticker",
        "holding_age_before",
        "signal_score",
        "score_rank",
        "entry_score",
        "entry_rank",
        "score_change_since_entry",
        "return_since_entry",
        "peak_return_since_entry",
        "underwater_days_since_entry",
        "blocked_sell_streak",
        "entry_thesis_family",
        "entry_thesis_score",
        "current_thesis_score",
        "thesis_score_change_since_entry",
        "can_sell_next_open",
        "sell_blocked",
        "exit_signal",
        "requested_action",
        "executed_action",
        "held_before",
    ]
    available = [column for column in keep if column in work.columns]
    work = work[available].copy()
    if "held_before" in work.columns:
        work = work.loc[work["held_before"].fillna(False).astype(bool)].copy()
        work = work.drop(columns=["held_before"])
    return work.reset_index(drop=True)
