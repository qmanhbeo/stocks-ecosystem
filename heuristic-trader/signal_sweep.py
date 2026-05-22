#!/usr/bin/env python3
"""
Canonical signal sweep for heuristic-trader.

Runs a fixed strategy set, writes canonical WFV outputs, applies profit-readiness
gates, executes cohort autopsy, and emits promote/research/kill labels.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt
from profit_pipeline import (
    ReadinessThresholds,
    _compute_curve_metrics,
    _compute_fallback_metrics,
    _compute_filter_metrics,
    run_readiness,
)
from signal_factory import prepare_signal_df_from_config
from risk_policy import (
    STATUS_LAB_PROMOTED_PENDING_EXECUTION,
    STATUS_RESEARCH_CANDIDATE,
    UPSTREAM_EXECUTION_ELIGIBLE_STATUSES,
    derive_execution_status,
)
from walk_forward_validate import (
    FOLDS,
    _rebuild_canonical_leaderboard,
    _write_canonical_manifest,
    _write_canonical_strategy_outputs,
    compute_strategy_summary,
    load_caches,
    run_strategy_on_fold,
)


ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent
ARTIFACTS_DIR = ROOT / "artifacts"
SWEEP_DIR = ARTIFACTS_DIR / "signal_sweeps"
DEFAULT_FAILURE_YEARS = "2016,2018,2024"
DEFAULT_SUCCESS_YEARS = "2017,2020,2021,2022,2025"
DEFAULT_PROMOTION_CONTRACT_CSV = WORKSPACE_ROOT / "data/features/recommendations/signal_promotion_contract_latest.csv"
DEFAULT_PROMOTION_FEEDBACK_CSV = WORKSPACE_ROOT / "data/features/recommendations/signal_promotion_feedback_latest.csv"


def _parse_years(value: str) -> list[int]:
    years = [int(v.strip()) for v in value.split(",") if v.strip()]
    if not years:
        raise ValueError("year list cannot be empty")
    return years


def _parse_csv_list(value: str) -> set[str]:
    return {v.strip() for v in value.split(",") if v.strip()}


def _strategy_to_signal_id(strategy_name: str) -> str | None:
    name = str(strategy_name)
    control_map = {
        "ctrl_s1_depth5": "s1",
        "ctrl_c16_depth5": "c16",
        "ctrl_c18_depth5": "c18",
        "ctrl_blend_70_30_depth5": "blend_s1_c16",
    }
    if name in control_map:
        return control_map[name]

    if name.startswith("m_c"):
        token = name.split("_", 2)[1]  # e.g. c8
        return token if token.startswith("c") else None
    if name.startswith("s1b_c"):
        token = name.split("_", 2)[1]  # e.g. c8
        return token if token.startswith("c") else None
    return None


def _load_promotion_contract(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    required = {"signal_id", "lab_promotion_status"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Promotion contract missing required columns: {missing}")
    out = df.copy()
    out["signal_id"] = out["signal_id"].astype(str).str.lower()
    out = out.sort_values("as_of_date" if "as_of_date" in out.columns else "signal_id").drop_duplicates(
        subset=["signal_id"], keep="last"
    )
    return out


def build_strategy_configs() -> dict[str, dict]:
    """Fixed sweep set: controls + standalone c4..c14 + S1 blended c4..c14."""
    base = {
        "top_k": 5,
        "rebalance_days": 10,
        "min_hold_days": 3,
        "candidate_scan_multiplier": 5,
        "sizing_mode": "fixed_initial",
    }

    configs: dict[str, dict] = {
        "ctrl_blend_70_30_depth5": {
            **base,
            "name": "ctrl_blend_70_30_depth5",
            "signal_type": "blend_70_30",
            "signal_col": "blend",
        },
        "ctrl_s1_depth5": {
            **base,
            "name": "ctrl_s1_depth5",
            "signal_type": "s1_only",
            "signal_col": "s1_proba",
        },
        "ctrl_c16_depth5": {
            **base,
            "name": "ctrl_c16_depth5",
            "signal_type": "c16_only",
            "signal_col": "order_volume_ratio_rank",
        },
        "ctrl_c18_depth5": {
            **base,
            "name": "ctrl_c18_depth5",
            "signal_type": "c18_only",
            "signal_col": "order_volume_ratio_rank_delta",
        },
    }

    matrix_cols = [
        "c4_oc_asym_5d",
        "c5_ins_relative_size_5d",
        "c5_signal_present",
        "c6_contrarian_intra_5d",
        "c7_ceiling_count_5d",
        "c8_vol_zscore_5d",
        "c9_reversal_1d",
        "c10_illiq_level_rank",
        "c11_ret_60d_lag_rank",
        "c12_gap_absorb_3",
        "c13_compress_blowoff_2",
        "c14_clv_volconf_resid_rank",
    ]

    for col in matrix_cols:
        standalone_name = f"m_{col}_depth5"
        configs[standalone_name] = {
            **base,
            "name": standalone_name,
            "signal_type": "surface_col",
            "source_surface": "rl_signal_matrix",
            "source_col": col,
            "signal_col": col,
        }
        blend_name = f"s1b_{col}_70_30_depth5"
        configs[blend_name] = {
            **base,
            "name": blend_name,
            "signal_type": "s1_surface_blend",
            "source_surface": "rl_signal_matrix",
            "source_col": col,
            "signal_col": "blend",
            "w_s1": 0.7,
            "w_surface": 0.3,
        }

    return configs


def _classify_strategy(
    *,
    readiness_row: pd.Series,
    failure_excess: float | None,
    failure_cash: float | None,
    failure_underfill: float | None,
    baseline_failure_excess: float | None,
    baseline_failure_cash: float | None,
    baseline_failure_underfill: float | None,
) -> tuple[str, str]:
    is_ready = bool(readiness_row.get("is_profit_ready", False))
    mean_excess = float(readiness_row.get("mean_excess_return", np.nan))
    worst_fold = float(readiness_row.get("worst_fold_return", np.nan))

    severe_vs_baseline = False
    if (
        baseline_failure_excess is not None
        and baseline_failure_cash is not None
        and baseline_failure_underfill is not None
        and failure_excess is not None
        and failure_cash is not None
        and failure_underfill is not None
    ):
        severe_vs_baseline = (
            (failure_excess < baseline_failure_excess - 0.03)
            or (failure_cash > baseline_failure_cash + 5.0)
            or (failure_underfill > baseline_failure_underfill + 5.0)
        )

    if is_ready and mean_excess > 0 and not severe_vs_baseline:
        return "PROMOTE_CANDIDATE", "passes readiness and no severe failure-cohort regression vs baseline"
    if (not np.isnan(mean_excess) and mean_excess < -0.05) or (not np.isnan(worst_fold) and worst_fold < -0.35):
        return "KILL", "fails profitability floor (mean_excess<-5% or worst_fold<-35%)"
    return "RESEARCH_ONLY", "inconclusive or mixed; keep for further testing"


def _safe_cohort_metric(autopsy_cohort_df: pd.DataFrame, cohort: str, metric: str) -> float | None:
    if autopsy_cohort_df is None or len(autopsy_cohort_df) == 0:
        return None
    rows = autopsy_cohort_df[autopsy_cohort_df["cohort"] == cohort]
    if len(rows) == 0:
        return None
    value = rows.iloc[0].get(metric, np.nan)
    if pd.isna(value):
        return None
    return float(value)


def _benchmark_total_return(start_date: str, end_date: str) -> float | None:
    import constraints as cn

    try:
        vn = cn.load_vnindex(start=start_date, end=end_date)
    except Exception:
        return None
    if vn is None or len(vn) == 0:
        return None

    start_open = float(vn["open"].iloc[0])
    end_open = float(vn["open"].iloc[-1])
    shares = int(100_000_000 / start_open)
    cost = shares * start_open * 1.001
    initial_cash = 100_000_000 - cost
    proceeds = shares * end_open * 0.9984
    final_value = initial_cash + proceeds
    return float((final_value / 100_000_000) - 1.0)


def _run_autopsy_for_config(
    *,
    strategy_name: str,
    config: dict,
    failure_years: list[int],
    success_years: list[int],
    price_cache: dict,
    liquid_lookup: dict,
    trad_lookup: dict,
    output_dir: Path,
) -> pd.DataFrame:
    years = sorted(set(failure_years) | set(success_years))
    rows: list[dict] = []

    for year in years:
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        signal_df = prepare_signal_df_from_config(config, start_date, end_date, allow_2026=False)
        result = bt.simulate_topk_constraint_compliant(
            signal_df,
            price_cache,
            signal_col=config["signal_col"],
            top_k=int(config["top_k"]),
            rebalance_days=int(config["rebalance_days"]),
            min_hold_days=int(config["min_hold_days"]),
            use_filters=True,
            liquid_lookup=liquid_lookup,
            trad_lookup=trad_lookup,
            collect_diagnostics=True,
            candidate_scan_multiplier=int(config.get("candidate_scan_multiplier", 3)),
            sizing_mode=str(config.get("sizing_mode", "fixed_initial")),
            fallback_mode=str(config.get("fallback_mode", "none")),
            gate_enabled=bool(config.get("gate_enabled", False)),
            gate_profile=str(config.get("gate_profile", "off")),
            exposure_floor=float(config.get("exposure_floor", 0.20)),
            exposure_ceiling=float(config.get("exposure_ceiling", 1.00)),
            kill_switch_thresholds=config.get("kill_switch_thresholds"),
            cooldown_rebalances=int(config.get("cooldown_rebalances", 2)),
        )
        benchmark_return = _benchmark_total_return(start_date, end_date)
        excess_return = (
            float(result.total_return - benchmark_return)
            if benchmark_return is not None
            else float("nan")
        )
        diags = result.diagnostics or {}
        curve_metrics = _compute_curve_metrics(result.curve, top_k=int(config["top_k"]))
        filter_metrics = _compute_filter_metrics(
            diags.get("filtered_breakdown", pd.DataFrame()),
            top_k=int(config["top_k"]),
        )
        fallback_metrics = _compute_fallback_metrics(diags.get("fallback_log", pd.DataFrame()))
        cohort = "failure" if year in failure_years else "success"
        row = {
            "strategy_name": strategy_name,
            "year": year,
            "cohort": cohort,
            "total_return": float(result.total_return),
            "excess_return": excess_return,
            "benchmark_return": float(benchmark_return) if benchmark_return is not None else float("nan"),
            "n_trades": int(result.n_trades),
            "n_filtered": int(result.n_filtered),
            "max_drawdown": float(result.max_drawdown),
        }
        row.update(curve_metrics)
        row.update(filter_metrics)
        row.update(fallback_metrics)
        rows.append(row)

    yearly_df = pd.DataFrame(rows).sort_values("year")
    yearly_df.to_csv(output_dir / "autopsy_yearly.csv", index=False)
    numeric_cols = [
        "total_return",
        "excess_return",
        "benchmark_return",
        "avg_cash_pct",
        "avg_invested_pct",
        "avg_n_holdings",
        "avg_underfill_pct",
        "underfilled_days_pct",
        "selection_fill_rate",
        "liquidity_rejection_rate",
        "tradability_rejection_rate",
        "fallback_trigger_rate",
        "n_trades",
        "n_filtered",
        "max_drawdown",
    ]
    cohort_df = yearly_df.groupby("cohort", dropna=False)[numeric_cols].mean(numeric_only=True).reset_index()
    cohort_df.to_csv(output_dir / "autopsy_cohort_summary.csv", index=False)
    return cohort_df


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canonical signal sweep with readiness/autopsy labeling")
    parser.add_argument("--output-dir", type=str, default="", help="Optional explicit output directory.")
    parser.add_argument("--failure-years", type=str, default=DEFAULT_FAILURE_YEARS)
    parser.add_argument("--success-years", type=str, default=DEFAULT_SUCCESS_YEARS)
    parser.add_argument("--skip-autopsy", action="store_true", help="Skip cohort autopsy stage.")
    parser.add_argument("--autopsy-limit", type=int, default=0, help="Limit autopsy to top-N readiness rows (0=all).")
    parser.add_argument("--strategy-limit", type=int, default=0, help="Limit sweep to first N predeclared strategies (0=all).")
    parser.add_argument(
        "--promotion-override-strategies",
        type=str,
        default="",
        help="Comma-separated strategy names to force OVERRIDE_PROMOTED status (requires explicit note justification).",
    )
    parser.add_argument("--min-positive-folds", type=int, default=7)
    parser.add_argument("--min-beating-benchmark-folds", type=int, default=5)
    parser.add_argument("--min-mean-excess-return", type=float, default=0.0)
    parser.add_argument("--max-mean-drawdown", type=float, default=0.35)
    parser.add_argument("--max-worst-fold-return", type=float, default=-0.30)
    parser.add_argument(
        "--promotion-contract-csv",
        type=str,
        default=str(DEFAULT_PROMOTION_CONTRACT_CSV),
        help="Shared lab->heuristic promotion contract CSV path.",
    )
    parser.add_argument(
        "--require-promotion-contract",
        action="store_true",
        help="Fail if promotion contract CSV is missing.",
    )
    parser.add_argument(
        "--publish-feedback-csv",
        type=str,
        default=str(DEFAULT_PROMOTION_FEEDBACK_CSV),
        help="Path for writing latest heuristic feedback table keyed by signal_id.",
    )
    return parser


def main() -> None:
    args = create_argument_parser().parse_args()
    out_dir = Path(args.output_dir) if args.output_dir else SWEEP_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir = out_dir / "canonical_wfv"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    autopsy_root = out_dir / "autopsy"
    autopsy_root.mkdir(parents=True, exist_ok=True)

    failure_years = _parse_years(args.failure_years)
    success_years = _parse_years(args.success_years)
    override_strategies = _parse_csv_list(args.promotion_override_strategies)

    thresholds = ReadinessThresholds(
        min_positive_folds=int(args.min_positive_folds),
        min_beating_benchmark_folds=int(args.min_beating_benchmark_folds),
        min_mean_excess_return=float(args.min_mean_excess_return),
        max_mean_drawdown=float(args.max_mean_drawdown),
        max_worst_fold_return=float(args.max_worst_fold_return),
    )

    configs = build_strategy_configs()
    if args.strategy_limit and args.strategy_limit > 0:
        items = list(configs.items())[: int(args.strategy_limit)]
        configs = dict(items)
    liquid_lookup, trad_lookup, price_cache = load_caches()

    strategy_metrics_map: dict[str, list[dict]] = {name: [] for name in configs}
    all_metrics: list[dict] = []
    for strategy_name, cfg in configs.items():
        print(f"[sweep] strategy={strategy_name}")
        for fold in FOLDS:
            metrics = run_strategy_on_fold(
                cfg,
                fold,
                liquid_lookup,
                trad_lookup,
                price_cache,
                collect_diagnostics=False,
                diagnostics_output_dir=None,
            )
            strategy_metrics_map[strategy_name].append(metrics)
            all_metrics.append(metrics)

    (out_dir / "fold_metrics_all.csv").write_text(pd.DataFrame(all_metrics).to_csv(index=False), encoding="utf-8")

    strategy_summaries = []
    for strategy_name, metrics_list in strategy_metrics_map.items():
        summary = compute_strategy_summary(metrics_list)
        if summary:
            strategy_summaries.append(summary)
            _write_canonical_strategy_outputs(
                canonical_root=canonical_dir,
                strategy_name=strategy_name,
                config=configs[strategy_name],
                strategy_metrics=metrics_list,
                summary_row=summary,
                active_folds=FOLDS,
            )
    leaderboard_df = _rebuild_canonical_leaderboard(canonical_dir)
    _write_canonical_manifest(canonical_dir, FOLDS, len(leaderboard_df))

    readiness_df, readiness_summary = run_readiness(
        canonical_dir=canonical_dir,
        thresholds=thresholds,
        output_dir=out_dir,
    )

    autopsy_targets = readiness_df["strategy_name"].tolist()
    if args.autopsy_limit and args.autopsy_limit > 0:
        autopsy_targets = autopsy_targets[: int(args.autopsy_limit)]
    if args.skip_autopsy:
        autopsy_targets = []

    autopsy_rows: list[dict] = []
    baseline_name = "ctrl_blend_70_30_depth5"
    baseline_failure_excess = None
    baseline_failure_cash = None
    baseline_failure_underfill = None

    autopsy_cache: dict[str, pd.DataFrame] = {}
    for strategy_name in autopsy_targets:
        strat_dir = autopsy_root / strategy_name
        strat_dir.mkdir(parents=True, exist_ok=True)
        cohort_df = _run_autopsy_for_config(
            strategy_name=strategy_name,
            config=configs[strategy_name],
            failure_years=failure_years,
            success_years=success_years,
            price_cache=price_cache,
            liquid_lookup=liquid_lookup,
            trad_lookup=trad_lookup,
            output_dir=strat_dir,
        )
        autopsy_cache[strategy_name] = cohort_df

        failure_excess = _safe_cohort_metric(cohort_df, "failure", "excess_return")
        success_excess = _safe_cohort_metric(cohort_df, "success", "excess_return")
        failure_cash = _safe_cohort_metric(cohort_df, "failure", "avg_cash_pct")
        success_cash = _safe_cohort_metric(cohort_df, "success", "avg_cash_pct")
        failure_underfill = _safe_cohort_metric(cohort_df, "failure", "avg_underfill_pct")
        success_underfill = _safe_cohort_metric(cohort_df, "success", "avg_underfill_pct")
        failure_fill = _safe_cohort_metric(cohort_df, "failure", "selection_fill_rate")
        success_fill = _safe_cohort_metric(cohort_df, "success", "selection_fill_rate")

        if strategy_name == baseline_name:
            baseline_failure_excess = failure_excess
            baseline_failure_cash = failure_cash
            baseline_failure_underfill = failure_underfill

        autopsy_rows.append(
            {
                "strategy_name": strategy_name,
                "failure_excess_return": failure_excess,
                "success_excess_return": success_excess,
                "failure_minus_success_excess": (
                    float(failure_excess - success_excess)
                    if failure_excess is not None and success_excess is not None
                    else np.nan
                ),
                "failure_cash_pct": failure_cash,
                "success_cash_pct": success_cash,
                "failure_underfill_pct": failure_underfill,
                "success_underfill_pct": success_underfill,
                "failure_selection_fill_rate": failure_fill,
                "success_selection_fill_rate": success_fill,
            }
        )

    autopsy_df = pd.DataFrame(autopsy_rows)
    if len(autopsy_df) > 0:
        autopsy_df.to_csv(out_dir / "autopsy_summary_by_strategy.csv", index=False)

    if baseline_name not in autopsy_cache and not args.skip_autopsy:
        baseline_dir = autopsy_root / baseline_name
        baseline_dir.mkdir(parents=True, exist_ok=True)
        baseline_cohort = _run_autopsy_for_config(
            strategy_name=baseline_name,
            config=configs[baseline_name],
            failure_years=failure_years,
            success_years=success_years,
            price_cache=price_cache,
            liquid_lookup=liquid_lookup,
            trad_lookup=trad_lookup,
            output_dir=baseline_dir,
        )
        baseline_failure_excess = _safe_cohort_metric(baseline_cohort, "failure", "excess_return")
        baseline_failure_cash = _safe_cohort_metric(baseline_cohort, "failure", "avg_cash_pct")
        baseline_failure_underfill = _safe_cohort_metric(baseline_cohort, "failure", "avg_underfill_pct")

    merged = readiness_df.copy()
    if len(autopsy_df) > 0:
        merged = merged.merge(autopsy_df, on="strategy_name", how="left")
    else:
        merged["failure_excess_return"] = np.nan
        merged["failure_cash_pct"] = np.nan
        merged["failure_underfill_pct"] = np.nan
        merged["failure_selection_fill_rate"] = np.nan

    if "failure_selection_fill_rate" not in merged.columns:
        merged["failure_selection_fill_rate"] = np.nan

    merged["signal_id"] = merged["strategy_name"].map(_strategy_to_signal_id)
    contract_path = Path(args.promotion_contract_csv)
    contract_enabled = False
    contract_missing = not contract_path.exists()
    if contract_missing and args.require_promotion_contract:
        raise FileNotFoundError(f"Required promotion contract not found: {contract_path}")
    if not contract_missing:
        contract_df = _load_promotion_contract(contract_path)
        if not contract_df.empty:
            contract_enabled = True
            contract_cols = [
                "signal_id",
                "lab_promotion_status",
                "proxy_gate_pass",
                "execution_readiness_verdict",
                "proxy_execution_score",
                "as_of_date",
            ]
            available_cols = [c for c in contract_cols if c in contract_df.columns]
            contract_view = contract_df[available_cols].copy()
            contract_view = contract_view.rename(
                columns={
                    "lab_promotion_status": "contract_lab_promotion_status",
                    "proxy_gate_pass": "contract_proxy_gate_pass",
                    "execution_readiness_verdict": "contract_execution_readiness_verdict",
                    "proxy_execution_score": "contract_proxy_execution_score",
                    "as_of_date": "contract_as_of_date",
                }
            )
            merged = merged.merge(contract_view, on="signal_id", how="left")

    if "contract_lab_promotion_status" not in merged.columns:
        merged["contract_lab_promotion_status"] = np.nan
    if "contract_proxy_gate_pass" not in merged.columns:
        merged["contract_proxy_gate_pass"] = np.nan
    if "contract_execution_readiness_verdict" not in merged.columns:
        merged["contract_execution_readiness_verdict"] = np.nan
    if "contract_proxy_execution_score" not in merged.columns:
        merged["contract_proxy_execution_score"] = np.nan
    if "contract_as_of_date" not in merged.columns:
        merged["contract_as_of_date"] = np.nan

    labels = []
    reasons = []
    statuses = []
    status_warnings = []
    for _, row in merged.iterrows():
        strategy_name = str(row.get("strategy_name", ""))
        is_control = strategy_name.startswith("ctrl_")
        upstream_status = None
        if contract_enabled and not is_control:
            if pd.notna(row.get("contract_lab_promotion_status")):
                upstream_status = str(row.get("contract_lab_promotion_status"))
            else:
                upstream_status = STATUS_RESEARCH_CANDIDATE
        upstream_allowed = (
            upstream_status in UPSTREAM_EXECUTION_ELIGIBLE_STATUSES
            if upstream_status is not None
            else True
        )

        label, reason = _classify_strategy(
            readiness_row=row,
            failure_excess=(None if pd.isna(row.get("failure_excess_return")) else float(row["failure_excess_return"])),
            failure_cash=(None if pd.isna(row.get("failure_cash_pct")) else float(row["failure_cash_pct"])),
            failure_underfill=(
                None if pd.isna(row.get("failure_underfill_pct")) else float(row["failure_underfill_pct"])
            ),
            baseline_failure_excess=baseline_failure_excess,
            baseline_failure_cash=baseline_failure_cash,
            baseline_failure_underfill=baseline_failure_underfill,
        )
        if not upstream_allowed and strategy_name not in override_strategies:
            label = "RESEARCH_ONLY"
            reason = f"blocked by lab promotion contract status '{upstream_status}'"

        gate_checks = {
            "all_pass": bool(row.get("is_profit_ready", False)) and bool(upstream_allowed),
        }
        status, status_warning = derive_execution_status(
            strategy_name=strategy_name,
            checks=gate_checks,
            manual_override=strategy_name in override_strategies,
            upstream_status=upstream_status,
        )
        labels.append(label)
        reasons.append(reason)
        statuses.append(status)
        status_warnings.append(status_warning)
        row_idx = row.name
        merged.loc[row_idx, "contract_upstream_allowed"] = bool(upstream_allowed)
        merged.loc[row_idx, "contract_upstream_status_used"] = upstream_status if upstream_status is not None else ""

    merged["contract_enabled"] = bool(contract_enabled)
    merged["decision_label"] = labels
    merged["decision_reason"] = reasons
    merged["promotion_status"] = statuses
    merged["promotion_status_warning"] = status_warnings
    merged.to_csv(out_dir / "signal_sweep_decisions.csv", index=False)

    feedback_df = (
        merged.dropna(subset=["signal_id"])
        .groupby("signal_id", dropna=False)
        .agg(
            as_of_date=("strategy_name", lambda _: datetime.now().strftime("%Y-%m-%d")),
            n_strategies=("strategy_name", "count"),
            promote_count=("decision_label", lambda s: int((s == "PROMOTE_CANDIDATE").sum())),
            kill_count=("decision_label", lambda s: int((s == "KILL").sum())),
            research_count=("decision_label", lambda s: int((s == "RESEARCH_ONLY").sum())),
            mean_excess_return=("mean_excess_return", "mean"),
            worst_fold_return=("worst_fold_return", "min"),
            mean_failure_cash_pct=("failure_cash_pct", "mean"),
            mean_failure_underfill_pct=("failure_underfill_pct", "mean"),
            mean_failure_selection_fill_rate=("failure_selection_fill_rate", "mean"),
        )
        .reset_index()
    )
    feedback_out = out_dir / "signal_promotion_feedback.csv"
    feedback_df.to_csv(feedback_out, index=False)
    publish_feedback_path = Path(args.publish_feedback_csv)
    publish_feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_df.to_csv(publish_feedback_path, index=False)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_strategies": int(len(configs)),
        "n_autopsy": int(len(autopsy_targets)),
        "failure_years": failure_years,
        "success_years": success_years,
        "thresholds": thresholds.__dict__,
        "readiness_summary": readiness_summary,
        "baseline_strategy": baseline_name,
        "baseline_failure_excess": baseline_failure_excess,
        "baseline_failure_cash": baseline_failure_cash,
        "baseline_failure_underfill": baseline_failure_underfill,
        "promotion_override_strategies": sorted(override_strategies),
        "promotion_contract_csv": str(contract_path),
        "promotion_contract_enabled": bool(contract_enabled),
        "promotion_contract_missing": bool(contract_missing),
        "promotion_feedback_csv": str(publish_feedback_path),
    }
    with open(out_dir / "signal_sweep_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[done] strategies={len(configs)} output={out_dir}")


if __name__ == "__main__":
    main()
