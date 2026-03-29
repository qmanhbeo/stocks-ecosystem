from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

import numpy as np
import pandas as pd

from src.deterministic_portfolio import (
    RESERVED_COLUMNS,
    build_market_inputs,
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    simulate_strategy,
)
from src.portfolio_friction_features import build_friction_feature_frame
from src.research_protocol import DEFAULT_PROTOCOL, PHASE_ORDER, ResearchProtocol, phase_mask
from src.standalone_signal_utils import spearman_stat, summarize_ic, yearly_ic


SECTOR_ROTATION_PATH = Path("data/features/xs_sector_rotation_daily.parquet")
PRICE_LIMIT_PATH = Path("data/features/xs_price_limit_daily.parquet")
DISPERSION_PATH = Path("data/features/xs_dispersion_regime_daily.parquet")


TRADABLE_STATE_BUILDERS: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "buyable": lambda frame: frame["can_buy_next_open"].fillna(False).astype(bool),
    "liq_open_basic": lambda frame: (
        (pd.to_numeric(frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(frame["clv"], errors="coerce") >= 0.45)
        & frame["can_buy_next_open"].fillna(False).astype(bool)
    ),
    "liq_open_strict": lambda frame: (
        (pd.to_numeric(frame["tv_to_adv20"], errors="coerce") >= 1.25)
        & (pd.to_numeric(frame["clv"], errors="coerce") >= 0.50)
        & frame["can_buy_next_open"].fillna(False).astype(bool)
    ),
}


@dataclass(frozen=True)
class ResearchBundle:
    matrix: pd.DataFrame
    price_panel: pd.DataFrame
    tradability: pd.DataFrame
    tradability_source: str
    benchmark_open: pd.Series
    feature_frame: pd.DataFrame


def _pct_rank_by_time(frame: pd.DataFrame, column: str, *, ascending: bool = True, fill_value: float = 0.5) -> pd.Series:
    ranked = pd.to_numeric(frame[column], errors="coerce").groupby(frame["time"], sort=False).rank(
        method="average",
        pct=True,
        ascending=ascending,
    )
    return ranked.fillna(float(fill_value)).astype(float)


def _safe_total_return(returns: np.ndarray) -> float | None:
    if returns.size == 0:
        return None
    gross = np.prod(1.0 + np.nan_to_num(returns, nan=0.0))
    return float(gross - 1.0)


def _safe_ratio(returns: np.ndarray) -> float | None:
    clean = np.asarray(returns, dtype=np.float64)
    clean = clean[np.isfinite(clean)]
    if clean.size < 2:
        return None
    std = float(clean.std(ddof=0))
    if std <= 0.0:
        return None
    return float(clean.mean() / std * np.sqrt(252.0))


def _safe_max_drawdown(values: np.ndarray) -> float | None:
    clean = np.asarray(values, dtype=np.float64)
    clean = clean[np.isfinite(clean)]
    if clean.size == 0:
        return None
    running_peak = np.maximum.accumulate(clean)
    drawdown = clean / np.clip(running_peak, 1e-12, None) - 1.0
    return float(drawdown.min())


def load_research_bundle(
    *,
    matrix_path: Path,
    tradability_path: Path,
    stock_dir: Path,
    benchmark_path: Path,
    start_year: int,
    end_year: int,
) -> ResearchBundle:
    matrix = pd.read_parquet(matrix_path)
    matrix["time"] = pd.to_datetime(matrix["time"])
    matrix = matrix[(matrix["time"].dt.year >= int(start_year)) & (matrix["time"].dt.year <= int(end_year))].copy()
    if matrix.empty:
        raise ValueError(f"No matrix rows in year range {start_year}-{end_year}")

    price_panel = load_price_panel(matrix["ticker"].drop_duplicates().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")

    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)
    benchmark_open = load_benchmark_open(benchmark_path)
    feature_frame = build_friction_feature_frame(matrix[["time", "ticker", "actual"]].copy(), price_panel, tradability)
    return ResearchBundle(
        matrix=matrix,
        price_panel=price_panel,
        tradability=tradability,
        tradability_source=tradability_source,
        benchmark_open=benchmark_open,
        feature_frame=feature_frame,
    )


def build_state_masks(feature_frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        name: builder(feature_frame).fillna(False).astype(bool)
        for name, builder in TRADABLE_STATE_BUILDERS.items()
    }


def compute_phase_portfolio_summary(
    daily: pd.DataFrame,
    *,
    protocol: ResearchProtocol = DEFAULT_PROTOCOL,
) -> dict[str, dict[str, object]]:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    out: dict[str, dict[str, object]] = {}
    for phase in PHASE_ORDER:
        mask = phase_mask(work, phase, date_column="execution_date", protocol=protocol)
        phase_daily = work.loc[mask].copy()
        if phase_daily.empty:
            out[phase] = {
                "days": 0,
                "portfolio_total_return": None,
                "benchmark_total_return": None,
                "relative_total_return": None,
                "information_ratio_annualized": None,
                "max_drawdown": None,
                "avg_cash_weight": None,
                "avg_daily_turnover": None,
            }
            continue
        portfolio_return = pd.to_numeric(phase_daily["portfolio_return"], errors="coerce").to_numpy(dtype=np.float64)
        benchmark_return = pd.to_numeric(phase_daily["benchmark_return"], errors="coerce").to_numpy(dtype=np.float64)
        relative_return = pd.to_numeric(phase_daily["relative_return"], errors="coerce").to_numpy(dtype=np.float64)
        portfolio_value = pd.to_numeric(phase_daily["portfolio_value_vnd"], errors="coerce").to_numpy(dtype=np.float64)
        out[phase] = {
            "days": int(len(phase_daily)),
            "portfolio_total_return": _safe_total_return(portfolio_return),
            "benchmark_total_return": _safe_total_return(benchmark_return),
            "relative_total_return": _safe_total_return(
                ((1.0 + portfolio_return) / np.clip(1.0 + benchmark_return, 1e-12, None)) - 1.0
            ),
            "information_ratio_annualized": _safe_ratio(relative_return),
            "max_drawdown": _safe_max_drawdown(portfolio_value),
            "avg_cash_weight": float(pd.to_numeric(phase_daily["cash_weight"], errors="coerce").mean()),
            "avg_daily_turnover": float(pd.to_numeric(phase_daily["turnover"], errors="coerce").mean()),
        }
    return out


def evaluate_signal_ic_by_phase(
    frame: pd.DataFrame,
    *,
    signal_column: str,
    state_mask: pd.Series,
    protocol: ResearchProtocol = DEFAULT_PROTOCOL,
    s1_column: str = "s1_proba",
) -> dict[str, dict[str, object]]:
    scoped = frame.loc[state_mask].copy()
    out: dict[str, dict[str, object]] = {}
    for phase in ("dev", "validation", "confirmation"):
        phase_frame = scoped.loc[phase_mask(scoped, phase, protocol=protocol)].copy()
        ic_rows = yearly_ic(phase_frame, signal_column, "actual")
        ic_summary = summarize_ic(ic_rows)
        corr = spearman_stat(phase_frame[signal_column], phase_frame[s1_column])
        out[phase] = {
            **ic_summary,
            "corr_with_s1": corr,
            "rows": int(len(phase_frame)),
            "dates": int(phase_frame["time"].nunique()) if not phase_frame.empty else 0,
        }
    return out


def compute_strategy_map_from_columns(
    matrix_columns: list[str],
    strategies: Mapping[str, tuple[str, ...] | list[str]],
) -> dict[str, list[str]]:
    available = set(matrix_columns) - RESERVED_COLUMNS
    strategy_map: dict[str, list[str]] = {}
    for name, columns in strategies.items():
        cols = [str(column) for column in columns]
        missing = sorted(set(cols) - available)
        if missing:
            raise ValueError(f"Strategy {name!r} requires missing columns: {missing}")
        strategy_map[name] = cols
    return strategy_map


def build_candidate_signal_frame(
    bundle: ResearchBundle,
    *,
    start_year: int = 2015,
    end_year: int = 2025,
) -> pd.DataFrame:
    base_matrix_cols = ["time", "ticker", "actual", "s1_proba"]
    optional_matrix_cols = [
        "c7_ceiling_count_5d",
        "c8_vol_zscore_5d",
        "c12_gap_absorb_3",
        "c13_compress_blowoff_2",
    ]
    carry_cols = [column for column in optional_matrix_cols if column in bundle.matrix.columns]
    frame = bundle.matrix[base_matrix_cols + carry_cols].copy()
    frame = frame.merge(
        bundle.feature_frame[
            [
                "time",
                "ticker",
                "clv",
                "tv_to_adv20",
                "xs_tv_to_adv20_rank",
                "xs_clv_rank",
                "xs_adv20_rank",
                "can_buy_next_open",
            ]
        ],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    price = bundle.price_panel[
        ["time", "ticker", "open", "close", "adv20_value", "traded_value_vnd"]
    ].copy()
    price = price.sort_values(["ticker", "time"]).reset_index(drop=True)
    price["prev_close"] = price.groupby("ticker", sort=False)["close"].shift(1)
    price["ret_1d"] = price.groupby("ticker", sort=False)["close"].pct_change(1, fill_method=None)
    price["ret_3d"] = price.groupby("ticker", sort=False)["close"].pct_change(3, fill_method=None)
    price["ret_5d"] = price.groupby("ticker", sort=False)["close"].pct_change(5, fill_method=None)
    prev20_high = price.groupby("ticker", sort=False)["close"].transform(
        lambda series: series.shift(1).rolling(20, min_periods=5).max()
    )
    price["breakout_20d"] = price["close"] / prev20_high - 1.0
    price["gap_to_prev_close"] = price["open"] / price["prev_close"] - 1.0
    frame = frame.merge(
        price[["time", "ticker", "ret_1d", "ret_3d", "ret_5d", "breakout_20d", "gap_to_prev_close"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    sector_rotation = pd.read_parquet(SECTOR_ROTATION_PATH)
    sector_rotation["time"] = pd.to_datetime(sector_rotation["time"])
    frame = frame.merge(
        sector_rotation[
            [
                "time",
                "ticker",
                "xs_intra_sector_rank",
                "xs_sector_rotation_signal",
                "xs_sector_mom_5d_rank",
                "xs_sector_mom_20d_rank",
                "xs_sector_accel",
                "xs_sector_breadth_5d",
            ]
        ],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    price_limit = pd.read_parquet(PRICE_LIMIT_PATH)
    price_limit["time"] = pd.to_datetime(price_limit["time"])
    frame = frame.merge(
        price_limit[
            [
                "time",
                "ticker",
                "xs_ceiling_count_5d",
                "xs_ceiling_count_20d",
                "xs_floor_count_5d",
                "xs_floor_count_20d",
                "xs_limit_net_5d",
            ]
        ],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    if DISPERSION_PATH.exists():
        dispersion = pd.read_parquet(DISPERSION_PATH)
        dispersion["time"] = pd.to_datetime(dispersion["time"])
        frame = frame.merge(
            dispersion[["time", "xs_breadth_up_5d", "xs_breadth_up_20d", "xs_dispersion_z20"]],
            on=["time"],
            how="left",
            validate="many_to_one",
        )

    frame = frame.sort_values(["ticker", "time"]).reset_index(drop=True)
    frame["prev_can_buy_next_open"] = (
        frame.groupby("ticker", sort=False)["can_buy_next_open"].shift(1).astype("boolean").fillna(False).astype(bool)
    )
    frame["release_flag"] = (
        frame["can_buy_next_open"].fillna(False).astype(bool)
        & ~frame["prev_can_buy_next_open"].fillna(False).astype(bool)
    ).astype(float)
    frame["buyable_score"] = frame["can_buy_next_open"].fillna(False).astype(float)

    frame["xs_ret_1d_rank"] = _pct_rank_by_time(frame, "ret_1d")
    frame["xs_ret_3d_rank"] = _pct_rank_by_time(frame, "ret_3d")
    frame["xs_gap_down_rank"] = _pct_rank_by_time(frame.assign(_gap_down=-pd.to_numeric(frame["gap_to_prev_close"], errors="coerce")), "_gap_down")
    frame["xs_breakout_20d_rank"] = _pct_rank_by_time(frame, "breakout_20d")
    frame["xs_ceiling_count_20d_rank"] = _pct_rank_by_time(frame, "xs_ceiling_count_20d")
    frame["xs_floor_count_5d_rank"] = _pct_rank_by_time(frame, "xs_floor_count_5d")
    frame["xs_floor_count_20d_rank"] = _pct_rank_by_time(frame, "xs_floor_count_20d")
    frame["xs_limit_net_5d_rank"] = _pct_rank_by_time(frame, "xs_limit_net_5d")
    frame["xs_sector_accel_rank"] = _pct_rank_by_time(frame, "xs_sector_accel")
    frame["xs_c13_rank"] = _pct_rank_by_time(frame, "c13_compress_blowoff_2") if "c13_compress_blowoff_2" in frame.columns else 0.5
    frame["xs_c12_rank"] = _pct_rank_by_time(frame, "c12_gap_absorb_3") if "c12_gap_absorb_3" in frame.columns else 0.5
    frame["xs_c8_rank"] = _pct_rank_by_time(frame, "c8_vol_zscore_5d") if "c8_vol_zscore_5d" in frame.columns else 0.5
    frame["xs_c7_rank"] = _pct_rank_by_time(frame, "c7_ceiling_count_5d") if "c7_ceiling_count_5d" in frame.columns else 0.5
    frame["xs_recent_weakness_rank"] = _pct_rank_by_time(
        frame.assign(_recent_weakness=-pd.to_numeric(frame["ret_1d"], errors="coerce")),
        "_recent_weakness",
    )

    frame["h152_liq_open_continue_3"] = (
        frame["xs_ret_3d_rank"]
        + frame["xs_tv_to_adv20_rank"]
        + frame["xs_clv_rank"]
        + frame["buyable_score"]
    ) / 4.0
    frame["h152_limit_release_pressure"] = (
        pd.to_numeric(frame["xs_ceiling_count_5d"], errors="coerce").fillna(0.5)
        + frame["release_flag"]
        + frame["xs_clv_rank"]
        + frame["xs_tv_to_adv20_rank"]
    ) / 4.0
    frame["h152_sector_laggard_tradable"] = (
        (1.0 - pd.to_numeric(frame["xs_intra_sector_rank"], errors="coerce").fillna(0.5))
        + pd.to_numeric(frame["xs_sector_rotation_signal"], errors="coerce").fillna(0.5)
        + frame["xs_tv_to_adv20_rank"]
        + frame["buyable_score"]
    ) / 4.0
    frame["h152_gap_quality_entry"] = (
        frame["xs_gap_down_rank"]
        + frame["xs_clv_rank"]
        + frame["xs_tv_to_adv20_rank"]
        + frame["buyable_score"]
    ) / 4.0
    frame["h152_breakout_volume_quality"] = (
        frame["xs_breakout_20d_rank"]
        + frame["xs_tv_to_adv20_rank"]
        + frame["xs_adv20_rank"]
        + frame["buyable_score"]
    ) / 4.0

    frame["h199_floor_release_rebound"] = (
        frame["xs_floor_count_5d_rank"]
        + frame["release_flag"]
        + frame["xs_gap_down_rank"]
        + frame["xs_clv_rank"]
    ) / 4.0
    frame["h199_ceiling_release_followthrough"] = (
        frame["xs_ceiling_count_20d_rank"]
        + frame["release_flag"]
        + frame["xs_breakout_20d_rank"]
        + frame["xs_clv_rank"]
    ) / 4.0
    frame["h199_sector_laggard_gap_absorb"] = (
        (1.0 - pd.to_numeric(frame["xs_intra_sector_rank"], errors="coerce").fillna(0.5))
        + pd.to_numeric(frame["xs_sector_mom_20d_rank"], errors="coerce").fillna(0.5)
        + frame["xs_c12_rank"]
        + frame["xs_gap_down_rank"]
    ) / 4.0
    frame["h199_breakout_after_compression"] = (
        frame["xs_breakout_20d_rank"]
        + frame["xs_c13_rank"]
        + frame["xs_c8_rank"]
        + frame["buyable_score"]
    ) / 4.0
    frame["h199_buyable_reversal_after_1d_weakness"] = (
        frame["xs_recent_weakness_rank"]
        + frame["xs_clv_rank"]
        + frame["xs_tv_to_adv20_rank"]
        + frame["buyable_score"]
    ) / 4.0

    frame["h204_sector_accel_release"] = (
        frame["xs_sector_accel_rank"]
        + frame["release_flag"]
        + frame["xs_tv_to_adv20_rank"]
        + frame["xs_clv_rank"]
    ) / 4.0
    frame["h204_ceiling_memory_gap_absorb"] = (
        frame["xs_ceiling_count_20d_rank"]
        + frame["xs_c12_rank"]
        + frame["xs_gap_down_rank"]
        + frame["buyable_score"]
    ) / 4.0
    frame["h204_breakout_sector_accel_buyable"] = (
        frame["xs_breakout_20d_rank"]
        + frame["xs_sector_accel_rank"]
        + frame["xs_adv20_rank"]
        + frame["buyable_score"]
    ) / 4.0
    frame["h204_sector_mom_laggard_volume"] = (
        (1.0 - pd.to_numeric(frame["xs_intra_sector_rank"], errors="coerce").fillna(0.5))
        + pd.to_numeric(frame["xs_sector_mom_20d_rank"], errors="coerce").fillna(0.5)
        + frame["xs_c8_rank"]
        + frame["xs_tv_to_adv20_rank"]
    ) / 4.0
    frame["h204_release_after_floor_pressure"] = (
        frame["xs_floor_count_20d_rank"]
        + frame["release_flag"]
        + frame["xs_clv_rank"]
        + frame["xs_c12_rank"]
    ) / 4.0

    frame = frame[(frame["time"].dt.year >= int(start_year)) & (frame["time"].dt.year <= int(end_year))].copy()
    return frame


def run_selector_candidate(
    *,
    scored_frame: pd.DataFrame,
    bundle: ResearchBundle,
    strategy_name: str,
    signal_columns: list[str],
    start_year: int,
    end_year: int,
    initial_notional_vnd: float,
    buy_fee_rate: float,
    sell_fee_rate: float,
    required_holding_age: int,
) -> object:
    market_inputs = build_market_inputs(
        scored_frame,
        bundle.price_panel,
        bundle.tradability,
        bundle.benchmark_open,
        tradability_source=bundle.tradability_source,
        strategy_names=[strategy_name],
        start_year=int(start_year),
        end_year=int(end_year),
    )
    return simulate_strategy(
        strategy_name=strategy_name,
        signal_columns=signal_columns,
        market_inputs=market_inputs,
        top_k=5,
        rebalance_every=5,
        weighting="equal",
        initial_notional_vnd=float(initial_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(required_holding_age),
        buy_fee_rate=float(buy_fee_rate),
        sell_fee_rate=float(sell_fee_rate),
        capital_gains_tax_rate=0.0,
    )
