"""
H269: narrow breakout-trust current-account compatibility audit.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    add_baseline_deltas,
    assign_entry_thesis_family,
    backtest_row_from_result,
    build_entry_allowed_matrix_from_mask,
    build_entry_row_mask,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
    run_entry_backtest,
)
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H268_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_entry_alpha_breakout_family_trust_compatibility_integration.json"
H266_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_entry_alpha_breakout_intraday_trust_audit.json"
H266_CANDIDATE_CACHE_PATH = ROOT / "artifacts/entry_alpha/h266_candidate_panel_2023_2025.parquet"
H266_LABEL_CACHE_PATH = ROOT / "artifacts/entry_alpha/h266_base_labels_2023_2025.parquet"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
BREAKOUT_FAMILY = "breakout_followthrough"
OPERATIONAL_BASELINE_VARIANT = "operational_sticky_baseline"
SPARSE_CONTROL_VARIANT = "carried_sparse_plus_sticky"
H269_CANDIDATE_VARIANT = "h268_overlay_plus_sticky"
MIN_ALLOWED_ROWS = 150
MIN_CONFIRMATION_ALLOWED_ROWS = 70
MAX_SPARSE_BOOK_RATE_INCREASE = 0.20
MAX_AVG_HOLDINGS_DROP = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H269: narrow breakout-trust current-account compatibility audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h268-summary", type=str, default=str(H268_SUMMARY_PATH))
    parser.add_argument("--h266-summary", type=str, default=str(H266_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=20)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.015)
    parser.add_argument("--candidate-cache", type=str, default=str(H266_CANDIDATE_CACHE_PATH))
    parser.add_argument("--labels-cache", type=str, default=str(H266_LABEL_CACHE_PATH))
    return parser.parse_args()


def _coerce_float(row: pd.Series | dict[str, object], column: str) -> float | None:
    value = pd.to_numeric(row.get(column), errors="coerce")
    return None if pd.isna(value) else float(value)


def _operational_diagnostics(daily: pd.DataFrame, *, top_k: int) -> dict[str, object]:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    mask = phase_mask(
        work,
        ["validation", "confirmation"],
        date_column="execution_date",
        protocol=INTRADAY_RESTART_PROTOCOL,
    )
    scoped = work.loc[mask].copy()
    if scoped.empty:
        return {
            "vc_days": 0,
            "vc_zero_holding_rate": None,
            "vc_single_holding_rate": None,
            "vc_sparse_book_rate": None,
            "vc_avg_num_holdings": None,
            "vc_avg_cash_weight": None,
            "latest_execution_date": None,
            "latest_held_tickers": [],
        }
    return {
        "vc_days": int(len(scoped)),
        "vc_zero_holding_rate": float((pd.to_numeric(scoped["num_holdings"], errors="coerce") <= 0).mean()),
        "vc_single_holding_rate": float((pd.to_numeric(scoped["num_holdings"], errors="coerce") == 1).mean()),
        "vc_sparse_book_rate": float((pd.to_numeric(scoped["num_holdings"], errors="coerce") < int(top_k)).mean()),
        "vc_avg_num_holdings": float(pd.to_numeric(scoped["num_holdings"], errors="coerce").mean()),
        "vc_avg_cash_weight": float(pd.to_numeric(scoped["cash_weight"], errors="coerce").mean()),
        "latest_execution_date": pd.Timestamp(scoped["execution_date"].iloc[-1]).isoformat(),
        "latest_held_tickers": list(scoped["held_tickers"].iloc[-1] or []),
    }


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    for column in [
        "confirmation_relative_delta",
        "overall_relative_delta",
        "confirmation_ir_delta",
        "overall_ir_delta",
        "allowed_rows",
        "confirmation_allowed_rows",
        "vc_sparse_book_rate",
        "vc_avg_num_holdings",
    ]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=[
            "confirmation_relative_delta",
            "overall_relative_delta",
            "confirmation_ir_delta",
            "overall_ir_delta",
            "vc_sparse_book_rate",
            "vc_avg_num_holdings",
            "variant",
        ],
        ascending=[False, False, False, False, True, False, True],
        ignore_index=True,
    )


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 220)
    print("H269: NARROW BREAKOUT-TRUST CURRENT-ACCOUNT COMPATIBILITY")
    print("=" * 220)
    print(
        f"{'variant':<32} {'val_rel':>10} {'2025_rel':>10} {'overall':>10} "
        f"{'val_d_op':>10} {'2025_d_op':>10} {'ov_d_op':>10} {'2025_d_sp':>10} "
        f"{'sparse_vc':>10} {'avg_hlds':>10}"
    )
    print("-" * 220)
    for row in results.itertuples(index=False):
        print(
            f"{str(row.variant):<32} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.overall_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+9.2f}% "
            f"{(row.overall_relative_delta or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return_delta_vs_sparse or 0.0)*100:>+9.2f}% "
            f"{(row.vc_sparse_book_rate or 0.0):>9.3f} "
            f"{(row.vc_avg_num_holdings or 0.0):>9.3f}"
        )


def main() -> None:
    args = parse_args()
    h268_summary_path = Path(args.h268_summary)
    h268_payload = load_summary_payload(h268_summary_path)
    if not bool(h268_payload.get("summary", {}).get("advance_to_h269", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="entry_alpha_breakout_trust_current_account_compatibility",
            name="h269_breakout_trust_current_account_compatibility",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H268 did not clear the family-local compatibility gate",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    best_variant = dict(h268_payload.get("summary", {}).get("best_variant", {}) or {})
    score_column = str(best_variant.get("score_column", "")).strip()
    threshold = _coerce_float(best_variant, "threshold")
    if not score_column or threshold is None:
        raise ValueError("H269 requires the H268 winner score and threshold")

    carried_sparse_contract = dict(h268_payload.get("summary", {}).get("carried_sparse_contract", {}) or {})
    if not carried_sparse_contract:
        raise ValueError("H269 requires the carried sparse contract from H268")

    h266_summary_path = Path(args.h266_summary)
    h266_payload = load_summary_payload(h266_summary_path)
    score_panel = pd.read_parquet(resolve_summary_artifact(h266_summary_path, "scored_panel"))
    if score_column not in score_panel.columns:
        raise ValueError(f"H269 score column missing from H266 scored panel: {score_column}")

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
        candidate_panel_path=Path(args.candidate_cache),
        labels_path=Path(args.labels_cache),
    )
    panel = prepare_entry_research_panel(candidate_panel, labels, protocol=INTRADAY_RESTART_PROTOCOL)
    panel = assign_entry_thesis_family(panel)
    panel = panel.merge(
        score_panel[["time", "ticker", score_column]].copy(),
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    market_dates = pd.to_datetime(inputs.market_inputs.dates)
    market_tickers = list(inputs.market_inputs.tickers)
    hard_on = (
        panel[["time", "activation_state"]]
        .drop_duplicates(subset=["time"])
        .assign(_on=lambda frame: frame["activation_state"].fillna("off").eq("on"))
        .set_index("time")["_on"]
    )
    aligned_hard_mask = np.asarray([bool(hard_on.get(pd.Timestamp(date), True)) for date in market_dates], dtype=bool)

    breakout_mask = panel["entry_thesis_family"].astype(str).eq(BREAKOUT_FAMILY)
    observed_breakout_mask = breakout_mask & panel[score_column].notna()
    gate_pass_mask = pd.to_numeric(panel[score_column], errors="coerce") >= float(threshold)
    sparse_mask = build_entry_row_mask(
        panel,
        top_m=int(carried_sparse_contract["top_m"]),
        min_selection_score=float(carried_sparse_contract["min_selection_score"]),
        min_score_gap=float(carried_sparse_contract["min_score_gap"]),
        require_buyable=True,
    )
    h269_mask = sparse_mask & (~breakout_mask | ~observed_breakout_mask | gate_pass_mask)

    operational_entry_allowed = np.ones((len(market_dates), len(market_tickers)), dtype=bool)
    sparse_entry_allowed = build_entry_allowed_matrix_from_mask(
        panel,
        dates=market_dates,
        tickers=market_tickers,
        mask=sparse_mask,
    )
    h269_entry_allowed = build_entry_allowed_matrix_from_mask(
        panel,
        dates=market_dates,
        tickers=market_tickers,
        mask=h269_mask,
    )

    run_specs = [
        (OPERATIONAL_BASELINE_VARIANT, operational_entry_allowed, pd.Series(True, index=panel.index, dtype=bool)),
        (SPARSE_CONTROL_VARIANT, sparse_entry_allowed, sparse_mask),
        (H269_CANDIDATE_VARIANT, h269_entry_allowed, h269_mask),
    ]
    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    latest_mask_frame = panel[
        ["time", "ticker", "research_phase", "entry_thesis_family", "selection_score", "candidate_pool_rank", "can_buy_next_open", score_column]
    ].copy()
    latest_mask_frame["carried_sparse_contract"] = sparse_mask.astype(bool).to_numpy()
    latest_mask_frame["h269_gate_pass"] = gate_pass_mask.fillna(False).astype(bool).to_numpy()
    latest_mask_frame["h269_overlay_allowed"] = h269_mask.astype(bool).to_numpy()

    for variant, entry_allowed_matrix, row_mask in run_specs:
        result = run_entry_backtest(
            inputs,
            entry_allowed_matrix=entry_allowed_matrix,
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
            top_k=int(args.top_k),
            rebalance_every=int(args.rebalance_every),
            activation_mask=aligned_hard_mask,
            incumbent_score_bonus=float(args.incumbent_score_bonus),
        )
        diagnostics = _operational_diagnostics(result.daily, top_k=int(args.top_k))
        extras = {
            "score_column": score_column,
            "threshold": None if variant == OPERATIONAL_BASELINE_VARIANT else float(threshold),
            "allowed_rows": None if variant == OPERATIONAL_BASELINE_VARIANT else int(pd.Series(row_mask, index=panel.index).sum()),
            "confirmation_allowed_rows": None
            if variant == OPERATIONAL_BASELINE_VARIANT
            else int((pd.Series(row_mask, index=panel.index) & panel["research_phase"].astype(str).eq("confirmation")).sum()),
            "breakout_allowed_rows": None
            if variant == OPERATIONAL_BASELINE_VARIANT
            else int((pd.Series(row_mask, index=panel.index) & breakout_mask).sum()),
            "breakout_observed_allowed_rows": None
            if variant == OPERATIONAL_BASELINE_VARIANT
            else int((pd.Series(row_mask, index=panel.index) & observed_breakout_mask).sum()),
            **diagnostics,
        }
        rows.append(
            backtest_row_from_result(
                variant=variant,
                family="breakout_trust_current_account_compatibility",
                result=result,
                protocol=INTRADAY_RESTART_PROTOCOL,
                extra=extras,
            )
        )
        daily_outputs[variant] = result.daily.copy()

    results = add_baseline_deltas(pd.DataFrame(rows), baseline_variant=OPERATIONAL_BASELINE_VARIANT)
    operational_baseline = results.loc[results["variant"] == OPERATIONAL_BASELINE_VARIANT].iloc[0]
    sparse_control = results.loc[results["variant"] == SPARSE_CONTROL_VARIANT].iloc[0]
    results["overall_relative_delta"] = (
        pd.to_numeric(results["overall_relative_total_return"], errors="coerce")
        - pd.to_numeric(operational_baseline.get("overall_relative_total_return"), errors="coerce")
    )
    results["overall_ir_delta"] = (
        pd.to_numeric(results["overall_information_ratio_annualized"], errors="coerce")
        - pd.to_numeric(operational_baseline.get("overall_information_ratio_annualized"), errors="coerce")
    )
    for metric in [
        "validation_relative_total_return",
        "confirmation_relative_total_return",
        "validation_information_ratio_annualized",
        "confirmation_information_ratio_annualized",
        "overall_relative_total_return",
        "overall_information_ratio_annualized",
    ]:
        results[f"{metric}_delta_vs_sparse"] = (
            pd.to_numeric(results[metric], errors="coerce")
            - pd.to_numeric(sparse_control.get(metric), errors="coerce")
        )

    ordered = _sort_results(results)
    _print_table(ordered)
    candidate_row = results.loc[results["variant"] == H269_CANDIDATE_VARIANT].iloc[0]

    operational_sparse_rate = _coerce_float(operational_baseline, "vc_sparse_book_rate")
    candidate_sparse_rate = _coerce_float(candidate_row, "vc_sparse_book_rate")
    operational_avg_holdings = _coerce_float(operational_baseline, "vc_avg_num_holdings")
    candidate_avg_holdings = _coerce_float(candidate_row, "vc_avg_num_holdings")
    coverage_ok = bool(
        (_coerce_float(candidate_row, "allowed_rows") or 0.0) >= float(MIN_ALLOWED_ROWS)
        and (_coerce_float(candidate_row, "confirmation_allowed_rows") or 0.0) >= float(MIN_CONFIRMATION_ALLOWED_ROWS)
    )
    narrowness_ok = bool(
        operational_sparse_rate is not None
        and candidate_sparse_rate is not None
        and operational_avg_holdings is not None
        and candidate_avg_holdings is not None
        and float(candidate_sparse_rate) <= float(operational_sparse_rate) + float(MAX_SPARSE_BOOK_RATE_INCREASE)
        and float(candidate_avg_holdings) >= float(operational_avg_holdings) - float(MAX_AVG_HOLDINGS_DROP)
    )
    passed = bool(
        coverage_ok
        and narrowness_ok
        and (_coerce_float(candidate_row, "validation_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(candidate_row, "confirmation_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(candidate_row, "overall_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(candidate_row, "validation_relative_total_return_delta_vs_sparse") or float("-inf")) > 0.0
        and (_coerce_float(candidate_row, "confirmation_relative_total_return_delta_vs_sparse") or float("-inf")) > 0.0
        and (_coerce_float(candidate_row, "overall_relative_total_return_delta_vs_sparse") or float("-inf")) > 0.0
    )
    mixed = bool(
        not passed
        and coverage_ok
        and (_coerce_float(candidate_row, "confirmation_relative_total_return_delta_vs_sparse") or float("-inf")) > 0.0
        and (_coerce_float(candidate_row, "overall_relative_total_return_delta_vs_sparse") or float("-inf")) > 0.0
        and narrowness_ok
    )
    decision = "PASSED" if passed else ("MIXED" if mixed else "FAILED")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h269_breakout_trust_current_account_compatibility_results.parquet"
    best_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h269_breakout_trust_current_account_compatibility_best_daily.parquet"
    baseline_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h269_breakout_trust_current_account_compatibility_baseline_daily.parquet"
    latest_panel_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h269_breakout_trust_current_account_compatibility_panel.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[H269_CANDIDATE_VARIANT].to_parquet(best_daily_path, index=False)
    daily_outputs[OPERATIONAL_BASELINE_VARIANT].to_parquet(baseline_daily_path, index=False)
    latest_mask_frame.to_parquet(latest_panel_path, index=False)

    summary = {
        "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
        "decision": decision,
        "advance_to_h270": bool(passed),
        "operational_baseline": operational_baseline.to_dict(),
        "sparse_control": sparse_control.to_dict(),
        "candidate_variant": candidate_row.to_dict(),
        "score_column": score_column,
        "threshold": float(threshold),
        "carried_sparse_contract": carried_sparse_contract,
        "coverage_guard": {
            "min_allowed_rows": int(MIN_ALLOWED_ROWS),
            "min_confirmation_allowed_rows": int(MIN_CONFIRMATION_ALLOWED_ROWS),
        },
        "narrowness_guard": {
            "max_sparse_book_rate_increase": float(MAX_SPARSE_BOOK_RATE_INCREASE),
            "max_avg_holdings_drop": float(MAX_AVG_HOLDINGS_DROP),
        },
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_breakout_trust_current_account_compatibility",
        name="h269_breakout_trust_current_account_compatibility",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "baseline_daily": str(baseline_daily_path),
            "panel": str(latest_panel_path),
        },
        metadata={
            "h268_summary": str(h268_summary_path),
            "h266_summary": str(h266_summary_path),
            "candidate_cache": str(args.candidate_cache),
            "labels_cache": str(args.labels_cache),
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "strategy": str(args.strategy),
            "top_k": int(args.top_k),
            "rebalance_every": int(args.rebalance_every),
            "top_m_max": int(args.top_m_max),
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
        },
    )


if __name__ == "__main__":
    main()
