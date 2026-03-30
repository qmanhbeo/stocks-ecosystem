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
from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes, resolve_summary_artifact
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    LATEST_H242_SUMMARY_PATH,
    backtest_row_from_result,
    build_entry_allowed_matrix_from_score,
    build_soft_exposure_scale,
    build_soft_threshold_by_date,
    build_soft_top_m_by_date,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
    run_entry_backtest,
)
from src.research_protocol import DEFAULT_PROTOCOL, phase_mask
from src.run_summary import write_run_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H243: pseudo-live compatibility check for the best entry-alpha variant")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h242-summary", type=str, default=str(LATEST_H242_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=20)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.015)
    return parser.parse_args()


def _variant_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 188)
    print("H243: ENTRY ALPHA PSEUDO-LIVE COMPATIBILITY")
    print("=" * 188)
    print(
        f"{'variant':<34} {'val_rel':>10} {'2025_rel':>10} {'2026+_rel':>10} "
        f"{'val_IR':>8} {'2025_IR':>8} {'2026+_IR':>8} {'promote':>8}"
    )
    print("-" * 188)
    for row in results.itertuples(index=False):
        print(
            f"{str(row.variant):<34} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.forward_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.confirmation_information_ratio_annualized if row.confirmation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.forward_information_ratio_annualized if row.forward_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{str(bool(row.promoted)):>8}"
        )


def _operational_diagnostics(daily: pd.DataFrame, *, top_k: int) -> dict[str, object]:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    mask = phase_mask(work, ["confirmation", "forward"], date_column="execution_date", protocol=DEFAULT_PROTOCOL)
    scoped = work.loc[mask].copy()
    if scoped.empty:
        return {
            "days": 0,
            "zero_holding_rate": None,
            "single_holding_rate": None,
            "sparse_book_rate": None,
            "avg_num_holdings": None,
            "avg_cash_weight": None,
            "latest_execution_date": None,
            "latest_held_tickers": [],
        }
    return {
        "days": int(len(scoped)),
        "zero_holding_rate": float((pd.to_numeric(scoped["num_holdings"], errors="coerce") <= 0).mean()),
        "single_holding_rate": float((pd.to_numeric(scoped["num_holdings"], errors="coerce") == 1).mean()),
        "sparse_book_rate": float((pd.to_numeric(scoped["num_holdings"], errors="coerce") < int(top_k)).mean()),
        "avg_num_holdings": float(pd.to_numeric(scoped["num_holdings"], errors="coerce").mean()),
        "avg_cash_weight": float(pd.to_numeric(scoped["cash_weight"], errors="coerce").mean()),
        "latest_execution_date": pd.Timestamp(scoped["execution_date"].iloc[-1]).isoformat(),
        "latest_held_tickers": list(scoped["held_tickers"].iloc[-1] or []),
    }


def main() -> None:
    args = parse_args()
    h242_summary_path = Path(args.h242_summary)
    h242_results_path = resolve_summary_artifact(h242_summary_path, "results")
    scores_path = resolve_summary_artifact(h242_summary_path, "scores")
    h242_results = pd.read_parquet(h242_results_path)
    chosen = h242_results.iloc[0]
    if str(chosen["variant"]) == "entry_model_only":
        chosen = h242_results.loc[h242_results["variant"] != "entry_model_only"].iloc[0]

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
    score_column = str(chosen["score_column"])
    if score_column not in score_panel.columns:
        raise ValueError(f"Entry score artifact does not contain {score_column!r}")
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
    base_threshold = float(chosen["threshold"])
    on_top_m = int(chosen.get("on_top_m", 10))
    off_top_m = int(chosen.get("off_top_m", 2))
    off_threshold_penalty = float(chosen.get("off_threshold_penalty", 0.08))
    soft_threshold_by_date = build_soft_threshold_by_date(
        base_threshold=base_threshold,
        exposure_scale=exposure_scale,
        off_penalty=off_threshold_penalty,
    )
    soft_top_m_by_date = build_soft_top_m_by_date(
        on_top_m=on_top_m,
        off_top_m=off_top_m,
        exposure_scale=exposure_scale,
    )

    base_entry_matrix = build_entry_allowed_matrix_from_score(
        panel,
        dates=market_dates,
        tickers=inputs.market_inputs.tickers,
        score_column=score_column,
        top_m=on_top_m,
        min_score=base_threshold,
        require_buyable=True,
    )
    soft_threshold_matrix = build_entry_allowed_matrix_from_score(
        panel,
        dates=market_dates,
        tickers=inputs.market_inputs.tickers,
        score_column=score_column,
        top_m=on_top_m,
        threshold_by_date=soft_threshold_by_date,
        require_buyable=True,
    )
    soft_breadth_matrix = build_entry_allowed_matrix_from_score(
        panel,
        dates=market_dates,
        tickers=inputs.market_inputs.tickers,
        score_column=score_column,
        top_m=on_top_m,
        min_score=base_threshold,
        top_m_by_date=soft_top_m_by_date,
        require_buyable=True,
    )

    chosen_variant = str(chosen["variant"])
    if chosen_variant == "entry_model_only":
        chosen_matrix = base_entry_matrix
        chosen_activation_scale = None
        chosen_activation_mask = None
    elif chosen_variant == "entry_model_soft_threshold":
        chosen_matrix = soft_threshold_matrix
        chosen_activation_scale = None
        chosen_activation_mask = None
    elif chosen_variant == "entry_model_soft_breadth":
        chosen_matrix = soft_breadth_matrix
        chosen_activation_scale = None
        chosen_activation_mask = None
    elif chosen_variant == "entry_model_soft_weights":
        chosen_matrix = base_entry_matrix
        chosen_activation_scale = aligned_soft_scale
        chosen_activation_mask = None
    elif chosen_variant == "entry_model_hard_veto":
        chosen_matrix = base_entry_matrix
        chosen_activation_scale = None
        chosen_activation_mask = aligned_hard_mask
    else:
        raise ValueError(f"Unsupported H242 variant {chosen_variant!r}")

    current_sticky = run_entry_backtest(
        inputs,
        entry_allowed_matrix=np.ones_like(base_entry_matrix, dtype=bool),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        activation_mask=aligned_hard_mask,
        incumbent_score_bonus=float(args.incumbent_score_bonus),
    )
    chosen_result = run_entry_backtest(
        inputs,
        entry_allowed_matrix=chosen_matrix,
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        activation_scale=chosen_activation_scale,
        activation_mask=chosen_activation_mask,
    )
    compatibility_result = run_entry_backtest(
        inputs,
        entry_allowed_matrix=chosen_matrix,
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        activation_mask=aligned_hard_mask,
        incumbent_score_bonus=float(args.incumbent_score_bonus),
    )
    parity_result = run_entry_backtest(
        inputs,
        entry_allowed_matrix=chosen_matrix,
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        activation_scale=chosen_activation_scale,
        activation_mask=chosen_activation_mask,
    )
    deterministic_parity = bool(chosen_result.daily.equals(parity_result.daily))

    rows = [
        backtest_row_from_result(
            variant="current_sticky_full_library",
            family="compatibility_control",
            result=current_sticky,
            extra={"source_variant": None, "deterministic_parity": True},
        ),
        backtest_row_from_result(
            variant="best_entry_variant",
            family="entry_alpha",
            result=chosen_result,
            extra={"source_variant": chosen_variant, "deterministic_parity": deterministic_parity},
        ),
        backtest_row_from_result(
            variant="best_entry_variant_plus_sticky",
            family="entry_alpha_plus_sticky",
            result=compatibility_result,
            extra={"source_variant": chosen_variant, "deterministic_parity": True},
        ),
    ]
    results = pd.DataFrame(rows)
    baseline = results.loc[results["variant"] == "current_sticky_full_library"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = (
            False
            if row["variant"] == "current_sticky_full_library"
            else additive_candidate_passes(row, baseline)
        )
    results = results.sort_values(
        by=[
            "promoted",
            "confirmation_relative_delta",
            "forward_relative_total_return",
            "forward_information_ratio_annualized",
            "variant",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    _variant_table(results)

    latest_time = pd.Timestamp(panel["time"].max())
    latest_frame = panel.loc[panel["time"] == latest_time].copy()
    latest_candidates = latest_frame[
        ["time", "ticker", "selection_score", "candidate_pool_rank", "can_buy_next_open", "activation_state", "activation_rel2", score_column]
    ].copy()
    if chosen_variant == "entry_model_soft_threshold":
        latest_allowed = build_entry_allowed_matrix_from_score(
            latest_frame,
            dates=[latest_time],
            tickers=latest_candidates["ticker"].tolist(),
            score_column=score_column,
            top_m=on_top_m,
            threshold_by_date={latest_time: soft_threshold_by_date[pd.Timestamp(latest_time)]},
            require_buyable=True,
        )[0]
    elif chosen_variant == "entry_model_soft_breadth":
        latest_allowed = build_entry_allowed_matrix_from_score(
            latest_frame,
            dates=[latest_time],
            tickers=latest_candidates["ticker"].tolist(),
            score_column=score_column,
            top_m=on_top_m,
            min_score=base_threshold,
            top_m_by_date={latest_time: soft_top_m_by_date[pd.Timestamp(latest_time)]},
            require_buyable=True,
        )[0]
    else:
        latest_allowed = build_entry_allowed_matrix_from_score(
            latest_frame,
            dates=[latest_time],
            tickers=latest_candidates["ticker"].tolist(),
            score_column=score_column,
            top_m=on_top_m,
            min_score=base_threshold,
            require_buyable=True,
        )[0]
    latest_candidates["entry_allowed_best_variant"] = latest_allowed
    latest_candidates["date_activation_blocked"] = bool(
        chosen_variant == "entry_model_hard_veto"
        and not bool(hard_on.get(pd.Timestamp(latest_time), True))
    )
    latest_candidates["effective_entry_allowed"] = (
        latest_candidates["entry_allowed_best_variant"].astype(bool)
        & ~latest_candidates["date_activation_blocked"].astype(bool)
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h243_entry_alpha_live_compatibility_results.parquet"
    best_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h243_entry_alpha_live_compatibility_best_daily.parquet"
    candidate_snapshot_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h243_entry_alpha_live_compatibility_latest_candidates.parquet"
    results.to_parquet(results_path, index=False)
    compatibility_result.daily.to_parquet(best_daily_path, index=False)
    latest_candidates.to_parquet(candidate_snapshot_path, index=False)

    summary = {
        "h242_best_variant": chosen.to_dict(),
        "current_sticky_full_library": results.loc[results["variant"] == "current_sticky_full_library"].iloc[0].to_dict(),
        "best_entry_variant": results.loc[results["variant"] == "best_entry_variant"].iloc[0].to_dict(),
        "best_entry_variant_plus_sticky": results.loc[results["variant"] == "best_entry_variant_plus_sticky"].iloc[0].to_dict(),
        "chosen_variant_operational_diagnostics": _operational_diagnostics(chosen_result.daily, top_k=int(args.top_k)),
        "compatibility_variant_operational_diagnostics": _operational_diagnostics(compatibility_result.daily, top_k=int(args.top_k)),
        "deterministic_parity": deterministic_parity,
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_live_compatibility",
        name="h243_entry_alpha_live_compatibility",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "latest_candidates": str(candidate_snapshot_path),
            "scores": str(scores_path),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "h242_summary": str(h242_summary_path),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "strategy": str(args.strategy),
            "top_k": int(args.top_k),
            "rebalance_every": int(args.rebalance_every),
            "top_m_max": int(args.top_m_max),
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
    )


if __name__ == "__main__":
    main()
