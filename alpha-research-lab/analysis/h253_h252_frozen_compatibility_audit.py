"""
H253: Frozen compatibility audit for the H252 hard report-window gate.

Purpose:
- test whether the H252 hard-gated H201 selector can challenge the frozen sticky
  incumbent without touching 2026+
- keep the event branch narrow and reuse only the promoted H252 implementation
"""

from __future__ import annotations

import argparse
import json
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
    blend_state_scoped_scores,
    resolve_summary_artifact,
    summary_is_skipped,
)
from src.champion_activation_utils import align_series_to_market_dates, load_champion_setup
from src.deterministic_portfolio import (
    build_market_inputs,
    compute_strategy_scores,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.event_surface_trust_research import build_event_regime_activation_scale
from src.repo_paths import artifact_path
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import (
    build_candidate_signal_frame,
    compute_phase_portfolio_summary,
    load_research_bundle,
)


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H201_SUMMARY_PATH = artifact_path("run_summaries/latest_portfolio_state_scoped_h199_atom_bakeoff.json")
H252_SUMMARY_PATH = artifact_path("run_summaries/latest_portfolio_h201_event_surface_trust_audit.json")
OUT_DIR = artifact_path("portfolio_baselines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H253: H252 frozen compatibility audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h201-summary", type=str, default=str(H201_SUMMARY_PATH))
    parser.add_argument("--h252-summary", type=str, default=str(H252_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.015)
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


def _load_h252_promoted_winner(summary_path: Path) -> tuple[dict[str, object], Path]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    best_candidate = summary.get("best_candidate", {})
    if not isinstance(best_candidate, dict) or not best_candidate:
        raise ValueError("H253 requires a non-empty H252 best candidate")
    if not bool(best_candidate.get("promoted")):
        raise ValueError("H253 requires H252 best candidate to be promoted")
    if str(best_candidate.get("variant")) != "winner_report_window_gate":
        raise ValueError("H253 only supports the promoted H252 hard report-window gate")
    regime_name = str(best_candidate.get("regime_name"))
    if regime_name != "top5_report_window_ge2":
        raise ValueError("H253 only supports the H252 top5_report_window_ge2 regime")
    topk_frame_path = resolve_summary_artifact(summary_path, "topk_frame")
    return best_candidate, topk_frame_path


def _parse_state_blend_name(strategy_name: str) -> tuple[str, float]:
    parts = str(strategy_name).split("__")
    if len(parts) != 3 or parts[0] != "state_blend":
        raise ValueError(f"Expected state blend strategy name, got {strategy_name!r}")
    return parts[1], float(parts[2]) / 100.0


def _phase_avg_activation_scale(daily: pd.DataFrame) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    for phase_name, years in (
        (
            "validation",
            set(
                range(
                    int(DEFAULT_PROTOCOL.validation_start_year),
                    int(DEFAULT_PROTOCOL.validation_end_year) + 1,
                )
            ),
        ),
        ("confirmation", {int(DEFAULT_PROTOCOL.confirmation_year)}),
    ):
        phase = work.loc[work["execution_date"].dt.year.isin(years)].copy()
        out[phase_name] = (
            None if phase.empty else float(pd.to_numeric(phase["activation_scale"], errors="coerce").mean())
        )
    return out


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 196)
    print("H253: H252 FROZEN COMPATIBILITY AUDIT")
    print("=" * 196)
    print(
        f"{'variant':<34} {'val_rel':>10} {'d_inc':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'d_inc':>9} {'cash':>8} {'promote':>8}"
    )
    print("-" * 196)
    for row in results.itertuples(index=False):
        print(
            f"{row.variant:<34} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.validation_ir_delta if row.validation_ir_delta is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{(row.validation_avg_cash_weight or 0.0)*100:>7.2f}% "
            f"{str(bool(row.promoted)):>8}"
        )


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    h201_results, winner_name = _load_h201_winner(Path(args.h201_summary))
    if winner_name is None:
        raise ValueError("H253 requires an H201 winner")

    winner_row = h201_results.loc[h201_results["strategy_name"] == winner_name].iloc[0]
    h252_winner, topk_frame_path = _load_h252_promoted_winner(Path(args.h252_summary))
    if str(h252_winner.get("strategy_name")) != winner_name:
        raise ValueError("H253 requires H252 promoted winner to use the H201 selector")
    regime_name = str(h252_winner["regime_name"])

    atom, atom_weight = _parse_state_blend_name(winner_name)
    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    candidate_frame = build_candidate_signal_frame(bundle, start_year=int(args.start_year), end_year=int(args.end_year))
    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )

    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    merged = bundle.matrix.merge(
        candidate_frame[["time", "ticker", atom]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    base_scored = compute_strategy_scores(
        merged,
        {"full_library": list(full_library_columns), atom: [atom]},
    )
    selector_scored = base_scored[["time", "ticker", "actual", "score__full_library"]].copy()
    selector_scored[f"score__{winner_name}"] = blend_state_scoped_scores(
        pd.to_numeric(base_scored["score__full_library"], errors="coerce"),
        pd.to_numeric(base_scored[f"score__{atom}"], errors="coerce"),
        liq_open_basic,
        atom_weight=float(atom_weight),
    )

    market_inputs = build_market_inputs(
        selector_scored,
        bundle.price_panel,
        bundle.tradability,
        bundle.benchmark_open,
        tradability_source=bundle.tradability_source,
        strategy_names=["full_library", winner_name],
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    topk_frame = pd.read_parquet(topk_frame_path)
    topk_frame["time"] = pd.to_datetime(topk_frame["time"])
    gate_schedule = build_event_regime_activation_scale(
        topk_frame,
        strategy_name=winner_name,
        regime_name=regime_name,
        on_scale=1.0,
        off_scale=0.0,
        all_dates=market_inputs.dates,
    )
    activation_scale = align_series_to_market_dates(gate_schedule, market_inputs.dates, fill_value=0.0)
    on_mask = pd.Series(activation_scale).round(12) == 1.0
    date_years = pd.Series(pd.to_datetime(market_inputs.dates)).dt.year

    champion_setup = load_champion_setup(
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
    )
    sticky_scale = align_series_to_market_dates(
        (champion_setup.rel2 > 0.0).astype(float),
        market_inputs.dates,
        fill_value=0.0,
    )
    fee_leg = float(args.round_trip_cost) / 2.0
    holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))

    variants = [
        {
            "variant": "winner_report_window_gate",
            "strategy_name": winner_name,
            "signal_columns": [winner_name],
            "activation_scale": activation_scale,
            "incumbent_score_bonus": 0.0,
            "regime_name": regime_name,
            "gate_share_overall": float(on_mask.mean()),
            "gate_share_validation": float(
                on_mask.loc[
                    date_years.isin(
                        range(
                            int(protocol.validation_start_year),
                            int(protocol.validation_end_year) + 1,
                        )
                    )
                ].mean()
            ),
            "gate_share_confirmation": float(on_mask.loc[date_years == int(protocol.confirmation_year)].mean()),
        },
        {
            "variant": "winner_always_on",
            "strategy_name": winner_name,
            "signal_columns": [winner_name],
            "activation_scale": None,
            "incumbent_score_bonus": 0.0,
            "regime_name": None,
            "gate_share_overall": 1.0,
            "gate_share_validation": 1.0,
            "gate_share_confirmation": 1.0,
        },
        {
            "variant": "full_library_plus_sticky",
            "strategy_name": "full_library",
            "signal_columns": list(full_library_columns),
            "activation_scale": sticky_scale,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
            "regime_name": "sticky_rel2_gt0",
            "gate_share_overall": float((pd.Series(sticky_scale) > 0.0).mean()),
            "gate_share_validation": float(
                (pd.Series(sticky_scale) > 0.0)
                .loc[
                    date_years.isin(
                        range(
                            int(protocol.validation_start_year),
                            int(protocol.validation_end_year) + 1,
                        )
                    )
                ]
                .mean()
            ),
            "gate_share_confirmation": float(
                (pd.Series(sticky_scale) > 0.0).loc[date_years == int(protocol.confirmation_year)].mean()
            ),
        },
    ]

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for spec in variants:
        result = simulate_strategy(
            strategy_name=str(spec["strategy_name"]),
            signal_columns=list(spec["signal_columns"]),
            market_inputs=market_inputs,
            top_k=int(args.top_k),
            rebalance_every=5,
            weighting="equal",
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            max_adv_participation=0.0,
            required_holding_age=int(holding_age),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            capital_gains_tax_rate=0.0,
            activation_scale=spec["activation_scale"],
            incumbent_score_bonus=float(spec["incumbent_score_bonus"]),
        )
        phase_summary = compute_phase_portfolio_summary(result.daily, protocol=protocol)
        avg_scales = _phase_avg_activation_scale(result.daily)
        row = {
            "variant": str(spec["variant"]),
            "strategy_name": str(spec["strategy_name"]),
            "regime_name": spec["regime_name"],
            "gate_share_overall": float(spec["gate_share_overall"]),
            "gate_share_validation": float(spec["gate_share_validation"]),
            "gate_share_confirmation": float(spec["gate_share_confirmation"]),
            "validation_avg_activation_scale": avg_scales["validation"],
            "confirmation_avg_activation_scale": avg_scales["confirmation"],
        }
        for phase in ("dev", "validation", "confirmation"):
            row[f"{phase}_relative_total_return"] = phase_summary[phase]["relative_total_return"]
            row[f"{phase}_information_ratio_annualized"] = phase_summary[phase]["information_ratio_annualized"]
            row[f"{phase}_avg_cash_weight"] = phase_summary[phase]["avg_cash_weight"]
            row[f"{phase}_avg_daily_turnover"] = phase_summary[phase]["avg_daily_turnover"]
        rows.append(row)
        daily_outputs[str(spec["variant"])] = result.daily.copy()

    results = pd.DataFrame(rows)
    incumbent = results.loc[results["variant"] == "full_library_plus_sticky"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, incumbent)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        candidate_variant = str(row["variant"]) == "winner_report_window_gate"
        results.loc[idx, "promoted"] = bool(candidate_variant and additive_candidate_passes(row, incumbent))
        validation_improves = (
            float(pd.to_numeric(results.loc[idx, "validation_relative_delta"], errors="coerce")) > 0.0
            or float(pd.to_numeric(results.loc[idx, "validation_ir_delta"], errors="coerce")) > 0.0
        )
        confirmation_improves = (
            float(pd.to_numeric(results.loc[idx, "confirmation_relative_delta"], errors="coerce")) > 0.0
            or float(pd.to_numeric(results.loc[idx, "confirmation_ir_delta"], errors="coerce")) > 0.0
        )
        results.loc[idx, "mixed"] = bool(
            candidate_variant
            and not bool(results.loc[idx, "promoted"])
            and (validation_improves or confirmation_improves)
        )

    results = results.sort_values(
        by=[
            "promoted",
            "mixed",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "variant",
        ],
        ascending=[False, False, False, False, False, True],
        ignore_index=True,
    )
    _print_table(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h253_h252_frozen_compatibility_audit_results.parquet"
    candidate_daily_path = OUT_DIR / f"{ts}_h253_h252_frozen_compatibility_audit_candidate_daily.parquet"
    gate_frame_path = OUT_DIR / f"{ts}_h253_h252_frozen_compatibility_audit_gate_frame.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs["winner_report_window_gate"].to_parquet(candidate_daily_path, index=False)
    pd.DataFrame(
        {
            "time": pd.to_datetime(market_inputs.dates),
            "winner_report_window_gate": pd.Series(activation_scale, dtype=float),
            "full_library_plus_sticky": pd.Series(sticky_scale, dtype=float),
        }
    ).to_parquet(gate_frame_path, index=False)

    promoted = results.loc[results["promoted"]].copy()
    mixed = results.loc[results["mixed"]].copy()
    verdict = "PASS" if not promoted.empty else "MIXED" if not mixed.empty else "FAIL"
    summary = {
        "protocol": protocol.describe(),
        "h201_winner": winner_row.to_dict(),
        "h252_best_candidate": h252_winner,
        "incumbent": incumbent.to_dict(),
        "winner_always_on": results.loc[results["variant"] == "winner_always_on"].iloc[0].to_dict(),
        "winner_report_window_gate": results.loc[results["variant"] == "winner_report_window_gate"].iloc[0].to_dict(),
        "verdict": verdict,
        "promoted": bool(results.loc[results["variant"] == "winner_report_window_gate", "promoted"].iloc[0]),
        "mixed": bool(results.loc[results["variant"] == "winner_report_window_gate", "mixed"].iloc[0]),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_h252_frozen_compatibility_audit",
        name="h253_h252_frozen_compatibility_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "candidate_daily": str(candidate_daily_path),
            "gate_frame": str(gate_frame_path),
        },
        metadata={
            "protocol": protocol.describe(),
            "h201_summary": str(args.h201_summary),
            "h252_summary": str(args.h252_summary),
            "regime_name": regime_name,
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
    )


if __name__ == "__main__":
    main()
