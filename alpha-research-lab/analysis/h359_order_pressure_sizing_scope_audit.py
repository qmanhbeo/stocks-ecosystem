"""
H359 - Order-Pressure Sizing / State-Scope Audit.

Question:
- H358 showed executable portfolio relevance for C16, but the equal feature
  addition narrowly failed the validation cash-drag health gate. Can one
  bounded smaller-weight or tradable-state-scoped variant keep the portfolio
  uplift without that execution-health breach?

Design:
- Exclude 2026 entirely.
- Reuse the H358 executable portfolio contract.
- Test only four predeclared variants:
  1. order weight 0.025,
  2. order weight 0.050,
  3. H358-equivalent order weight 1/14 only where the row is buyable next open,
  4. order weight 0.050 only where the row is buyable next open.

Decision ladder:
- PASSED: at least one variant passes the locked additive portfolio gate and
  H358 execution-health gate.
- MIXED: a variant improves validation and confirmation but still misses
  execution health.
- FAILED: no bounded variant keeps executable relevance.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys
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

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes
from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns
from src.repo_paths import artifact_path, data_path
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import load_research_bundle, run_selector_candidate

from h358_order_pressure_portfolio_tradability_audit import (
    ORDER_FEATURE,
    _execution_health_flags,
    _flatten_phase_rows,
    _load_order_pressure,
    _phase_execution_summary,
)


MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = artifact_path("portfolio_baselines")
START_YEAR = 2015
END_YEAR = 2025
H358_EQUIVALENT_WEIGHT = 1.0 / 14.0


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


def _blend_score(base: pd.Series, order: pd.Series, *, weight: float, mask: pd.Series | None = None) -> pd.Series:
    blended = ((1.0 - float(weight)) * base + float(weight) * order).clip(0.0, 1.0)
    if mask is None:
        return blended.astype(float)
    scoped = pd.Series(mask, index=base.index).fillna(False).astype(bool)
    out = base.copy()
    out.loc[scoped] = blended.loc[scoped]
    return out.astype(float)


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 180)
    print("H359: ORDER-PRESSURE SIZING / STATE-SCOPE AUDIT")
    print("=" * 180)
    print(
        f"{'strategy':<46} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'cash_d':>8} {'health':>8} {'verdict':>8}"
    )
    print("-" * 180)
    for row in results.itertuples(index=False):
        print(
            f"{row.strategy_name:<46} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(getattr(row, 'validation_relative_delta', 0.0) or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{getattr(row, 'validation_ir_delta', float('nan')) if getattr(row, 'validation_ir_delta', None) is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(getattr(row, 'confirmation_relative_delta', 0.0) or 0.0)*100:>+8.2f}% "
            f"{getattr(row, 'validation_cash_delta', 0.0) or 0.0:>+8.4f} "
            f"{str(bool(getattr(row, 'passes_execution_health', False))):>8} "
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
    full_library_columns = resolve_strategy_columns(matrix.columns.tolist(), "full_library")

    base_scored = compute_strategy_scores(
        merged,
        {
            "full_library_baseline": list(full_library_columns),
            "order_pressure_only": [ORDER_FEATURE],
        },
    )
    tradability = bundle.tradability[["time", "ticker", "can_buy_next_open"]].copy()
    tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce").dt.normalize()
    tradability["ticker"] = tradability["ticker"].astype(str).str.upper()
    base_scored = base_scored.merge(tradability, on=["time", "ticker"], how="left", validate="one_to_one")
    buyable = base_scored["can_buy_next_open"].fillna(False).astype(bool)
    base = base_scored["score__full_library_baseline"]
    order_score = base_scored["score__order_pressure_only"]

    scored = base_scored[["time", "ticker", "actual"]].copy()
    variants: dict[str, dict[str, object]] = {
        "full_library_baseline": {"columns": list(full_library_columns), "kind": "baseline"},
        "order_w0025": {"weight": 0.025, "scoped": False},
        "order_w0050": {"weight": 0.050, "scoped": False},
        "order_w0071_buyable": {"weight": H358_EQUIVALENT_WEIGHT, "scoped": True},
        "order_w0050_buyable": {"weight": 0.050, "scoped": True},
    }
    scored["score__full_library_baseline"] = base
    for name, spec in variants.items():
        if name == "full_library_baseline":
            continue
        scored[f"score__{name}"] = _blend_score(
            base,
            order_score,
            weight=float(spec["weight"]),
            mask=buyable if bool(spec["scoped"]) else None,
        )

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for strategy_name, spec in variants.items():
        signal_columns = list(full_library_columns) if strategy_name == "full_library_baseline" else [f"blended::{strategy_name}"]
        result = run_selector_candidate(
            scored_frame=scored,
            bundle=bundle,
            strategy_name=strategy_name,
            signal_columns=signal_columns,
            start_year=int(args.start_year),
            end_year=int(args.end_year),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            required_holding_age=int(required_holding_age),
        )
        phase_summary = _phase_execution_summary(result.daily)
        row = _flatten_phase_rows(strategy_name, signal_columns, phase_summary, result.summary)
        row["variant_spec"] = spec
        rows.append(row)
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    for idx, row in results.iterrows():
        if row["strategy_name"] == "full_library_baseline":
            results.loc[idx, "validation_relative_delta"] = 0.0
            results.loc[idx, "validation_ir_delta"] = 0.0
            results.loc[idx, "confirmation_relative_delta"] = 0.0
            results.loc[idx, "confirmation_ir_delta"] = 0.0
            results.loc[idx, "validation_cash_delta"] = 0.0
            results.loc[idx, "confirmation_cash_delta"] = 0.0
            results.loc[idx, "passes_execution_health"] = True
            results.loc[idx, "portfolio_gate_pass"] = False
            results.loc[idx, "verdict"] = "BASELINE"
            continue
        deltas = additive_candidate_deltas(row, baseline)
        health = _execution_health_flags(row, baseline)
        for key, value in {**deltas, **health}.items():
            results.loc[idx, key] = value
        portfolio_pass = additive_candidate_passes(row, baseline)
        health_pass = bool(health["passes_execution_health"])
        if portfolio_pass and health_pass:
            verdict = "PASSED"
        elif (
            (deltas["validation_relative_delta"] > 0.0 and deltas["confirmation_relative_delta"] >= 0.0)
            or portfolio_pass
        ):
            verdict = "MIXED"
        else:
            verdict = "FAILED"
        results.loc[idx, "portfolio_gate_pass"] = bool(portfolio_pass)
        results.loc[idx, "verdict"] = verdict

    candidates = results.loc[results["strategy_name"] != "full_library_baseline"].copy()
    passed = candidates.loc[candidates["verdict"] == "PASSED"].copy()
    if not passed.empty:
        final_verdict = "PASSED"
        winner = passed.sort_values(
            by=["validation_relative_delta", "validation_ir_delta", "confirmation_relative_delta"],
            ascending=[False, False, False],
        ).iloc[0]
        branch_decision = (
            "A bounded C16 sizing/state-scope variant passes both portfolio and execution-health gates. "
            "Advance to low-resource feature-publication design for the winning scoped signal."
        )
    else:
        mixed = candidates.loc[candidates["verdict"] == "MIXED"].copy()
        if not mixed.empty:
            final_verdict = "MIXED"
            winner = mixed.sort_values(
                by=["portfolio_gate_pass", "validation_relative_delta", "confirmation_relative_delta"],
                ascending=[False, False, False],
            ).iloc[0]
            branch_decision = (
                "Bounded C16 variants still do not clear both portfolio and execution-health gates. "
                "Keep C16 unpublished and park further same-contract tuning."
            )
        else:
            final_verdict = "FAILED"
            winner = candidates.sort_values(
                by=["validation_relative_delta", "confirmation_relative_delta"],
                ascending=[False, False],
            ).iloc[0]
            branch_decision = (
                "No bounded C16 sizing/state-scope variant preserved executable relevance. "
                "Park C16 as unpublished offline evidence."
            )

    results = results.sort_values(by=["strategy_name"], ascending=True, ignore_index=True)
    _print_table(results)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h359_order_pressure_sizing_scope_results.parquet"
    winner_daily_path = OUT_DIR / f"{ts}_h359_order_pressure_sizing_scope_winner_daily.parquet"
    details_path = artifact_path("run_summaries") / f"{ts}_h359_order_pressure_sizing_scope_audit_details.json"

    results.to_parquet(results_path, index=False)
    daily_outputs[str(winner["strategy_name"])].to_parquet(winner_daily_path, index=False)

    summary = {
        "verdict": final_verdict,
        "protocol": protocol.describe(),
        "order_feature": ORDER_FEATURE,
        "h358_equivalent_weight": H358_EQUIVALENT_WEIGHT,
        "baseline": baseline.to_dict(),
        "winner": winner.to_dict(),
        "tested_variants": results.to_dict("records"),
        "branch_decision": branch_decision,
        "next_step": {
            "PASSED": "Design a low-resource C16 publisher and update docs only after verifying the artifact contract.",
            "MIXED": "Park C16 as unpublished evidence; reopen only for a learned model contract or downstream RL consumer need.",
            "FAILED": "Park C16 as unpublished evidence under the current executable portfolio contract.",
        }[final_verdict],
    }
    details_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_order_pressure_sizing_scope_audit",
        name="h359_order_pressure_sizing_scope_audit",
        summary=summary,
        artifacts={
            "results": results_path,
            "winner_daily": winner_daily_path,
            "details": details_path,
            "matrix": Path(args.matrix),
            "order_stats": Path(args.order_stats),
            "tradability": Path(args.tradability),
        },
        metadata={
            "signal": "H359",
            "family": "order_pressure",
            "protocol": protocol.describe(),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
        },
    )
    print(f"VERDICT: {final_verdict}", flush=True)
    print(f"winner: {winner['strategy_name']}", flush=True)
    print(f"summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
