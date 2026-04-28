"""
H358 - Order-Pressure Portfolio / Tradability Audit.

Question:
- H356/H357 showed CafeF posted order-volume pressure is a strong standalone
  and full-library-residual signal. Does it still help when expressed as an
  executable top-5 portfolio under the shared tradability contract?

Design:
- Exclude 2026 entirely.
- Merge the H356 `order_volume_ratio_rank` feature onto the full RL matrix.
- Fill missing order-pressure rows neutrally through the existing deterministic
  score path.
- Compare executable top-5 equal-weight, rebalance-5 portfolios:
  1. full_library baseline,
  2. full_library + order_pressure,
  3. order_pressure only diagnostic.

Decision ladder:
- PASSED: full_library + order_pressure passes the locked additive portfolio
  gate and does not materially worsen execution health.
- MIXED: portfolio returns improve but execution health is worse, or validation
  improvement is too small for publication.
- FAILED: validation/confirmation portfolio relevance does not survive.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_market_rules import required_holding_age_for_sell

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes
from src.deterministic_portfolio import RESERVED_COLUMNS, compute_strategy_scores, resolve_strategy_columns
from src.repo_paths import artifact_path, data_path
from src.research_protocol import DEFAULT_PROTOCOL, phase_mask
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import compute_phase_portfolio_summary, load_research_bundle, run_selector_candidate


MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = artifact_path("portfolio_baselines")

ORDER_FEATURE = "order_volume_ratio_rank"
START_YEAR = 2015
END_YEAR = 2025
TURNOVER_DELTA_LIMIT = 0.03
CASH_DELTA_LIMIT = 0.02
BLOCKED_BUY_DELTA_LIMIT = 0.25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--order-stats", type=str, default=str(ORDER_STATS_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _ratio(left: pd.Series, right: pd.Series) -> pd.Series:
    left_num = pd.to_numeric(left, errors="coerce")
    right_num = pd.to_numeric(right, errors="coerce")
    denom = left_num + right_num
    return (left_num - right_num).div(denom.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)


def _load_order_pressure(order_stats_path: Path, *, start_year: int, end_year: int) -> pd.DataFrame:
    order = pd.read_parquet(
        order_stats_path,
        columns=["ticker", "date", "buy_order_volume", "sell_order_volume"],
    ).copy()
    order = order.rename(columns={"date": "time"})
    order["time"] = pd.to_datetime(order["time"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].astype(str).str.upper()
    order = order.loc[order["time"].dt.year.between(int(start_year), int(end_year))].dropna(subset=["time", "ticker"])
    order["order_volume_ratio"] = _ratio(order["buy_order_volume"], order["sell_order_volume"])
    order[ORDER_FEATURE] = (
        pd.to_numeric(order["order_volume_ratio"], errors="coerce")
        .groupby(order["time"], sort=False)
        .rank(method="average", pct=True, ascending=True)
    )
    return order[["time", "ticker", ORDER_FEATURE]].dropna(subset=[ORDER_FEATURE])


def _phase_execution_summary(daily: pd.DataFrame) -> dict[str, dict[str, object]]:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    phases = compute_phase_portfolio_summary(work, protocol=DEFAULT_PROTOCOL)
    out: dict[str, dict[str, object]] = {}
    for phase, phase_summary in phases.items():
        scoped = work.loc[phase_mask(work, phase, date_column="execution_date", protocol=DEFAULT_PROTOCOL)]
        days = max(int(len(scoped)), 1)
        out[phase] = {
            **phase_summary,
            "blocked_buy_events": int(pd.to_numeric(scoped["blocked_buy_count"], errors="coerce").fillna(0).sum()),
            "blocked_sell_events": int(pd.to_numeric(scoped["blocked_sell_count"], errors="coerce").fillna(0).sum()),
            "capacity_clipped_events": int(pd.to_numeric(scoped["capacity_clipped_count"], errors="coerce").fillna(0).sum()),
            "blocked_buy_events_per_day": float(
                pd.to_numeric(scoped["blocked_buy_count"], errors="coerce").fillna(0).sum() / days
            ),
            "avg_num_holdings": _safe_float(pd.to_numeric(scoped["num_holdings"], errors="coerce").mean())
            if not scoped.empty else None,
            "avg_selected_count": _safe_float(pd.to_numeric(scoped["selected_count"], errors="coerce").mean())
            if not scoped.empty else None,
        }
    return out


def _flatten_phase_rows(
    strategy_name: str,
    signal_columns: list[str],
    phase_summary: dict[str, dict[str, object]],
    overall_summary: dict[str, object],
) -> dict[str, object]:
    row: dict[str, object] = {
        "strategy_name": strategy_name,
        "signal_columns": list(signal_columns),
        "overall_relative_total_return": overall_summary.get("relative_total_return"),
        "overall_information_ratio_annualized": overall_summary.get("information_ratio_annualized"),
        "overall_avg_daily_turnover": overall_summary.get("avg_daily_turnover"),
        "overall_avg_cash_weight": overall_summary.get("avg_cash_weight"),
        "overall_blocked_buy_events": overall_summary.get("blocked_buy_events"),
        "overall_blocked_sell_events": overall_summary.get("blocked_sell_events"),
    }
    for phase in ("dev", "validation", "confirmation"):
        phase_row = phase_summary[phase]
        prefix = f"{phase}_"
        row[prefix + "relative_total_return"] = phase_row["relative_total_return"]
        row[prefix + "information_ratio_annualized"] = phase_row["information_ratio_annualized"]
        row[prefix + "avg_daily_turnover"] = phase_row["avg_daily_turnover"]
        row[prefix + "avg_cash_weight"] = phase_row["avg_cash_weight"]
        row[prefix + "blocked_buy_events"] = phase_row["blocked_buy_events"]
        row[prefix + "blocked_sell_events"] = phase_row["blocked_sell_events"]
        row[prefix + "blocked_buy_events_per_day"] = phase_row["blocked_buy_events_per_day"]
        row[prefix + "avg_num_holdings"] = phase_row["avg_num_holdings"]
    return row


def _execution_health_flags(candidate: pd.Series, baseline: pd.Series) -> dict[str, object]:
    val_turnover_delta = (_safe_float(candidate.get("validation_avg_daily_turnover")) or 0.0) - (
        _safe_float(baseline.get("validation_avg_daily_turnover")) or 0.0
    )
    conf_turnover_delta = (_safe_float(candidate.get("confirmation_avg_daily_turnover")) or 0.0) - (
        _safe_float(baseline.get("confirmation_avg_daily_turnover")) or 0.0
    )
    val_cash_delta = (_safe_float(candidate.get("validation_avg_cash_weight")) or 0.0) - (
        _safe_float(baseline.get("validation_avg_cash_weight")) or 0.0
    )
    conf_cash_delta = (_safe_float(candidate.get("confirmation_avg_cash_weight")) or 0.0) - (
        _safe_float(baseline.get("confirmation_avg_cash_weight")) or 0.0
    )
    val_blocked_delta = (_safe_float(candidate.get("validation_blocked_buy_events_per_day")) or 0.0) - (
        _safe_float(baseline.get("validation_blocked_buy_events_per_day")) or 0.0
    )
    conf_blocked_delta = (_safe_float(candidate.get("confirmation_blocked_buy_events_per_day")) or 0.0) - (
        _safe_float(baseline.get("confirmation_blocked_buy_events_per_day")) or 0.0
    )
    return {
        "validation_turnover_delta": val_turnover_delta,
        "confirmation_turnover_delta": conf_turnover_delta,
        "validation_cash_delta": val_cash_delta,
        "confirmation_cash_delta": conf_cash_delta,
        "validation_blocked_buy_events_per_day_delta": val_blocked_delta,
        "confirmation_blocked_buy_events_per_day_delta": conf_blocked_delta,
        "passes_execution_health": bool(
            val_turnover_delta <= TURNOVER_DELTA_LIMIT
            and conf_turnover_delta <= TURNOVER_DELTA_LIMIT
            and val_cash_delta <= CASH_DELTA_LIMIT
            and conf_cash_delta <= CASH_DELTA_LIMIT
            and val_blocked_delta <= BLOCKED_BUY_DELTA_LIMIT
            and conf_blocked_delta <= BLOCKED_BUY_DELTA_LIMIT
        ),
    }


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 176)
    print("H358: ORDER-PRESSURE PORTFOLIO / TRADABILITY AUDIT")
    print("=" * 176)
    print(
        f"{'strategy':<42} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'turn_d':>8} {'cash_d':>8} {'verdict':>8}"
    )
    print("-" * 176)
    for row in results.itertuples(index=False):
        print(
            f"{row.strategy_name:<42} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(getattr(row, 'validation_relative_delta', 0.0) or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{getattr(row, 'validation_ir_delta', float('nan')) if getattr(row, 'validation_ir_delta', None) is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(getattr(row, 'confirmation_relative_delta', 0.0) or 0.0)*100:>+8.2f}% "
            f"{getattr(row, 'validation_turnover_delta', 0.0) or 0.0:>+8.4f} "
            f"{getattr(row, 'validation_cash_delta', 0.0) or 0.0:>+8.4f} "
            f"{str(row.verdict):>8}"
        )


def main() -> None:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    protocol = DEFAULT_PROTOCOL
    fee_leg = float(args.round_trip_cost) / 2.0
    required_holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))

    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    matrix = bundle.matrix.copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    order = _load_order_pressure(Path(args.order_stats), start_year=int(args.start_year), end_year=int(args.end_year))
    merged = matrix.merge(order, on=["time", "ticker"], how="left", validate="one_to_one")
    order_coverage = {
        "matrix_rows": int(len(matrix)),
        "order_feature_rows": int(merged[ORDER_FEATURE].notna().sum()),
        "order_feature_coverage_pct": float(merged[ORDER_FEATURE].notna().mean() * 100.0) if len(merged) else 0.0,
        "dates_with_order_feature": int(merged.loc[merged[ORDER_FEATURE].notna(), "time"].nunique()),
        "tickers_with_order_feature": int(merged.loc[merged[ORDER_FEATURE].notna(), "ticker"].nunique()),
    }

    full_library_columns = resolve_strategy_columns(matrix.columns.tolist(), "full_library")
    strategies = {
        "full_library_baseline": list(full_library_columns),
        "full_library_plus_order_pressure": list(full_library_columns) + [ORDER_FEATURE],
        "order_pressure_only": [ORDER_FEATURE],
    }
    scored = compute_strategy_scores(merged, strategies)

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for strategy_name, signal_columns in strategies.items():
        result = run_selector_candidate(
            scored_frame=scored,
            bundle=bundle,
            strategy_name=strategy_name,
            signal_columns=list(signal_columns),
            start_year=int(args.start_year),
            end_year=int(args.end_year),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            required_holding_age=int(required_holding_age),
        )
        phase_summary = _phase_execution_summary(result.daily)
        rows.append(_flatten_phase_rows(strategy_name, list(signal_columns), phase_summary, result.summary))
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    candidate_name = "full_library_plus_order_pressure"
    for idx, row in results.iterrows():
        if row["strategy_name"] == "full_library_baseline":
            results.loc[idx, "validation_relative_delta"] = 0.0
            results.loc[idx, "validation_ir_delta"] = 0.0
            results.loc[idx, "confirmation_relative_delta"] = 0.0
            results.loc[idx, "confirmation_ir_delta"] = 0.0
            results.loc[idx, "validation_turnover_delta"] = 0.0
            results.loc[idx, "confirmation_turnover_delta"] = 0.0
            results.loc[idx, "validation_cash_delta"] = 0.0
            results.loc[idx, "confirmation_cash_delta"] = 0.0
            results.loc[idx, "passes_execution_health"] = True
            results.loc[idx, "verdict"] = "BASELINE"
            continue
        deltas = additive_candidate_deltas(row, baseline)
        health = _execution_health_flags(row, baseline)
        for key, value in {**deltas, **health}.items():
            results.loc[idx, key] = value
        portfolio_pass = additive_candidate_passes(row, baseline)
        health_pass = bool(health["passes_execution_health"])
        if row["strategy_name"] == candidate_name and portfolio_pass and health_pass:
            verdict = "PASSED"
        elif row["strategy_name"] == candidate_name and (
            (deltas["validation_relative_delta"] > 0.0 and deltas["confirmation_relative_delta"] >= 0.0)
            or portfolio_pass
        ):
            verdict = "MIXED"
        else:
            verdict = "FAILED" if row["strategy_name"] == candidate_name else "DIAGNOSTIC"
        results.loc[idx, "portfolio_gate_pass"] = bool(portfolio_pass)
        results.loc[idx, "verdict"] = verdict

    candidate = results.loc[results["strategy_name"] == candidate_name].iloc[0]
    final_verdict = str(candidate["verdict"])
    if final_verdict == "PASSED":
        branch_decision = (
            "Order pressure improves the executable full-library portfolio without materially worsening "
            "turnover, cash drag, or blocked-buy pressure. Advance to publication design."
        )
    elif final_verdict == "MIXED":
        branch_decision = (
            "Order pressure has some executable relevance, but the portfolio/tradability gate is not clean "
            "enough for immediate publication."
        )
    else:
        branch_decision = (
            "Order pressure does not survive the executable portfolio/tradability audit strongly enough "
            "for publication under the current contract."
        )

    results = results.sort_values(
        by=["strategy_name"],
        ascending=True,
        ignore_index=True,
    )
    _print_table(results)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h358_order_pressure_portfolio_results.parquet"
    candidate_daily_path = OUT_DIR / f"{ts}_h358_order_pressure_portfolio_candidate_daily.parquet"
    baseline_daily_path = OUT_DIR / f"{ts}_h358_order_pressure_portfolio_baseline_daily.parquet"
    details_path = artifact_path("run_summaries") / f"{ts}_h358_order_pressure_portfolio_tradability_audit_details.json"

    results.to_parquet(results_path, index=False)
    daily_outputs[candidate_name].to_parquet(candidate_daily_path, index=False)
    daily_outputs["full_library_baseline"].to_parquet(baseline_daily_path, index=False)

    summary = {
        "verdict": final_verdict,
        "protocol": protocol.describe(),
        "order_feature": ORDER_FEATURE,
        "order_coverage": order_coverage,
        "baseline": baseline.to_dict(),
        "candidate": candidate.to_dict(),
        "tested_strategies": results.to_dict("records"),
        "decision_thresholds": {
            "portfolio_gate": "additive_candidate_passes default H200/H207 thresholds",
            "validation_turnover_delta_limit": TURNOVER_DELTA_LIMIT,
            "confirmation_turnover_delta_limit": TURNOVER_DELTA_LIMIT,
            "validation_cash_delta_limit": CASH_DELTA_LIMIT,
            "confirmation_cash_delta_limit": CASH_DELTA_LIMIT,
            "blocked_buy_events_per_day_delta_limit": BLOCKED_BUY_DELTA_LIMIT,
        },
        "branch_decision": branch_decision,
        "next_step": {
            "PASSED": "Design and verify the published order-pressure feature artifact before updating consumer docs.",
            "MIXED": "Keep C16 as an unpublished candidate; inspect whether learned weighting or a smaller state-scope is justified.",
            "FAILED": "Do not publish order pressure under the current executable portfolio contract.",
        }[final_verdict],
    }
    details_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_order_pressure_portfolio_tradability_audit",
        name="h358_order_pressure_portfolio_tradability_audit",
        summary=summary,
        artifacts={
            "results": results_path,
            "candidate_daily": candidate_daily_path,
            "baseline_daily": baseline_daily_path,
            "details": details_path,
            "matrix": Path(args.matrix),
            "order_stats": Path(args.order_stats),
            "tradability": Path(args.tradability),
        },
        metadata={
            "signal": "H358",
            "family": "order_pressure",
            "protocol": protocol.describe(),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
        },
    )
    print(f"Order coverage={order_coverage['order_feature_coverage_pct']:.2f}%", flush=True)
    print(f"VERDICT: {final_verdict}", flush=True)
    print(f"summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
