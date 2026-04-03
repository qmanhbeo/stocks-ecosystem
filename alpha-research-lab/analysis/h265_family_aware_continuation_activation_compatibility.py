"""
H265: Sticky-activation compatibility for the H264 family-aware continuation veto winner.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes, load_summary_payload, resolve_summary_artifact
from src.champion_activation_utils import align_series_to_market_dates, load_champion_setup
from src.exit_branch_utils import extract_exit_spec
from src.exit_experiment_utils import load_full_library_backbone, run_exit_variants
from src.intraday_exit_research import build_intraday_router_feature_frame
from src.research_protocol import ResearchProtocol
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H258_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
H264_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_exit_family_aware_continuation_veto_integration.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h258-summary", type=str, default=str(H258_SUMMARY_PATH))
    parser.add_argument("--h264-summary", type=str, default=str(H264_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.015)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    h264_summary_path = Path(args.h264_summary)
    h264_payload = load_summary_payload(h264_summary_path)
    if not bool(h264_payload.get("summary", {}).get("advance_to_h265", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_family_aware_continuation_activation_compatibility",
            name="h265_family_aware_continuation_activation_compatibility",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H264 produced no promoted family-aware deterministic winner",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    reduced_shape_panel = pd.read_parquet(resolve_summary_artifact(Path(args.h258_summary), "reduced_shape_panel"))
    intraday_feature_frame = build_intraday_router_feature_frame(reduced_shape_panel)
    _, _, market_inputs = load_full_library_backbone(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        extra_feature_frame=intraday_feature_frame,
        extra_feature_columns=["intraday_observed", "first_hour_fade_proxy", "weak_open_strong_close_proxy", "failed_breakout_proxy", "open_drive_then_fade_proxy"],
    )

    winner = pd.Series(h264_payload.get("summary", {}).get("overall_winner", {}))
    exit_rule_name, exit_rule_params = extract_exit_spec(winner)
    if exit_rule_name is None:
        raise ValueError("H265 expected an exit rule spec in the H264 winner")

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
    variants = [
        {
            "variant": "winner_always_on",
            "variant_group": "winner",
            "exit_rule_name": exit_rule_name,
            "exit_rule_params": exit_rule_params,
        },
        {
            "variant": "winner_plus_sticky",
            "variant_group": "winner_plus_sticky",
            "exit_rule_name": exit_rule_name,
            "exit_rule_params": exit_rule_params,
            "activation_scale": activation_scale,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
        {
            "variant": "full_library_plus_sticky",
            "variant_group": "baseline",
            "activation_scale": activation_scale,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
    ]
    output = run_exit_variants(
        market_inputs=market_inputs,
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        variants=variants,
    )
    results = output.results.copy()
    results["variant_group"] = results["variant"].map({str(spec["variant"]): str(spec["variant_group"]) for spec in variants})
    baseline = results.loc[results["variant"] == "full_library_plus_sticky"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = bool(
            row["variant"] != "full_library_plus_sticky"
            and additive_candidate_passes(row, baseline)
        )
    results = results.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "confirmation_ir_delta",
            "variant",
        ],
        ascending=[False, False, False, False, False, True],
        ignore_index=True,
    )
    sticky_winner = results.loc[results["variant"] == "winner_plus_sticky"].iloc[0]
    always_on_winner = results.loc[results["variant"] == "winner_always_on"].iloc[0]
    passed = bool(sticky_winner.get("promoted", False))
    mixed = bool(not passed and bool(always_on_winner.get("promoted", False)))
    verdict = "PASSED" if passed else "MIXED" if mixed else "FAILED"

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h265_family_aware_continuation_activation_compatibility_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h265_family_aware_continuation_activation_compatibility_best_daily.parquet"
    best_exit_path = OUT_DIR / f"{ts}_h265_family_aware_continuation_activation_compatibility_best_exit_panel.parquet"

    results.to_parquet(results_path, index=False)
    output.daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)
    output.exit_panels[str(results.iloc[0]["variant"])].to_parquet(best_exit_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_exit_family_aware_continuation_activation_compatibility",
        name="h265_family_aware_continuation_activation_compatibility",
        summary={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "decision": verdict,
            "winner_exit_variant": str(winner.get("variant")),
            "winner": results.iloc[0].to_dict(),
            "sticky_candidate": sticky_winner.to_dict(),
            "always_on_candidate": always_on_winner.to_dict(),
        },
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "best_exit_panel": str(best_exit_path),
        },
        metadata={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "h264_summary": str(h264_summary_path),
            "branch_contract": "Sticky-compatibility test for the H264 family-aware deterministic continuation veto winner on 2023-2025 only",
        },
    )


if __name__ == "__main__":
    main()
