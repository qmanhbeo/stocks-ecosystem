"""
H224: Sticky-activation compatibility for the promoted corporate-event exit winner.
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

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes, summary_is_skipped, resolve_summary_artifact
from src.champion_activation_utils import align_series_to_market_dates, load_champion_setup
from src.event_surface_research import EVENT_CORE_FEATURES
from src.exit_branch_utils import extract_exit_spec, load_baseline_variant, resolve_exit_leader
from src.exit_experiment_utils import load_full_library_backbone, run_exit_variants
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
EVENT_SURFACE_PATH = Path("data/features/event_surface_daily.parquet")
H223_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_exit_event_surface_integration.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--event-surface", type=str, default=str(EVENT_SURFACE_PATH))
    parser.add_argument("--h223-summary", type=str, default=str(H223_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.015)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    if summary_is_skipped(Path(args.h223_summary)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_event_surface_activation_compatibility",
            name="h224_event_surface_activation_compatibility",
            summary={"protocol": protocol.describe(), "skipped": True, "reason": "H223 was skipped"},
            artifacts={},
            metadata={"protocol": protocol.describe()},
        )
        return
    baseline_variant = load_baseline_variant(Path(args.h223_summary), default="full_library_plus_sticky")
    _, leader = resolve_exit_leader(Path(args.h223_summary), baseline_variant=baseline_variant)
    if leader is None or bool(leader.get("promoted", False)) is False or str(leader.get("variant")) == str(baseline_variant):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_event_surface_activation_compatibility",
            name="h224_event_surface_activation_compatibility",
            summary={"protocol": protocol.describe(), "skipped": True, "reason": "H223 produced no promoted event exit winner"},
            artifacts={},
            metadata={"protocol": protocol.describe()},
        )
        return
    exit_rule_name, exit_rule_params = extract_exit_spec(leader)
    event_surface = pd.read_parquet(Path(args.event_surface))
    _, _, market_inputs = load_full_library_backbone(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        extra_feature_frame=event_surface,
        extra_feature_columns=EVENT_CORE_FEATURES,
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
    activation_scale = align_series_to_market_dates((champion_setup.rel2 > 0.0).astype(float), market_inputs.dates, fill_value=0.0)
    variants = [
        {"variant": "winner_always_on", "exit_rule_name": exit_rule_name, "exit_rule_params": exit_rule_params},
        {"variant": "winner_plus_sticky", "exit_rule_name": exit_rule_name, "exit_rule_params": exit_rule_params, "activation_scale": activation_scale, "incumbent_score_bonus": float(args.incumbent_score_bonus)},
        {"variant": "full_library_plus_sticky", "activation_scale": activation_scale, "incumbent_score_bonus": float(args.incumbent_score_bonus)},
    ]
    output = run_exit_variants(
        market_inputs=market_inputs,
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        variants=variants,
    )
    results = output.results.copy()
    baseline = results.loc[results["variant"] == "full_library_plus_sticky"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = False if row["variant"] == "full_library_plus_sticky" else additive_candidate_passes(row, baseline)
    results = results.sort_values(by=["promoted", "validation_relative_delta", "validation_ir_delta", "confirmation_relative_delta", "variant"], ascending=[False, False, False, False, True], ignore_index=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h224_event_surface_activation_compatibility_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h224_event_surface_activation_compatibility_best_daily.parquet"
    best_exit_path = OUT_DIR / f"{ts}_h224_event_surface_activation_compatibility_best_exit_panel.parquet"
    results.to_parquet(results_path, index=False)
    output.daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)
    output.exit_panels[str(results.iloc[0]["variant"])].to_parquet(best_exit_path, index=False)
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_event_surface_activation_compatibility",
        name="h224_event_surface_activation_compatibility",
        summary={"protocol": protocol.describe(), "winner_exit_variant": str(leader["variant"]), "winner": results.iloc[0].to_dict()},
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path), "best_exit_panel": str(best_exit_path)},
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
