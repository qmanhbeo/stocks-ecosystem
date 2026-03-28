"""
H137: Nested walk-forward portfolio-construction selection.

Purpose:
- replace full-sample construction picking with an honest train/test selection loop
- choose the best H136-style portfolio config on past years only
- freeze that config and test it on the next year
- measure whether portfolio construction can be learned stably enough to justify further ML

Default design:
- expanding train window with a minimum of 4 years
- one test year at a time
- same realistic execution rules as H135/H136
- same config space as H136 unless overridden

Usage:
    conda run -n stocks python analysis/h137_nested_portfolio_selection.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

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
    WEIGHTING_RULES,
    build_market_inputs,
    compute_strategy_scores,
    default_strategy_names,
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
    summarize_daily_results,
)
from src.portfolio_construction_search import (
    build_year_splits,
    candidate_sort_key,
    enumerate_config_grid,
    parse_min_score_grid,
    sort_candidate_results,
)
from src.run_summary import write_run_summary

RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = Path("artifacts/portfolio_baselines")


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
        help="Built-in signal blend to select over",
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=4)
    parser.add_argument(
        "--train-years",
        type=int,
        default=0,
        help="Optional rolling train-window size; 0 means expanding from start-year",
    )
    parser.add_argument("--top-k-grid", nargs="+", type=int, default=[3, 5, 8, 10])
    parser.add_argument("--rebalance-grid", nargs="+", type=int, default=[3, 5, 10])
    parser.add_argument(
        "--weighting-grid",
        nargs="+",
        default=list(WEIGHTING_RULES),
        choices=list(WEIGHTING_RULES),
    )
    parser.add_argument(
        "--min-score-grid",
        nargs="+",
        default=None,
        help="Optional explicit thresholds; use 'none' to include the ungated baseline",
    )
    parser.add_argument("--portfolio-notional-vnd", type=float, default=1_000_000_000.0)
    parser.add_argument("--max-adv-participation", type=float, default=0.0)
    parser.add_argument("--buy-fee-rate", type=float, default=0.0015)
    parser.add_argument("--sell-fee-rate", type=float, default=0.0015)
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--top-train-configs", type=int, default=5)
    return parser.parse_args()


def _print_split_table(split_rows: list[dict[str, object]]) -> None:
    print("\n" + "=" * 162)
    print("H137: NESTED PORTFOLIO SELECTION")
    print("=" * 162)
    print(
        f"{'test':<6} {'train':<11} {'top_k':>5} {'cad':>5} {'weight':>8} {'gate':>7} "
        f"{'train_ret':>10} {'test_ret':>10} {'test_rel':>10} {'IR':>8} "
        f"{'max_dd':>9} {'turn/day':>10} {'yrs+':>7}"
    )
    print("-" * 162)
    for row in split_rows:
        gate = "none" if row["min_score"] is None else f"{row['min_score']:.3f}"
        print(
            f"{row['test_year']:<6} "
            f"{row['train_start_year']}-{row['train_end_year']:<6} "
            f"{row['top_k']:>5} {row['rebalance_every']:>5} {row['weighting']:>8} {gate:>7} "
            f"{row['train_portfolio_total_return']*100:>+9.2f}% "
            f"{row['test_portfolio_total_return']*100:>+9.2f}% "
            f"{row['test_relative_total_return']*100:>+9.2f}% "
            f"{row['test_information_ratio_annualized'] if row['test_information_ratio_annualized'] is not None else float('nan'):>8.2f} "
            f"{row['test_max_drawdown']*100:>8.2f}% "
            f"{row['test_avg_daily_turnover']*100:>9.2f}% "
            f"{row['test_positive_years']:>3}/{row['test_total_years']:<3}"
        )


def _count_selected_configs(split_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[tuple[int, int, str, float | None], int] = {}
    for row in split_rows:
        key = (
            int(row["top_k"]),
            int(row["rebalance_every"]),
            str(row["weighting"]),
            None if row["min_score"] is None else float(row["min_score"]),
        )
        counts[key] = counts.get(key, 0) + 1
    out = []
    for (top_k, rebalance_every, weighting, min_score), count in sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2], -1.0 if item[0][3] is None else item[0][3]),
    ):
        out.append(
            {
                "top_k": top_k,
                "rebalance_every": rebalance_every,
                "weighting": weighting,
                "min_score": min_score,
                "count": count,
            }
        )
    return out


def main() -> None:
    args = parse_args()
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

    print("Loading prices and ADV20...")
    price_panel = load_price_panel(scored["ticker"].unique().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")
    print(f"  price rows={len(price_panel):,}")

    print(f"Loading tradability flags: {tradability_path}")
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)
    print(f"  source={tradability_source} | rows={len(tradability):,}")

    benchmark_open = load_benchmark_open(benchmark_path)
    required_holding_age = required_holding_age_for_sell(
        min_hold_days_override=int(args.required_holding_age)
    )
    train_years = int(args.train_years) if int(args.train_years) > 0 else None
    splits = build_year_splits(
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_train_years=int(args.min_train_years),
        train_years=train_years,
    )
    print(
        f"Strategy: {args.strategy} ({len(signal_columns)} signals) | "
        f"splits={len(splits)} | train_years={'expanding' if train_years is None else train_years} | "
        f"required_holding_age={required_holding_age}"
    )

    selected_rows: list[dict[str, object]] = []
    stitched_daily_parts: list[pd.DataFrame] = []
    candidate_rows: list[dict[str, object]] = []
    rolling_capital = float(args.portfolio_notional_vnd)

    for split in splits:
        train_start_year = int(split["train_start_year"])
        train_end_year = int(split["train_end_year"])
        test_year = int(split["test_year"])

        train_market_inputs = build_market_inputs(
            scored,
            price_panel,
            tradability,
            benchmark_open,
            tradability_source=tradability_source,
            strategy_names=[str(args.strategy)],
            start_year=train_start_year,
            end_year=train_end_year,
        )
        test_market_inputs = build_market_inputs(
            scored,
            price_panel,
            tradability,
            benchmark_open,
            tradability_source=tradability_source,
            strategy_names=[str(args.strategy)],
            start_year=test_year,
            end_year=test_year,
        )
        train_score_col = f"score__{args.strategy}"
        train_scores = scored.loc[
            scored["time"].dt.year.between(train_start_year, train_end_year),
            train_score_col,
        ]
        min_score_grid = parse_min_score_grid(args.min_score_grid, train_scores)
        grid = enumerate_config_grid(
            top_k_grid=args.top_k_grid,
            rebalance_grid=args.rebalance_grid,
            weighting_grid=args.weighting_grid,
            min_score_grid=min_score_grid,
        )

        split_candidate_rows: list[dict[str, object]] = []
        for top_k, rebalance_every, weighting, min_score in grid:
            train_result = simulate_strategy(
                strategy_name=str(args.strategy),
                signal_columns=signal_columns,
                market_inputs=train_market_inputs,
                top_k=int(top_k),
                rebalance_every=int(rebalance_every),
                weighting=str(weighting),
                initial_notional_vnd=float(args.portfolio_notional_vnd),
                max_adv_participation=float(args.max_adv_participation),
                required_holding_age=int(required_holding_age),
                buy_fee_rate=float(args.buy_fee_rate),
                sell_fee_rate=float(args.sell_fee_rate),
                capital_gains_tax_rate=float(args.capital_gains_tax_rate),
                min_score=float(min_score) if min_score is not None else None,
            )
            row = {
                "train_start_year": train_start_year,
                "train_end_year": train_end_year,
                "test_year": test_year,
                "top_k": int(top_k),
                "rebalance_every": int(rebalance_every),
                "weighting": str(weighting),
                "min_score": float(min_score) if min_score is not None else None,
                "signal_columns": list(train_result.signal_columns),
            }
            row.update(train_result.summary)
            row["rebalance_event_days"] = row.pop("rebalance_days")
            split_candidate_rows.append(row)
            candidate_rows.append(row.copy())

        ranked_candidates = sort_candidate_results(pd.DataFrame(split_candidate_rows))
        selected = ranked_candidates.iloc[0].to_dict()
        test_result = simulate_strategy(
            strategy_name=str(args.strategy),
            signal_columns=signal_columns,
            market_inputs=test_market_inputs,
            top_k=int(selected["top_k"]),
            rebalance_every=int(selected["rebalance_every"]),
            weighting=str(selected["weighting"]),
            initial_notional_vnd=float(rolling_capital),
            max_adv_participation=float(args.max_adv_participation),
            required_holding_age=int(required_holding_age),
            buy_fee_rate=float(args.buy_fee_rate),
            sell_fee_rate=float(args.sell_fee_rate),
            capital_gains_tax_rate=float(args.capital_gains_tax_rate),
            min_score=float(selected["min_score"]) if selected["min_score"] is not None else None,
        )
        test_summary = dict(test_result.summary)
        rolling_capital = float(test_summary["final_portfolio_value_vnd"])

        selected_row = {
            "train_start_year": train_start_year,
            "train_end_year": train_end_year,
            "test_year": test_year,
            "top_k": int(selected["top_k"]),
            "rebalance_every": int(selected["rebalance_every"]),
            "weighting": str(selected["weighting"]),
            "min_score": None if selected["min_score"] is None else float(selected["min_score"]),
            "train_portfolio_total_return": float(selected["portfolio_total_return"]),
            "train_relative_total_return": float(selected["relative_total_return"]),
            "train_information_ratio_annualized": selected["information_ratio_annualized"],
            "train_avg_daily_turnover": float(selected["avg_daily_turnover"]),
            "test_portfolio_total_return": float(test_summary["portfolio_total_return"]),
            "test_relative_total_return": float(test_summary["relative_total_return"]),
            "test_portfolio_annualized_return": test_summary["portfolio_annualized_return"],
            "test_information_ratio_annualized": test_summary["information_ratio_annualized"],
            "test_max_drawdown": float(test_summary["max_drawdown"]),
            "test_avg_daily_turnover": float(test_summary["avg_daily_turnover"]),
            "test_positive_years": int(test_summary["positive_years"]),
            "test_total_years": int(test_summary["total_years"]),
            "candidate_count": int(len(ranked_candidates)),
            "top_train_configs": json.loads(
                ranked_candidates.head(int(args.top_train_configs)).to_json(orient="records")
            ),
        }
        selected_rows.append(selected_row)
        stitched_daily_parts.append(
            test_result.daily.assign(
                train_start_year=train_start_year,
                train_end_year=train_end_year,
                test_year=test_year,
                top_k=int(selected["top_k"]),
                rebalance_every=int(selected["rebalance_every"]),
                weighting=str(selected["weighting"]),
                min_score=None if selected["min_score"] is None else float(selected["min_score"]),
            )
        )

    stitched_daily = pd.concat(stitched_daily_parts, ignore_index=True).sort_values("execution_date").reset_index(drop=True)
    overall_summary = summarize_daily_results(
        stitched_daily,
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        top_k=0,
    )
    overall_summary["top_k"] = None
    overall_summary["selected_config_counts"] = _count_selected_configs(selected_rows)
    overall_summary["num_test_splits"] = int(len(selected_rows))
    overall_summary["test_years"] = [int(row["test_year"]) for row in selected_rows]

    _print_split_table(selected_rows)

    print("\nOverall out-of-sample summary")
    print(
        f"  total_return={overall_summary['portfolio_total_return']*100:+.2f}% | "
        f"ann_return={overall_summary['portfolio_annualized_return']*100 if overall_summary['portfolio_annualized_return'] is not None else float('nan'):+.2f}% | "
        f"relative={overall_summary['relative_total_return']*100:+.2f}% | "
        f"IR={overall_summary['information_ratio_annualized'] if overall_summary['information_ratio_annualized'] is not None else float('nan'):.2f} | "
        f"max_dd={overall_summary['max_drawdown']*100:.2f}%"
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selected_path = OUT_DIR / f"{ts}_h137_nested_portfolio_selection_selected_configs.parquet"
    candidates_path = OUT_DIR / f"{ts}_h137_nested_portfolio_selection_train_candidates.parquet"
    daily_path = OUT_DIR / f"{ts}_h137_nested_portfolio_selection_oos_daily.parquet"
    pd.DataFrame(selected_rows).to_parquet(selected_path, index=False)
    pd.DataFrame(candidate_rows).to_parquet(candidates_path, index=False)
    stitched_daily.to_parquet(daily_path, index=False)

    summary = {
        "strategy": str(args.strategy),
        "year_range": [int(args.start_year), int(args.end_year)],
        "min_train_years": int(args.min_train_years),
        "train_years": None if train_years is None else int(train_years),
        "top_k_grid": sorted(set(int(v) for v in args.top_k_grid)),
        "rebalance_grid": sorted(set(int(v) for v in args.rebalance_grid)),
        "weighting_grid": [str(v) for v in args.weighting_grid],
        "min_score_grid_mode": list(args.min_score_grid) if args.min_score_grid is not None else "train_quantiles",
        "required_holding_age": int(required_holding_age),
        "portfolio_notional_vnd": float(args.portfolio_notional_vnd),
        "max_adv_participation": float(args.max_adv_participation),
        "buy_fee_rate": float(args.buy_fee_rate),
        "sell_fee_rate": float(args.sell_fee_rate),
        "capital_gains_tax_rate": float(args.capital_gains_tax_rate),
        "splits": selected_rows,
        "overall_oos": overall_summary,
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_nested_selection",
        name="h137_nested_portfolio_selection",
        summary=summary,
        artifacts={
            "selected_configs": str(selected_path),
            "train_candidates": str(candidates_path),
            "oos_daily": str(daily_path),
        },
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
        },
    )

    print(f"\nSaved selected configs -> {selected_path}")
    print(f"Saved train candidates -> {candidates_path}")
    print(f"Saved OOS daily        -> {daily_path}")
    print(f"Saved run summary      -> {summary_path}")


if __name__ == "__main__":
    main()
