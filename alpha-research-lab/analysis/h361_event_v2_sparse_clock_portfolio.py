"""
H361 - Event-v2 Sparse-Clock Portfolio Audit.

Question:
- Event-v2 states failed additive, entry-label, and payoff-shape promotion.
  Can the remaining allowed reopening condition work: a stricter portfolio-level
  sparse clock that only nudges already-strong full-library names?

Design:
- Reuse the saved H321 event-v2 cascade panel; do not refit event thresholds.
- Exclude 2026 entirely.
- Use the executable top-5 / rebalance-5 portfolio with shared tradability.
- Test exactly one fixed sparse-clock variant:
  add a +0.03 score bonus only when:
    * the ticker is in `today_self_accel_high` or `recent5_high_self_no_today`,
    * the full-library score is already in the daily top quintile,
    * the ticker is buyable at the next open.

Decision:
- PASSED requires the additive portfolio gate, execution-health gate, and no
  material validation/confirmation downside-tail worsening.
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

from src.additive_selector_research import (
    additive_candidate_deltas,
    additive_candidate_passes,
    resolve_summary_artifact,
)
from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns
from src.repo_paths import artifact_path, data_path
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import compute_phase_portfolio_summary, load_research_bundle, run_selector_candidate

from h358_order_pressure_portfolio_tradability_audit import _execution_health_flags, _flatten_phase_rows


MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H321_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_hawkes_disclosure_cascade.json"
OUT_DIR = artifact_path("portfolio_baselines")

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
START_YEAR = 2023
END_YEAR = 2025
EVENT_BONUS = 0.03
BASE_RANK_FLOOR = 0.80
BAD_TAIL_THRESHOLD = -0.03
Q10_MAX_WORSENING = -0.0025
BAD_TAIL_MAX_WORSENING = 0.010
STRATEGY_NAME = "event_sparse_clock_bonus"
EVENT_COLUMNS = ("today_self_accel_high", "recent5_high_self_no_today")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h321-summary", type=str, default=str(H321_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _phase_execution_summary(daily: pd.DataFrame) -> dict[str, dict[str, object]]:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    phases = compute_phase_portfolio_summary(work, protocol=PROTOCOL)
    out: dict[str, dict[str, object]] = {}
    for phase, phase_summary in phases.items():
        scoped = work.loc[phase_mask(work, phase, date_column="execution_date", protocol=PROTOCOL)]
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
        }
    return out


def _load_event_states(summary_path: Path) -> pd.DataFrame:
    panel_path = resolve_summary_artifact(summary_path, "panel")
    panel = pd.read_parquet(panel_path, columns=["time", "ticker", *EVENT_COLUMNS]).copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel["ticker"] = panel["ticker"].astype(str).str.upper()
    panel = panel.loc[panel["time"].dt.year.between(START_YEAR, END_YEAR)].dropna(subset=["time", "ticker"])
    for col in EVENT_COLUMNS:
        panel[col] = panel[col].fillna(False).astype(bool)
    panel["event_sparse_clock_active"] = panel[list(EVENT_COLUMNS)].any(axis=1)
    return panel[["time", "ticker", "event_sparse_clock_active"]].drop_duplicates(["time", "ticker"])


def _risk_rows(daily_by_strategy: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for strategy, daily in daily_by_strategy.items():
        work = daily.copy()
        work["execution_date"] = pd.to_datetime(work["execution_date"])
        for phase in ("dev", "validation", "confirmation"):
            scoped = work.loc[phase_mask(work, phase, date_column="execution_date", protocol=PROTOCOL)]
            rel = pd.to_numeric(scoped["relative_return"], errors="coerce").dropna()
            rows.append(
                {
                    "strategy_name": strategy,
                    "phase": phase,
                    "daily_relative_mean": _safe_float(rel.mean()) if not rel.empty else None,
                    "daily_relative_q10": _safe_float(rel.quantile(0.10)) if not rel.empty else None,
                    "daily_relative_bad_tail_rate": _safe_float((rel <= BAD_TAIL_THRESHOLD).mean()) if not rel.empty else None,
                }
            )
    return pd.DataFrame(rows)


def _risk_gate(risk: pd.DataFrame) -> dict[str, object]:
    baseline = risk.loc[risk["strategy_name"] == "full_library_baseline"].set_index("phase")
    candidate = risk.loc[risk["strategy_name"] == STRATEGY_NAME].set_index("phase")
    out: dict[str, object] = {}
    passes = True
    for phase in ("validation", "confirmation"):
        q10_delta = (_safe_float(candidate.loc[phase, "daily_relative_q10"]) or 0.0) - (
            _safe_float(baseline.loc[phase, "daily_relative_q10"]) or 0.0
        )
        bad_tail_delta = (_safe_float(candidate.loc[phase, "daily_relative_bad_tail_rate"]) or 0.0) - (
            _safe_float(baseline.loc[phase, "daily_relative_bad_tail_rate"]) or 0.0
        )
        out[f"{phase}_daily_relative_q10_delta"] = q10_delta
        out[f"{phase}_bad_tail_rate_delta"] = bad_tail_delta
        passes = passes and q10_delta >= Q10_MAX_WORSENING and bad_tail_delta <= BAD_TAIL_MAX_WORSENING
    out["passes_downside_tail_gate"] = bool(passes)
    return out


def main() -> None:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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
    full_library_columns = resolve_strategy_columns(matrix.columns.tolist(), "full_library")
    scored = compute_strategy_scores(matrix, {"full_library_baseline": list(full_library_columns)})

    events = _load_event_states(Path(args.h321_summary))
    scored = scored.merge(events, on=["time", "ticker"], how="left", validate="one_to_one")
    scored["event_sparse_clock_active"] = scored["event_sparse_clock_active"].fillna(False).astype(bool)
    tradability = bundle.tradability[["time", "ticker", "can_buy_next_open"]].copy()
    tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce").dt.normalize()
    tradability["ticker"] = tradability["ticker"].astype(str).str.upper()
    scored = scored.merge(tradability, on=["time", "ticker"], how="left", validate="one_to_one")
    scored["can_buy_next_open"] = scored["can_buy_next_open"].fillna(False).astype(bool)

    base = scored["score__full_library_baseline"].astype(float)
    base_rank = base.groupby(scored["time"], sort=False).rank(method="average", pct=True)
    eligible = scored["event_sparse_clock_active"] & scored["can_buy_next_open"] & (base_rank >= BASE_RANK_FLOOR)
    scored[f"score__{STRATEGY_NAME}"] = base + EVENT_BONUS * eligible.astype(float)

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for strategy_name, signal_columns in {
        "full_library_baseline": list(full_library_columns),
        STRATEGY_NAME: ["event_sparse_clock_bonus"],
    }.items():
        result = run_selector_candidate(
            scored_frame=scored[["time", "ticker", "actual", f"score__{strategy_name}"]],
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
        row = _flatten_phase_rows(strategy_name, signal_columns, _phase_execution_summary(result.daily), result.summary)
        rows.append(row)
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    candidate_idx = results.index[results["strategy_name"] == STRATEGY_NAME][0]
    candidate = results.loc[candidate_idx].copy()
    for key, value in {**additive_candidate_deltas(candidate, baseline), **_execution_health_flags(candidate, baseline)}.items():
        results.loc[candidate_idx, key] = value
        candidate[key] = value
    results.loc[candidate_idx, "portfolio_gate_pass"] = bool(additive_candidate_passes(candidate, baseline))

    risk = _risk_rows(daily_outputs)
    tail_gate = _risk_gate(risk)
    for key, value in tail_gate.items():
        results.loc[candidate_idx, key] = value
    contract_pass = bool(
        results.loc[candidate_idx, "portfolio_gate_pass"]
        and results.loc[candidate_idx, "passes_execution_health"]
        and tail_gate["passes_downside_tail_gate"]
    )
    results.loc[candidate_idx, "verdict"] = "PASSED" if contract_pass else "FAILED"
    results.loc[results["strategy_name"] == "full_library_baseline", "portfolio_gate_pass"] = False
    results.loc[results["strategy_name"] == "full_library_baseline", "passes_execution_health"] = True
    results.loc[results["strategy_name"] == "full_library_baseline", "passes_downside_tail_gate"] = True
    results.loc[results["strategy_name"] == "full_library_baseline", "verdict"] = "BASELINE"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h361_event_sparse_clock_portfolio_results.parquet"
    risk_path = OUT_DIR / f"{ts}_h361_event_sparse_clock_portfolio_risk.parquet"
    candidate_daily_path = OUT_DIR / f"{ts}_h361_event_sparse_clock_portfolio_candidate_daily.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h361_event_sparse_clock_portfolio_details.json"
    results.to_parquet(results_path, index=False)
    risk.to_parquet(risk_path, index=False)
    daily_outputs[STRATEGY_NAME].to_parquet(candidate_daily_path, index=False)
    details_path.write_text(
        json.dumps(
            {
                "event_active_rows": int(scored["event_sparse_clock_active"].sum()),
                "eligible_bonus_rows": int(eligible.sum()),
                "tail_gate": tail_gate,
                "results": results.to_dict(orient="records"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    candidate_row = results.loc[results["strategy_name"] == STRATEGY_NAME].iloc[0]
    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_event_v2_sparse_clock_portfolio",
        name="h361_event_v2_sparse_clock_portfolio",
        summary={
            "verdict": "PASSED" if contract_pass else "FAILED",
            "branch_decision": (
                "Event-v2 sparse clock passed the strict portfolio-level reopening gate."
                if contract_pass
                else "Event-v2 sparse clock did not pass the strict portfolio-level reopening gate; keep event-v2 parked."
            ),
            "event_active_rows": int(scored["event_sparse_clock_active"].sum()),
            "eligible_bonus_rows": int(eligible.sum()),
            "portfolio_gate_pass": bool(candidate_row.get("portfolio_gate_pass")),
            "passes_execution_health": bool(candidate_row.get("passes_execution_health")),
            "passes_downside_tail_gate": bool(candidate_row.get("passes_downside_tail_gate")),
            "validation_relative_delta": _safe_float(candidate_row.get("validation_relative_delta")),
            "confirmation_relative_delta": _safe_float(candidate_row.get("confirmation_relative_delta")),
            "validation_daily_relative_q10_delta": _safe_float(candidate_row.get("validation_daily_relative_q10_delta")),
            "confirmation_daily_relative_q10_delta": _safe_float(candidate_row.get("confirmation_daily_relative_q10_delta")),
        },
        artifacts={
            "h321_summary": str(Path(args.h321_summary)),
            "results": str(results_path),
            "risk": str(risk_path),
            "candidate_daily": str(candidate_daily_path),
            "details": str(details_path),
        },
        metadata={
            "protocol": PROTOCOL.describe(),
            "event_columns": list(EVENT_COLUMNS),
            "event_bonus": EVENT_BONUS,
            "base_rank_floor": BASE_RANK_FLOOR,
            "bad_tail_threshold": BAD_TAIL_THRESHOLD,
            "source_limited_protocol": "2023 dev / 2024 validation / 2025 confirmation; 2026 excluded",
        },
    )

    print("\nH361: EVENT-V2 SPARSE-CLOCK PORTFOLIO AUDIT")
    print(f"  verdict: {'PASSED' if contract_pass else 'FAILED'}")
    print(f"  portfolio gate: {bool(candidate_row.get('portfolio_gate_pass'))}")
    print(f"  execution health: {bool(candidate_row.get('passes_execution_health'))}")
    print(f"  downside tail gate: {bool(candidate_row.get('passes_downside_tail_gate'))}")
    print(f"  validation rel delta: {(_safe_float(candidate_row.get('validation_relative_delta')) or 0.0) * 100:+.2f}%")
    print(f"  confirmation rel delta: {(_safe_float(candidate_row.get('confirmation_relative_delta')) or 0.0) * 100:+.2f}%")
    print(f"  eligible bonus rows: {int(eligible.sum()):,}")
    print(f"  summary: {summary_path}")


if __name__ == "__main__":
    main()
