"""
H252: Light offline trust audit for H201 using promoted H251 event regimes.

Purpose:
- keep event-surface reuse narrow after H251
- audit whether date-level event trust can improve the H201 offline lead through
  mild exposure control, without reopening a broader event-family search
- keep the live sticky branch frozen and avoid any 2026+ read
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
from src.champion_activation_utils import align_series_to_market_dates
from src.deterministic_portfolio import build_market_inputs, compute_strategy_scores, simulate_strategy, resolve_strategy_columns
from src.event_surface_trust_research import (
    EVENT_TRUST_REGIME_SPECS,
    build_event_regime_activation_scale,
    build_topk_event_regime_frame,
)
from src.repo_paths import artifact_path
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import compute_phase_portfolio_summary, load_research_bundle, build_candidate_signal_frame


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
EVENT_SURFACE_PATH = data_path("features/event_surface_daily.parquet")
H201_SUMMARY_PATH = artifact_path("run_summaries/latest_portfolio_state_scoped_h199_atom_bakeoff.json")
H251_SUMMARY_PATH = artifact_path("run_summaries/latest_portfolio_event_surface_trust_modulator.json")
OUT_DIR = artifact_path("portfolio_baselines")

PRIMARY_REGIME_NAME = "top5_report_window_ge2"
SECONDARY_REGIME_NAME = "top5_recent_filing_ge1"
VARIANT_SPECS = (
    {
        "variant": "winner_always_on",
        "regime_name": None,
        "on_scale": 1.0,
        "off_scale": 1.0,
    },
    {
        "variant": "winner_report_window_gate",
        "regime_name": PRIMARY_REGIME_NAME,
        "on_scale": 1.0,
        "off_scale": 0.0,
    },
    {
        "variant": "winner_report_window_half_off",
        "regime_name": PRIMARY_REGIME_NAME,
        "on_scale": 1.0,
        "off_scale": 0.5,
    },
    {
        "variant": "winner_recent_filing_half_off",
        "regime_name": SECONDARY_REGIME_NAME,
        "on_scale": 1.0,
        "off_scale": 0.5,
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H252: H201 event-surface trust audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--event-surface", type=str, default=str(EVENT_SURFACE_PATH))
    parser.add_argument("--h201-summary", type=str, default=str(H201_SUMMARY_PATH))
    parser.add_argument("--h251-summary", type=str, default=str(H251_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--top-k", type=int, default=5)
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


def _load_h251_promoted_regimes(summary_path: Path) -> list[str]:
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    promoted = payload.get("summary", {}).get("promoted_candidates", [])
    names = []
    for row in promoted:
        if not isinstance(row, dict):
            continue
        regime_name = row.get("regime_name")
        if regime_name:
            names.append(str(regime_name))
    return names


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
    print("\n" + "=" * 198)
    print("H252: H201 EVENT-SURFACE TRUST AUDIT")
    print("=" * 198)
    print(
        f"{'variant':<34} {'regime':<24} {'off':>6} {'val_rel':>10} {'d_rel':>9} "
        f"{'val_IR':>8} {'d_IR':>8} {'2025_rel':>10} {'2025_d':>9} {'promote':>8}"
    )
    print("-" * 198)
    for row in results.itertuples(index=False):
        print(
            f"{row.variant:<34} "
            f"{(row.regime_name or '-'): <24} "
            f"{row.off_scale:>5.2f} "
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
    protocol = DEFAULT_PROTOCOL
    h201_results, winner_name = _load_h201_winner(Path(args.h201_summary))
    if winner_name is None:
        raise ValueError("H252 requires an H201 winner")

    promoted_regimes = _load_h251_promoted_regimes(Path(args.h251_summary))
    for required_regime in (PRIMARY_REGIME_NAME, SECONDARY_REGIME_NAME):
        if required_regime not in promoted_regimes:
            raise ValueError(f"H252 requires H251-promoted regime {required_regime!r}")

    winner_row = h201_results.loc[h201_results["strategy_name"] == winner_name].iloc[0]
    h201_atom, h201_weight = _parse_state_blend_name(winner_name)

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
        candidate_frame[["time", "ticker", h201_atom]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    base_scored = compute_strategy_scores(
        merged,
        {"full_library": list(full_library_columns), h201_atom: [h201_atom]},
    )
    selector_scored = base_scored[["time", "ticker", "actual", "score__full_library"]].copy()
    selector_scored[f"score__{winner_name}"] = blend_state_scoped_scores(
        pd.to_numeric(base_scored["score__full_library"], errors="coerce"),
        pd.to_numeric(base_scored[f"score__{h201_atom}"], errors="coerce"),
        liq_open_basic,
        atom_weight=float(h201_weight),
    )

    event_surface = pd.read_parquet(Path(args.event_surface))
    event_surface["time"] = pd.to_datetime(event_surface["time"])
    event_surface = event_surface[
        (event_surface["time"].dt.year >= int(args.start_year))
        & (event_surface["time"].dt.year <= int(args.end_year))
    ].copy()
    topk_frame = build_topk_event_regime_frame(
        selector_scored[["time", "ticker", "actual", f"score__{winner_name}"]].copy(),
        strategy_names=[winner_name],
        event_surface=event_surface,
        top_k=int(args.top_k),
    )

    market_inputs = build_market_inputs(
        selector_scored[["time", "ticker", "actual", f"score__{winner_name}"]].copy(),
        bundle.price_panel,
        bundle.tradability,
        bundle.benchmark_open,
        tradability_source=bundle.tradability_source,
        strategy_names=[winner_name],
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    fee_leg = float(args.round_trip_cost) / 2.0
    holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for spec in VARIANT_SPECS:
        activation_scale = None
        gate_share_overall = 1.0
        gate_share_validation = 1.0
        gate_share_confirmation = 1.0
        if spec["regime_name"] is not None:
            schedule = build_event_regime_activation_scale(
                topk_frame,
                strategy_name=winner_name,
                regime_name=str(spec["regime_name"]),
                on_scale=float(spec["on_scale"]),
                off_scale=float(spec["off_scale"]),
                all_dates=market_inputs.dates,
            )
            activation_scale = align_series_to_market_dates(schedule, market_inputs.dates, fill_value=float(spec["off_scale"]))
            on_value = float(spec["on_scale"])
            on_mask = pd.Series(activation_scale).round(12) == round(on_value, 12)
            date_years = pd.Series(pd.to_datetime(market_inputs.dates)).dt.year
            gate_share_overall = float(on_mask.mean())
            gate_share_validation = float(
                on_mask.loc[
                    date_years.isin(
                        range(
                            int(protocol.validation_start_year),
                            int(protocol.validation_end_year) + 1,
                        )
                    )
                ].mean()
            )
            gate_share_confirmation = float(on_mask.loc[date_years == int(protocol.confirmation_year)].mean())

        result = simulate_strategy(
            strategy_name=winner_name,
            signal_columns=[winner_name],
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
            activation_scale=activation_scale,
            incumbent_score_bonus=0.0,
        )
        phase_summary = compute_phase_portfolio_summary(result.daily, protocol=protocol)
        avg_scales = _phase_avg_activation_scale(result.daily)

        row = {
            "variant": str(spec["variant"]),
            "strategy_name": winner_name,
            "regime_name": spec["regime_name"],
            "count_column": None if spec["regime_name"] is None else EVENT_TRUST_REGIME_SPECS[str(spec["regime_name"])][0],
            "threshold": None if spec["regime_name"] is None else int(EVENT_TRUST_REGIME_SPECS[str(spec["regime_name"])][1]),
            "on_scale": float(spec["on_scale"]),
            "off_scale": float(spec["off_scale"]),
            "gate_share_overall": gate_share_overall,
            "gate_share_validation": gate_share_validation,
            "gate_share_confirmation": gate_share_confirmation,
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
    baseline = results.loc[results["variant"] == "winner_always_on"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        validation_improves = (
            float(pd.to_numeric(results.loc[idx, "validation_relative_delta"], errors="coerce")) > 0.0
            or float(pd.to_numeric(results.loc[idx, "validation_ir_delta"], errors="coerce")) > 0.0
        )
        confirmation_improves = (
            float(pd.to_numeric(results.loc[idx, "confirmation_relative_delta"], errors="coerce")) > 0.0
            or float(pd.to_numeric(results.loc[idx, "confirmation_ir_delta"], errors="coerce")) > 0.0
        )
        results.loc[idx, "promoted"] = (
            False if row["variant"] == "winner_always_on" else additive_candidate_passes(row, baseline)
        )
        results.loc[idx, "mixed"] = bool(
            row["variant"] != "winner_always_on"
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
    results_path = OUT_DIR / f"{ts}_h252_h201_event_surface_trust_audit_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h252_h201_event_surface_trust_audit_best_daily.parquet"
    topk_frame_path = OUT_DIR / f"{ts}_h252_h201_event_surface_trust_audit_topk_frame.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)
    topk_frame.to_parquet(topk_frame_path, index=False)

    promoted = results.loc[results["promoted"]].copy()
    mixed = results.loc[results["mixed"]].copy()
    verdict = "PASS" if not promoted.empty else "MIXED" if not mixed.empty else "FAIL"
    summary = {
        "protocol": protocol.describe(),
        "h201_winner": winner_row.to_dict(),
        "h251_promoted_regimes": promoted_regimes,
        "baseline": baseline.to_dict(),
        "best_candidate": results.iloc[0].to_dict() if not results.empty else {},
        "verdict": verdict,
        "promoted_candidates": promoted[
            [
                "variant",
                "regime_name",
                "off_scale",
                "validation_relative_delta",
                "validation_ir_delta",
                "confirmation_relative_delta",
                "confirmation_ir_delta",
            ]
        ].to_dict("records"),
        "mixed_candidates": mixed[
            [
                "variant",
                "regime_name",
                "off_scale",
                "validation_relative_delta",
                "validation_ir_delta",
                "confirmation_relative_delta",
                "confirmation_ir_delta",
            ]
        ].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_h201_event_surface_trust_audit",
        name="h252_h201_event_surface_trust_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "topk_frame": str(topk_frame_path),
        },
        metadata={
            "protocol": protocol.describe(),
            "event_surface": str(args.event_surface),
            "h201_summary": str(args.h201_summary),
            "h251_summary": str(args.h251_summary),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
        },
    )


if __name__ == "__main__":
    main()
