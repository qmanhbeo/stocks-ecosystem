"""
H141: Small construction sweep inside the retail-viable liquidity region.

Purpose:
- take only the liquidity settings that survived H140
- re-open a tiny, controlled long-only construction menu inside that region
- decide whether a simple retail-sized configuration still beats the benchmark without excessive cash drag

Usage:
    conda run -n stocks python analysis/h141_capacity_aware_construction_sweep.py
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
)
from src.portfolio_construction_search import retail_viable_mask, sort_retail_results
from src.run_summary import write_run_summary

RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
LATEST_H140_SUMMARY = ROOT / "artifacts/run_summaries/latest_portfolio_retail_validation.json"
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
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--h140-results", type=str, default="")
    parser.add_argument("--top-k-grid", nargs="+", type=int, default=[3, 5])
    parser.add_argument("--rebalance-grid", nargs="+", type=int, default=[5, 10])
    parser.add_argument(
        "--weighting-grid",
        nargs="+",
        default=["equal"],
        choices=list(WEIGHTING_RULES),
    )
    parser.add_argument(
        "--min-score-grid",
        nargs="+",
        default=["none", "0.52"],
        help="Explicit score gates for the small capacity-aware menu",
    )
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--viable-max-cash-weight", type=float, default=0.25)
    parser.add_argument("--viable-min-positive-years", type=int, default=5)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _parse_min_score_grid(raw_values: list[str]) -> list[float | None]:
    parsed: list[float | None] = []
    for value in raw_values:
        text = str(value).strip().lower()
        parsed.append(None if text in {"none", "null", "na"} else float(text))
    return parsed


def _resolve_h140_results_path(explicit_path: str) -> Path:
    if explicit_path:
        return Path(explicit_path)
    payload = json.loads(LATEST_H140_SUMMARY.read_text(encoding="utf-8"))
    artifact_path = payload.get("artifacts", {}).get("results")
    if not artifact_path:
        raise ValueError(f"No results artifact recorded in {LATEST_H140_SUMMARY}")
    return Path(artifact_path)


def _load_viable_liquidity_settings(results_path: Path, *, max_cash_weight: float, min_positive_years: int) -> pd.DataFrame:
    results = pd.read_parquet(results_path)
    viable = results.loc[
        retail_viable_mask(
            results,
            max_avg_cash_weight=float(max_cash_weight),
            min_positive_years=int(min_positive_years),
        )
    ].copy()
    if viable.empty:
        return viable
    setting_columns = [
        "portfolio_notional_vnd",
        "max_adv_participation",
        "min_adv20_value_vnd",
        "round_trip_cost",
    ]
    for optional_column in ("max_position_vnd", "max_names_if_liquidity_thin"):
        if optional_column in viable.columns:
            setting_columns.append(optional_column)
    return (
        viable[setting_columns]
        .drop_duplicates()
        .sort_values(
            by=["portfolio_notional_vnd", "max_adv_participation", "min_adv20_value_vnd", "round_trip_cost"],
            ignore_index=True,
        )
    )


def _print_top(results: pd.DataFrame, *, title: str, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 216)
    print(title)
    print("=" * 216)
    print(
        f"{'rank':<5} {'top_k':>5} {'cad':>5} {'weight':>8} {'gate':>7} {'notional':>11} {'adv_cap':>8} {'adv_floor':>10} {'rt_cost':>8} "
        f"{'tot_ret':>10} {'rel_ret':>10} {'ann_ret':>10} {'IR':>8} {'cash':>8} {'turn/day':>10} {'max_dd':>9} {'yrs+':>7}"
    )
    print("-" * 216)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        gate = "none" if row.min_score is None else f"{row.min_score:.3f}"
        print(
            f"{i:<5} {row.top_k:>5} {row.rebalance_every:>5} {row.weighting:>8} {gate:>7} "
            f"{row.portfolio_notional_vnd/1e6:>10.0f}m {row.max_adv_participation*100:>7.2f}% {row.min_adv20_value_vnd/1e9:>9.2f}B {row.round_trip_cost*100:>7.2f}% "
            f"{row.portfolio_total_return*100:>+9.2f}% {row.relative_total_return*100:>+9.2f}% "
            f"{row.portfolio_annualized_return*100 if row.portfolio_annualized_return is not None else float('nan'):>+9.2f}% "
            f"{row.information_ratio_annualized if row.information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.avg_cash_weight*100:>7.2f}% {row.avg_daily_turnover*100:>9.2f}% {row.max_drawdown*100:>8.2f}% "
            f"{row.positive_years:>3}/{row.total_years:<3}"
        )


def main() -> None:
    args = parse_args()
    h140_results_path = _resolve_h140_results_path(str(args.h140_results))
    liquidity_settings = _load_viable_liquidity_settings(
        h140_results_path,
        max_cash_weight=float(args.viable_max_cash_weight),
        min_positive_years=int(args.viable_min_positive_years),
    )

    if liquidity_settings.empty:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        summary_path = write_run_summary(
            ts=ts,
            mode="portfolio_capacity_aware_sweep",
            name="h141_capacity_aware_construction_sweep",
            summary={
                "strategy": str(args.strategy),
                "year_range": [int(args.start_year), int(args.end_year)],
                "h140_results": str(h140_results_path),
                "liquidity_setting_count": 0,
                "num_scenarios": 0,
                "retail_acceptable_count": 0,
                "winner": None,
            },
            artifacts={},
            metadata={"h140_results": str(h140_results_path)},
        )
        print("No retail-viable H140 liquidity settings found; H141 stops here.")
        print(f"Saved run summary -> {summary_path}")
        return

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
    market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=[str(args.strategy)],
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    required_holding_age = required_holding_age_for_sell(
        min_hold_days_override=int(args.required_holding_age)
    )
    min_score_grid = _parse_min_score_grid(list(args.min_score_grid))
    print(
        f"Strategy: {args.strategy} ({len(signal_columns)} signals) | liquidity_settings={len(liquidity_settings)} | "
        f"construction_scenarios={len(liquidity_settings) * len(set(args.top_k_grid)) * len(set(args.rebalance_grid)) * len(set(args.weighting_grid)) * len(min_score_grid)} | "
        f"required_holding_age={required_holding_age}"
    )

    rows: list[dict[str, object]] = []
    best_viable_daily: pd.DataFrame | None = None
    best_viable_key: tuple | None = None

    for setting in liquidity_settings.itertuples(index=False):
        max_position_vnd = float(getattr(setting, "max_position_vnd", 0.0) or 0.0)
        raw_max_names = getattr(setting, "max_names_if_liquidity_thin", None)
        max_names_if_liquidity_thin = None if pd.isna(raw_max_names) or raw_max_names in (None, 0) else int(raw_max_names)
        fee_leg = float(setting.round_trip_cost) / 2.0
        for top_k in sorted(set(int(v) for v in args.top_k_grid)):
            for rebalance_every in sorted(set(int(v) for v in args.rebalance_grid)):
                for weighting in list(dict.fromkeys(str(v) for v in args.weighting_grid)):
                    for min_score in min_score_grid:
                        result = simulate_strategy(
                            strategy_name=str(args.strategy),
                            signal_columns=signal_columns,
                            market_inputs=market_inputs,
                            top_k=int(top_k),
                            rebalance_every=int(rebalance_every),
                            weighting=str(weighting),
                            initial_notional_vnd=float(setting.portfolio_notional_vnd),
                            max_adv_participation=float(setting.max_adv_participation),
                            required_holding_age=int(required_holding_age),
                            buy_fee_rate=float(fee_leg),
                            sell_fee_rate=float(fee_leg),
                            capital_gains_tax_rate=float(args.capital_gains_tax_rate),
                            min_score=min_score,
                            min_adv20_value_vnd=float(setting.min_adv20_value_vnd),
                            max_position_vnd=max_position_vnd,
                            max_names_if_liquidity_thin=max_names_if_liquidity_thin,
                        )
                        row = {
                            "top_k": int(top_k),
                            "rebalance_every": int(rebalance_every),
                            "weighting": str(weighting),
                            "min_score": min_score,
                            "portfolio_notional_vnd": float(setting.portfolio_notional_vnd),
                            "max_adv_participation": float(setting.max_adv_participation),
                            "min_adv20_value_vnd": float(setting.min_adv20_value_vnd),
                            "round_trip_cost": float(setting.round_trip_cost),
                            "max_position_vnd": max_position_vnd,
                            "max_names_if_liquidity_thin": max_names_if_liquidity_thin,
                            **result.summary,
                        }
                        rows.append(row)
                        if retail_viable_mask(
                            pd.DataFrame([row]),
                            max_avg_cash_weight=float(args.viable_max_cash_weight),
                            min_positive_years=int(args.viable_min_positive_years),
                        ).iloc[0]:
                            rank_key = (
                                float(row["relative_total_return"]),
                                float(row["portfolio_total_return"]),
                                float(row["information_ratio_annualized"] or -999.0),
                                -float(row["avg_cash_weight"]),
                                -float(row["avg_daily_turnover"]),
                            )
                            if best_viable_key is None or rank_key > best_viable_key:
                                best_viable_key = rank_key
                                best_viable_daily = result.daily.copy()

    results = sort_retail_results(pd.DataFrame(rows))
    acceptable = results.loc[
        retail_viable_mask(
            results,
            max_avg_cash_weight=float(args.viable_max_cash_weight),
            min_positive_years=int(args.viable_min_positive_years),
        )
    ].reset_index(drop=True)
    _print_top(results, title="H141: CAPACITY-AWARE CONSTRUCTION SWEEP", top_n=int(args.top_results))
    if not acceptable.empty:
        _print_top(acceptable, title="H141: RETAIL-ACCEPTABLE WINNERS", top_n=min(int(args.top_results), len(acceptable)))
    else:
        print("\nNo H141 construction satisfied the retail viability gate.")

    winners_by_liquidity = (
        results.groupby(
            [
                "portfolio_notional_vnd",
                "max_adv_participation",
                "min_adv20_value_vnd",
                "round_trip_cost",
                "max_position_vnd",
                "max_names_if_liquidity_thin",
            ],
            dropna=False,
            as_index=False,
        )
        .first()
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h141_capacity_aware_construction_sweep_results.parquet"
    acceptable_path = OUT_DIR / f"{ts}_h141_capacity_aware_construction_sweep_acceptable.parquet"
    results.to_parquet(results_path, index=False)
    acceptable.to_parquet(acceptable_path, index=False)

    artifacts = {
        "results": str(results_path),
        "acceptable_results": str(acceptable_path),
    }
    if best_viable_daily is not None:
        best_daily_path = OUT_DIR / f"{ts}_h141_capacity_aware_construction_sweep_best_daily.parquet"
        best_viable_daily.to_parquet(best_daily_path, index=False)
        artifacts["best_daily"] = str(best_daily_path)

    summary = {
        "strategy": str(args.strategy),
        "year_range": [int(args.start_year), int(args.end_year)],
        "required_holding_age": int(required_holding_age),
        "liquidity_setting_count": int(len(liquidity_settings)),
        "h140_results": str(h140_results_path),
        "num_scenarios": int(len(results)),
        "retail_viability_rule": {
            "relative_total_return_gt": 0.0,
            "avg_cash_weight_lt": float(args.viable_max_cash_weight),
            "positive_years_gte": int(args.viable_min_positive_years),
        },
        "best_overall": json.loads(results.head(1).to_json(orient="records"))[0] if not results.empty else None,
        "best_retail_acceptable": json.loads(acceptable.head(1).to_json(orient="records"))[0] if not acceptable.empty else None,
        "top_results": json.loads(results.head(min(int(args.top_results), len(results))).to_json(orient="records")),
        "top_retail_acceptable": json.loads(acceptable.head(min(int(args.top_results), len(acceptable))).to_json(orient="records")),
        "winners_by_liquidity": json.loads(winners_by_liquidity.to_json(orient="records")),
        "retail_acceptable_count": int(len(acceptable)),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_capacity_aware_sweep",
        name="h141_capacity_aware_construction_sweep",
        summary=summary,
        artifacts=artifacts,
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
            "h140_results": str(h140_results_path),
        },
    )

    print(f"\nRetail-acceptable H141 scenarios: {len(acceptable)}")
    print(f"Saved results -> {results_path}")
    print(f"Saved acceptable subset -> {acceptable_path}")
    if best_viable_daily is not None:
        print(f"Saved best daily path -> {artifacts['best_daily']}")
    print(f"Saved run summary -> {summary_path}")


if __name__ == "__main__":
    main()
