"""
H206: Sticky-activation compatibility for a promoted H205 pair-selector winner.

Purpose:
- test whether the promoted H205 pair selector survives the frozen sticky activation rule
- keep activation fixed at h175__rel2_gt0 + sticky_bonus_0p015
- only run if H205 produces a promoted winner

Usage:
    conda run -n stocks python analysis/h206_pair_selector_activation_compatibility.py
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
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import build_candidate_signal_frame, compute_phase_portfolio_summary, load_research_bundle


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H205_SUMMARY_PATH = Path("artifacts/run_summaries/latest_portfolio_state_scoped_pairwise_bakeoff.json")
OUT_DIR = Path("artifacts/portfolio_baselines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h205-summary", type=str, default=str(H205_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.015)
    return parser.parse_args()


def _load_h205_winner(summary_path: Path) -> tuple[pd.DataFrame, str | None]:
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


def _parse_pair_blend_name(strategy_name: str) -> tuple[str, str, float]:
    parts = str(strategy_name).split("__")
    if len(parts) != 4 or parts[0] != "state_pair_blend":
        raise ValueError(f"Expected state pair blend strategy name, got {strategy_name!r}")
    return parts[1], parts[2], float(parts[3]) / 100.0


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 184)
    print("H206: PAIR SELECTOR / STICKY ACTIVATION COMPATIBILITY")
    print("=" * 184)
    print(
        f"{'variant':<40} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'promote':>8}"
    )
    print("-" * 184)
    for row in results.itertuples(index=False):
        print(
            f"{row.variant:<40} "
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
    h205_results, winner_name = _load_h205_winner(Path(args.h205_summary))
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if winner_name is None:
        summary = {
            "protocol": protocol.describe(),
            "skipped": True,
            "reason": "H205 produced no promoted winner",
        }
        write_run_summary(
            ts=ts,
            mode="portfolio_pair_selector_activation_compatibility",
            name="h206_pair_selector_activation_compatibility",
            summary=summary,
            artifacts={},
            metadata={"protocol": protocol.describe(), "h205_summary": str(args.h205_summary)},
        )
        print("H206 skipped: H205 produced no promoted winner.")
        return

    atom_a, atom_b, pair_weight = _parse_pair_blend_name(winner_name)

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
        candidate_frame[["time", "ticker", atom_a, atom_b, "tv_to_adv20", "clv", "can_buy_next_open"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    pair_strategy_name = f"full_library_pair__{atom_a}__{atom_b}"
    scored = compute_strategy_scores(
        merged,
        {
            "full_library": list(full_library_columns),
            pair_strategy_name: list(full_library_columns) + [atom_a, atom_b],
        },
    )
    selector_scored = scored[["time", "ticker", "actual", "score__full_library"]].copy()
    selector_scored[f"score__{winner_name}"] = blend_state_scoped_scores(
        pd.to_numeric(scored["score__full_library"], errors="coerce"),
        pd.to_numeric(scored[f"score__{pair_strategy_name}"], errors="coerce"),
        liq_open_basic,
        atom_weight=float(pair_weight),
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
    activation_scale = align_series_to_market_dates(
        (champion_setup.rel2 > 0.0).astype(float),
        market_inputs.dates,
        fill_value=0.0,
    )
    fee_leg = float(args.round_trip_cost) / 2.0
    holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))

    variants = [
        {
            "variant": "winner_always_on",
            "strategy_name": winner_name,
            "signal_columns": [winner_name],
            "activation_scale": None,
            "incumbent_score_bonus": 0.0,
        },
        {
            "variant": "winner_plus_sticky",
            "strategy_name": winner_name,
            "signal_columns": [winner_name],
            "activation_scale": activation_scale,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
        {
            "variant": "full_library_plus_sticky",
            "strategy_name": "full_library",
            "signal_columns": list(full_library_columns),
            "activation_scale": activation_scale,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
    ]

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for spec in variants:
        result = simulate_strategy(
            strategy_name=str(spec["strategy_name"]),
            signal_columns=list(spec["signal_columns"]),
            market_inputs=market_inputs,
            top_k=5,
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
        row = {"variant": str(spec["variant"])}
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
        results.loc[idx, "promoted"] = False if row["variant"] == "full_library_plus_sticky" else additive_candidate_passes(row, incumbent)

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

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h206_pair_selector_activation_compatibility_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h206_pair_selector_activation_compatibility_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)

    promoted = results.loc[results["promoted"]].copy()
    summary = {
        "protocol": protocol.describe(),
        "winner_selector": winner_name,
        "incumbent": incumbent.to_dict(),
        "winner": results.iloc[0].to_dict(),
        "promoted_candidates": promoted[
            [
                "variant",
                "validation_relative_delta",
                "validation_ir_delta",
                "confirmation_relative_delta",
                "confirmation_ir_delta",
            ]
        ].to_dict("records"),
        "tested_candidates": results[
            [
                "variant",
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
        mode="portfolio_pair_selector_activation_compatibility",
        name="h206_pair_selector_activation_compatibility",
        summary=summary,
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path)},
        metadata={
            "protocol": protocol.describe(),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "h205_summary": str(args.h205_summary),
        },
    )


if __name__ == "__main__":
    main()
