from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))

from shared_market_rules import required_holding_age_for_sell

from src.activation_alpha import load_activation_experiment_inputs
from src.activation_meta import ACTIVATION_META_PATH, load_or_build_activation_meta
from src.activation_meta_experiment_utils import (
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    selector_recent_relative_ewm_from_prev,
)


@dataclass(frozen=True)
class ChampionSetup:
    selector_name: str
    selector_strategy_name: str
    signal_columns: tuple[str, ...]
    inputs: object
    meta_state: pd.DataFrame
    rel2: pd.Series
    common_kwargs: dict[str, object]


def load_champion_setup(
    *,
    start_year: int,
    end_year: int,
    meta_start_year: int = 2015,
    round_trip_cost: float = 0.003,
    required_holding_age: int = 3,
    initial_notional_vnd: float = 100_000_000.0,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    activation_state_path: Path = ACTIVATION_STATE_PATH,
    activation_meta_path: Path = ACTIVATION_META_PATH,
) -> ChampionSetup:
    inputs = load_activation_experiment_inputs(
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=int(start_year),
        end_year=int(end_year),
    )
    meta_state, _ = load_or_build_activation_meta(
        out_path=activation_meta_path,
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        activation_state_path=activation_state_path,
        start_year=int(meta_start_year),
        end_year=int(end_year),
        round_trip_cost=float(round_trip_cost),
        required_holding_age=int(required_holding_age),
        initial_notional_vnd=float(initial_notional_vnd),
    )
    meta_state = meta_state[
        (meta_state["time"].dt.year >= int(start_year))
        & (meta_state["time"].dt.year <= int(end_year))
    ].copy()
    selector = next(selector for selector in inputs.selectors if selector.name == "full_library_k5_r5_eq")
    rel2 = selector_recent_relative_ewm_from_prev(meta_state, prefix="full", span=2)
    rel2.index = pd.to_datetime(meta_state["time"])
    fee_leg = float(round_trip_cost) / 2.0
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(required_holding_age))
    common_kwargs = dict(
        strategy_name=selector.strategy_name,
        signal_columns=list(selector.signal_columns),
        market_inputs=inputs.market_inputs,
        top_k=int(selector.top_k),
        rebalance_every=int(selector.rebalance_every),
        weighting=str(selector.weighting),
        initial_notional_vnd=float(initial_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(hold_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=0.0,
    )
    return ChampionSetup(
        selector_name=selector.name,
        selector_strategy_name=selector.strategy_name,
        signal_columns=tuple(selector.signal_columns),
        inputs=inputs,
        meta_state=meta_state,
        rel2=rel2,
        common_kwargs=common_kwargs,
    )


def align_series_to_market_dates(series: pd.Series, market_dates: np.ndarray, *, fill_value: float = 0.0) -> np.ndarray:
    aligned = (
        pd.DataFrame({"time": pd.to_datetime(series.index), "value": pd.to_numeric(series, errors="coerce")})
        .drop_duplicates("time")
        .set_index("time")
        .reindex(pd.to_datetime(market_dates))
    )
    return aligned["value"].fillna(float(fill_value)).to_numpy(dtype=np.float64)
