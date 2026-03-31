"""
H196: One-atom additive bakeoff on top of the full-library selector backbone.

Purpose:
- test whether the H152 tradability-conditioned survivors help as additive atoms
- keep the live sticky branch frozen while improving the offline selector only
- enforce the locked dev / validation / confirmation protocol

Usage:
    conda run -n stocks python analysis/h196_additive_atom_bakeoff.py
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

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes
from src.deterministic_portfolio import RESERVED_COLUMNS, compute_strategy_scores, resolve_strategy_columns
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import (
    compute_phase_portfolio_summary,
    evaluate_signal_ic_by_phase,
    load_research_bundle,
    build_candidate_signal_frame,
    run_selector_candidate,
)


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"

ATOM_SIGNALS = (
    "h152_sector_laggard_tradable",
    "h152_limit_release_pressure",
    "h152_liq_open_continue_3",
    "h152_breakout_volume_quality",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 188)
    print("H196: ONE-ATOM ADDITIVE BAKEOFF")
    print("=" * 188)
    print(
        f"{'strategy':<42} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'liq_ic_val':>11} {'promote':>8}"
    )
    print("-" * 188)
    for row in results.itertuples(index=False):
        print(
            f"{row.strategy_name:<42} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.validation_ir_delta if row.validation_ir_delta is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{row.liq_open_basic_validation_avg_ic if row.liq_open_basic_validation_avg_ic is not None else float('nan'):>+10.4f} "
            f"{str(bool(row.promoted)):>8}"
        )


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
    missing_atoms = sorted(set(ATOM_SIGNALS) - set(candidate_frame.columns))
    if missing_atoms:
        raise ValueError(f"Missing H152 atoms for H196: {missing_atoms}")

    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )

    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    merged = bundle.matrix.merge(
        candidate_frame[["time", "ticker"] + list(ATOM_SIGNALS)],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    available = [column for column in merged.columns if column not in RESERVED_COLUMNS]
    missing = sorted(set(full_library_columns) - set(available))
    if missing:
        raise ValueError(f"Missing full-library columns for H196: {missing}")

    strategies = {"full_library_baseline": list(full_library_columns)}
    for atom in ATOM_SIGNALS:
        strategies[f"full_library_plus__{atom}"] = list(full_library_columns) + [atom]

    scored = compute_strategy_scores(merged, strategies)
    scored_with_states = scored.merge(
        candidate_frame[["time", "ticker", "s1_proba", "tv_to_adv20", "clv", "can_buy_next_open"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    fee_leg = float(args.round_trip_cost) / 2.0
    required_holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
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
        phase_summary = compute_phase_portfolio_summary(result.daily, protocol=protocol)
        ic_basic = evaluate_signal_ic_by_phase(
            scored_with_states,
            signal_column=f"score__{strategy_name}",
            state_mask=liq_open_basic,
            protocol=protocol,
        )
        row = {
            "strategy_name": strategy_name,
            "signal_columns": list(signal_columns),
            "overall_relative_total_return": float(result.summary["relative_total_return"]),
            "overall_information_ratio_annualized": result.summary["information_ratio_annualized"],
        }
        for phase in ("dev", "validation", "confirmation"):
            row[f"{phase}_relative_total_return"] = phase_summary[phase]["relative_total_return"]
            row[f"{phase}_information_ratio_annualized"] = phase_summary[phase]["information_ratio_annualized"]
            row[f"{phase}_avg_cash_weight"] = phase_summary[phase]["avg_cash_weight"]
            row[f"{phase}_avg_daily_turnover"] = phase_summary[phase]["avg_daily_turnover"]
            row[f"liq_open_basic_{phase}_avg_ic"] = ic_basic[phase]["avg_ic"]
            row[f"liq_open_basic_{phase}_corr_with_s1"] = ic_basic[phase]["corr_with_s1"]
        rows.append(row)
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = (
            False if row["strategy_name"] == "full_library_baseline" else additive_candidate_passes(row, baseline)
        )

    results = results.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "strategy_name",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )

    _print_table(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h196_additive_atom_bakeoff_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h196_additive_atom_bakeoff_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["strategy_name"])].to_parquet(best_daily_path, index=False)

    promoted = results.loc[results["promoted"]].copy()
    summary = {
        "protocol": protocol.describe(),
        "baseline": baseline.to_dict(),
        "winner": results.iloc[0].to_dict(),
        "promoted_candidates": promoted[
            [
                "strategy_name",
                "validation_relative_delta",
                "validation_ir_delta",
                "confirmation_relative_delta",
                "confirmation_ir_delta",
            ]
        ].to_dict("records"),
        "tested_candidates": results[
            [
                "strategy_name",
                "validation_relative_total_return",
                "validation_relative_delta",
                "validation_information_ratio_annualized",
                "validation_ir_delta",
                "confirmation_relative_total_return",
                "confirmation_relative_delta",
                "promoted",
            ]
        ].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_additive_atom_bakeoff",
        name="h196_additive_atom_bakeoff",
        summary=summary,
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path)},
        metadata={"protocol": protocol.describe(), "start_year": int(args.start_year), "end_year": int(args.end_year)},
    )


if __name__ == "__main__":
    main()
