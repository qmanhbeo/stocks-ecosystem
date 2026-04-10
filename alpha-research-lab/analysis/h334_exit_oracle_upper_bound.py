"""
H334: constrained legal-exit oracle upper-bound audit.

Question:
    Before training a smarter exit model, is there enough exit-timing capacity
    in legal, predeclared hold horizons to justify ML at all?

Design:
    - keep the frozen full_library top-5 / rebalance-5 backbone
    - use actual executed buy entries from the simulated blotter
    - allow only legal exits at predeclared horizons: 3d / 5d / 10d / 15d
    - if a scheduled exit is sell-blocked, use the first legal sell thereafter
    - compare fixed-horizon utilities against a constrained hindsight oracle
    - keep 2026+ out of the predictive decision

This is an upper-bound audit, not a deployable policy. A pass only means the
next honest step may try to distill a causal exit rule.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
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

from shared_market_rules import required_holding_age_for_sell  # noqa: E402

from src.deterministic_portfolio import simulate_strategy  # noqa: E402
from src.exit_experiment_utils import load_full_library_backbone  # noqa: E402
from src.research_protocol import DEFAULT_PROTOCOL, assign_research_phase  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

EXIT_HORIZONS = (3, 5, 10, 15)
DEFAULT_ROUND_TRIP_COST = 0.003
DEFAULT_DRAWDOWN_PENALTY = 0.25


@dataclass(frozen=True)
class ExitOutcome:
    horizon: int
    scheduled_exit_idx: int
    legal_exit_idx: int
    blocked_extra_days: int
    scheduled_exit_date: pd.Timestamp
    legal_exit_date: pd.Timestamp
    stock_return_net: float
    benchmark_return: float
    relative_return: float
    path_mae: float
    path_mfe: float
    utility: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=DEFAULT_ROUND_TRIP_COST)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--drawdown-penalty", type=float, default=DEFAULT_DRAWDOWN_PENALTY)
    return parser.parse_args()


def _safe_return(start_open: float, end_open: float) -> float | None:
    if not (np.isfinite(start_open) and np.isfinite(end_open) and start_open > 0.0 and end_open > 0.0):
        return None
    return float(end_open / start_open - 1.0)


def _first_legal_exit_idx(
    *,
    scheduled_exit_idx: int,
    ticker_idx: int,
    dates: np.ndarray,
    open_matrix: np.ndarray,
    can_sell_matrix: np.ndarray,
    max_exit_year: int,
) -> int | None:
    if scheduled_exit_idx >= len(dates):
        return None
    for exit_idx in range(int(scheduled_exit_idx), len(dates)):
        if pd.Timestamp(dates[exit_idx]).year > int(max_exit_year):
            return None
        decision_idx = exit_idx - 1
        if decision_idx < 0:
            continue
        exit_open = open_matrix[exit_idx, ticker_idx]
        if not (np.isfinite(exit_open) and exit_open > 0.0):
            continue
        if bool(can_sell_matrix[decision_idx, ticker_idx]):
            return int(exit_idx)
    return None


def _outcome_for_horizon(
    *,
    horizon: int,
    entry_idx: int,
    ticker_idx: int,
    dates: np.ndarray,
    open_matrix: np.ndarray,
    benchmark_open: np.ndarray,
    can_sell_matrix: np.ndarray,
    round_trip_cost: float,
    drawdown_penalty: float,
) -> ExitOutcome | None:
    scheduled_exit_idx = int(entry_idx) + int(horizon)
    legal_exit_idx = _first_legal_exit_idx(
        scheduled_exit_idx=scheduled_exit_idx,
        ticker_idx=ticker_idx,
        dates=dates,
        open_matrix=open_matrix,
        can_sell_matrix=can_sell_matrix,
        max_exit_year=DEFAULT_PROTOCOL.forward_start_year - 1,
    )
    if legal_exit_idx is None:
        return None

    entry_open = float(open_matrix[int(entry_idx), int(ticker_idx)])
    exit_open = float(open_matrix[int(legal_exit_idx), int(ticker_idx)])
    stock_gross = _safe_return(entry_open, exit_open)
    benchmark_return = _safe_return(float(benchmark_open[int(entry_idx)]), float(benchmark_open[int(legal_exit_idx)]))
    if stock_gross is None:
        return None
    if benchmark_return is None:
        benchmark_return = 0.0

    path = open_matrix[int(entry_idx) : int(legal_exit_idx) + 1, int(ticker_idx)].astype(float)
    path = path[np.isfinite(path) & (path > 0.0)]
    if len(path) == 0:
        return None
    path_returns = path / entry_open - 1.0
    path_mae = float(max(0.0, -float(np.nanmin(path_returns))))
    path_mfe = float(max(0.0, float(np.nanmax(path_returns))))
    stock_return_net = float(stock_gross - float(round_trip_cost))
    relative_return = float(stock_return_net - float(benchmark_return))
    utility = float(relative_return - float(drawdown_penalty) * path_mae)
    return ExitOutcome(
        horizon=int(horizon),
        scheduled_exit_idx=int(scheduled_exit_idx),
        legal_exit_idx=int(legal_exit_idx),
        blocked_extra_days=int(legal_exit_idx - scheduled_exit_idx),
        scheduled_exit_date=pd.Timestamp(dates[int(scheduled_exit_idx)]),
        legal_exit_date=pd.Timestamp(dates[int(legal_exit_idx)]),
        stock_return_net=stock_return_net,
        benchmark_return=float(benchmark_return),
        relative_return=relative_return,
        path_mae=path_mae,
        path_mfe=path_mfe,
        utility=utility,
    )


def build_exit_outcomes(
    *,
    baseline_blotter: pd.DataFrame,
    market_inputs,
    required_holding_age: int,
    round_trip_cost: float,
    drawdown_penalty: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    legal_min = required_holding_age_for_sell(min_hold_days_override=int(required_holding_age))
    horizons = tuple(h for h in EXIT_HORIZONS if h >= int(legal_min))
    dates = pd.to_datetime(market_inputs.dates)
    date_to_idx = {pd.Timestamp(ts): idx for idx, ts in enumerate(dates)}
    ticker_to_idx = {ticker: idx for idx, ticker in enumerate(market_inputs.tickers)}
    open_matrix = np.asarray(market_inputs.open_matrix, dtype=np.float64)
    benchmark_open = np.asarray(market_inputs.benchmark_open, dtype=np.float64)
    can_sell_matrix = np.asarray(market_inputs.can_sell_matrix, dtype=bool)

    entries = baseline_blotter.loc[baseline_blotter["executed_action"].astype(str) == "buy"].copy()
    entries["entry_id"] = np.arange(len(entries), dtype=int)
    entries["entry_signal_date"] = pd.to_datetime(entries["signal_date"], errors="coerce")
    entries["entry_execution_date"] = pd.to_datetime(entries["execution_date"], errors="coerce")
    entries["ticker"] = entries["ticker"].astype(str).str.upper()

    rows: list[dict[str, object]] = []
    long_rows: list[dict[str, object]] = []
    for entry in entries.itertuples(index=False):
        entry_date = pd.Timestamp(entry.entry_execution_date)
        ticker = str(entry.ticker)
        entry_idx = date_to_idx.get(entry_date)
        ticker_idx = ticker_to_idx.get(ticker)
        if entry_idx is None or ticker_idx is None:
            continue
        entry_open = float(open_matrix[int(entry_idx), int(ticker_idx)])
        if not (np.isfinite(entry_open) and entry_open > 0.0):
            continue

        outcomes: dict[int, ExitOutcome] = {}
        for horizon in horizons:
            outcome = _outcome_for_horizon(
                horizon=int(horizon),
                entry_idx=int(entry_idx),
                ticker_idx=int(ticker_idx),
                dates=np.asarray(dates),
                open_matrix=open_matrix,
                benchmark_open=benchmark_open,
                can_sell_matrix=can_sell_matrix,
                round_trip_cost=float(round_trip_cost),
                drawdown_penalty=float(drawdown_penalty),
            )
            if outcome is not None:
                outcomes[int(horizon)] = outcome
                long_rows.append(
                    {
                        "entry_id": int(entry.entry_id),
                        "entry_signal_date": pd.Timestamp(entry.entry_signal_date),
                        "entry_execution_date": entry_date,
                        "ticker": ticker,
                        "entry_score": float(entry.entry_score) if pd.notna(entry.entry_score) else None,
                        "entry_rank": float(entry.entry_rank) if pd.notna(entry.entry_rank) else None,
                        "entry_thesis_family": getattr(entry, "entry_thesis_family", None),
                        "horizon": int(horizon),
                        "scheduled_exit_date": outcome.scheduled_exit_date,
                        "legal_exit_date": outcome.legal_exit_date,
                        "blocked_extra_days": int(outcome.blocked_extra_days),
                        "stock_return_net": float(outcome.stock_return_net),
                        "benchmark_return": float(outcome.benchmark_return),
                        "relative_return": float(outcome.relative_return),
                        "path_mae": float(outcome.path_mae),
                        "path_mfe": float(outcome.path_mfe),
                        "utility": float(outcome.utility),
                    }
                )
        if not outcomes:
            continue
        oracle = max(outcomes.values(), key=lambda item: (item.utility, item.relative_return, -item.horizon))
        fixed = {h: outcomes.get(h) for h in horizons}
        row = {
            "entry_id": int(entry.entry_id),
            "time": pd.Timestamp(entry.entry_signal_date),
            "entry_signal_date": pd.Timestamp(entry.entry_signal_date),
            "entry_execution_date": entry_date,
            "ticker": ticker,
            "entry_score": float(entry.entry_score) if pd.notna(entry.entry_score) else None,
            "entry_rank": float(entry.entry_rank) if pd.notna(entry.entry_rank) else None,
            "entry_thesis_family": getattr(entry, "entry_thesis_family", None),
            "entry_open": entry_open,
            "oracle_horizon": int(oracle.horizon),
            "oracle_legal_exit_date": oracle.legal_exit_date,
            "oracle_blocked_extra_days": int(oracle.blocked_extra_days),
            "oracle_stock_return_net": float(oracle.stock_return_net),
            "oracle_benchmark_return": float(oracle.benchmark_return),
            "oracle_relative_return": float(oracle.relative_return),
            "oracle_path_mae": float(oracle.path_mae),
            "oracle_path_mfe": float(oracle.path_mfe),
            "oracle_utility": float(oracle.utility),
            "available_horizons": ",".join(str(h) for h in sorted(outcomes)),
        }
        for horizon in horizons:
            outcome = fixed[horizon]
            prefix = f"h{horizon}"
            row[f"{prefix}_available"] = outcome is not None
            row[f"{prefix}_utility"] = float(outcome.utility) if outcome is not None else np.nan
            row[f"{prefix}_relative_return"] = float(outcome.relative_return) if outcome is not None else np.nan
            row[f"{prefix}_stock_return_net"] = float(outcome.stock_return_net) if outcome is not None else np.nan
            row[f"{prefix}_path_mae"] = float(outcome.path_mae) if outcome is not None else np.nan
            row[f"{prefix}_path_mfe"] = float(outcome.path_mfe) if outcome is not None else np.nan
            row[f"{prefix}_blocked_extra_days"] = int(outcome.blocked_extra_days) if outcome is not None else np.nan
        rows.append(row)

    wide = pd.DataFrame(rows)
    long = pd.DataFrame(long_rows)
    if not wide.empty:
        wide = assign_research_phase(wide, date_column="time", protocol=DEFAULT_PROTOCOL)
    if not long.empty:
        long = assign_research_phase(long, date_column="entry_signal_date", protocol=DEFAULT_PROTOCOL)
    return wide, long


def _phase_summary(frame: pd.DataFrame, *, horizons: tuple[int, ...]) -> tuple[pd.DataFrame, dict[str, object]]:
    rows: list[dict[str, object]] = []
    best_fixed_by_phase: dict[str, int | None] = {}
    for phase in ("dev", "validation", "confirmation"):
        phase_frame = frame.loc[frame["research_phase"] == phase].copy()
        if phase_frame.empty:
            rows.append({"phase": phase, "entries": 0})
            best_fixed_by_phase[phase] = None
            continue

        row: dict[str, object] = {
            "phase": phase,
            "entries": int(len(phase_frame)),
            "tickers": int(phase_frame["ticker"].nunique()),
            "dates": int(phase_frame["time"].nunique()),
            "oracle_utility_mean": float(phase_frame["oracle_utility"].mean()),
            "oracle_relative_mean": float(phase_frame["oracle_relative_return"].mean()),
            "oracle_mae_mean": float(phase_frame["oracle_path_mae"].mean()),
            "oracle_mfe_mean": float(phase_frame["oracle_path_mfe"].mean()),
        }
        fixed_means: dict[int, float] = {}
        for horizon in horizons:
            col = f"h{horizon}_utility"
            rel_col = f"h{horizon}_relative_return"
            avail_col = f"h{horizon}_available"
            row[f"h{horizon}_available_rate"] = float(phase_frame[avail_col].mean())
            row[f"h{horizon}_utility_mean"] = float(phase_frame[col].mean())
            row[f"h{horizon}_relative_mean"] = float(phase_frame[rel_col].mean())
            row[f"h{horizon}_blocked_extra_mean"] = float(phase_frame[f"h{horizon}_blocked_extra_days"].mean())
            fixed_means[int(horizon)] = row[f"h{horizon}_utility_mean"]

        best_horizon = max(fixed_means, key=lambda h: fixed_means[h])
        best_fixed_by_phase[phase] = int(best_horizon)
        best_col = f"h{best_horizon}_utility"
        row["best_fixed_horizon"] = int(best_horizon)
        row["best_fixed_utility_mean"] = float(phase_frame[best_col].mean())
        row["oracle_uplift_vs_best_fixed"] = float(row["oracle_utility_mean"] - row["best_fixed_utility_mean"])
        row["oracle_uplift_positive_rate"] = float((phase_frame["oracle_utility"] > phase_frame[best_col] + 1e-12).mean())
        row["oracle_not_best_fixed_rate"] = float((phase_frame["oracle_horizon"] != int(best_horizon)).mean())
        for horizon in horizons:
            row[f"oracle_h{horizon}_choice_rate"] = float((phase_frame["oracle_horizon"] == int(horizon)).mean())
        rows.append(row)

    summary = pd.DataFrame(rows)
    by_phase = {row["phase"]: row for row in summary.to_dict(orient="records")}
    validation = by_phase.get("validation", {})
    confirmation = by_phase.get("confirmation", {})
    validation_uplift = validation.get("oracle_uplift_vs_best_fixed")
    confirmation_uplift = confirmation.get("oracle_uplift_vs_best_fixed")
    validation_not_fixed = validation.get("oracle_not_best_fixed_rate")
    confirmation_not_fixed = confirmation.get("oracle_not_best_fixed_rate")
    pass_condition = bool(
        validation_uplift is not None
        and confirmation_uplift is not None
        and float(validation_uplift) >= 0.01
        and float(confirmation_uplift) >= 0.005
        and float(validation_not_fixed or 0.0) >= 0.20
        and float(confirmation_not_fixed or 0.0) >= 0.20
    )
    mixed_condition = bool(
        validation_uplift is not None
        and confirmation_uplift is not None
        and float(validation_uplift) > 0.003
        and float(confirmation_uplift) > 0.0
    )
    if pass_condition:
        verdict = "PASSED"
        branch_decision = (
            "The constrained legal-exit oracle has material validation and confirmation uplift over fixed horizons. "
            "Advance to exit-mdp-lite or discrete-exit-hazard distillation; do not treat the oracle as a tradable rule."
        )
    elif mixed_condition:
        verdict = "MIXED"
        branch_decision = (
            "The constrained oracle shows some uplift but not enough diversity / confirmation strength for broad ML. "
            "Narrow to hazard labels or a stricter state subset before training a policy."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The constrained oracle did not create a material upper bound over fixed horizons. "
            "Park the smart-exit ML ladder on the current data contract."
        )
    decision = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "pass_condition": pass_condition,
        "mixed_condition": mixed_condition,
        "best_fixed_by_phase": best_fixed_by_phase,
        "validation_uplift_vs_best_fixed": validation_uplift,
        "confirmation_uplift_vs_best_fixed": confirmation_uplift,
        "validation_not_best_fixed_rate": validation_not_fixed,
        "confirmation_not_best_fixed_rate": confirmation_not_fixed,
    }
    return summary, decision


def main() -> int:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    _, _, market_inputs = load_full_library_backbone(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    fee_leg = float(args.round_trip_cost) / 2.0
    baseline = simulate_strategy(
        strategy_name="full_library",
        signal_columns=["full_library"],
        market_inputs=market_inputs,
        top_k=5,
        rebalance_every=5,
        weighting="equal",
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(args.required_holding_age),
        buy_fee_rate=fee_leg,
        sell_fee_rate=fee_leg,
        capital_gains_tax_rate=0.0,
        capture_blotter=True,
    )
    if baseline.blotter is None or baseline.blotter.empty:
        raise ValueError("Baseline blotter is empty; cannot run H334")

    legal_min = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    horizons = tuple(h for h in EXIT_HORIZONS if h >= int(legal_min))
    wide, long = build_exit_outcomes(
        baseline_blotter=baseline.blotter,
        market_inputs=market_inputs,
        required_holding_age=int(args.required_holding_age),
        round_trip_cost=float(args.round_trip_cost),
        drawdown_penalty=float(args.drawdown_penalty),
    )
    if wide.empty or long.empty:
        raise ValueError("No legal exit outcomes available for H334")

    phase_results, decision = _phase_summary(wide, horizons=horizons)

    phase_results_path = OUT_DIR / f"{ts}_h334_exit_oracle_upper_bound_phase_results.parquet"
    entry_outcomes_path = OUT_DIR / f"{ts}_h334_exit_oracle_upper_bound_entry_outcomes.parquet"
    horizon_outcomes_path = OUT_DIR / f"{ts}_h334_exit_oracle_upper_bound_horizon_outcomes.parquet"
    baseline_daily_path = OUT_DIR / f"{ts}_h334_exit_oracle_upper_bound_baseline_daily.parquet"
    details_path = DETAILS_DIR / f"{ts}_h334_exit_oracle_upper_bound_details.json"

    phase_results.to_parquet(phase_results_path, index=False)
    wide.to_parquet(entry_outcomes_path, index=False)
    long.to_parquet(horizon_outcomes_path, index=False)
    baseline.daily.to_parquet(baseline_daily_path, index=False)

    mechanics = {
        "start_year": int(args.start_year),
        "end_year": int(args.end_year),
        "entry_rows": int(len(wide)),
        "horizon_rows": int(len(long)),
        "tickers": int(wide["ticker"].nunique()),
        "entry_dates": int(wide["time"].nunique()),
        "horizons": list(horizons),
        "required_holding_age": int(args.required_holding_age),
        "legal_min_holding_age": int(legal_min),
        "round_trip_cost": float(args.round_trip_cost),
        "drawdown_penalty": float(args.drawdown_penalty),
        "max_exit_year": int(DEFAULT_PROTOCOL.forward_start_year - 1),
    }
    summary = {
        **decision,
        "mechanics": mechanics,
        "phase_results": phase_results.to_dict(orient="records"),
    }
    details_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_exit_oracle_upper_bound",
        name="h334_exit_oracle_upper_bound",
        summary=summary,
        artifacts={
            "phase_results": phase_results_path,
            "entry_outcomes": entry_outcomes_path,
            "horizon_outcomes": horizon_outcomes_path,
            "baseline_daily": baseline_daily_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": "A sequential, legal exit target is worth learning only if a constrained fixed-horizon oracle materially beats fixed exits.",
            "protocol": DEFAULT_PROTOCOL.describe(),
            "no_tuning_window": "2026+",
        },
    )

    display_cols = [
        "phase",
        "entries",
        "best_fixed_horizon",
        "best_fixed_utility_mean",
        "oracle_utility_mean",
        "oracle_uplift_vs_best_fixed",
        "oracle_not_best_fixed_rate",
    ]
    print("H334 exit-oracle upper bound")
    print("=" * 72)
    print(f"verdict: {decision['verdict']}")
    print(f"branch decision: {decision['branch_decision']}")
    print(phase_results[display_cols].to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
