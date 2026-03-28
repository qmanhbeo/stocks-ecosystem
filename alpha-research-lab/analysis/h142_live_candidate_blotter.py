"""
H142: Live/paper-trade candidate blotter for the current retail-sized winner.

Purpose:
- convert the best current capacity-aware construction into an execution-facing daily blotter
- expose target notionals, ADV usage, blocked trades, and expected turnover for paper/live tracking
- make fill validation the next bottleneck instead of further backtest complexity

Usage:
    conda run -n stocks python analysis/h142_live_candidate_blotter.py
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
from src.run_summary import write_run_summary

RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
LATEST_H141_SUMMARY = Path("artifacts/run_summaries/latest_portfolio_capacity_aware_sweep.json")
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
    )
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--latest-execution-days", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=0)
    parser.add_argument("--rebalance-every", type=int, default=0)
    parser.add_argument("--weighting", type=str, default="", choices=[""] + list(WEIGHTING_RULES))
    parser.add_argument("--min-score", type=str, default="")
    parser.add_argument("--portfolio-notional-vnd", type=float, default=0.0)
    parser.add_argument("--max-adv-participation", type=float, default=0.0)
    parser.add_argument("--min-adv20-value-vnd", type=float, default=0.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.0)
    parser.add_argument("--max-position-vnd", type=float, default=0.0)
    parser.add_argument("--max-names-if-liquidity-thin", type=int, default=0)
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _load_default_candidate() -> dict[str, object]:
    payload = json.loads(LATEST_H141_SUMMARY.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    candidate = summary.get("best_retail_acceptable") or summary.get("best_overall")
    if not candidate:
        raise ValueError(f"No H141 winner available in {LATEST_H141_SUMMARY}")
    return dict(candidate)


def _resolve_candidate(args: argparse.Namespace) -> dict[str, object]:
    explicit_ready = (
        int(args.top_k) > 0
        and int(args.rebalance_every) > 0
        and bool(str(args.weighting))
        and float(args.portfolio_notional_vnd) > 0.0
        and float(args.max_adv_participation) > 0.0
        and float(args.min_adv20_value_vnd) > 0.0
        and float(args.round_trip_cost) > 0.0
    )
    candidate = {} if explicit_ready else _load_default_candidate()

    if int(args.top_k) > 0:
        candidate["top_k"] = int(args.top_k)
    if int(args.rebalance_every) > 0:
        candidate["rebalance_every"] = int(args.rebalance_every)
    if str(args.weighting):
        candidate["weighting"] = str(args.weighting)
    if str(args.min_score):
        text = str(args.min_score).strip().lower()
        candidate["min_score"] = None if text in {"none", "null", "na"} else float(text)
    if float(args.portfolio_notional_vnd) > 0.0:
        candidate["portfolio_notional_vnd"] = float(args.portfolio_notional_vnd)
    if float(args.max_adv_participation) > 0.0:
        candidate["max_adv_participation"] = float(args.max_adv_participation)
    if float(args.min_adv20_value_vnd) > 0.0:
        candidate["min_adv20_value_vnd"] = float(args.min_adv20_value_vnd)
    if float(args.round_trip_cost) > 0.0:
        candidate["round_trip_cost"] = float(args.round_trip_cost)
    if float(args.max_position_vnd) > 0.0:
        candidate["max_position_vnd"] = float(args.max_position_vnd)
    if int(args.max_names_if_liquidity_thin) > 0:
        candidate["max_names_if_liquidity_thin"] = int(args.max_names_if_liquidity_thin)

    required = [
        "top_k",
        "rebalance_every",
        "weighting",
        "portfolio_notional_vnd",
        "max_adv_participation",
        "min_adv20_value_vnd",
        "round_trip_cost",
    ]
    missing = [key for key in required if key not in candidate or pd.isna(candidate[key])]
    if missing:
        raise ValueError(f"Incomplete H142 candidate configuration; missing {missing}")
    return candidate


def _aggregate_day(group: pd.DataFrame) -> dict[str, object]:
    def _tickers(mask: pd.Series) -> list[str]:
        return sorted(group.loc[mask, "ticker"].astype(str).unique().tolist())

    target_pct = pd.to_numeric(group["target_pct_adv20"], errors="coerce")
    return {
        "target_tickers": _tickers(group["selected"] & (group["desired_weight"] > 1e-12)),
        "held_after_tickers": _tickers(group["held_after"]),
        "buy_tickers": _tickers(group["executed_action"] == "buy"),
        "sell_tickers": _tickers(group["executed_action"] == "sell"),
        "blocked_buy_tickers": _tickers(group["buy_blocked"]),
        "blocked_sell_tickers": _tickers(group["sell_blocked"]),
        "avg_target_pct_adv20": float(target_pct.mean()) if target_pct.notna().any() else None,
        "max_target_pct_adv20": float(target_pct.max()) if target_pct.notna().any() else None,
        "max_single_target_notional_vnd": float(pd.to_numeric(group["target_notional_vnd"], errors="coerce").max()),
    }


def main() -> None:
    args = parse_args()
    candidate = _resolve_candidate(args)
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
    fee_leg = float(candidate["round_trip_cost"]) / 2.0
    max_names_if_liquidity_thin = candidate.get("max_names_if_liquidity_thin")
    if max_names_if_liquidity_thin in (None, 0) or pd.isna(max_names_if_liquidity_thin):
        max_names_if_liquidity_thin = None
    else:
        max_names_if_liquidity_thin = int(max_names_if_liquidity_thin)

    print(
        f"Candidate: top_k={int(candidate['top_k'])}, rebalance={int(candidate['rebalance_every'])}, "
        f"weighting={candidate['weighting']}, gate={'none' if candidate.get('min_score') is None else candidate['min_score']}, "
        f"notional={float(candidate['portfolio_notional_vnd'])/1e6:.0f}m, adv_cap={float(candidate['max_adv_participation'])*100:.2f}%, "
        f"adv_floor={float(candidate['min_adv20_value_vnd'])/1e9:.2f}B"
    )

    result = simulate_strategy(
        strategy_name=str(args.strategy),
        signal_columns=signal_columns,
        market_inputs=market_inputs,
        top_k=int(candidate["top_k"]),
        rebalance_every=int(candidate["rebalance_every"]),
        weighting=str(candidate["weighting"]),
        initial_notional_vnd=float(candidate["portfolio_notional_vnd"]),
        max_adv_participation=float(candidate["max_adv_participation"]),
        required_holding_age=int(required_holding_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=float(args.capital_gains_tax_rate),
        min_score=None if candidate.get("min_score") is None or pd.isna(candidate.get("min_score")) else float(candidate["min_score"]),
        min_adv20_value_vnd=float(candidate["min_adv20_value_vnd"]),
        max_position_vnd=float(candidate.get("max_position_vnd", 0.0) or 0.0),
        max_names_if_liquidity_thin=max_names_if_liquidity_thin,
        capture_blotter=True,
    )
    if result.blotter is None:
        raise ValueError("Expected blotter output from simulate_strategy(capture_blotter=True)")

    daily = result.daily.copy()
    blotter = result.blotter.copy()
    daily["execution_date"] = pd.to_datetime(daily["execution_date"])
    blotter["execution_date"] = pd.to_datetime(blotter["execution_date"])
    blotter["signal_date"] = pd.to_datetime(blotter["signal_date"])

    unique_execution_dates = sorted(daily["execution_date"].drop_duplicates())
    keep_count = max(int(args.latest_execution_days), 1)
    keep_dates = set(unique_execution_dates[-keep_count:])
    daily_window = daily.loc[daily["execution_date"].isin(keep_dates)].copy().reset_index(drop=True)
    blotter_window = blotter.loc[blotter["execution_date"].isin(keep_dates)].copy().reset_index(drop=True)

    aggregated_rows = []
    for execution_date, group in blotter_window.groupby("execution_date", sort=True):
        aggregated_rows.append({"execution_date": execution_date, **_aggregate_day(group)})
    aggregated = pd.DataFrame(aggregated_rows)
    daily_summary = daily_window.merge(aggregated, on="execution_date", how="left")
    daily_summary["candidate_top_k"] = int(candidate["top_k"])
    daily_summary["candidate_rebalance_every"] = int(candidate["rebalance_every"])
    daily_summary["candidate_weighting"] = str(candidate["weighting"])
    daily_summary["candidate_min_score"] = None if candidate.get("min_score") is None or pd.isna(candidate.get("min_score")) else float(candidate["min_score"])
    daily_summary["portfolio_notional_vnd"] = float(candidate["portfolio_notional_vnd"])
    daily_summary["max_adv_participation"] = float(candidate["max_adv_participation"])
    daily_summary["min_adv20_value_vnd"] = float(candidate["min_adv20_value_vnd"])
    daily_summary["round_trip_cost"] = float(candidate["round_trip_cost"])
    daily_summary["max_position_vnd"] = float(candidate.get("max_position_vnd", 0.0) or 0.0)
    daily_summary["max_names_if_liquidity_thin"] = max_names_if_liquidity_thin

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    detail_path = OUT_DIR / f"{ts}_h142_live_candidate_blotter_detail.parquet"
    daily_path = OUT_DIR / f"{ts}_h142_live_candidate_blotter_daily.parquet"
    blotter_window.to_parquet(detail_path, index=False)
    daily_summary.to_parquet(daily_path, index=False)

    latest_row = (
        json.loads(daily_summary.tail(1).to_json(orient="records", date_format="iso"))[0]
        if not daily_summary.empty
        else None
    )
    summary = {
        "strategy": str(args.strategy),
        "year_range": [int(args.start_year), int(args.end_year)],
        "required_holding_age": int(required_holding_age),
        "candidate": {
            "top_k": int(candidate["top_k"]),
            "rebalance_every": int(candidate["rebalance_every"]),
            "weighting": str(candidate["weighting"]),
            "min_score": None if candidate.get("min_score") is None or pd.isna(candidate.get("min_score")) else float(candidate["min_score"]),
            "portfolio_notional_vnd": float(candidate["portfolio_notional_vnd"]),
            "max_adv_participation": float(candidate["max_adv_participation"]),
            "min_adv20_value_vnd": float(candidate["min_adv20_value_vnd"]),
            "round_trip_cost": float(candidate["round_trip_cost"]),
            "max_position_vnd": float(candidate.get("max_position_vnd", 0.0) or 0.0),
            "max_names_if_liquidity_thin": max_names_if_liquidity_thin,
        },
        "latest_execution_days": int(keep_count),
        "window_start_execution_date": daily_summary["execution_date"].min().isoformat() if not daily_summary.empty else None,
        "window_end_execution_date": daily_summary["execution_date"].max().isoformat() if not daily_summary.empty else None,
        "window_days": int(len(daily_summary)),
        "detail_rows": int(len(blotter_window)),
        "latest_day": latest_row,
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_live_candidate_blotter",
        name="h142_live_candidate_blotter",
        summary=summary,
        artifacts={
            "detail": str(detail_path),
            "daily": str(daily_path),
        },
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
        },
    )

    print(f"Saved blotter detail -> {detail_path}")
    print(f"Saved daily blotter -> {daily_path}")
    print(f"Saved run summary -> {summary_path}")


if __name__ == "__main__":
    main()
