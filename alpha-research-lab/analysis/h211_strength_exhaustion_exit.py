"""
H211: Strength-exhaustion exit family.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes
from src.exit_alpha import ExitRuleSpec
from src.exit_branch_utils import load_baseline_variant, resolve_exit_anchor
from src.exit_experiment_utils import load_full_library_backbone, run_exit_variants
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H210_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_exit_liquidity_deterioration.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h210-summary", type=str, default=str(H210_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    baseline_variant = load_baseline_variant(Path(args.h210_summary))
    _, leader = resolve_exit_anchor(Path(args.h210_summary), baseline_variant=baseline_variant)
    if leader is None:
        raise ValueError("H211 requires a prior exit leader")
    _, _, market_inputs = load_full_library_backbone(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    variants = [{"variant": str(leader["variant"]), "exit_rule_name": leader.get("exit_rule_name"), "exit_rule_params": leader.get("exit_rule_params")}]
    for return_thr in (0.15, 0.25):
        spec = ExitRuleSpec(family="strength_exhaustion", params={"return_since_entry_threshold": return_thr, "score_drop_threshold": 0.05})
        variants.append({"variant": spec.variant_name, "exit_rule_name": spec.family, "exit_rule_params": spec.params})
    output = run_exit_variants(market_inputs=market_inputs, initial_notional_vnd=float(args.portfolio_notional_vnd), round_trip_cost=float(args.round_trip_cost), required_holding_age=int(args.required_holding_age), variants=variants)
    results = output.results.copy()
    baseline = results.loc[results["variant"] == str(leader["variant"])].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = False if row["variant"] == str(leader["variant"]) else additive_candidate_passes(row, baseline)
    results = results.sort_values(by=["promoted", "validation_relative_delta", "validation_ir_delta", "confirmation_relative_delta", "variant"], ascending=[False, False, False, False, True], ignore_index=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h211_strength_exhaustion_exit_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h211_strength_exhaustion_exit_best_daily.parquet"
    best_exit_path = OUT_DIR / f"{ts}_h211_strength_exhaustion_exit_best_exit_panel.parquet"
    results.to_parquet(results_path, index=False)
    output.daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)
    output.exit_panels[str(results.iloc[0]["variant"])].to_parquet(best_exit_path, index=False)
    write_run_summary(ts=ts, mode="portfolio_exit_strength_exhaustion", name="h211_strength_exhaustion_exit", summary={"protocol": protocol.describe(), "baseline_variant": str(leader["variant"]), "winner": results.iloc[0].to_dict()}, artifacts={"results": str(results_path), "best_daily": str(best_daily_path), "best_exit_panel": str(best_exit_path)}, metadata={"protocol": protocol.describe()})


if __name__ == "__main__":
    main()
