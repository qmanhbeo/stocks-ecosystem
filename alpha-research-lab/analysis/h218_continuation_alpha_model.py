"""
H218: Continuation alpha model for hold-vs-exit advantage.
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

from src.continuation_exit_research import (
    BASE_CONTINUATION_FEATURES,
    CONTINUATION_HORIZON_DAYS,
    ContinuationModelSpec,
    build_continuation_dataset,
    fit_continuation_model,
)
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


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
    parser.add_argument("--horizon-days", type=int, default=CONTINUATION_HORIZON_DAYS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    bundle = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        horizon_days=int(args.horizon_days),
    )
    specs = [
        ContinuationModelSpec(name="continuation_core", feature_columns=tuple(BASE_CONTINUATION_FEATURES)),
        ContinuationModelSpec(name="continuation_plus_thesis", feature_columns=tuple(BASE_CONTINUATION_FEATURES + ["thesis_score_change_since_entry"])),
        ContinuationModelSpec(name="continuation_plus_rank", feature_columns=tuple(BASE_CONTINUATION_FEATURES + ["thesis_score_change_since_entry", "score_rank", "entry_rank"])),
    ]
    fits = [fit_continuation_model(bundle.panel, spec=spec) for spec in specs]
    results = pd.DataFrame([fit.summary_row for fit in fits]).sort_values(
        by=["promoted", "validation_auc", "validation_top_quintile_hold_advantage", "confirmation_auc", "model_name"],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    winner = fits[[fit.spec.name for fit in fits].index(str(results.iloc[0]["model_name"]))]
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h218_continuation_alpha_model_results.parquet"
    scored_path = OUT_DIR / f"{ts}_h218_continuation_alpha_model_scored_dataset.parquet"
    baseline_daily_path = OUT_DIR / f"{ts}_h218_continuation_alpha_model_baseline_daily.parquet"
    results.to_parquet(results_path, index=False)
    winner.scored_dataset.to_parquet(scored_path, index=False)
    bundle.baseline_daily.to_parquet(baseline_daily_path, index=False)
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_continuation_alpha_model",
        name="h218_continuation_alpha_model",
        summary={
            "protocol": protocol.describe(),
            "horizon_days": int(args.horizon_days),
            "winner": results.iloc[0].to_dict(),
        },
        artifacts={
            "results": str(results_path),
            "scored_dataset": str(scored_path),
            "baseline_daily": str(baseline_daily_path),
        },
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
