"""
H151: Narrow tradability-conditioned composite bakeoff.

Purpose:
- reopen selection-side research without touching the frozen live sticky branch
- test whether the H150 conditional winners form a stronger selector than the current full-library baseline
- enforce the locked discovery / validation / confirmation protocol in code

Usage:
    conda run -n stocks python analysis/h151_tradability_conditioned_composite_bakeoff.py
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

from src.deterministic_portfolio import RESERVED_COLUMNS, compute_strategy_scores, default_strategy_names, resolve_strategy_columns
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import (
    compute_phase_portfolio_summary,
    evaluate_signal_ic_by_phase,
    load_research_bundle,
    run_selector_candidate,
)


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


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
    print("\n" + "=" * 176)
    print("H151: TRADABILITY-CONDITIONED COMPOSITE BAKEOFF")
    print("=" * 176)
    print(
        f"{'strategy':<18} {'dev_rel':>10} {'val_rel':>10} {'conf_rel':>10} "
        f"{'val_IR':>8} {'conf_IR':>8} {'liq_ic_dev':>11} {'liq_ic_val':>11} {'liq_ic_2025':>12} {'promote':>8}"
    )
    print("-" * 176)
    for row in results.itertuples(index=False):
        print(
            f"{row.strategy_name:<18} "
            f"{(row.dev_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.confirmation_information_ratio_annualized if row.confirmation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.liq_open_basic_dev_avg_ic if row.liq_open_basic_dev_avg_ic is not None else float('nan'):>+10.4f} "
            f"{row.liq_open_basic_validation_avg_ic if row.liq_open_basic_validation_avg_ic is not None else float('nan'):>+10.4f} "
            f"{row.liq_open_basic_confirmation_avg_ic if row.liq_open_basic_confirmation_avg_ic is not None else float('nan'):>+11.4f} "
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

    available = [column for column in bundle.matrix.columns if column not in RESERVED_COLUMNS]
    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    strategies = {
        "full_library_baseline": full_library_columns,
        "core_4": ["s1_proba", "c7_ceiling_count_5d", "c12_gap_absorb_3", "c13_compress_blowoff_2"],
        "core_5": ["s1_proba", "c7_ceiling_count_5d", "c10_illiq_level_rank", "c12_gap_absorb_3", "c13_compress_blowoff_2"],
        "core_6": ["s1_proba", "c7_ceiling_count_5d", "c8_vol_zscore_5d", "c10_illiq_level_rank", "c12_gap_absorb_3", "c13_compress_blowoff_2"],
    }
    missing = sorted({column for cols in strategies.values() for column in cols} - set(available))
    if missing:
        raise ValueError(f"Missing signal columns for H151: {missing}")

    scored = compute_strategy_scores(bundle.matrix, strategies)
    scored_with_states = scored.merge(
        bundle.matrix[["time", "ticker", "s1_proba"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    ).merge(
        bundle.feature_frame[["time", "ticker", "tv_to_adv20", "clv", "can_buy_next_open"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    liq_open_basic = (
        (pd.to_numeric(scored_with_states["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(scored_with_states["clv"], errors="coerce") >= 0.45)
        & scored_with_states["can_buy_next_open"].fillna(False).astype(bool)
    )
    liq_open_strict = (
        (pd.to_numeric(scored_with_states["tv_to_adv20"], errors="coerce") >= 1.25)
        & (pd.to_numeric(scored_with_states["clv"], errors="coerce") >= 0.50)
        & scored_with_states["can_buy_next_open"].fillna(False).astype(bool)
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
        ic_strict = evaluate_signal_ic_by_phase(
            scored_with_states,
            signal_column=f"score__{strategy_name}",
            state_mask=liq_open_strict,
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
            row[f"liq_open_basic_{phase}_avg_ic"] = ic_basic[phase]["avg_ic"]
            row[f"liq_open_basic_{phase}_corr_with_s1"] = ic_basic[phase]["corr_with_s1"]
            row[f"liq_open_basic_{phase}_pct_years_positive"] = ic_basic[phase]["pct_years_positive"]
            row[f"liq_open_strict_{phase}_avg_ic"] = ic_strict[phase]["avg_ic"]
        rows.append(row)
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    results["beats_validation_baseline"] = (
        (pd.to_numeric(results["validation_relative_total_return"], errors="coerce") > float(baseline["validation_relative_total_return"]))
        | (pd.to_numeric(results["validation_information_ratio_annualized"], errors="coerce") > float(baseline["validation_information_ratio_annualized"]))
    )
    results["survives_confirmation"] = (
        (pd.to_numeric(results["confirmation_relative_total_return"], errors="coerce") > 0.0)
        | (pd.to_numeric(results["confirmation_information_ratio_annualized"], errors="coerce") > 0.0)
    )
    results["promoted"] = results["beats_validation_baseline"] & results["survives_confirmation"]
    results = results.sort_values(
        by=[
            "promoted",
            "validation_relative_total_return",
            "validation_information_ratio_annualized",
            "confirmation_relative_total_return",
            "strategy_name",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )

    _print_table(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h151_tradability_conditioned_composite_bakeoff_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h151_tradability_conditioned_composite_bakeoff_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["strategy_name"])].to_parquet(best_daily_path, index=False)

    promoted = results.loc[results["promoted"]].copy()
    summary = {
        "protocol": protocol.describe(),
        "baseline": baseline.to_dict(),
        "winner": results.iloc[0].to_dict(),
        "promoted_candidates": promoted[["strategy_name", "validation_relative_total_return", "confirmation_relative_total_return"]].to_dict("records"),
        "tested_candidates": results[["strategy_name", "validation_relative_total_return", "validation_information_ratio_annualized", "confirmation_relative_total_return", "promoted"]].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_tradability_composite_bakeoff",
        name="h151_tradability_conditioned_composite_bakeoff",
        summary=summary,
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path)},
        metadata={"protocol": protocol.describe(), "start_year": int(args.start_year), "end_year": int(args.end_year)},
    )


if __name__ == "__main__":
    main()
