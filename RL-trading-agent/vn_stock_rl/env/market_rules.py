"""RL adapters for the shared execution-reality rules."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))

from shared_market_rules import (
    DEFAULT_EXECUTION_POLICY,
    can_schedule_sell as shared_can_schedule_sell,
    compute_tradability_flags,
    required_holding_age_for_sell,
)


def build_tradability_cache(df: pd.DataFrame) -> dict[str, np.ndarray]:
    flags = compute_tradability_flags(df[["time", "close", "volume"]].copy())
    return {
        "has_volume": flags["has_volume"].to_numpy(dtype=bool, copy=True),
        "is_ceiling": flags["is_ceiling"].to_numpy(dtype=bool, copy=True),
        "is_floor": flags["is_floor"].to_numpy(dtype=bool, copy=True),
        "can_buy_next_open": flags["can_buy_next_open"].to_numpy(dtype=bool, copy=True),
        "can_sell_next_open": flags["can_sell_next_open"].to_numpy(dtype=bool, copy=True),
    }


def resolve_required_holding_age(min_hold_days: int | None = None) -> int:
    return required_holding_age_for_sell(
        DEFAULT_EXECUTION_POLICY,
        min_hold_days_override=min_hold_days,
    )


def can_schedule_exit(holding_age: int, min_hold_days: int | None = None) -> bool:
    return shared_can_schedule_sell(
        holding_age,
        DEFAULT_EXECUTION_POLICY,
        min_hold_days_override=min_hold_days,
    )


def tradability_info_for_step(
    *,
    can_buy: np.ndarray,
    can_sell: np.ndarray,
    has_volume: np.ndarray,
    is_ceiling: np.ndarray,
    is_floor: np.ndarray,
    step_idx: int,
) -> dict[str, bool]:
    if step_idx < 0 or step_idx >= len(can_buy):
        return {
            "has_volume": False,
            "is_ceiling": False,
            "is_floor": False,
            "can_buy_next_open": False,
            "can_sell_next_open": False,
        }
    return {
        "has_volume": bool(has_volume[step_idx]),
        "is_ceiling": bool(is_ceiling[step_idx]),
        "is_floor": bool(is_floor[step_idx]),
        "can_buy_next_open": bool(can_buy[step_idx]),
        "can_sell_next_open": bool(can_sell[step_idx]),
    }
