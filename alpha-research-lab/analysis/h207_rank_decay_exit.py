"""
H207: Rank-decay exit family on top of the frozen full-library selector.
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

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes
from src.exit_alpha import ExitRuleSpec
from src.exit_experiment_utils import load_full_library_backbone, run_exit_variants
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = Path("artifacts/portfolio_baselines")


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
    print("\n" + "=" * 186)
    print("H207: RANK-DECAY EXIT")
    print("=" * 186)
    print(
        f"{'variant':<56} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'exit_evts':>10} {'promote':>8}"
    )
    print("-" * 186)
    for row in results.itertuples(index=False):
        print(
            f"{row.variant:<56} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.validation_ir_delta if row.validation_ir_delta is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{int(row.exit_rule_trigger_events) if pd.notna(row.exit_rule_trigger_events) else 0:>10d} "
            f"{str(bool(row.promoted)):>8}"
        )


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    _, _, market_inputs = load_full_library_backbone(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    variants: list[dict[str, object]] = [{"variant": "always_on_baseline"}]
    for threshold in (5, 8, 10):
        for margin in (0.0, 0.02, 0.05):
            spec = ExitRuleSpec(
                family="rank_decay",
                params={"rank_exit_threshold": int(threshold), "replacement_margin": float(margin)},
            )
            variants.append(
                {
                    "variant": spec.variant_name,
                    "exit_rule_name": spec.family,
                    "exit_rule_params": spec.params,
                }
            )

    output = run_exit_variants(
        market_inputs=market_inputs,
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        variants=variants,
    )
    results = output.results.copy()
    baseline = results.loc[results["variant"] == "always_on_baseline"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = False if row["variant"] == "always_on_baseline" else additive_candidate_passes(row, baseline)
    results = results.sort_values(
        by=["promoted", "validation_relative_delta", "validation_ir_delta", "confirmation_relative_delta", "variant"],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    _print_table(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h207_rank_decay_exit_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h207_rank_decay_exit_best_daily.parquet"
    best_exit_path = OUT_DIR / f"{ts}_h207_rank_decay_exit_best_exit_panel.parquet"
    results.to_parquet(results_path, index=False)
    output.daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)
    output.exit_panels[str(results.iloc[0]["variant"])].to_parquet(best_exit_path, index=False)

    summary = {
        "protocol": protocol.describe(),
        "baseline": baseline.to_dict(),
        "winner": results.iloc[0].to_dict(),
        "promoted_candidates": results.loc[results["promoted"], ["variant", "validation_relative_delta", "validation_ir_delta", "confirmation_relative_delta", "confirmation_ir_delta"]].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_rank_decay",
        name="h207_rank_decay_exit",
        summary=summary,
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path), "best_exit_panel": str(best_exit_path)},
        metadata={"protocol": protocol.describe(), "start_year": int(args.start_year), "end_year": int(args.end_year)},
    )


if __name__ == "__main__":
    main()
