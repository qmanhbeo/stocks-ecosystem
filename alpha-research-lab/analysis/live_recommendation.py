from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from path_utils import data_path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.deterministic_portfolio import default_strategy_names
from src.live_recommendation import build_live_recommendation, summarize_live_recommendation
from src.recommendation_policies import LATEST_LIVE_OVERLAY_SUMMARY
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate shared recommendation candidates for the lab")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--strategy", type=str, default="full_library", choices=list(default_strategy_names()))
    parser.add_argument("--profile-name", type=str, default="alpha_full_library_live")
    parser.add_argument("--as-of-date", type=str, default=None)
    parser.add_argument("--output-root", type=str, default=None)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--overlay-summary", type=str, default=str(LATEST_LIVE_OVERLAY_SUMMARY))
    parser.add_argument("--disable-live-overlay-gate", action="store_true")
    parser.add_argument("--allow-stale-inputs", action="store_true")
    parser.add_argument("--allow-stale-overlay", action="store_true")
    parser.add_argument("--allow-overlay-signal-date-mismatch", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_live_recommendation(
        profile_name=str(args.profile_name),
        strategy=str(args.strategy),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        as_of_date=args.as_of_date,
        output_root=Path(args.output_root) if args.output_root else None,
        apply_live_overlay_gate=not bool(args.disable_live_overlay_gate),
        overlay_summary_path=Path(args.overlay_summary),
        allow_stale_inputs=bool(args.allow_stale_inputs),
        allow_stale_overlay=bool(args.allow_stale_overlay),
        allow_overlay_signal_date_mismatch=bool(args.allow_overlay_signal_date_mismatch),
    )
    summary = summarize_live_recommendation(result, top_n=int(args.top_n))
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    mode = f"recommendation_candidates_{str(args.profile_name).strip().lower()}"
    write_run_summary(
        ts=ts,
        mode=mode,
        name="live_recommendation",
        summary=summary,
        artifacts={
            "candidates": str(result.candidate_path),
            "manifest": str(result.manifest_path),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "strategy": str(args.strategy),
            "overlay_summary": str(args.overlay_summary),
            "live_overlay_gate_enabled": not bool(args.disable_live_overlay_gate),
            "allow_stale_inputs": bool(args.allow_stale_inputs),
            "allow_stale_overlay": bool(args.allow_stale_overlay),
            "allow_overlay_signal_date_mismatch": bool(args.allow_overlay_signal_date_mismatch),
        },
    )

    candidates = result.candidates.copy()
    eligible = candidates.loc[candidates["eligible"].astype(bool)].copy()
    eligible = eligible.sort_values(["time", "eligible_rank", "ticker"]).head(max(int(args.top_n), 1))

    print("\nLIVE RECOMMENDATION")
    print(f"profile: {summary['profile_name']}")
    print(f"as_of_date: {summary['as_of_date']}")
    print(f"eligible_count: {summary['eligible_count']} / {summary['candidate_count']}")
    print(f"candidate_path: {result.candidate_path}")
    print(f"manifest_path: {result.manifest_path}")
    if eligible.empty:
        print("No eligible candidates.")
        return
    view = eligible[["ticker", "score_raw", "score_rank_pct", "score_final", "eligible_rank", "activation_state"]].copy()
    print(view.to_string(index=False))


if __name__ == "__main__":
    main()
