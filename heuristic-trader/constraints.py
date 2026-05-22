"""Trading constraints for heuristic-trader, wired to shared execution rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from datetime import datetime


THIS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = THIS_DIR.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
SHARED_RECOMMENDATION_ROOT = WORKSPACE_ROOT / "shared-recommendation"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(SHARED_RECOMMENDATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_RECOMMENDATION_ROOT))

from shared_market_rules.execution import (  # noqa: E402
    DEFAULT_EXECUTION_POLICY,
    DEFAULT_TRADABILITY_COLUMNS,
    ExecutionPolicy,
    TradabilityColumns,
    can_execute_buy as _shared_can_execute_buy,
    can_execute_sell as _shared_can_execute_sell,
    can_schedule_sell as _shared_can_schedule_sell,
    compute_price_limit_flags as _shared_compute_price_limit_flags,
    compute_tradability_flags as _shared_compute_tradability_flags,
    earliest_sell_step_after_entry as _shared_earliest_sell_step_after_entry,
    required_holding_age_for_sell as _shared_required_holding_age_for_sell,
)
from shared_recommendation.artifacts import (  # noqa: E402
    default_market_data_dir,
    default_tradability_path,
    shared_data_root,
)


DEFAULT_BUY_FEE_RATE = 0.001
DEFAULT_SELL_FEE_RATE = 0.0015
DEFAULT_CAPITAL_GAINS_TAX_RATE = 0.0001

DATA_ROOT = str(shared_data_root())
VNINDEX_DAILY = default_market_data_dir() / "gia_lich_su_VNINDEX_1D.parquet"
TRADABILITY_DAILY = default_tradability_path()


class DecisionTiming(str, Enum):
    CLOSE_T = "close_t"


class EntryTiming(str, Enum):
    OPEN_T_PLUS_1 = "open_t_plus_1"


def required_holding_age_for_sell(
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    min_hold_days_override: int | None = None,
) -> int:
    return _shared_required_holding_age_for_sell(
        policy,
        min_hold_days_override=min_hold_days_override,
    )


def earliest_sell_step_after_entry(
    entry_execution_step: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> int:
    return _shared_earliest_sell_step_after_entry(entry_execution_step, policy)


def can_schedule_sell(
    holding_age: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    min_hold_days_override: int | None = None,
) -> bool:
    return _shared_can_schedule_sell(
        holding_age,
        policy,
        min_hold_days_override=min_hold_days_override,
    )


def can_execute_buy(
    can_buy_next_open: bool,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> bool:
    return _shared_can_execute_buy(can_buy_next_open, policy)


def can_execute_sell(
    can_sell_next_open: bool,
    holding_age: int,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    min_hold_days_override: int | None = None,
) -> bool:
    return _shared_can_execute_sell(
        can_sell_next_open,
        holding_age,
        policy,
        min_hold_days_override=min_hold_days_override,
    )


def compute_price_limit_flags(
    frame: pd.DataFrame,
    close_col: str = "close",
    prev_close_col: str | None = None,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> pd.DataFrame:
    return _shared_compute_price_limit_flags(
        frame,
        close_col=close_col,
        prev_close_col=prev_close_col,
        policy=policy,
    )


def compute_tradability_flags(
    frame: pd.DataFrame,
    close_col: str = "close",
    volume_col: str = "volume",
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
) -> pd.DataFrame:
    return _shared_compute_tradability_flags(
        frame,
        close_col=close_col,
        volume_col=volume_col,
        policy=policy,
        columns=DEFAULT_TRADABILITY_COLUMNS,
    )


class PositionSide(str, Enum):
    LONG = "long"
    CASH = "cash"


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
    holdings: dict[str, Holding] | None = None

    def __post_init__(self):
        if self.holdings is None:
            self.holdings = {}

    def can_buy(self, ticker: str, tradability: dict) -> bool:
        if ticker in self.holdings:
            return False
        return tradability.get("can_buy_next_open", True)

    def can_sell(self, ticker: str, holding_age: int, tradability: dict) -> bool:
        if ticker not in self.holdings:
            return False
        return can_execute_sell(tradability.get("can_sell_next_open", True), holding_age)

    def buy(self, ticker: str, time: pd.Timestamp, shares: int, price: float) -> None:
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
        portfolio_value_before * buy_turnover * buy_fee_rate
        + portfolio_value_before * sell_turnover * sell_fee_rate
        + max(0, portfolio_value_after - portfolio_value_before) * capital_gains_tax_rate
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
