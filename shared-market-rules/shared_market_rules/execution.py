"""Canonical execution reality and tradability helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ExecutionPolicy:
    decision_timing: str = "close_t"
    entry_timing: str = "open_t_plus_1"
    settlement_lag_days: int = 2
    # With close-based decisions and next-open execution, Vietnam T+2.5 settlement
    # means the first legal sell decision is close[T+3], which fills at open[T+4].
    earliest_sell_fill_offset_from_entry_open: int = 3
    price_limit_pct: float = 0.07
    price_limit_tolerance: float = 0.001
    buy_block_on_zero_volume: bool = True
    sell_block_on_zero_volume: bool = True
    buy_block_on_ceiling: bool = True
    sell_block_on_floor: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TradabilityColumns:
    has_volume: str = "has_volume"
    is_ceiling: str = "is_ceiling"
    is_floor: str = "is_floor"
    can_buy_next_open: str = "can_buy_next_open"
    can_sell_next_open: str = "can_sell_next_open"


DEFAULT_EXECUTION_POLICY = ExecutionPolicy()
DEFAULT_TRADABILITY_COLUMNS = TradabilityColumns()


def required_holding_age_for_sell(
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    *,
    min_hold_days_override: int | None = None,
) -> int:
    if min_hold_days_override is not None:
        return max(
            int(min_hold_days_override),
            int(policy.earliest_sell_fill_offset_from_entry_open),
        )
    return int(policy.earliest_sell_fill_offset_from_entry_open)


def earliest_sell_step_after_entry(
    entry_execution_step: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> int:
    return int(entry_execution_step) + int(policy.earliest_sell_fill_offset_from_entry_open)


def can_schedule_sell(
    holding_age: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    *,
    min_hold_days_override: int | None = None,
) -> bool:
    return int(holding_age) >= required_holding_age_for_sell(
        policy,
        min_hold_days_override=min_hold_days_override,
    )


def can_execute_buy(
    can_buy_next_open: bool,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> bool:
    return bool(can_buy_next_open)


def can_execute_sell(
    can_sell_next_open: bool,
    holding_age: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    *,
    min_hold_days_override: int | None = None,
) -> bool:
    return bool(can_sell_next_open) and can_schedule_sell(
        holding_age,
        policy,
        min_hold_days_override=min_hold_days_override,
    )


def compute_price_limit_flags(
    frame: pd.DataFrame,
    *,
    close_col: str = "close",
    prev_close_col: str | None = None,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> pd.DataFrame:
    if close_col not in frame.columns:
        raise ValueError(f"Missing required close column: {close_col}")

    close = pd.to_numeric(frame[close_col], errors="coerce")
    if prev_close_col is not None:
        if prev_close_col not in frame.columns:
            raise ValueError(f"Missing required prev_close column: {prev_close_col}")
        prev_close = pd.to_numeric(frame[prev_close_col], errors="coerce")
    else:
        prev_close = close.shift(1)

    safe_prev_close = prev_close.where(prev_close != 0.0)
    ret = (close / safe_prev_close) - 1.0
    limit_pct = float(policy.price_limit_pct)
    tolerance = float(policy.price_limit_tolerance)
    is_ceiling = ret.between(limit_pct - tolerance, limit_pct + tolerance, inclusive="both").fillna(False)
    is_floor = ret.between(-(limit_pct + tolerance), -(limit_pct - tolerance), inclusive="both").fillna(False)

    return pd.DataFrame(
        {
            "prev_close": prev_close,
            "return_from_prev_close": ret,
            DEFAULT_TRADABILITY_COLUMNS.is_ceiling: is_ceiling.astype(bool),
            DEFAULT_TRADABILITY_COLUMNS.is_floor: is_floor.astype(bool),
        },
        index=frame.index,
    )


def compute_tradability_flags(
    frame: pd.DataFrame,
    *,
    close_col: str = "close",
    volume_col: str = "volume",
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    columns: TradabilityColumns = DEFAULT_TRADABILITY_COLUMNS,
) -> pd.DataFrame:
    if volume_col not in frame.columns:
        raise ValueError(f"Missing required volume column: {volume_col}")

    price_flags = compute_price_limit_flags(frame, close_col=close_col, policy=policy)
    volume = pd.to_numeric(frame[volume_col], errors="coerce")
    has_volume = volume.fillna(0.0) > 0.0

    can_buy = pd.Series(True, index=frame.index, dtype=bool)
    can_sell = pd.Series(True, index=frame.index, dtype=bool)

    if policy.buy_block_on_zero_volume:
        can_buy &= has_volume
    if policy.sell_block_on_zero_volume:
        can_sell &= has_volume
    if policy.buy_block_on_ceiling:
        can_buy &= ~price_flags[columns.is_ceiling]
    if policy.sell_block_on_floor:
        can_sell &= ~price_flags[columns.is_floor]

    passthrough_cols = [col for col in ("time", "ticker") if col in frame.columns]
    data = frame[passthrough_cols].copy() if passthrough_cols else pd.DataFrame(index=frame.index)
    data[columns.has_volume] = has_volume.astype(bool)
    data[columns.is_ceiling] = price_flags[columns.is_ceiling].astype(bool)
    data[columns.is_floor] = price_flags[columns.is_floor].astype(bool)
    data[columns.can_buy_next_open] = can_buy.astype(bool)
    data[columns.can_sell_next_open] = can_sell.astype(bool)
    return data.reset_index(drop=True) if passthrough_cols else data
