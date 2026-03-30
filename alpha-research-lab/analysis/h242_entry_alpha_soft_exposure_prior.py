from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_alpha import BENCHMARK_PATH, RL_MATRIX_PATH, STOCK_DIR, TRADABILITY_PATH
from src.additive_selector_research import resolve_summary_artifact
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    LATEST_H241_SUMMARY_PATH,
    add_baseline_deltas,
    backtest_row_from_result,
    build_entry_allowed_matrix_from_score,
    build_soft_exposure_scale,
    build_soft_threshold_by_date,
    build_soft_top_m_by_date,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
    run_entry_backtest,
)
from src.run_summary import write_run_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H242: use activation alpha as a soft exposure prior for entry alpha")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h241-summary", type=str, default=str(LATEST_H241_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=20)
    parser.add_argument("--on-top-m", type=int, default=10)
    parser.add_argument("--off-top-m", type=int, default=2)
    parser.add_argument("--off-threshold-penalty", type=float, default=0.08)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.015)
    return parser.parse_args()


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 180)
    print("H242: ENTRY ALPHA SOFT EXPOSURE PRIOR")
    print("=" * 180)
    print(
        f"{'variant':<32} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'promote':>8}"
    )
    print("-" * 180)
    for row in results.itertuples(index=False):
        print(
            f"{str(row.variant):<32} "
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
    h241_summary_path = Path(args.h241_summary)
    results_path = resolve_summary_artifact(h241_summary_path, "results")
    scores_path = resolve_summary_artifact(h241_summary_path, "scores")
    h241_results = pd.read_parquet(results_path)
    h241_results = h241_results.loc[h241_results["variant"] != "score_sparse_baseline"].copy()
    if h241_results.empty:
        raise ValueError("H241 results contain no model variants")
    chosen = h241_results.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_auc",
            "confirmation_relative_delta",
            "variant",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    ).iloc[0]
    score_column = str(chosen["score_column"])
    base_threshold = float(chosen["threshold"])

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
    score_panel = pd.read_parquet(scores_path)
    score_panel["time"] = pd.to_datetime(score_panel["time"])
    if score_column not in score_panel.columns:
        raise ValueError(f"H241 score artifact does not contain {score_column!r}")
    panel = panel.merge(
        score_panel[["time", "ticker", score_column]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    exposure_scale = build_soft_exposure_scale(panel)
    market_dates = pd.to_datetime(inputs.market_inputs.dates)
    aligned_soft_scale = np.asarray([float(exposure_scale.get(pd.Timestamp(date), 1.0)) for date in market_dates], dtype=float)
    hard_on = (
        panel[["time", "activation_state"]]
        .drop_duplicates(subset=["time"])
        .assign(_on=lambda frame: frame["activation_state"].fillna("off").eq("on"))
        .set_index("time")["_on"]
    )
    aligned_hard_mask = np.asarray([bool(hard_on.get(pd.Timestamp(date), True)) for date in market_dates], dtype=bool)
    soft_threshold_by_date = build_soft_threshold_by_date(
        base_threshold=base_threshold,
        exposure_scale=exposure_scale,
        off_penalty=float(args.off_threshold_penalty),
    )
    soft_top_m_by_date = build_soft_top_m_by_date(
        on_top_m=int(args.on_top_m),
        off_top_m=int(args.off_top_m),
        exposure_scale=exposure_scale,
    )

    variants = [
        {
            "variant": "entry_model_only",
            "entry_allowed_matrix": build_entry_allowed_matrix_from_score(
                panel,
                dates=market_dates,
                tickers=inputs.market_inputs.tickers,
                score_column=score_column,
                top_m=int(args.on_top_m),
                min_score=base_threshold,
                require_buyable=True,
            ),
            "activation_scale": None,
            "activation_mask": None,
            "incumbent_score_bonus": 0.0,
        },
        {
            "variant": "entry_model_soft_threshold",
            "entry_allowed_matrix": build_entry_allowed_matrix_from_score(
                panel,
                dates=market_dates,
                tickers=inputs.market_inputs.tickers,
                score_column=score_column,
                top_m=int(args.on_top_m),
                threshold_by_date=soft_threshold_by_date,
                require_buyable=True,
            ),
            "activation_scale": None,
            "activation_mask": None,
            "incumbent_score_bonus": 0.0,
        },
        {
            "variant": "entry_model_soft_breadth",
            "entry_allowed_matrix": build_entry_allowed_matrix_from_score(
                panel,
                dates=market_dates,
                tickers=inputs.market_inputs.tickers,
                score_column=score_column,
                top_m=int(args.on_top_m),
                min_score=base_threshold,
                top_m_by_date=soft_top_m_by_date,
                require_buyable=True,
            ),
            "activation_scale": None,
            "activation_mask": None,
            "incumbent_score_bonus": 0.0,
        },
        {
            "variant": "entry_model_soft_weights",
            "entry_allowed_matrix": build_entry_allowed_matrix_from_score(
                panel,
                dates=market_dates,
                tickers=inputs.market_inputs.tickers,
                score_column=score_column,
                top_m=int(args.on_top_m),
                min_score=base_threshold,
                require_buyable=True,
            ),
            "activation_scale": aligned_soft_scale,
            "activation_mask": None,
            "incumbent_score_bonus": 0.0,
        },
        {
            "variant": "entry_model_hard_veto",
            "entry_allowed_matrix": build_entry_allowed_matrix_from_score(
                panel,
                dates=market_dates,
                tickers=inputs.market_inputs.tickers,
                score_column=score_column,
                top_m=int(args.on_top_m),
                min_score=base_threshold,
                require_buyable=True,
            ),
            "activation_scale": None,
            "activation_mask": aligned_hard_mask,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
    ]

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for spec in variants:
        result = run_entry_backtest(
            inputs,
            entry_allowed_matrix=spec["entry_allowed_matrix"],
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
            top_k=int(args.top_k),
            rebalance_every=int(args.rebalance_every),
            activation_scale=spec["activation_scale"],
            activation_mask=spec["activation_mask"],
            incumbent_score_bonus=float(spec["incumbent_score_bonus"]),
        )
        rows.append(
            backtest_row_from_result(
                variant=str(spec["variant"]),
                family="soft_prior",
                result=result,
                extra={
                    "model_name": str(chosen["model_name"]),
                    "threshold": base_threshold,
                    "score_column": score_column,
                    "on_top_m": int(args.on_top_m),
                    "off_top_m": int(args.off_top_m),
                    "off_threshold_penalty": float(args.off_threshold_penalty),
                },
            )
        )
        daily_outputs[str(spec["variant"])] = result.daily.copy()

    results = add_baseline_deltas(pd.DataFrame(rows), baseline_variant="entry_model_only")
    _print_table(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path_out = ENTRY_ALPHA_OUT_DIR / f"{ts}_h242_entry_alpha_soft_exposure_prior_results.parquet"
    best_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h242_entry_alpha_soft_exposure_prior_best_daily.parquet"
    results.to_parquet(results_path_out, index=False)
    daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)

    summary = {
        "h241_best_model": chosen.to_dict(),
        "baseline": results.loc[results["variant"] == "entry_model_only"].iloc[0].to_dict(),
        "best_variant": results.iloc[0].to_dict(),
        "promoted_candidates": results.loc[results["promoted"], ["variant", "validation_relative_delta", "validation_ir_delta", "confirmation_relative_delta"]].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_soft_exposure_prior",
        name="h242_entry_alpha_soft_exposure_prior",
        summary=summary,
        artifacts={
            "results": str(results_path_out),
            "best_daily": str(best_daily_path),
            "scores": str(scores_path),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "h241_summary": str(h241_summary_path),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "strategy": str(args.strategy),
            "top_k": int(args.top_k),
            "rebalance_every": int(args.rebalance_every),
            "top_m_max": int(args.top_m_max),
            "on_top_m": int(args.on_top_m),
            "off_top_m": int(args.off_top_m),
            "off_threshold_penalty": float(args.off_threshold_penalty),
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
    )


if __name__ == "__main__":
    main()
