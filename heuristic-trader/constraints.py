"""Trading constraints for dumb trading agent - mirrors RL-trading-agent rules."""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from datetime import datetime


DEFAULT_BUY_FEE_RATE = 0.001
DEFAULT_SELL_FEE_RATE = 0.0015
DEFAULT_CAPITAL_GAINS_TAX_RATE = 0.0001

DATA_ROOT = "/home/manh/stocks-ecosystem/data"
VNINDEX_DAILY = f"{DATA_ROOT}/stock/gia_lich_su_VNINDEX_1D.parquet"
TRADABILITY_DAILY = f"{DATA_ROOT}/features/execution/tradability_daily.parquet"


class DecisionTiming(str, Enum):
    CLOSE_T = "close_t"


class EntryTiming(str, Enum):
    OPEN_T_PLUS_1 = "open_t_plus_1"


@dataclass(frozen=True)
class ExecutionPolicy:
    decision_timing: str = "close_t"
    entry_timing: str = "open_t_plus_1"
    settlement_lag_days: int = 2
    earliest_sell_fill_offset_from_entry_open: int = 3
    price_limit_pct: float = 0.07
    price_limit_tolerance: float = 0.001
    buy_block_on_zero_volume: bool = True
    sell_block_on_zero_volume: bool = True
    buy_block_on_ceiling: bool = True
    sell_block_on_floor: bool = True


DEFAULT_EXECUTION_POLICY = ExecutionPolicy()


def required_holding_age_for_sell(
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    min_hold_days_override: int | None = None,
) -> int:
    if min_hold_days_override is not None:
        return max(min_hold_days_override, policy.earliest_sell_fill_offset_from_entry_open)
    return policy.earliest_sell_fill_offset_from_entry_open


def earliest_sell_step_after_entry(
    entry_execution_step: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> int:
    return entry_execution_step + policy.earliest_sell_fill_offset_from_entry_open


def can_schedule_sell(
    holding_age: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    min_hold_days_override: int | None = None,
) -> bool:
    return holding_age >= required_holding_age_for_sell(policy, min_hold_days_override)


def can_execute_buy(
    can_buy_next_open: bool,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> bool:
    return bool(can_buy_next_open)


def can_execute_sell(
    can_sell_next_open: bool,
    holding_age: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    min_hold_days_override: int | None = None,
) -> bool:
    return can_sell_next_open and can_schedule_sell(
        holding_age, policy, min_hold_days_override
    )


def compute_price_limit_flags(
    frame: pd.DataFrame,
    close_col: str = "close",
    prev_close_col: str | None = None,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> pd.DataFrame:
    close = pd.to_numeric(frame[close_col], errors="coerce")
    if prev_close_col is not None:
        prev_close = pd.to_numeric(frame[prev_close_col], errors="coerce")
    else:
        prev_close = close.shift(1)

    safe_prev_close = prev_close.where(prev_close != 0.0)
    ret = (close / safe_prev_close) - 1.0
    limit_pct = policy.price_limit_pct
    tolerance = policy.price_limit_tolerance
    is_ceiling = ret.between(
        limit_pct - tolerance, limit_pct + tolerance, inclusive="both"
    ).fillna(False)
    is_floor = ret.between(
        -(limit_pct + tolerance), -(limit_pct - tolerance), inclusive="both"
    ).fillna(False)

    return pd.DataFrame({
        "prev_close": prev_close,
        "return_from_prev_close": ret,
        "is_ceiling": is_ceiling.astype(bool),
        "is_floor": is_floor.astype(bool),
    }, index=frame.index)


def compute_tradability_flags(
    frame: pd.DataFrame,
    close_col: str = "close",
    volume_col: str = "volume",
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> pd.DataFrame:
    price_flags = compute_price_limit_flags(frame, close_col=close_col, policy=policy)
    volume = pd.to_numeric(frame[volume_col], errors="coerce").fillna(0.0)
    has_volume = volume > 0.0

    can_buy = pd.Series(True, index=frame.index, dtype=bool)
    can_sell = pd.Series(True, index=frame.index, dtype=bool)

    if policy.buy_block_on_zero_volume:
        can_buy &= has_volume
    if policy.sell_block_on_zero_volume:
        can_sell &= has_volume
    if policy.buy_block_on_ceiling:
        can_buy &= ~price_flags["is_ceiling"]
    if policy.sell_block_on_floor:
        can_sell &= ~price_flags["is_floor"]

    can_buy_next_open = can_buy.shift(1).fillna(False)
    can_sell_next_open = can_sell.shift(1).fillna(False)

    return pd.DataFrame({
        "has_volume": has_volume.astype(bool),
        "is_ceiling": price_flags["is_ceiling"],
        "is_floor": price_flags["is_floor"],
        "can_buy_next_open": can_buy_next_open.astype(bool),
        "can_sell_next_open": can_sell_next_open.astype(bool),
    }, index=frame.index)


class PositionSide(str, Enum):
    LONG = "long"
    CASH = "cash"


@dataclass(frozen=True)
class TradabilityColumns:
    has_volume: str = "has_volume"
    is_ceiling: str = "is_ceiling"
    is_floor: str = "is_floor"
    can_buy_next_open: str = "can_buy_next_open"
    can_sell_next_open: str = "can_sell_next_open"


DEFAULT_TRADABILITY_COLUMNS = TradabilityColumns()


@dataclass
class Holding:
    ticker: str
    entry_time: pd.Timestamp
    shares: int
    entry_price: float

    @property
    def holding_age(self, current_time: pd.Timestamp) -> int:
        return (current_time - self.entry_time).days


@dataclass
class Portfolio:
    cash: float = 1_000_000_000.0
    holdings: dict[str, Holding] = None

    def __post_init__(self):
        if self.holdings is None:
            self.holdings = {}

    def can_buy(self, ticker: str, tradability: dict) -> bool:
        if ticker in self.holdings:
            return False
        return tradability.get("can_buy_next_open", True)

    def can_sell(
        self, ticker: str, holding_age: int, tradability: dict
    ) -> bool:
        if ticker not in self.holdings:
            return False
        return can_execute_sell(
            tradability.get("can_sell_next_open", True),
            holding_age,
        )

    def buy(
        self,
        ticker: str,
        time: pd.Timestamp,
        shares: int,
        price: float,
    ) -> None:
        cost = shares * price
        if self.cash >= cost:
            self.cash -= cost
            self.holdings[ticker] = Holding(ticker, time, shares, price)

    def sell(
        self,
        ticker: str,
        time: pd.Timestamp,
        shares: int | None = None,
        price: float = 0.0,
    ) -> float:
        if ticker not in self.holdings:
            return 0.0
        holding = self.holdings[ticker]
        sell_shares = shares if shares else holding.shares
        proceeds = sell_shares * price
        self.cash += proceeds
        if shares is None or shares >= holding.shares:
            del self.holdings[ticker]
        else:
            holding.shares -= sell_shares
        return proceeds


def load_vnindex(start: str | None = None, end: str | None = None) -> pd.DataFrame:
    df = pd.read_parquet(VNINDEX_DAILY)
    df = df.sort_values("time").reset_index(drop=True)
    if start:
        df = df[df["time"] >= pd.to_datetime(start)]
    if end:
        df = df[df["time"] <= pd.to_datetime(end)]
    return df


def load_tradability(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
) -> pd.DataFrame:
    df = pd.read_parquet(TRADABILITY_DAILY)
    if start:
        df = df[df["time"] >= pd.to_datetime(start)]
    if end:
        df = df[df["time"] <= pd.to_datetime(end)]
    if tickers:
        df = df[df["ticker"].isin(tickers)]
    return df


def compute_portfolio_return(
    portfolio_value_before: float,
    portfolio_value_after: float,
    buy_turnover: float,
    sell_turnover: float,
    buy_fee_rate: float = DEFAULT_BUY_FEE_RATE,
    sell_fee_rate: float = DEFAULT_SELL_FEE_RATE,
    capital_gains_tax_rate: float = DEFAULT_CAPITAL_GAINS_TAX_RATE,
) -> float:
    fees = (
        portfolio_value_before * buy_turnover * buy_fee_rate +
        portfolio_value_before * sell_turnover * sell_fee_rate +
        max(0, portfolio_value_after - portfolio_value_before) * capital_gains_tax_rate
    )
    return (portfolio_value_after - portfolio_value_before - fees) / portfolio_value_before


if __name__ == "__main__":
    print("Vietnam Market Constraints:")
    print(f"  Price limit: ±{DEFAULT_EXECUTION_POLICY.price_limit_pct:.0%}")
    print(f"  Settlement: T+{DEFAULT_EXECUTION_POLICY.settlement_lag_days}")
    print(f"  Min hold days: {required_holding_age_for_sell()}")
    print(f"  Decision timing: {DEFAULT_EXECUTION_POLICY.decision_timing}")
    print(f"  Entry timing: {DEFAULT_EXECUTION_POLICY.entry_timing}")
    print(f"  Buy fee: {DEFAULT_BUY_FEE_RATE:.3%}")
    print(f"  Sell fee: {DEFAULT_SELL_FEE_RATE:.3%}")
    print(f"  CGT: {DEFAULT_CAPITAL_GAINS_TAX_RATE:.3%}")
    vn = load_vnindex()
    print(f"  VNINDEX: {vn.shape[0]} days, {vn['time'].min()} to {vn['time'].max()}")