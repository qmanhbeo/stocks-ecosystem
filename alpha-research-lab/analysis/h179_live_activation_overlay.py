"""
H179: Execution-facing live/paper activation overlay for the active live branch.

Purpose:
- turn the fixed H175 activation rule into a paper-trade blotter
- report both the latest completed execution and the next-open recommendation
- state clearly whether the signal matrix is current enough for a true live recommendation
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_meta import ACTIVATION_META_PATH
from src.activation_meta_experiment_utils import (
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
)
from src.champion_activation_utils import (
    ChampionVariantSpec,
    current_live_variant,
    load_champion_setup,
    project_champion_variant_to_next_open,
    run_champion_variant,
)
from src.champion_branch_experiment_utils import (
    jsonable,
    latest_execution_window,
    summarize_latest_recommendation,
)
from src.run_summary import write_run_summary

OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    default_spec = current_live_variant()
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
    parser.add_argument("--incumbent-score-bonus", type=float, default=float(default_spec.incumbent_score_bonus))
    parser.add_argument(
        "--blocked-buy-ewm3-max-quantile",
        type=float,
        default=None if default_spec.blocked_buy_span != 3 else float(default_spec.blocked_buy_max_quantile),
    )
    parser.add_argument(
        "--blocked-buy-ewm5-max-quantile",
        type=float,
        default=None if default_spec.blocked_buy_span != 5 else float(default_spec.blocked_buy_max_quantile),
    )
    parser.add_argument("--max-names-per-sector", type=int, default=default_spec.max_names_per_sector)
    parser.add_argument("--disable-blocked-buy-veto", action="store_true")
    parser.add_argument("--disable-sector-cap", action="store_true")
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


def main() -> None:
    args = parse_args()
    matrix_path = Path(args.matrix)
    stock_dir = Path(args.stock_dir)
    latest_matrix_year = _latest_matrix_year(matrix_path)
    end_year = min(int(args.end_year), latest_matrix_year)
    setup = load_champion_setup(
        start_year=int(args.start_year),
        end_year=int(end_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        matrix_path=matrix_path,
        tradability_path=Path(args.tradability),
        stock_dir=stock_dir,
        benchmark_path=Path(args.benchmark),
        activation_state_path=Path(args.activation_state),
        activation_meta_path=Path(args.activation_meta),
    )
    blocked_quantile = None
    blocked_span = None
    if not args.disable_blocked_buy_veto:
        blocked_quantile = (
            args.blocked_buy_ewm3_max_quantile
            if args.blocked_buy_ewm3_max_quantile is not None
            else args.blocked_buy_ewm5_max_quantile
        )
        if blocked_quantile is not None:
            blocked_span = 3 if args.blocked_buy_ewm3_max_quantile is not None else 5
    spec = ChampionVariantSpec(
        name="custom_live_overlay",
        incumbent_score_bonus=float(args.incumbent_score_bonus),
        blocked_buy_span=blocked_span,
        blocked_buy_max_quantile=blocked_quantile,
        max_names_per_sector=None if args.disable_sector_cap else args.max_names_per_sector,
    )
    run = run_champion_variant(setup, spec=spec, capture_blotter=True)
    result = run.result
    if result.blotter is None:
        raise ValueError("Expected capture_blotter=True to return blotter rows")
    projected_run = project_champion_variant_to_next_open(setup, spec=spec, capture_blotter=True)
    if projected_run.result.blotter is None:
        raise ValueError("Expected projected next-open run to return blotter rows")

    daily = result.daily.copy()
    daily["signal_date"] = pd.to_datetime(daily["signal_date"])
    daily["execution_date"] = pd.to_datetime(daily["execution_date"])
    rel_lookup = run.rel_series.reindex(pd.to_datetime(daily["signal_date"]))
    daily["recent_rel2"] = rel_lookup.to_numpy(dtype=float)
    if run.blocked_buy_series is not None:
        blocked_lookup = run.blocked_buy_series.reindex(pd.to_datetime(daily["signal_date"]))
        daily[f"blocked_buy_ewm{int(spec.blocked_buy_span)}"] = blocked_lookup.to_numpy(dtype=float)

    latest_execution_days = max(int(args.latest_execution_days), 1)
    daily_window = latest_execution_window(daily, execution_days=latest_execution_days)
    keep_dates = set(pd.to_datetime(daily_window["execution_date"]).drop_duplicates())
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
    next_daily_path = OUT_DIR / f"{ts}_h179_live_activation_overlay_next_open_daily.parquet"
    next_detail_path = OUT_DIR / f"{ts}_h179_live_activation_overlay_next_open_detail.parquet"
    daily_window.to_parquet(daily_path, index=False)
    blotter_window.to_parquet(detail_path, index=False)
    projected_daily = projected_run.result.daily.copy()
    projected_daily["signal_date"] = pd.to_datetime(projected_daily["signal_date"])
    projected_daily["execution_date"] = pd.to_datetime(projected_daily["execution_date"])
    projected_latest = projected_daily.sort_values("execution_date").tail(1).copy()
    projected_latest.to_parquet(next_daily_path, index=False)
    projected_detail = projected_run.result.blotter.copy()
    projected_detail["execution_date"] = pd.to_datetime(projected_detail["execution_date"])
    if not projected_latest.empty:
        projected_exec_date = pd.Timestamp(projected_latest.iloc[0]["execution_date"])
        projected_detail = projected_detail.loc[
            projected_detail["execution_date"] == projected_exec_date
        ].copy().reset_index(drop=True)
    projected_detail.to_parquet(next_detail_path, index=False)

    latest_row = (
        jsonable(daily_window.sort_values("execution_date").tail(1).iloc[0].to_dict())
        if not daily_window.empty
        else {}
    )
    latest_stock_date = _latest_stock_date(stock_dir)
    matrix_max_time = pd.to_datetime(setup.inputs.matrix["time"]).max()
    stale_signal_matrix = bool(latest_stock_date is not None and pd.Timestamp(matrix_max_time) < pd.Timestamp(latest_stock_date))
    veto_desc = "none"
    if spec.blocked_buy_span is not None and spec.blocked_buy_max_quantile is not None:
        veto_desc = f"blocked{int(spec.blocked_buy_span)}<=q{int(round(float(spec.blocked_buy_max_quantile) * 100.0))}"

    summary = {
        "meta_source": setup.meta_source,
        "activation_rule": "h175__rel2_gt0",
        "incumbent_score_bonus": float(args.incumbent_score_bonus),
        "implementation_veto": veto_desc,
        "blocked_buy_on_threshold": run.blocked_buy_on_threshold,
        "blocked_buy_off_threshold": run.blocked_buy_off_threshold,
        "max_names_per_sector": spec.max_names_per_sector,
        "selector": setup.selector_name,
        "signal_matrix_end": str(pd.Timestamp(matrix_max_time).date()),
        "latest_stock_date": str(pd.Timestamp(latest_stock_date).date()) if latest_stock_date is not None else None,
        "stale_signal_matrix": stale_signal_matrix,
        "latest_day": latest_row,
        "latest_completed_day": latest_row,
        "next_open_recommendation": summarize_latest_recommendation(
            projected_run.result.daily,
            projected_run.result.blotter,
        ),
        "portfolio_summary": jsonable(result.summary),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_live_activation_overlay",
        name="h179_live_activation_overlay",
        summary=summary,
        artifacts={
            "daily": str(daily_path),
            "detail": str(detail_path),
            "next_daily": str(next_daily_path),
            "next_detail": str(next_detail_path),
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
            "max_names_per_sector": spec.max_names_per_sector,
            "disable_blocked_buy_veto": bool(args.disable_blocked_buy_veto),
            "disable_sector_cap": bool(args.disable_sector_cap),
        },
    )

    print("\nH179: LIVE ACTIVATION OVERLAY")
    print("Latest completed execution:")
    print(pd.DataFrame([summary["latest_completed_day"]]).to_string(index=False) if latest_row else "No latest row")
    next_rec = summary["next_open_recommendation"]
    if next_rec:
        print("\nNext-open recommendation:")
        print(pd.DataFrame([next_rec]).to_string(index=False))
    if stale_signal_matrix:
        print(
            f"\nNOTE: signal matrix ends at {pd.Timestamp(matrix_max_time).date()} while stock data extends to {pd.Timestamp(latest_stock_date).date()}."
        )


if __name__ == "__main__":
    main()
