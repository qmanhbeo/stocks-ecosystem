"""
H223: Deterministic exit integration for the event-surface winner.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes
from src.event_surface_research import EVENT_CORE_FEATURES, build_event_hazard_params
from src.exit_alpha import ExitRuleSpec
from src.exit_branch_utils import extract_exit_spec, load_baseline_variant, resolve_exit_leader
from src.exit_experiment_utils import load_full_library_backbone, run_exit_variants
from src.run_summary import write_run_summary
from src.research_protocol import DEFAULT_PROTOCOL


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
EVENT_SURFACE_PATH = Path("data/features/event_surface_daily.parquet")
H211_SUMMARY_PATH = Path("artifacts/run_summaries/latest_portfolio_exit_strength_exhaustion.json")
H222_SUMMARY_PATH = Path("artifacts/run_summaries/latest_portfolio_exit_event_surface_predictive_screen.json")
OUT_DIR = Path("artifacts/portfolio_baselines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--event-surface", type=str, default=str(EVENT_SURFACE_PATH))
    parser.add_argument("--h211-summary", type=str, default=str(H211_SUMMARY_PATH))
    parser.add_argument("--h222-summary", type=str, default=str(H222_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    baseline_variant = load_baseline_variant(Path(args.h211_summary))
    _, anchor = resolve_exit_leader(Path(args.h211_summary), baseline_variant=baseline_variant)
    if anchor is None:
        raise ValueError("H223 requires the H211 winner")
    from src.additive_selector_research import resolve_summary_artifact, summary_is_skipped
    if summary_is_skipped(Path(args.h222_summary)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_event_surface_integration",
            name="h223_event_surface_exit_integration",
            summary={"protocol": protocol.describe(), "skipped": True, "reason": "H222 was skipped"},
            artifacts={},
            metadata={"protocol": protocol.describe()},
        )
        return
    results = pd.read_parquet(resolve_summary_artifact(Path(args.h222_summary), "results"))
    promoted = results.loc[results["promoted"]].copy() if "promoted" in results.columns else pd.DataFrame()
    if promoted.empty:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_event_surface_integration",
            name="h223_event_surface_exit_integration",
            summary={"protocol": protocol.describe(), "skipped": True, "reason": "H222 produced no promoted event model"},
            artifacts={},
            metadata={"protocol": protocol.describe()},
        )
        return

    model_row = promoted.iloc[0]
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
    base_name, base_params = extract_exit_spec(anchor)
    variants = [{"variant": str(anchor["variant"]), "exit_rule_name": base_name, "exit_rule_params": base_params}]
    for threshold in (0.45, 0.50, 0.55):
        hazard_params = build_event_hazard_params(model_row, continue_prob_threshold=threshold)
        hazard_spec = ExitRuleSpec(family="continuation_hazard", params=hazard_params)
        variants.append({"variant": f"event_only__{threshold:.2f}".replace(".", "p"), "exit_rule_name": hazard_spec.family, "exit_rule_params": hazard_spec.params})
        combo_spec = {
            "rules": [
                {"name": hazard_spec.family, "params": hazard_spec.params},
                {"name": base_name, "params": base_params},
            ]
        }
        variants.append({"variant": f"event_or_h211__{threshold:.2f}".replace(".", "p"), "exit_rule_name": "multi_rule_any", "exit_rule_params": combo_spec})
    output = run_exit_variants(
        market_inputs=market_inputs,
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        variants=variants,
    )
    results = output.results.copy()
    baseline = results.loc[results["variant"] == str(anchor["variant"])].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = False if row["variant"] == str(anchor["variant"]) else additive_candidate_passes(row, baseline)
    results = results.sort_values(by=["promoted", "validation_relative_delta", "validation_ir_delta", "confirmation_relative_delta", "variant"], ascending=[False, False, False, False, True], ignore_index=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h223_event_surface_exit_integration_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h223_event_surface_exit_integration_best_daily.parquet"
    best_exit_path = OUT_DIR / f"{ts}_h223_event_surface_exit_integration_best_exit_panel.parquet"
    results.to_parquet(results_path, index=False)
    output.daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)
    output.exit_panels[str(results.iloc[0]["variant"])].to_parquet(best_exit_path, index=False)
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_event_surface_integration",
        name="h223_event_surface_exit_integration",
        summary={"protocol": protocol.describe(), "baseline_variant": str(anchor["variant"]), "event_model": model_row.to_dict(), "winner": results.iloc[0].to_dict()},
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path), "best_exit_panel": str(best_exit_path)},
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
