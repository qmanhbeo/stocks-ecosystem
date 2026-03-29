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
from src.deterministic_portfolio import simulate_strategy


SECTOR_PATH = Path("data/features/sector_classification.parquet")
CURRENT_CHAMPION_REFERENCE_SUMMARY_PATH = Path(
    "artifacts/run_summaries/latest_portfolio_activation_impl_pain_sector_combo.json"
)


@dataclass(frozen=True)
class ChampionSetup:
    selector_name: str
    selector_strategy_name: str
    signal_columns: tuple[str, ...]
    inputs: object
    meta_state: pd.DataFrame
    meta_source: str
    rel2: pd.Series
    common_kwargs: dict[str, object]


@dataclass(frozen=True)
class ChampionVariantSpec:
    name: str
    rel_span: int = 2
    rel_threshold: float = 0.0
    incumbent_score_bonus: float = 0.0
    blocked_buy_span: int | None = None
    blocked_buy_max_quantile: float | None = None
    blocked_buy_off_quantile: float | None = None
    max_names_per_sector: int | None = None


@dataclass(frozen=True)
class ChampionVariantRun:
    spec: ChampionVariantSpec
    gate: pd.Series
    rel_series: pd.Series
    blocked_buy_series: pd.Series | None
    blocked_buy_on_threshold: float | None
    blocked_buy_off_threshold: float | None
    sector_labels: tuple[str | None, ...] | None
    result: object


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
    meta_state, meta_source = load_or_build_activation_meta(
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
        meta_source=meta_source,
        rel2=rel2,
        common_kwargs=common_kwargs,
    )


def current_champion_variant() -> ChampionVariantSpec:
    return ChampionVariantSpec(
        name="impl__blocked5_q80_sector_cap_3",
        rel_span=2,
        rel_threshold=0.0,
        incumbent_score_bonus=0.015,
        blocked_buy_span=5,
        blocked_buy_max_quantile=0.80,
        max_names_per_sector=3,
    )


def load_sector_labels_for_market_inputs(
    tickers: tuple[str, ...],
    *,
    sector_path: Path = SECTOR_PATH,
) -> tuple[str | None, ...]:
    sectors = pd.read_parquet(sector_path)[["symbol", "icb_name2"]].drop_duplicates("symbol")
    sector_map = dict(zip(sectors["symbol"], sectors["icb_name2"]))
    return tuple(sector_map.get(ticker) for ticker in tickers)


def align_series_to_market_dates(series: pd.Series, market_dates: np.ndarray, *, fill_value: float = 0.0) -> np.ndarray:
    aligned = (
        pd.DataFrame({"time": pd.to_datetime(series.index), "value": pd.to_numeric(series, errors="coerce")})
        .drop_duplicates("time")
        .set_index("time")
        .reindex(pd.to_datetime(market_dates))
    )
    return aligned["value"].fillna(float(fill_value)).to_numpy(dtype=np.float64)


def calibration_mask_before_year(meta_state: pd.DataFrame, year: int) -> pd.Series:
    times = pd.to_datetime(meta_state["time"])
    return times.dt.year < int(year)


def calibration_mask_year_range(meta_state: pd.DataFrame, start_year: int, end_year: int) -> pd.Series:
    times = pd.to_datetime(meta_state["time"])
    return (times.dt.year >= int(start_year)) & (times.dt.year <= int(end_year))


def _numeric_meta_series(meta_state: pd.DataFrame, column: str) -> pd.Series:
    return pd.Series(
        pd.to_numeric(meta_state[column], errors="coerce").to_numpy(dtype=np.float64),
        index=pd.to_datetime(meta_state["time"]),
        dtype=np.float64,
    )


def _quantile_threshold(series: pd.Series, quantile: float, calibration_mask: pd.Series | None = None) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    if calibration_mask is not None:
        mask = pd.Series(calibration_mask)
        if len(mask) == len(numeric):
            mask.index = numeric.index
        elif not mask.index.equals(numeric.index):
            mask = mask.reindex(numeric.index, fill_value=False)
        numeric = numeric.loc[mask.astype(bool)]
    numeric = numeric.replace([np.inf, -np.inf], np.nan).dropna()
    if numeric.empty:
        return float("nan")
    return float(numeric.quantile(float(quantile)))


def _hysteresis_gate(
    *,
    rel_on: pd.Series,
    blocked: pd.Series,
    on_threshold: float,
    off_threshold: float,
) -> pd.Series:
    rel_bool = rel_on.fillna(False).astype(bool).tolist()
    blocked_values = pd.to_numeric(blocked, errors="coerce").fillna(float("inf")).tolist()
    state = False
    out: list[bool] = []
    for rel_is_on, blocked_value in zip(rel_bool, blocked_values):
        if not state:
            state = bool(rel_is_on and blocked_value <= float(on_threshold))
        else:
            if (not rel_is_on) or blocked_value > float(off_threshold):
                state = False
        out.append(state)
    return pd.Series(out, index=rel_on.index, dtype=bool)


def build_champion_gate(
    setup: ChampionSetup,
    *,
    spec: ChampionVariantSpec,
    calibration_mask: pd.Series | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series | None, float | None, float | None]:
    rel_series = selector_recent_relative_ewm_from_prev(setup.meta_state, prefix="full", span=int(spec.rel_span))
    rel_series.index = pd.to_datetime(setup.meta_state["time"])
    rel_on = rel_series > float(spec.rel_threshold)

    blocked_series: pd.Series | None = None
    on_threshold: float | None = None
    off_threshold: float | None = None
    gate = rel_on.copy()

    if spec.blocked_buy_span is not None and spec.blocked_buy_max_quantile is not None:
        blocked_series = _numeric_meta_series(
            setup.meta_state,
            f"full_recent_blocked_buy_ewm{int(spec.blocked_buy_span)}",
        )
        on_threshold = _quantile_threshold(
            blocked_series,
            float(spec.blocked_buy_max_quantile),
            calibration_mask,
        )
        if spec.blocked_buy_off_quantile is not None:
            off_threshold = _quantile_threshold(
                blocked_series,
                float(spec.blocked_buy_off_quantile),
                calibration_mask,
            )
            gate = _hysteresis_gate(
                rel_on=rel_on,
                blocked=blocked_series,
                on_threshold=on_threshold,
                off_threshold=off_threshold,
            )
        else:
            gate = rel_on & (blocked_series <= float(on_threshold))

    return gate.astype(bool), rel_series.astype(float), blocked_series, on_threshold, off_threshold


def run_champion_variant(
    setup: ChampionSetup,
    *,
    spec: ChampionVariantSpec,
    calibration_mask: pd.Series | None = None,
    capture_blotter: bool = False,
) -> ChampionVariantRun:
    gate, rel_series, blocked_series, on_threshold, off_threshold = build_champion_gate(
        setup,
        spec=spec,
        calibration_mask=calibration_mask,
    )
    activation_scale = align_series_to_market_dates(
        gate.astype(float),
        setup.inputs.market_inputs.dates,
        fill_value=0.0,
    )
    kwargs = dict(setup.common_kwargs)
    kwargs["activation_scale"] = activation_scale
    kwargs["incumbent_score_bonus"] = float(spec.incumbent_score_bonus)
    kwargs["capture_blotter"] = bool(capture_blotter)
    sector_labels: tuple[str | None, ...] | None = None
    if spec.max_names_per_sector is not None:
        sector_labels = load_sector_labels_for_market_inputs(setup.inputs.market_inputs.tickers)
        kwargs["sector_labels"] = sector_labels
        kwargs["max_names_per_sector"] = int(spec.max_names_per_sector)
    result = simulate_strategy(**kwargs)
    return ChampionVariantRun(
        spec=spec,
        gate=gate,
        rel_series=rel_series,
        blocked_buy_series=blocked_series,
        blocked_buy_on_threshold=on_threshold,
        blocked_buy_off_threshold=off_threshold,
        sector_labels=sector_labels,
        result=result,
    )


def slice_execution_year(daily: pd.DataFrame, year: int) -> pd.DataFrame:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    return work.loc[work["execution_date"].dt.year == int(year)].reset_index(drop=True)


def latest_execution_window(daily: pd.DataFrame, execution_days: int) -> pd.DataFrame:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    keep_dates = set(sorted(work["execution_date"].drop_duplicates())[-max(int(execution_days), 1):])
    return work.loc[work["execution_date"].isin(keep_dates)].reset_index(drop=True)
