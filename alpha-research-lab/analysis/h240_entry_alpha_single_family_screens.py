from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_alpha import BENCHMARK_PATH, RL_MATRIX_PATH, STOCK_DIR, TRADABILITY_PATH
from src.entry_alpha import build_entry_allowed_matrix
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    backtest_row_from_result,
    add_baseline_deltas,
    build_entry_allowed_matrix_from_mask,
    build_single_family_screen_frame,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
    run_entry_backtest,
)
from src.run_summary import write_run_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H240: stock-specific single-family entry-screen sweep")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=20)
    parser.add_argument("--screen-top-m", type=int, default=10)
    parser.add_argument("--baseline-min-selection-score", type=float, default=0.65)
    parser.add_argument("--baseline-min-score-gap", type=float, default=None)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    return parser.parse_args()


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 180)
    print("H240: ENTRY ALPHA SINGLE-FAMILY SCREENS")
    print("=" * 180)
    print(
        f"{'variant':<34} {'family':<15} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'promote':>8}"
    )
    print("-" * 180)
    for row in results.itertuples(index=False):
        print(
            f"{str(row.variant):<34} {str(row.family or '-'):<15} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.validation_ir_delta if row.validation_ir_delta is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{str(bool(row.promoted)):>8}"
        )


def main() -> None:
    args = parse_args()
    inputs, candidate_panel, labels = load_or_build_entry_artifacts(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        top_m_max=int(args.top_m_max),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    panel = prepare_entry_research_panel(candidate_panel, labels)
    panel, screen_specs = build_single_family_screen_frame(panel)

    baseline_matrix = build_entry_allowed_matrix(
        panel,
        dates=pd.to_datetime(inputs.market_inputs.dates),
        tickers=inputs.market_inputs.tickers,
        top_m=int(args.screen_top_m),
        min_selection_score=float(args.baseline_min_selection_score),
        min_score_gap=None if args.baseline_min_score_gap is None else float(args.baseline_min_score_gap),
        require_buyable=True,
    )
    baseline_result = run_entry_backtest(
        inputs,
        entry_allowed_matrix=baseline_matrix,
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
    )
    rows = [
        backtest_row_from_result(
            variant="score_sparse_baseline",
            family="baseline",
            result=baseline_result,
            extra={
                "top_m": int(args.screen_top_m),
                "baseline_min_selection_score": float(args.baseline_min_selection_score),
                "baseline_min_score_gap": None if args.baseline_min_score_gap is None else float(args.baseline_min_score_gap),
            },
        )
    ]
    daily_outputs: dict[str, pd.DataFrame] = {"score_sparse_baseline": baseline_result.daily.copy()}

    top_m_mask = pd.to_numeric(panel["candidate_pool_rank"], errors="coerce") <= int(args.screen_top_m)
    for spec in screen_specs:
        screen_mask = top_m_mask & panel[spec.name].fillna(False).astype(bool)
        entry_allowed_matrix = build_entry_allowed_matrix_from_mask(
            panel,
            dates=pd.to_datetime(inputs.market_inputs.dates),
            tickers=inputs.market_inputs.tickers,
            mask=screen_mask,
        )
        result = run_entry_backtest(
            inputs,
            entry_allowed_matrix=entry_allowed_matrix,
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
            top_k=int(args.top_k),
            rebalance_every=int(args.rebalance_every),
        )
        rows.append(
            backtest_row_from_result(
                variant=spec.name,
                family=spec.family,
                result=result,
                extra={
                    "description": spec.description,
                    "top_m": int(args.screen_top_m),
                    "allowed_rows": int(screen_mask.sum()),
                    "validation_allowed_rows": int((screen_mask & (panel["research_phase"] == "validation")).sum()),
                    "confirmation_allowed_rows": int((screen_mask & (panel["research_phase"] == "confirmation")).sum()),
                },
            )
        )
        daily_outputs[spec.name] = result.daily.copy()

    results = add_baseline_deltas(pd.DataFrame(rows), baseline_variant="score_sparse_baseline")
    _print_table(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h240_entry_alpha_single_family_screens_results.parquet"
    best_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h240_entry_alpha_single_family_screens_best_daily.parquet"
    screen_panel_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h240_entry_alpha_single_family_screens_panel.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)
    panel.to_parquet(screen_panel_path, index=False)

    summary = {
        "baseline": results.loc[results["variant"] == "score_sparse_baseline"].iloc[0].to_dict(),
        "best_variant": results.iloc[0].to_dict(),
        "promoted_candidates": results.loc[results["promoted"], ["variant", "family", "validation_relative_delta", "validation_ir_delta", "confirmation_relative_delta"]].to_dict("records"),
        "screen_count": int(len(screen_specs)),
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_single_family_screens",
        name="h240_entry_alpha_single_family_screens",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "screen_panel": str(screen_panel_path),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "strategy": str(args.strategy),
            "top_k": int(args.top_k),
            "rebalance_every": int(args.rebalance_every),
            "top_m_max": int(args.top_m_max),
            "screen_top_m": int(args.screen_top_m),
            "baseline_min_selection_score": float(args.baseline_min_selection_score),
            "baseline_min_score_gap": None if args.baseline_min_score_gap is None else float(args.baseline_min_score_gap),
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
        },
    )


if __name__ == "__main__":
    main()
