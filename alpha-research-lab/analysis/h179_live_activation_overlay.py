"""
H179: Execution-facing live/paper activation overlay for the current champion.

Purpose:
- turn the fixed H175 activation rule into a paper-trade blotter
- report the latest matrix-supported activation decision and held book
- state clearly whether the signal matrix is current enough for a true live recommendation
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
from src.run_summary import write_run_summary

OUT_DIR = Path("artifacts/portfolio_baselines")
SECTOR_PATH = Path("data/features/sector_classification.parquet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--activation-state", type=str, default=str(ACTIVATION_STATE_PATH))
    parser.add_argument("--activation-meta", type=str, default=str(ACTIVATION_META_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--latest-execution-days", type=int, default=20)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.0)
    parser.add_argument("--blocked-buy-ewm3-max-quantile", type=float, default=None)
    parser.add_argument("--blocked-buy-ewm5-max-quantile", type=float, default=None)
    parser.add_argument("--max-names-per-sector", type=int, default=None)
    return parser.parse_args()


def _latest_matrix_year(matrix_path: Path) -> int:
    frame = pd.read_parquet(matrix_path, columns=["time"])
    frame["time"] = pd.to_datetime(frame["time"])
    return int(frame["time"].dt.year.max())


def _latest_stock_date(stock_dir: Path) -> pd.Timestamp | None:
    benchmark_path = stock_dir / "gia_lich_su_VNINDEX_1D.parquet"
    if not benchmark_path.exists():
        return None
    frame = pd.read_parquet(benchmark_path, columns=["time"])
    frame["time"] = pd.to_datetime(frame["time"])
    return pd.Timestamp(frame["time"].max()) if not frame.empty else None


def _jsonable(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _sector_labels_for_market_inputs(tickers: tuple[str, ...]) -> tuple[str | None, ...]:
    sectors = pd.read_parquet(SECTOR_PATH)[["symbol", "icb_name2"]].drop_duplicates("symbol")
    sector_map = dict(zip(sectors["symbol"], sectors["icb_name2"]))
    return tuple(sector_map.get(ticker) for ticker in tickers)


def main() -> None:
    args = parse_args()
    matrix_path = Path(args.matrix)
    stock_dir = Path(args.stock_dir)
    latest_matrix_year = _latest_matrix_year(matrix_path)
    end_year = min(int(args.end_year), latest_matrix_year)

    inputs = load_activation_experiment_inputs(
        matrix_path=matrix_path,
        tradability_path=Path(args.tradability),
        stock_dir=stock_dir,
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(end_year),
    )
    meta_state, meta_source = load_or_build_activation_meta(
        out_path=Path(args.activation_meta),
        matrix_path=matrix_path,
        tradability_path=Path(args.tradability),
        stock_dir=stock_dir,
        benchmark_path=Path(args.benchmark),
        activation_state_path=Path(args.activation_state),
        start_year=int(args.start_year),
        end_year=int(end_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    selector = next(selector for selector in inputs.selectors if selector.name == "full_library_k5_r5_eq")
    rel2 = selector_recent_relative_ewm_from_prev(meta_state, prefix="full", span=2)
    rel2.index = pd.to_datetime(meta_state["time"])
    gate = rel2 > 0.0
    veto_desc = "none"
    if args.blocked_buy_ewm3_max_quantile is not None:
        blocked3 = pd.Series(
            pd.to_numeric(meta_state["full_recent_blocked_buy_ewm3"], errors="coerce").to_numpy(),
            index=pd.to_datetime(meta_state["time"]),
        )
        threshold = float(blocked3.quantile(float(args.blocked_buy_ewm3_max_quantile)))
        gate = gate & (blocked3 <= threshold)
        veto_desc = f"blocked3<=q{int(round(float(args.blocked_buy_ewm3_max_quantile) * 100.0))}"
    if args.blocked_buy_ewm5_max_quantile is not None:
        blocked5 = pd.Series(
            pd.to_numeric(meta_state["full_recent_blocked_buy_ewm5"], errors="coerce").to_numpy(),
            index=pd.to_datetime(meta_state["time"]),
        )
        threshold = float(blocked5.quantile(float(args.blocked_buy_ewm5_max_quantile)))
        gate = gate & (blocked5 <= threshold)
        veto_desc = f"blocked5<=q{int(round(float(args.blocked_buy_ewm5_max_quantile) * 100.0))}"
    aligned = (
        pd.DataFrame({"time": pd.to_datetime(meta_state["time"]), "activation_scale": gate.astype(float), "recent_rel2": rel2})
        .drop_duplicates("time")
        .set_index("time")
        .reindex(pd.to_datetime(inputs.market_inputs.dates))
    )
    activation_scale = aligned["activation_scale"].fillna(0.0).to_numpy(dtype=np.float64)
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    fee_leg = float(args.round_trip_cost) / 2.0

    result = simulate_strategy(
        strategy_name=selector.strategy_name,
        signal_columns=list(selector.signal_columns),
        market_inputs=inputs.market_inputs,
        top_k=int(selector.top_k),
        rebalance_every=int(selector.rebalance_every),
        weighting=str(selector.weighting),
        initial_notional_vnd=float(args.initial_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(hold_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=0.0,
        activation_scale=activation_scale,
        capture_blotter=True,
        incumbent_score_bonus=float(args.incumbent_score_bonus),
        sector_labels=_sector_labels_for_market_inputs(inputs.market_inputs.tickers) if args.max_names_per_sector else None,
        max_names_per_sector=args.max_names_per_sector,
    )
    if result.blotter is None:
        raise ValueError("Expected capture_blotter=True to return blotter rows")

    daily = result.daily.copy()
    daily["signal_date"] = pd.to_datetime(daily["signal_date"])
    daily["execution_date"] = pd.to_datetime(daily["execution_date"])
    daily = daily.merge(
        aligned.reset_index().rename(columns={"index": "time"}),
        left_on="signal_date",
        right_on="time",
        how="left",
    ).drop(columns=["time"])

    latest_execution_days = max(int(args.latest_execution_days), 1)
    keep_dates = set(sorted(daily["execution_date"].drop_duplicates())[-latest_execution_days:])
    daily_window = daily.loc[daily["execution_date"].isin(keep_dates)].copy().reset_index(drop=True)
    if result.blotter.empty or "execution_date" not in result.blotter.columns:
        blotter_window = result.blotter.copy()
    else:
        blotter_window = result.blotter.loc[
            pd.to_datetime(result.blotter["execution_date"]).isin(keep_dates)
        ].copy().reset_index(drop=True)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = OUT_DIR / f"{ts}_h179_live_activation_overlay_daily.parquet"
    detail_path = OUT_DIR / f"{ts}_h179_live_activation_overlay_detail.parquet"
    daily_window.to_parquet(daily_path, index=False)
    blotter_window.to_parquet(detail_path, index=False)

    latest_row = (
        _jsonable(daily_window.sort_values("execution_date").tail(1).iloc[0].to_dict())
        if not daily_window.empty
        else {}
    )
    latest_stock_date = _latest_stock_date(stock_dir)
    matrix_max_time = pd.to_datetime(inputs.matrix["time"]).max()
    stale_signal_matrix = bool(latest_stock_date is not None and pd.Timestamp(matrix_max_time) < pd.Timestamp(latest_stock_date))

    summary = {
        "meta_source": meta_source,
        "activation_rule": "h175__rel2_gt0",
        "incumbent_score_bonus": float(args.incumbent_score_bonus),
        "implementation_veto": veto_desc,
        "max_names_per_sector": args.max_names_per_sector,
        "selector": selector.name,
        "signal_matrix_end": str(pd.Timestamp(matrix_max_time).date()),
        "latest_stock_date": str(pd.Timestamp(latest_stock_date).date()) if latest_stock_date is not None else None,
        "stale_signal_matrix": stale_signal_matrix,
        "latest_day": latest_row,
        "portfolio_summary": _jsonable(result.summary),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_live_activation_overlay",
        name="h179_live_activation_overlay",
        summary=summary,
        artifacts={
            "daily": str(daily_path),
            "detail": str(detail_path),
        },
        metadata={
            "matrix": str(args.matrix),
            "activation_meta": str(args.activation_meta),
            "benchmark": str(args.benchmark),
            "start_year": int(args.start_year),
            "end_year": int(end_year),
            "latest_execution_days": int(latest_execution_days),
            "blocked_buy_ewm3_max_quantile": args.blocked_buy_ewm3_max_quantile,
            "blocked_buy_ewm5_max_quantile": args.blocked_buy_ewm5_max_quantile,
            "max_names_per_sector": args.max_names_per_sector,
        },
    )

    print("\nH179: LIVE ACTIVATION OVERLAY")
    print(pd.DataFrame([summary["latest_day"]]).to_string(index=False) if latest_row else "No latest row")
    if stale_signal_matrix:
        print(
            f"\nNOTE: signal matrix ends at {pd.Timestamp(matrix_max_time).date()} while stock data extends to {pd.Timestamp(latest_stock_date).date()}."
        )


if __name__ == "__main__":
    main()
