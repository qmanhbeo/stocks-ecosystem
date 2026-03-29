from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from shared_market_rules import required_holding_age_for_sell

from src.deterministic_portfolio import (
    THESIS_FAMILY_COMPONENTS,
    build_market_inputs,
    compute_strategy_scores,
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.exit_alpha import ExitRuleSpec, build_exit_state_panel
from src.research_protocol import DEFAULT_PROTOCOL
from src.tradability_conditioned_research import compute_phase_portfolio_summary, load_research_bundle


@dataclass(frozen=True)
class ExitExperimentOutput:
    results: pd.DataFrame
    daily_outputs: dict[str, pd.DataFrame]
    exit_panels: dict[str, pd.DataFrame]


def load_full_library_backbone(
    *,
    matrix_path: Path,
    tradability_path: Path,
    stock_dir: Path,
    benchmark_path: Path,
    start_year: int,
    end_year: int,
) -> tuple[object, pd.DataFrame, object]:
    bundle = load_research_bundle(
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=int(start_year),
        end_year=int(end_year),
    )
    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    scored = compute_strategy_scores(bundle.matrix, {"full_library": list(full_library_columns)})
    price_panel = load_price_panel(scored["ticker"].unique().tolist(), stock_dir)
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)
    benchmark_open = load_benchmark_open(benchmark_path)
    market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=["full_library"],
        start_year=int(start_year),
        end_year=int(end_year),
        feature_frame=bundle.matrix,
        feature_columns=sorted({column for cols in THESIS_FAMILY_COMPONENTS.values() for column in cols if column in bundle.matrix.columns}),
    )
    return bundle, scored, market_inputs


def run_exit_variants(
    *,
    market_inputs,
    initial_notional_vnd: float,
    round_trip_cost: float,
    required_holding_age: int,
    variants: list[dict[str, object]],
) -> ExitExperimentOutput:
    protocol = DEFAULT_PROTOCOL
    fee_leg = float(round_trip_cost) / 2.0
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(required_holding_age))

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    exit_panels: dict[str, pd.DataFrame] = {}
    for spec in variants:
        result = simulate_strategy(
            strategy_name="full_library",
            signal_columns=["full_library"],
            market_inputs=market_inputs,
            top_k=5,
            rebalance_every=5,
            weighting="equal",
            initial_notional_vnd=float(initial_notional_vnd),
            max_adv_participation=0.0,
            required_holding_age=int(hold_age),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            capital_gains_tax_rate=0.0,
            capture_blotter=True,
            activation_scale=spec.get("activation_scale"),
            incumbent_score_bonus=float(spec.get("incumbent_score_bonus", 0.0)),
            exit_rule_name=spec.get("exit_rule_name"),
            exit_rule_params=spec.get("exit_rule_params"),
        )
        phase_summary = compute_phase_portfolio_summary(result.daily, protocol=protocol)
        row = {
            "variant": str(spec["variant"]),
            "exit_rule_name": spec.get("exit_rule_name"),
            "exit_rule_params": spec.get("exit_rule_params"),
        }
        for phase in ("dev", "validation", "confirmation"):
            row[f"{phase}_relative_total_return"] = phase_summary[phase]["relative_total_return"]
            row[f"{phase}_information_ratio_annualized"] = phase_summary[phase]["information_ratio_annualized"]
            row[f"{phase}_avg_cash_weight"] = phase_summary[phase]["avg_cash_weight"]
            row[f"{phase}_avg_daily_turnover"] = phase_summary[phase]["avg_daily_turnover"]
        row["overall_relative_total_return"] = result.summary["relative_total_return"]
        row["overall_information_ratio_annualized"] = result.summary["information_ratio_annualized"]
        row["exit_rule_trigger_events"] = result.summary.get("exit_rule_trigger_events")
        row["avg_exit_signal_count"] = result.summary.get("avg_exit_signal_count")
        rows.append(row)
        daily_outputs[str(spec["variant"])] = result.daily.copy()
        exit_panels[str(spec["variant"])] = build_exit_state_panel(result.blotter if result.blotter is not None else pd.DataFrame())

    return ExitExperimentOutput(
        results=pd.DataFrame(rows),
        daily_outputs=daily_outputs,
        exit_panels=exit_panels,
    )


def resolve_best_variant(
    results: pd.DataFrame,
    *,
    baseline_variant: str,
) -> tuple[pd.Series, pd.Series]:
    baseline = results.loc[results["variant"] == baseline_variant].iloc[0]
    ordered = results.sort_values(
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
    return baseline, ordered.iloc[0]
