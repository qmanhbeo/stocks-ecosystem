"""
H204: Third-wave tradability-conditioned signal search.

Purpose:
- search for a fresh family of tradability-transition atoms after the H203/H205 pair branch fails
- keep the live sticky branch frozen while reopening only selector discovery
- enforce the locked dev / validation / confirmation protocol

Usage:
    conda run -n stocks python analysis/h204_third_wave_tradability_conditioned_search.py
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

from src.deterministic_portfolio import compute_strategy_scores
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


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"

THIRD_WAVE_SIGNALS = (
    "h204_sector_accel_release",
    "h204_ceiling_memory_gap_absorb",
    "h204_breakout_sector_accel_buyable",
    "h204_sector_mom_laggard_volume",
    "h204_release_after_floor_pressure",
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


def _print_signal_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 196)
    print("H204: THIRD-WAVE TRADABILITY-CONDITIONED SIGNAL SEARCH")
    print("=" * 196)
    print(
        f"{'signal':<36} {'dev_ic':>9} {'dev_corr':>9} {'dev_yrs+':>9} "
        f"{'val_ic':>9} {'2025_ic':>9} {'gate':>6} {'port_val':>10} {'port_2025':>10} {'promote':>8}"
    )
    print("-" * 196)
    for row in results.itertuples(index=False):
        dev_pos = 0.0 if row.dev_pct_years_positive is None else row.dev_pct_years_positive * 100.0
        print(
            f"{row.signal_name:<36} "
            f"{row.dev_avg_ic if row.dev_avg_ic is not None else float('nan'):>+8.4f} "
            f"{row.dev_corr_with_s1 if row.dev_corr_with_s1 is not None else float('nan'):>+8.4f} "
            f"{dev_pos:>8.1f}% "
            f"{row.validation_avg_ic if row.validation_avg_ic is not None else float('nan'):>+8.4f} "
            f"{row.confirmation_avg_ic if row.confirmation_avg_ic is not None else float('nan'):>+8.4f} "
            f"{str(bool(row.dev_gate_pass)):>6} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{str(bool(row.promoted_to_composite_stage)):>8}"
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
    missing_signals = sorted(set(THIRD_WAVE_SIGNALS) - set(candidate_frame.columns))
    if missing_signals:
        raise ValueError(f"Missing H204 signal columns: {missing_signals}")

    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )

    rows: list[dict[str, object]] = []
    survivors: list[str] = []
    for signal_name in THIRD_WAVE_SIGNALS:
        phase_ic = evaluate_signal_ic_by_phase(
            candidate_frame,
            signal_column=signal_name,
            state_mask=liq_open_basic,
            protocol=protocol,
        )
        dev = phase_ic["dev"]
        dev_gate = gate_pass(dev.get("avg_ic"), dev.get("corr_with_s1"), dev.get("pct_years_positive"))
        row = {
            "signal_name": signal_name,
            "dev_avg_ic": dev.get("avg_ic"),
            "dev_corr_with_s1": dev.get("corr_with_s1"),
            "dev_pct_years_positive": dev.get("pct_years_positive"),
            "validation_avg_ic": phase_ic["validation"].get("avg_ic"),
            "validation_corr_with_s1": phase_ic["validation"].get("corr_with_s1"),
            "confirmation_avg_ic": phase_ic["confirmation"].get("avg_ic"),
            "dev_gate_pass": bool(dev_gate),
            "pass_ic_threshold": PASS_IC,
            "pass_corr_threshold": PASS_CORR,
            "pass_pct_years_threshold": PASS_PCT_YEARS,
        }
        rows.append(row)
        if dev_gate:
            survivors.append(signal_name)

    results = pd.DataFrame(rows)
    portfolio_results: dict[str, dict[str, object]] = {}
    fee_leg = float(args.round_trip_cost) / 2.0
    required_holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    if survivors:
        scored = compute_strategy_scores(
            candidate_frame[["time", "ticker", "actual"] + survivors].copy(),
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
            portfolio_results[signal_name] = compute_phase_portfolio_summary(result.daily, protocol=protocol)

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
    results["promoted_to_composite_stage"] = (
        results["dev_gate_pass"]
        & results["survives_validation"]
        & results["survives_confirmation"]
        & results["has_portfolio_relevance"]
    )
    results = results.sort_values(
        by=[
            "promoted_to_composite_stage",
            "validation_avg_ic",
            "validation_relative_total_return",
            "signal_name",
        ],
        ascending=[False, False, False, True],
        ignore_index=True,
    )

    _print_signal_table(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h204_third_wave_tradability_conditioned_search_results.parquet"
    results.to_parquet(results_path, index=False)
    summary = {
        "protocol": protocol.describe(),
        "survivors": results.loc[results["dev_gate_pass"], "signal_name"].tolist(),
        "promoted": results.loc[
            results["promoted_to_composite_stage"],
            ["signal_name", "validation_avg_ic", "confirmation_avg_ic"],
        ].to_dict("records"),
        "tested_signals": results[
            [
                "signal_name",
                "dev_avg_ic",
                "dev_corr_with_s1",
                "validation_avg_ic",
                "confirmation_avg_ic",
                "promoted_to_composite_stage",
            ]
        ].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="tradability_conditioned_signal_search_v3",
        name="h204_third_wave_tradability_conditioned_search",
        summary=summary,
        artifacts={"results": str(results_path)},
        metadata={"protocol": protocol.describe(), "start_year": int(args.start_year), "end_year": int(args.end_year)},
    )


if __name__ == "__main__":
    main()
