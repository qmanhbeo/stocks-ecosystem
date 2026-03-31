"""
H222: Predictive screening for the corporate-event surface against the continuation target.
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

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.continuation_exit_research import BASE_CONTINUATION_FEATURES, ContinuationModelSpec, build_continuation_dataset, fit_continuation_model
from src.event_surface_research import EVENT_CORE_FEATURES, merge_event_surface
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H221_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_exit_event_surface_artifact.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h221-summary", type=str, default=str(H221_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    h221_summary = load_summary_payload(Path(args.h221_summary))
    passed = bool(h221_summary.get("summary", {}).get("coverage_gate_passed", False))
    if not passed:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_event_surface_predictive_screen",
            name="h222_event_surface_predictive_screen",
            summary={
                "protocol": protocol.describe(),
                "skipped": True,
                "reason": "H221 coverage gate failed",
            },
            artifacts={},
            metadata={"protocol": protocol.describe()},
        )
        return

    event_surface_path = resolve_summary_artifact(Path(args.h221_summary), "event_surface")
    event_surface = pd.read_parquet(event_surface_path)
    continuation = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
    )
    merged = merge_event_surface(continuation.panel, event_surface).merged_panel
    specs = [
        ContinuationModelSpec(name="event_only_core", feature_columns=tuple(EVENT_CORE_FEATURES)),
        ContinuationModelSpec(name="event_plus_path_core", feature_columns=tuple(EVENT_CORE_FEATURES + BASE_CONTINUATION_FEATURES)),
        ContinuationModelSpec(name="event_plus_path_thesis", feature_columns=tuple(EVENT_CORE_FEATURES + BASE_CONTINUATION_FEATURES + ["thesis_score_change_since_entry"])),
    ]
    fits = [fit_continuation_model(merged, spec=spec) for spec in specs]
    results = pd.DataFrame([fit.summary_row for fit in fits]).sort_values(
        by=["promoted", "validation_auc", "validation_top_quintile_hold_advantage", "confirmation_auc", "model_name"],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    winner = fits[[fit.spec.name for fit in fits].index(str(results.iloc[0]["model_name"]))]
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h222_event_surface_predictive_screen_results.parquet"
    scored_path = OUT_DIR / f"{ts}_h222_event_surface_predictive_screen_scored_dataset.parquet"
    results.to_parquet(results_path, index=False)
    winner.scored_dataset.to_parquet(scored_path, index=False)
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_event_surface_predictive_screen",
        name="h222_event_surface_predictive_screen",
        summary={
            "protocol": protocol.describe(),
            "winner": results.iloc[0].to_dict(),
        },
        artifacts={
            "results": str(results_path),
            "scored_dataset": str(scored_path),
        },
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
