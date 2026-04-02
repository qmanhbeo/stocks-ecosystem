"""
H250: Contradiction-state router screen and direct selector audit.

Purpose:
- test whether disagreement states between continuation and reversal signals
  contain a new selector edge
- keep the live sticky branch frozen
- enforce the locked 2015-2025 research protocol

Usage:
    conda run -n stocks python analysis/h250_contradiction_state_router.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path

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
    summary_is_skipped,
    blend_state_scoped_scores,
)
from src.contradiction_state_router import H250_SIGNAL_NAMES, add_h250_router_signals
from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns
from src.repo_paths import artifact_path
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.standalone_signal_utils import PASS_CORR, PASS_IC, PASS_PCT_YEARS, gate_pass
from src.tradability_conditioned_research import (
    build_candidate_signal_frame,
    compute_phase_portfolio_summary,
    evaluate_signal_ic_by_phase,
    load_research_bundle,
    run_selector_candidate,
)


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H201_SUMMARY_PATH = artifact_path("run_summaries/latest_portfolio_state_scoped_h199_atom_bakeoff.json")
OUT_DIR = artifact_path("portfolio_baselines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H250: contradiction-state router")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h201-summary", type=str, default=str(H201_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _load_h201_winner(summary_path: Path) -> tuple[pd.DataFrame, str | None]:
    if summary_is_skipped(summary_path):
        return pd.DataFrame(), None
    results_path = resolve_summary_artifact(summary_path, "results")
    results = pd.read_parquet(results_path)
    promoted = results.loc[results["promoted"]].copy()
    if promoted.empty:
        return results, None
    winner = str(
        promoted.sort_values(
            by=[
                "validation_relative_delta",
                "validation_ir_delta",
                "confirmation_relative_delta",
                "validation_avg_cash_weight",
                "validation_avg_daily_turnover",
                "strategy_name",
            ],
            ascending=[False, False, False, True, True, True],
        ).iloc[0]["strategy_name"]
    )
    return results, winner


def _parse_state_blend_name(strategy_name: str) -> tuple[str, float]:
    parts = str(strategy_name).split("__")
    if len(parts) != 3 or parts[0] != "state_blend":
        raise ValueError(f"Expected state blend strategy name, got {strategy_name!r}")
    return parts[1], float(parts[2]) / 100.0


def _print_screen_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 224)
    print("H250: CONTRADICTION-STATE ROUTER SCREEN")
    print("=" * 224)
    print(
        f"{'signal':<40} {'active%':>8} {'dev_ic':>9} {'dev_corr':>9} {'val_ic':>9} "
        f"{'2025_ic':>9} {'val_rel':>10} {'2025_rel':>10} {'promote':>8}"
    )
    print("-" * 224)
    for row in results.itertuples(index=False):
        print(
            f"{row.signal_name:<40} "
            f"{(row.active_share_overall or 0.0)*100:>7.2f}% "
            f"{row.dev_avg_ic if row.dev_avg_ic is not None else float('nan'):>+8.4f} "
            f"{row.dev_corr_with_s1 if row.dev_corr_with_s1 is not None else float('nan'):>+8.4f} "
            f"{row.validation_avg_ic if row.validation_avg_ic is not None else float('nan'):>+8.4f} "
            f"{row.confirmation_avg_ic if row.confirmation_avg_ic is not None else float('nan'):>+8.4f} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{str(bool(row.promoted_to_selector_audit)):>8}"
        )


def _print_audit_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 212)
    print("H250: DIRECT SELECTOR AUDIT")
    print("=" * 212)
    print(
        f"{'strategy':<46} {'val_rel':>10} {'d_base':>9} {'d_h201':>9} {'val_IR':>8} "
        f"{'2025_rel':>10} {'d_base':>9} {'d_h201':>9}"
    )
    print("-" * 212)
    for row in results.itertuples(index=False):
        print(
            f"{row.strategy_name:<46} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta_vs_baseline or 0.0)*100:>+8.2f}% "
            f"{(row.validation_relative_delta_vs_h201 or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta_vs_baseline or 0.0)*100:>+8.2f}% "
            f"{(row.confirmation_relative_delta_vs_h201 or 0.0)*100:>+8.2f}% "
        )


def _active_share(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0)
    return float((numeric > 0.0).mean())


def _screen_results(candidate_frame: pd.DataFrame, bundle, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )

    rows: list[dict[str, object]] = []
    survivors: list[str] = []
    for signal_name in H250_SIGNAL_NAMES:
        phase_ic = evaluate_signal_ic_by_phase(
            candidate_frame,
            signal_column=signal_name,
            state_mask=liq_open_basic,
            protocol=DEFAULT_PROTOCOL,
        )
        dev = phase_ic["dev"]
        dev_gate = gate_pass(dev.get("avg_ic"), dev.get("corr_with_s1"), dev.get("pct_years_positive"))
        rows.append(
            {
                "signal_name": signal_name,
                "active_share_overall": _active_share(candidate_frame[signal_name]),
                "dev_avg_ic": dev.get("avg_ic"),
                "dev_corr_with_s1": dev.get("corr_with_s1"),
                "dev_pct_years_positive": dev.get("pct_years_positive"),
                "validation_avg_ic": phase_ic["validation"].get("avg_ic"),
                "confirmation_avg_ic": phase_ic["confirmation"].get("avg_ic"),
                "dev_gate_pass": bool(dev_gate),
                "pass_ic_threshold": PASS_IC,
                "pass_corr_threshold": PASS_CORR,
                "pass_pct_years_threshold": PASS_PCT_YEARS,
            }
        )
        if dev_gate:
            survivors.append(signal_name)

    results = pd.DataFrame(rows)
    daily_outputs: dict[str, pd.DataFrame] = {}
    portfolio_results: dict[str, dict[str, object]] = {}
    fee_leg = float(args.round_trip_cost) / 2.0
    required_holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    if survivors:
        scored = compute_strategy_scores(
            candidate_frame[["time", "ticker", "actual"] + list(survivors)].copy(),
            {signal_name: [signal_name] for signal_name in survivors},
        )
        for signal_name in survivors:
            result = run_selector_candidate(
                scored_frame=scored,
                bundle=bundle,
                strategy_name=signal_name,
                signal_columns=[signal_name],
                start_year=int(args.start_year),
                end_year=int(args.end_year),
                initial_notional_vnd=float(args.portfolio_notional_vnd),
                buy_fee_rate=float(fee_leg),
                sell_fee_rate=float(fee_leg),
                required_holding_age=int(required_holding_age),
            )
            daily_outputs[signal_name] = result.daily.copy()
            portfolio_results[signal_name] = compute_phase_portfolio_summary(result.daily, protocol=DEFAULT_PROTOCOL)

    for idx, row in results.iterrows():
        phase_summary = portfolio_results.get(str(row["signal_name"]), {})
        for phase in ("dev", "validation", "confirmation"):
            results.loc[idx, f"{phase}_relative_total_return"] = (
                None if phase not in phase_summary else phase_summary[phase]["relative_total_return"]
            )
            results.loc[idx, f"{phase}_information_ratio_annualized"] = (
                None if phase not in phase_summary else phase_summary[phase]["information_ratio_annualized"]
            )

    results["survives_validation"] = pd.to_numeric(results["validation_avg_ic"], errors="coerce") > 0.0
    results["survives_confirmation"] = pd.to_numeric(results["confirmation_avg_ic"], errors="coerce") > 0.0
    results["has_portfolio_relevance"] = (
        (pd.to_numeric(results["validation_relative_total_return"], errors="coerce") > 0.0)
        | (pd.to_numeric(results["confirmation_relative_total_return"], errors="coerce") > 0.0)
    )
    results["promoted_to_selector_audit"] = (
        results["dev_gate_pass"]
        & results["survives_validation"]
        & results["survives_confirmation"]
        & results["has_portfolio_relevance"]
    )
    results = results.sort_values(
        by=[
            "promoted_to_selector_audit",
            "validation_avg_ic",
            "validation_relative_total_return",
            "confirmation_avg_ic",
            "signal_name",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    return results, daily_outputs


def _audit_results(
    candidate_frame: pd.DataFrame,
    bundle,
    args: argparse.Namespace,
    *,
    winner_signal: str,
    h201_winner_name: str,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    h201_atom, h201_weight = _parse_state_blend_name(h201_winner_name)

    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )

    merged = bundle.matrix.merge(
        candidate_frame[["time", "ticker", winner_signal, h201_atom]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    additive_name = f"full_library_plus__{winner_signal}"
    base_scored = compute_strategy_scores(
        merged,
        {
            "full_library_baseline": list(full_library_columns),
            additive_name: list(full_library_columns) + [winner_signal],
            h201_atom: [h201_atom],
        },
    )
    audit_scored = base_scored[
        [
            "time",
            "ticker",
            "actual",
            "score__full_library_baseline",
            f"score__{additive_name}",
        ]
    ].copy()
    audit_scored[f"score__{h201_winner_name}"] = blend_state_scoped_scores(
        pd.to_numeric(base_scored["score__full_library_baseline"], errors="coerce"),
        pd.to_numeric(base_scored[f"score__{h201_atom}"], errors="coerce"),
        liq_open_basic,
        atom_weight=float(h201_weight),
    )

    fee_leg = float(args.round_trip_cost) / 2.0
    required_holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    strategies = (
        ("full_library_baseline", audit_scored),
        (additive_name, audit_scored),
        (h201_winner_name, audit_scored),
    )

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for strategy_name, scored_frame in strategies:
        result = run_selector_candidate(
            scored_frame=scored_frame,
            bundle=bundle,
            strategy_name=strategy_name,
            signal_columns=[strategy_name],
            start_year=int(args.start_year),
            end_year=int(args.end_year),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            required_holding_age=int(required_holding_age),
        )
        phase_summary = compute_phase_portfolio_summary(result.daily, protocol=DEFAULT_PROTOCOL)
        rows.append(
            {
                "strategy_name": strategy_name,
                "validation_relative_total_return": phase_summary["validation"]["relative_total_return"],
                "validation_information_ratio_annualized": phase_summary["validation"]["information_ratio_annualized"],
                "confirmation_relative_total_return": phase_summary["confirmation"]["relative_total_return"],
                "confirmation_information_ratio_annualized": phase_summary["confirmation"]["information_ratio_annualized"],
            }
        )
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    h201 = results.loc[results["strategy_name"] == h201_winner_name].iloc[0]
    for idx, row in results.iterrows():
        base_deltas = additive_candidate_deltas(row, baseline)
        h201_deltas = additive_candidate_deltas(row, h201)
        results.loc[idx, "validation_relative_delta_vs_baseline"] = base_deltas["validation_relative_delta"]
        results.loc[idx, "validation_ir_delta_vs_baseline"] = base_deltas["validation_ir_delta"]
        results.loc[idx, "confirmation_relative_delta_vs_baseline"] = base_deltas["confirmation_relative_delta"]
        results.loc[idx, "confirmation_ir_delta_vs_baseline"] = base_deltas["confirmation_ir_delta"]
        results.loc[idx, "validation_relative_delta_vs_h201"] = h201_deltas["validation_relative_delta"]
        results.loc[idx, "validation_ir_delta_vs_h201"] = h201_deltas["validation_ir_delta"]
        results.loc[idx, "confirmation_relative_delta_vs_h201"] = h201_deltas["confirmation_relative_delta"]
        results.loc[idx, "confirmation_ir_delta_vs_h201"] = h201_deltas["confirmation_ir_delta"]
        results.loc[idx, "passes_baseline_gate"] = (
            False if row["strategy_name"] in {"full_library_baseline", h201_winner_name} else additive_candidate_passes(row, baseline)
        )
        results.loc[idx, "beats_h201_offline_lead"] = (
            False if row["strategy_name"] != additive_name else additive_candidate_passes(row, h201)
        )
    return results, daily_outputs, audit_scored


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    candidate_frame = build_candidate_signal_frame(bundle, start_year=int(args.start_year), end_year=int(args.end_year))
    extra_columns = ["c9_reversal_1d", "c14_clv_volconf_resid_rank"]
    candidate_frame = candidate_frame.merge(
        bundle.matrix[["time", "ticker"] + extra_columns],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    candidate_frame = add_h250_router_signals(candidate_frame)

    screen_results, screen_daily_outputs = _screen_results(candidate_frame, bundle, args)
    _print_screen_table(screen_results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    screen_results_path = OUT_DIR / f"{ts}_h250_contradiction_state_router_screen_results.parquet"
    screen_results.to_parquet(screen_results_path, index=False)

    promoted = screen_results.loc[screen_results["promoted_to_selector_audit"]].copy()
    summary: dict[str, object] = {
        "protocol": protocol.describe(),
        "screen_survivors": screen_results.loc[screen_results["dev_gate_pass"], "signal_name"].tolist(),
        "screen_promoted": promoted[
            ["signal_name", "validation_avg_ic", "confirmation_avg_ic", "validation_relative_total_return"]
        ].to_dict("records"),
    }
    artifacts: dict[str, str] = {"screen_results": str(screen_results_path)}
    metadata = {
        "protocol": protocol.describe(),
        "start_year": int(args.start_year),
        "end_year": int(args.end_year),
        "h201_summary": str(args.h201_summary),
    }

    if promoted.empty:
        summary.update(
            {
                "winner": {},
                "audit_skipped": True,
                "verdict": "FAIL",
                "reason": "No contradiction-state router cleared the selector-audit gate",
            }
        )
        write_run_summary(
            ts=ts,
            mode="portfolio_contradiction_state_router",
            name="h250_contradiction_state_router",
            summary=summary,
            artifacts=artifacts,
            metadata=metadata,
        )
        return

    winner_signal = str(promoted.iloc[0]["signal_name"])
    h201_results, h201_winner_name = _load_h201_winner(Path(args.h201_summary))
    if h201_winner_name is None:
        summary.update(
            {
                "winner": promoted.iloc[0].to_dict(),
                "audit_skipped": True,
                "verdict": "MIXED",
                "reason": "H201 winner unavailable for direct comparison",
            }
        )
        write_run_summary(
            ts=ts,
            mode="portfolio_contradiction_state_router",
            name="h250_contradiction_state_router",
            summary=summary,
            artifacts=artifacts,
            metadata=metadata,
        )
        return

    audit_results, audit_daily_outputs, audit_scored = _audit_results(
        candidate_frame,
        bundle,
        args,
        winner_signal=winner_signal,
        h201_winner_name=h201_winner_name,
    )
    _print_audit_table(audit_results)

    audit_results_path = OUT_DIR / f"{ts}_h250_contradiction_state_router_audit_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h250_contradiction_state_router_best_daily.parquet"
    audit_scored_path = OUT_DIR / f"{ts}_h250_contradiction_state_router_audit_scored.parquet"
    audit_results.to_parquet(audit_results_path, index=False)
    audit_scored.to_parquet(audit_scored_path, index=False)
    best_row = promoted.iloc[0]
    best_daily_name = f"full_library_plus__{winner_signal}"
    audit_daily_outputs[best_daily_name].to_parquet(best_daily_path, index=False)
    artifacts.update(
        {
            "audit_results": str(audit_results_path),
            "best_daily": str(best_daily_path),
            "audit_scored": str(audit_scored_path),
        }
    )

    baseline_row = audit_results.loc[audit_results["strategy_name"] == "full_library_baseline"].iloc[0]
    h201_row = audit_results.loc[audit_results["strategy_name"] == h201_winner_name].iloc[0]
    winner_audit_row = audit_results.loc[audit_results["strategy_name"] == best_daily_name].iloc[0]
    passes_baseline = bool(winner_audit_row["passes_baseline_gate"])
    beats_h201 = bool(winner_audit_row["beats_h201_offline_lead"])
    verdict = "PASS" if passes_baseline and beats_h201 else "MIXED" if passes_baseline else "FAIL"

    summary.update(
        {
            "winner": best_row.to_dict(),
            "audit_skipped": False,
            "audit_candidate": winner_audit_row.to_dict(),
            "baseline": baseline_row.to_dict(),
            "h201_offline_lead": h201_row.to_dict(),
            "h201_summary_winner": h201_results.loc[h201_results["strategy_name"] == h201_winner_name].iloc[0].to_dict(),
            "passes_baseline_gate": passes_baseline,
            "beats_h201_offline_lead": beats_h201,
            "verdict": verdict,
        }
    )
    write_run_summary(
        ts=ts,
        mode="portfolio_contradiction_state_router",
        name="h250_contradiction_state_router",
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )


if __name__ == "__main__":
    main()
