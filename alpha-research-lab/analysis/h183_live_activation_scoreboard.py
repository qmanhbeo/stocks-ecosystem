"""
H183: Activated-vs-always-on live scoreboard for the current-year paper book.

Compares the current champion selector:
    full_library + k5_r5_eq

against the active live activation overlay:
    h175__rel2_gt0 + sticky_bonus_0p015

using the matrix-supported current-year slice.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
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
    load_sector_labels_for_market_inputs,
    run_champion_variant,
)
from src.champion_branch_experiment_utils import jsonable, slice_execution_year, summarize_daily_slice
from src.deterministic_portfolio import simulate_strategy
from src.run_summary import write_run_summary

OUT_DIR = Path("artifacts/portfolio_baselines")


def parse_args() -> argparse.Namespace:
    default_spec = current_live_variant()
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--activation-state", type=str, default=str(ACTIVATION_STATE_PATH))
    parser.add_argument("--activation-meta", type=str, default=str(ACTIVATION_META_PATH))
    parser.add_argument("--history-start-year", type=int, default=2019)
    parser.add_argument("--evaluation-year", type=int, default=2026)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
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


def main() -> None:
    args = parse_args()
    setup = load_champion_setup(
        start_year=int(args.history_start_year),
        end_year=int(args.evaluation_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
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
        name="custom_live_scoreboard",
        incumbent_score_bonus=float(args.incumbent_score_bonus),
        blocked_buy_span=blocked_span,
        blocked_buy_max_quantile=blocked_quantile,
        max_names_per_sector=None if args.disable_sector_cap else args.max_names_per_sector,
    )
    activated = run_champion_variant(setup, spec=spec)

    always_kwargs = dict(setup.common_kwargs)
    always_kwargs["incumbent_score_bonus"] = float(args.incumbent_score_bonus)
    if spec.max_names_per_sector:
        always_kwargs["sector_labels"] = load_sector_labels_for_market_inputs(setup.inputs.market_inputs.tickers)
        always_kwargs["max_names_per_sector"] = int(spec.max_names_per_sector)
    always_on = simulate_strategy(**always_kwargs)

    always_on_slice = slice_execution_year(always_on.daily, int(args.evaluation_year))
    activated_slice = slice_execution_year(activated.result.daily, int(args.evaluation_year))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = OUT_DIR / f"{ts}_h183_live_activation_scoreboard_daily.parquet"
    daily = activated_slice.copy()
    daily["variant"] = "activated"
    base_daily = always_on_slice.copy()
    base_daily["variant"] = "always_on"
    pd.concat([daily, base_daily], ignore_index=True).to_parquet(daily_path, index=False)

    activated_summary = summarize_daily_slice(activated_slice)
    always_summary = summarize_daily_slice(always_on_slice)
    veto_desc = "none"
    if spec.blocked_buy_span is not None and spec.blocked_buy_max_quantile is not None:
        veto_desc = f"blocked{int(spec.blocked_buy_span)}<=q{int(round(float(spec.blocked_buy_max_quantile) * 100.0))}"
    summary = {
        "meta_source": setup.meta_source,
        "activation_rule": "h175__rel2_gt0",
        "incumbent_score_bonus": float(args.incumbent_score_bonus),
        "implementation_veto": veto_desc,
        "blocked_buy_on_threshold": activated.blocked_buy_on_threshold,
        "blocked_buy_off_threshold": activated.blocked_buy_off_threshold,
        "max_names_per_sector": spec.max_names_per_sector,
        "selector": setup.selector_name,
        "evaluation_year": int(args.evaluation_year),
        "activated": activated_summary,
        "always_on": always_summary,
        "delta_relative_total_return": (
            None
            if activated_summary["relative_total_return"] is None or always_summary["relative_total_return"] is None
            else float(activated_summary["relative_total_return"] - always_summary["relative_total_return"])
        ),
        "delta_information_ratio_annualized": (
            None
            if activated_summary["information_ratio_annualized"] is None or always_summary["information_ratio_annualized"] is None
            else float(activated_summary["information_ratio_annualized"] - always_summary["information_ratio_annualized"])
        ),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_live_activation_scoreboard",
        name="h183_live_activation_scoreboard",
        summary=summary,
        artifacts={"daily": str(daily_path)},
        metadata={
            "matrix": str(args.matrix),
            "activation_meta": str(args.activation_meta),
            "history_start_year": int(args.history_start_year),
            "evaluation_year": int(args.evaluation_year),
            "blocked_buy_ewm3_max_quantile": args.blocked_buy_ewm3_max_quantile,
            "blocked_buy_ewm5_max_quantile": args.blocked_buy_ewm5_max_quantile,
            "max_names_per_sector": spec.max_names_per_sector,
            "disable_blocked_buy_veto": bool(args.disable_blocked_buy_veto),
            "disable_sector_cap": bool(args.disable_sector_cap),
        },
    )

    print("\nH183: LIVE ACTIVATION SCOREBOARD")
    print(pd.DataFrame([{
        "variant": "activated",
        "relative_total_return": activated_summary["relative_total_return"],
        "information_ratio_annualized": activated_summary["information_ratio_annualized"],
        "avg_cash_weight": activated_summary["avg_cash_weight"],
        "latest_held_tickers": activated_summary["latest_day"].get("held_tickers", []),
    }, {
        "variant": "always_on",
        "relative_total_return": always_summary["relative_total_return"],
        "information_ratio_annualized": always_summary["information_ratio_annualized"],
        "avg_cash_weight": always_summary["avg_cash_weight"],
        "latest_held_tickers": always_summary["latest_day"].get("held_tickers", []),
    }]).to_string(index=False))


if __name__ == "__main__":
    main()
