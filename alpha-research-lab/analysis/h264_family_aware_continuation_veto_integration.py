"""
H264: Deterministic family-aware continuation veto integration with explicit path-only controls.
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
from src.continuation_exit_research import (
    BASE_CONTINUATION_FEATURES,
    CONTINUATION_HORIZON_DAYS,
    ContinuationModelSpec,
    build_continuation_dataset,
    fit_continuation_model,
)
from src.exit_experiment_utils import load_full_library_backbone, run_exit_variants
from src.intraday_exit_research import (
    FAMILY_SCOPED_BASELINE_MODEL_NAME,
    build_family_aware_continuation_rule_params,
    build_intraday_router_feature_frame,
    continuation_model_params_from_row,
)
from src.research_protocol import ResearchProtocol, assign_research_phase
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H258_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
H262_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_exit_intraday_family_contradiction_audit.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
PATH_CORE_SPEC = ContinuationModelSpec(name=FAMILY_SCOPED_BASELINE_MODEL_NAME, feature_columns=tuple(BASE_CONTINUATION_FEATURES))
THRESHOLDS = (0.40, 0.45, 0.50, 0.55, 0.60)
BASELINE_VARIANT = "always_on_baseline"
MAX_EXTRA_CASH_WEIGHT = 0.15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h258-summary", type=str, default=str(H258_SUMMARY_PATH))
    parser.add_argument("--h262-summary", type=str, default=str(H262_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--horizon-days", type=int, default=CONTINUATION_HORIZON_DAYS)
    return parser.parse_args()


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(
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


def _group_leader(results: pd.DataFrame, group: str) -> pd.Series | None:
    group_rows = results.loc[results["variant_group"].astype(str) == str(group)].copy()
    if group_rows.empty:
        return None
    return _ordered(group_rows).iloc[0]


def _family_path_rule_params(
    family_path_results: pd.DataFrame,
    global_model_row: pd.Series,
    *,
    threshold: float,
) -> dict[str, object]:
    family_models = {
        str(row["entry_thesis_family"]): continuation_model_params_from_row(row)
        for _, row in family_path_results.iterrows()
    }
    return {
        "continue_prob_threshold": float(threshold),
        "family_models": family_models,
        "default_model": continuation_model_params_from_row(global_model_row),
    }


def main() -> None:
    args = parse_args()
    h258_summary_path = Path(args.h258_summary)
    h262_summary_path = Path(args.h262_summary)
    h258_payload = load_summary_payload(h258_summary_path)
    h262_payload = load_summary_payload(h262_summary_path)
    if not bool(h258_payload.get("summary", {}).get("advance_to_h259", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_family_aware_continuation_veto_integration",
            name="h264_family_aware_continuation_veto_integration",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H258 did not clear the reduced-shape contract gate",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return
    if not bool(h262_payload.get("summary", {}).get("advance_to_h263", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_family_aware_continuation_veto_integration",
            name="h264_family_aware_continuation_veto_integration",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H262 did not clear the family contradiction gate",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    reduced_shape_panel = pd.read_parquet(resolve_summary_artifact(h258_summary_path, "reduced_shape_panel"))
    family_summary = pd.read_parquet(resolve_summary_artifact(h262_summary_path, "family_summary"))
    router_results = pd.read_parquet(resolve_summary_artifact(h262_summary_path, "results"))

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
        horizon_days=int(args.horizon_days),
    )
    panel = continuation.panel.copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel = assign_research_phase(panel, date_column="time", protocol=INTRADAY_RESTART_PROTOCOL)

    global_fit = fit_continuation_model(panel, spec=PATH_CORE_SPEC)
    family_path_rows: list[pd.Series] = []
    for family in sorted(str(value) for value in panel["entry_thesis_family"].dropna().unique().tolist()):
        family_frame = panel.loc[panel["entry_thesis_family"].astype(str) == family].copy()
        fit = fit_continuation_model(
            family_frame,
            spec=ContinuationModelSpec(name=FAMILY_SCOPED_BASELINE_MODEL_NAME, feature_columns=tuple(BASE_CONTINUATION_FEATURES)),
        )
        row = pd.Series(dict(fit.summary_row))
        row["entry_thesis_family"] = family
        family_path_rows.append(row)
    family_path_results = pd.DataFrame(family_path_rows)

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

    variants: list[dict[str, object]] = [
        {
            "variant": BASELINE_VARIANT,
            "variant_group": "baseline",
            "threshold": None,
        }
    ]
    global_params = continuation_model_params_from_row(global_fit.summary_row)
    for threshold in THRESHOLDS:
        variants.append(
            {
                "variant": f"global_path_core__thr_{str(threshold).replace('.', 'p')}",
                "variant_group": "global_path_core",
                "threshold": float(threshold),
                "exit_rule_name": "continuation_hazard",
                "exit_rule_params": {**global_params, "continue_prob_threshold": float(threshold)},
            }
        )
        variants.append(
            {
                "variant": f"family_path_core__thr_{str(threshold).replace('.', 'p')}",
                "variant_group": "family_path_core",
                "threshold": float(threshold),
                "exit_rule_name": "continuation_hazard",
                "exit_rule_params": _family_path_rule_params(
                    family_path_results,
                    pd.Series(global_fit.summary_row),
                    threshold=float(threshold),
                ),
            }
        )
        variants.append(
            {
                "variant": f"family_router__thr_{str(threshold).replace('.', 'p')}",
                "variant_group": "family_router",
                "threshold": float(threshold),
                "exit_rule_name": "continuation_hazard",
                "exit_rule_params": build_family_aware_continuation_rule_params(
                    family_summary,
                    router_results,
                    family_path_results,
                    default_model_row=pd.Series(global_fit.summary_row),
                    continue_prob_threshold=float(threshold),
                ),
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
    group_map = {str(spec["variant"]): str(spec["variant_group"]) for spec in variants}
    threshold_map = {str(spec["variant"]): spec.get("threshold") for spec in variants}
    results["variant_group"] = results["variant"].map(group_map)
    results["threshold"] = results["variant"].map(threshold_map)

    baseline = results.loc[results["variant"] == BASELINE_VARIANT].iloc[0]
    baseline_val_cash = float(pd.to_numeric(baseline.get("validation_avg_cash_weight"), errors="coerce"))
    baseline_conf_cash = float(pd.to_numeric(baseline.get("confirmation_avg_cash_weight"), errors="coerce"))
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        validation_cash = float(pd.to_numeric(row.get("validation_avg_cash_weight"), errors="coerce"))
        confirmation_cash = float(pd.to_numeric(row.get("confirmation_avg_cash_weight"), errors="coerce"))
        exit_events = float(pd.to_numeric(row.get("exit_rule_trigger_events"), errors="coerce"))
        usable_cutoff = bool(
            row["variant"] != BASELINE_VARIANT
            and exit_events > 0.0
            and validation_cash <= baseline_val_cash + MAX_EXTRA_CASH_WEIGHT
            and confirmation_cash <= baseline_conf_cash + MAX_EXTRA_CASH_WEIGHT
        )
        results.loc[idx, "usable_cutoff"] = usable_cutoff
        results.loc[idx, "promoted"] = bool(
            row["variant"] != BASELINE_VARIANT
            and usable_cutoff
            and additive_candidate_passes(row, baseline)
        )
        results.loc[idx, "validation_cash_delta"] = validation_cash - baseline_val_cash
        results.loc[idx, "confirmation_cash_delta"] = confirmation_cash - baseline_conf_cash

    results = _ordered(results)
    overall_winner = results.iloc[0]
    global_leader = _group_leader(results, "global_path_core")
    family_path_leader = _group_leader(results, "family_path_core")
    family_router_leader = _group_leader(results, "family_router")
    if family_router_leader is None or global_leader is None or family_path_leader is None:
        raise ValueError("H264 expected non-empty global, family-path, and family-router variant groups")

    passed = bool(
        family_router_leader["variant"] == overall_winner["variant"]
        and bool(family_router_leader.get("promoted", False))
    )
    mixed = bool(
        not passed
        and bool(family_router_leader.get("usable_cutoff", False))
        and (
            float(pd.to_numeric(family_router_leader.get("validation_relative_delta"), errors="coerce"))
            >= max(
                float(pd.to_numeric(global_leader.get("validation_relative_delta"), errors="coerce")),
                float(pd.to_numeric(family_path_leader.get("validation_relative_delta"), errors="coerce")),
            )
            or float(pd.to_numeric(family_router_leader.get("validation_ir_delta"), errors="coerce"))
            >= max(
                float(pd.to_numeric(global_leader.get("validation_ir_delta"), errors="coerce")),
                float(pd.to_numeric(family_path_leader.get("validation_ir_delta"), errors="coerce")),
            )
        )
        and float(pd.to_numeric(family_router_leader.get("confirmation_relative_delta"), errors="coerce")) >= -0.05
    )
    verdict = "PASSED" if passed else "MIXED" if mixed else "FAILED"

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h264_family_aware_continuation_veto_integration_results.parquet"
    winner_daily_path = OUT_DIR / f"{ts}_h264_family_aware_continuation_veto_integration_best_daily.parquet"
    winner_exit_path = OUT_DIR / f"{ts}_h264_family_aware_continuation_veto_integration_best_exit_panel.parquet"
    router_daily_path = OUT_DIR / f"{ts}_h264_family_aware_continuation_veto_integration_router_daily.parquet"
    router_exit_path = OUT_DIR / f"{ts}_h264_family_aware_continuation_veto_integration_router_exit_panel.parquet"

    results.to_parquet(results_path, index=False)
    output.daily_outputs[str(overall_winner["variant"])].to_parquet(winner_daily_path, index=False)
    output.exit_panels[str(overall_winner["variant"])].to_parquet(winner_exit_path, index=False)
    output.daily_outputs[str(family_router_leader["variant"])].to_parquet(router_daily_path, index=False)
    output.exit_panels[str(family_router_leader["variant"])].to_parquet(router_exit_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_exit_family_aware_continuation_veto_integration",
        name="h264_family_aware_continuation_veto_integration",
        summary={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "decision": verdict,
            "advance_to_h265": verdict == "PASSED",
            "baseline_variant": BASELINE_VARIANT,
            "overall_winner": overall_winner.to_dict(),
            "global_path_core_leader": global_leader.to_dict(),
            "family_path_core_leader": family_path_leader.to_dict(),
            "family_router_leader": family_router_leader.to_dict(),
            "router_intraday_families": sorted(
                str(value)
                for value in family_summary.loc[family_summary["router_uses_intraday"].fillna(False).astype(bool), "entry_thesis_family"].tolist()
            ),
            "usable_cutoff_rule": {
                "max_extra_cash_weight_vs_baseline": MAX_EXTRA_CASH_WEIGHT,
                "requires_positive_exit_events": True,
            },
        },
        artifacts={
            "results": str(results_path),
            "best_daily": str(winner_daily_path),
            "best_exit_panel": str(winner_exit_path),
            "family_router_daily": str(router_daily_path),
            "family_router_exit_panel": str(router_exit_path),
        },
        metadata={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "h258_summary": str(h258_summary_path),
            "h262_summary": str(h262_summary_path),
            "branch_contract": "Deterministic family-aware continuation veto with explicit global and family path-only controls on 2023-2025 only",
        },
    )


if __name__ == "__main__":
    main()
