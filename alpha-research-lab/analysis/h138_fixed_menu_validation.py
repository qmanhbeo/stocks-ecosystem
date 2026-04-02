"""
H138: Fixed-menu honest validation for simple portfolio constructions.

Purpose:
- remove yearly re-selection entirely
- compare a tiny menu of plain long-only constructions on an honest holdout period
- decide whether any simple fixed rule is robust enough to keep the long-only path alive

Default candidate menu:
- `k5_r10_eq`: top-5, rebalance every 10 signal days, equal weight
- `k5_r5_eq`: top-5, rebalance every 5 signal days, equal weight
- `k3_r5_eq`: top-3, rebalance every 5 signal days, equal weight

Default holdout:
- train: 2015-2018
- test: 2019-2025

Usage:
    conda run -n stocks python analysis/h138_fixed_menu_validation.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path


import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_market_rules import required_holding_age_for_sell

from src.deterministic_portfolio import (
    build_market_inputs,
    compute_strategy_scores,
    default_strategy_names,
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.portfolio_construction_search import parse_fixed_menu_candidates
from src.run_summary import write_run_summary

RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument(
        "--strategy",
        type=str,
        default="full_library",
        choices=list(default_strategy_names()),
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--train-end-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="name:top_k:rebalance_every:weighting:min_score ; may be repeated",
    )
    parser.add_argument("--portfolio-notional-vnd", type=float, default=1_000_000_000.0)
    parser.add_argument("--max-adv-participation", type=float, default=0.0)
    parser.add_argument("--buy-fee-rate", type=float, default=0.0015)
    parser.add_argument("--sell-fee-rate", type=float, default=0.0015)
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _sort_results(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(
        by=[
            "test_relative_total_return",
            "test_portfolio_total_return",
            "test_information_ratio_annualized",
            "test_avg_daily_turnover",
            "name",
        ],
        ascending=[False, False, False, True, True],
        ignore_index=True,
    )


def _print_table(rows: list[dict[str, object]], train_years: str, test_years: str) -> None:
    print("\n" + "=" * 156)
    print("H138: FIXED-MENU HONEST VALIDATION")
    print("=" * 156)
    print(f"Train={train_years} | Test={test_years}")
    print(
        f"{'name':<12} {'top_k':>5} {'cad':>5} {'weight':>8} {'gate':>7} "
        f"{'train_ret':>10} {'test_ret':>10} {'test_rel':>10} {'ann_ret':>10} "
        f"{'IR':>8} {'max_dd':>9} {'turn/day':>10} {'yrs+':>7}"
    )
    print("-" * 156)
    for row in rows:
        gate = "none" if row["min_score"] is None else f"{row['min_score']:.3f}"
        print(
            f"{row['name']:<12} "
            f"{row['top_k']:>5} {row['rebalance_every']:>5} {row['weighting']:>8} {gate:>7} "
            f"{row['train_portfolio_total_return']*100:>+9.2f}% "
            f"{row['test_portfolio_total_return']*100:>+9.2f}% "
            f"{row['test_relative_total_return']*100:>+9.2f}% "
            f"{row['test_portfolio_annualized_return']*100 if row['test_portfolio_annualized_return'] is not None else float('nan'):>+9.2f}% "
            f"{row['test_information_ratio_annualized'] if row['test_information_ratio_annualized'] is not None else float('nan'):>8.2f} "
            f"{row['test_max_drawdown']*100:>8.2f}% "
            f"{row['test_avg_daily_turnover']*100:>9.2f}% "
            f"{row['test_positive_years']:>3}/{row['test_total_years']:<3}"
        )


def main() -> None:
    args = parse_args()
    if args.train_end_year < args.start_year:
        raise ValueError("train_end_year must be >= start_year")
    if args.end_year <= args.train_end_year:
        raise ValueError("end_year must be greater than train_end_year")

    matrix_path = Path(args.matrix)
    tradability_path = Path(args.tradability)
    stock_dir = Path(args.stock_dir)
    benchmark_path = Path(args.benchmark)

    print(f"Loading signal matrix: {matrix_path}")
    matrix = pd.read_parquet(matrix_path)
    matrix["time"] = pd.to_datetime(matrix["time"])
    matrix = matrix[(matrix["time"].dt.year >= args.start_year) & (matrix["time"].dt.year <= args.end_year)].copy()
    if matrix.empty:
        raise ValueError(f"No matrix rows in year range {args.start_year}-{args.end_year}")
    print(f"  rows={len(matrix):,} | tickers={matrix['ticker'].nunique()} | dates={matrix['time'].nunique()}")

    signal_columns = resolve_strategy_columns(matrix.columns.tolist(), str(args.strategy))
    scored = compute_strategy_scores(matrix, {str(args.strategy): signal_columns})
    candidates = parse_fixed_menu_candidates(args.candidate)

    print("Loading prices and ADV20...")
    price_panel = load_price_panel(scored["ticker"].unique().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")
    print(f"  price rows={len(price_panel):,}")

    print(f"Loading tradability flags: {tradability_path}")
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)
    print(f"  source={tradability_source} | rows={len(tradability):,}")

    benchmark_open = load_benchmark_open(benchmark_path)
    train_market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=[str(args.strategy)],
        start_year=int(args.start_year),
        end_year=int(args.train_end_year),
    )
    test_market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=[str(args.strategy)],
        start_year=int(args.train_end_year) + 1,
        end_year=int(args.end_year),
    )

    required_holding_age = required_holding_age_for_sell(
        min_hold_days_override=int(args.required_holding_age)
    )
    print(
        f"Strategy: {args.strategy} ({len(signal_columns)} signals) | candidates={len(candidates)} | "
        f"required_holding_age={required_holding_age}"
    )

    rows: list[dict[str, object]] = []
    oos_daily_parts: list[pd.DataFrame] = []
    for candidate in candidates:
        train_result = simulate_strategy(
            strategy_name=str(args.strategy),
            signal_columns=signal_columns,
            market_inputs=train_market_inputs,
            top_k=int(candidate["top_k"]),
            rebalance_every=int(candidate["rebalance_every"]),
            weighting=str(candidate["weighting"]),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            max_adv_participation=float(args.max_adv_participation),
            required_holding_age=int(required_holding_age),
            buy_fee_rate=float(args.buy_fee_rate),
            sell_fee_rate=float(args.sell_fee_rate),
            capital_gains_tax_rate=float(args.capital_gains_tax_rate),
            min_score=float(candidate["min_score"]) if candidate["min_score"] is not None else None,
        )
        test_result = simulate_strategy(
            strategy_name=str(args.strategy),
            signal_columns=signal_columns,
            market_inputs=test_market_inputs,
            top_k=int(candidate["top_k"]),
            rebalance_every=int(candidate["rebalance_every"]),
            weighting=str(candidate["weighting"]),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            max_adv_participation=float(args.max_adv_participation),
            required_holding_age=int(required_holding_age),
            buy_fee_rate=float(args.buy_fee_rate),
            sell_fee_rate=float(args.sell_fee_rate),
            capital_gains_tax_rate=float(args.capital_gains_tax_rate),
            min_score=float(candidate["min_score"]) if candidate["min_score"] is not None else None,
        )
        row = {
            "name": str(candidate["name"]),
            "top_k": int(candidate["top_k"]),
            "rebalance_every": int(candidate["rebalance_every"]),
            "weighting": str(candidate["weighting"]),
            "min_score": None if candidate["min_score"] is None else float(candidate["min_score"]),
            "signal_columns": list(train_result.signal_columns),
            "train_portfolio_total_return": float(train_result.summary["portfolio_total_return"]),
            "train_relative_total_return": float(train_result.summary["relative_total_return"]),
            "train_portfolio_annualized_return": train_result.summary["portfolio_annualized_return"],
            "train_information_ratio_annualized": train_result.summary["information_ratio_annualized"],
            "train_avg_daily_turnover": float(train_result.summary["avg_daily_turnover"]),
            "test_portfolio_total_return": float(test_result.summary["portfolio_total_return"]),
            "test_relative_total_return": float(test_result.summary["relative_total_return"]),
            "test_portfolio_annualized_return": test_result.summary["portfolio_annualized_return"],
            "test_information_ratio_annualized": test_result.summary["information_ratio_annualized"],
            "test_max_drawdown": float(test_result.summary["max_drawdown"]),
            "test_avg_daily_turnover": float(test_result.summary["avg_daily_turnover"]),
            "test_avg_cash_weight": float(test_result.summary["avg_cash_weight"]),
            "test_positive_years": int(test_result.summary["positive_years"]),
            "test_total_years": int(test_result.summary["total_years"]),
        }
        rows.append(row)
        oos_daily_parts.append(
            test_result.daily.assign(
                candidate_name=str(candidate["name"]),
                top_k=int(candidate["top_k"]),
                rebalance_every=int(candidate["rebalance_every"]),
                weighting=str(candidate["weighting"]),
                min_score=None if candidate["min_score"] is None else float(candidate["min_score"]),
            )
        )

    results = _sort_results(pd.DataFrame(rows))
    result_rows = json.loads(results.to_json(orient="records"))
    _print_table(
        result_rows,
        train_years=f"{args.start_year}-{args.train_end_year}",
        test_years=f"{args.train_end_year + 1}-{args.end_year}",
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h138_fixed_menu_validation_results.parquet"
    daily_path = OUT_DIR / f"{ts}_h138_fixed_menu_validation_oos_daily.parquet"
    results.to_parquet(results_path, index=False)
    pd.concat(oos_daily_parts, ignore_index=True).to_parquet(daily_path, index=False)

    summary = {
        "strategy": str(args.strategy),
        "year_range": [int(args.start_year), int(args.end_year)],
        "train_end_year": int(args.train_end_year),
        "required_holding_age": int(required_holding_age),
        "portfolio_notional_vnd": float(args.portfolio_notional_vnd),
        "max_adv_participation": float(args.max_adv_participation),
        "buy_fee_rate": float(args.buy_fee_rate),
        "sell_fee_rate": float(args.sell_fee_rate),
        "capital_gains_tax_rate": float(args.capital_gains_tax_rate),
        "candidates": result_rows,
        "best_candidate": result_rows[0] if result_rows else {},
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_fixed_menu_validation",
        name="h138_fixed_menu_validation",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "oos_daily": str(daily_path),
        },
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
        },
    )

    print(f"\nSaved results -> {results_path}")
    print(f"Saved OOS daily -> {daily_path}")
    print(f"Saved run summary -> {summary_path}")


if __name__ == "__main__":
    main()
