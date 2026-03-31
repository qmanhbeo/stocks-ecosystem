"""
H249: Selector-relative activation audit for the H201 winner.

Purpose:
- test whether the H201 selector lead fails only because sticky activation is
  calibrated to full_library rather than to the selector's own recent returns
- keep the live branch frozen and evaluate offline on 2015-2025 only

Usage:
    conda run -n stocks python analysis/h249_selector_relative_activation_audit.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
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

from src.activation_alpha import BENCHMARK_PATH, RL_MATRIX_PATH, STOCK_DIR, TRADABILITY_PATH
from src.activation_meta import ACTIVATION_META_PATH, load_or_build_activation_meta, selector_meta_from_daily
from src.activation_meta_experiment_utils import selector_recent_relative_ewm_from_prev
from src.additive_selector_research import (
    additive_candidate_deltas,
    additive_candidate_passes,
    resolve_summary_artifact,
    summary_is_skipped,
)
from src.champion_activation_utils import align_series_to_market_dates
from src.deterministic_portfolio import (
    build_market_inputs,
    compute_strategy_scores,
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.repo_paths import artifact_path
from src.research_protocol import DEFAULT_PROTOCOL, PHASE_ORDER, assign_research_phase
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import (
    build_candidate_signal_frame,
    compute_phase_portfolio_summary,
    load_research_bundle,
)
from src.additive_selector_research import blend_state_scoped_scores


H201_SUMMARY_PATH = artifact_path("run_summaries/latest_portfolio_state_scoped_h199_atom_bakeoff.json")
OUT_DIR = artifact_path("portfolio_baselines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H249: selector-relative activation audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--activation-meta", type=str, default=str(ACTIVATION_META_PATH))
    parser.add_argument("--h201-summary", type=str, default=str(H201_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
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


def _parse_state_blend_name(strategy_name: str) -> tuple[str, float]:
    parts = str(strategy_name).split("__")
    if len(parts) != 3 or parts[0] != "state_blend":
        raise ValueError(f"Expected state blend strategy name, got {strategy_name!r}")
    return parts[1], float(parts[2]) / 100.0


def _phase_gate_summary(gate_frame: pd.DataFrame, *, value_column: str) -> dict[str, float | None]:
    assigned = gate_frame[["time", value_column]].copy()
    assigned["time"] = pd.to_datetime(assigned["time"], errors="coerce")
    assigned = assigned.dropna(subset=["time"]).reset_index(drop=True)
    assigned = assign_research_phase(assigned, date_column="time", protocol=DEFAULT_PROTOCOL)
    numeric = pd.to_numeric(assigned[value_column], errors="coerce")
    out: dict[str, float | None] = {
        "gate_share_overall": float(numeric.mean()) if not numeric.empty else None,
    }
    for phase in PHASE_ORDER:
        phase_frame = assigned.loc[assigned["research_phase"] == phase].copy()
        values = pd.to_numeric(phase_frame[value_column], errors="coerce")
        out[f"gate_share_{phase}"] = float(values.mean()) if not values.empty else None
    return out


def _row_from_result(
    *,
    variant: str,
    strategy_name: str,
    result,
    gate_summary: dict[str, float | None],
) -> dict[str, object]:
    phase_summary = compute_phase_portfolio_summary(result.daily, protocol=DEFAULT_PROTOCOL)
    row: dict[str, object] = {"variant": variant, "strategy_name": strategy_name}
    for phase in ("dev", "validation", "confirmation"):
        row[f"{phase}_relative_total_return"] = phase_summary[phase]["relative_total_return"]
        row[f"{phase}_information_ratio_annualized"] = phase_summary[phase]["information_ratio_annualized"]
        row[f"{phase}_avg_cash_weight"] = phase_summary[phase]["avg_cash_weight"]
        row[f"{phase}_avg_daily_turnover"] = phase_summary[phase]["avg_daily_turnover"]
    row.update(gate_summary)
    return row


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 212)
    print("H249: SELECTOR-RELATIVE ACTIVATION AUDIT")
    print("=" * 212)
    print(
        f"{'variant':<42} {'gate%':>8} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} "
        f"{'d_IR':>8} {'2025_rel':>10} {'2025_d':>9} {'promote':>8}"
    )
    print("-" * 212)
    for row in results.itertuples(index=False):
        print(
            f"{row.variant:<42} "
            f"{(row.gate_share_overall if row.gate_share_overall is not None else float('nan'))*100:>7.2f}% "
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
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if winner_name is None:
        summary = {
            "protocol": protocol.describe(),
            "skipped": True,
            "reason": "H201 produced no promoted winner",
        }
        write_run_summary(
            ts=ts,
            mode="portfolio_selector_relative_activation_audit",
            name="h249_selector_relative_activation_audit",
            summary=summary,
            artifacts={},
            metadata={"protocol": protocol.describe(), "h201_summary": str(args.h201_summary)},
        )
        print("H249 skipped: H201 produced no promoted winner.")
        return

    winner_row = h201_results.loc[h201_results["strategy_name"] == winner_name].iloc[0]
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

    price_panel = load_price_panel(selector_scored["ticker"].unique().tolist(), Path(args.stock_dir))
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, Path(args.tradability))
    benchmark_open = load_benchmark_open(Path(args.benchmark))
    market_inputs = build_market_inputs(
        selector_scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=["full_library", winner_name],
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )

    activation_meta, meta_source = load_or_build_activation_meta(
        out_path=Path(args.activation_meta),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
    )
    activation_meta = activation_meta[
        (activation_meta["time"].dt.year >= int(args.start_year))
        & (activation_meta["time"].dt.year <= int(args.end_year))
    ].copy()

    fee_leg = float(args.round_trip_cost) / 2.0
    holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    common_kwargs = dict(
        top_k=5,
        rebalance_every=5,
        weighting="equal",
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(holding_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=0.0,
    )

    winner_always_on_result = simulate_strategy(
        strategy_name=winner_name,
        signal_columns=[winner_name],
        market_inputs=market_inputs,
        activation_scale=None,
        incumbent_score_bonus=0.0,
        **common_kwargs,
    )
    winner_meta = selector_meta_from_daily(
        winner_always_on_result.daily,
        prefix="winner",
        rebalance_every=5,
    )
    selector_meta = activation_meta.merge(winner_meta, on="time", how="left", validate="one_to_one")

    full_rel2 = selector_recent_relative_ewm_from_prev(selector_meta, prefix="full", span=2)
    winner_rel2 = selector_recent_relative_ewm_from_prev(selector_meta, prefix="winner", span=2)
    full_rel2.index = pd.to_datetime(selector_meta["time"])
    winner_rel2.index = pd.to_datetime(selector_meta["time"])

    gate_frame = pd.DataFrame(
        {
            "time": pd.to_datetime(selector_meta["time"]).to_numpy(),
            "full_rel2": pd.to_numeric(full_rel2, errors="coerce").to_numpy(dtype=float),
            "winner_rel2": pd.to_numeric(winner_rel2, errors="coerce").to_numpy(dtype=float),
        }
    )
    gate_frame["full_gate_on"] = pd.to_numeric(gate_frame["full_rel2"], errors="coerce") > 0.0
    gate_frame["winner_gate_on"] = pd.to_numeric(gate_frame["winner_rel2"], errors="coerce") > 0.0
    gate_frame["gate_agree"] = gate_frame["full_gate_on"] == gate_frame["winner_gate_on"]

    full_activation_scale = align_series_to_market_dates(
        gate_frame.set_index("time")["full_gate_on"].astype(float),
        market_inputs.dates,
        fill_value=0.0,
    )
    winner_activation_scale = align_series_to_market_dates(
        gate_frame.set_index("time")["winner_gate_on"].astype(float),
        market_inputs.dates,
        fill_value=0.0,
    )

    gate_summaries = {
        "winner_always_on": {
            "gate_share_overall": 1.0,
            "gate_share_dev": 1.0,
            "gate_share_validation": 1.0,
            "gate_share_confirmation": 1.0,
            "gate_share_forward": None,
        },
        "winner_plus_full_rel2_sticky": _phase_gate_summary(gate_frame, value_column="full_gate_on"),
        "winner_plus_selector_rel2_sticky": _phase_gate_summary(gate_frame, value_column="winner_gate_on"),
        "full_library_plus_sticky": _phase_gate_summary(gate_frame, value_column="full_gate_on"),
    }

    rows = [
        _row_from_result(
            variant="winner_always_on",
            strategy_name=winner_name,
            result=winner_always_on_result,
            gate_summary=gate_summaries["winner_always_on"],
        )
    ]
    daily_outputs = {"winner_always_on": winner_always_on_result.daily.copy()}

    variant_specs = [
        {
            "variant": "winner_plus_full_rel2_sticky",
            "strategy_name": winner_name,
            "signal_columns": [winner_name],
            "activation_scale": full_activation_scale,
        },
        {
            "variant": "winner_plus_selector_rel2_sticky",
            "strategy_name": winner_name,
            "signal_columns": [winner_name],
            "activation_scale": winner_activation_scale,
        },
        {
            "variant": "full_library_plus_sticky",
            "strategy_name": "full_library",
            "signal_columns": list(full_library_columns),
            "activation_scale": full_activation_scale,
        },
    ]

    for spec in variant_specs:
        result = simulate_strategy(
            strategy_name=str(spec["strategy_name"]),
            signal_columns=list(spec["signal_columns"]),
            market_inputs=market_inputs,
            activation_scale=spec["activation_scale"],
            incumbent_score_bonus=float(args.incumbent_score_bonus),
            **common_kwargs,
        )
        rows.append(
            _row_from_result(
                variant=str(spec["variant"]),
                strategy_name=str(spec["strategy_name"]),
                result=result,
                gate_summary=gate_summaries[str(spec["variant"])],
            )
        )
        daily_outputs[str(spec["variant"])] = result.daily.copy()

    results = pd.DataFrame(rows)
    incumbent = results.loc[results["variant"] == "full_library_plus_sticky"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, incumbent)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = (
            False
            if row["variant"] != "winner_plus_selector_rel2_sticky"
            else additive_candidate_passes(row, incumbent)
        )

    results = results.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "variant",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    _print_table(results)

    agreement_summary = _phase_gate_summary(gate_frame, value_column="gate_agree")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h249_selector_relative_activation_audit_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h249_selector_relative_activation_audit_best_daily.parquet"
    selector_meta_path = OUT_DIR / f"{ts}_h249_selector_relative_activation_audit_selector_meta.parquet"
    gate_frame_path = OUT_DIR / f"{ts}_h249_selector_relative_activation_audit_gate_frame.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)
    selector_meta.to_parquet(selector_meta_path, index=False)
    gate_frame.to_parquet(gate_frame_path, index=False)

    summary = {
        "protocol": protocol.describe(),
        "h201_winner": winner_row.to_dict(),
        "incumbent": incumbent.to_dict(),
        "winner_selector_always_on": results.loc[results["variant"] == "winner_always_on"].iloc[0].to_dict(),
        "winner_selector_plus_full_rel2_sticky": results.loc[
            results["variant"] == "winner_plus_full_rel2_sticky"
        ].iloc[0].to_dict(),
        "winner_selector_plus_selector_rel2_sticky": results.loc[
            results["variant"] == "winner_plus_selector_rel2_sticky"
        ].iloc[0].to_dict(),
        "gate_agreement": agreement_summary,
        "promoted": bool(
            results.loc[results["variant"] == "winner_plus_selector_rel2_sticky", "promoted"].iloc[0]
        ),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_selector_relative_activation_audit",
        name="h249_selector_relative_activation_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "selector_meta": str(selector_meta_path),
            "gate_frame": str(gate_frame_path),
        },
        metadata={
            "protocol": protocol.describe(),
            "h201_summary": str(args.h201_summary),
            "activation_meta_source": meta_source,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
        },
    )


if __name__ == "__main__":
    main()
