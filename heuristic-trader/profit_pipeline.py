#!/usr/bin/env python3
"""
Profit pipeline for heuristic-trader.

Purpose:
1) Turn canonical walk-forward outputs into explicit profit-readiness gates.
2) Run year-cohort execution autopsy to explain PnL conversion failures.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import backtest as bt
from horizon_lens import compute_horizon_metrics_from_curve, horizon_metrics_to_wide, to_records
from runtime_helpers import compute_vnindex_total_return
from risk_policy import RiskPolicy, derive_execution_status, evaluate_strategy_row
from run_backtest import load_caches
from signal_factory import prepare_signal_df_from_config
from strategies import loader as strategy_loader


ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = ROOT / "artifacts"
CANONICAL_WFV_DIR = ARTIFACTS_DIR / "canonical_wfv"
PROFIT_PIPELINE_DIR = ARTIFACTS_DIR / "profit_pipeline"


@dataclass(frozen=True)
class ReadinessThresholds:
    min_positive_folds: int = 7
    min_beating_benchmark_folds: int = 5
    min_mean_excess_return: float = 0.0
    max_mean_drawdown: float = 0.35
    max_worst_fold_return: float = -0.30


def _load_canonical_strategy_config(canonical_dir: Path, strategy_name: str) -> tuple[dict | None, Path]:
    config_path = canonical_dir / "strategies" / strategy_name / "config_effective.json"
    if not config_path.exists():
        return None, config_path
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f), config_path


def _load_canonical_window(canonical_dir: Path) -> tuple[str, str]:
    manifest_path = canonical_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        folds = payload.get("folds", [])
        if isinstance(folds, list) and len(folds) > 0:
            starts = [str(x.get("test_start")) for x in folds if x.get("test_start")]
            ends = [str(x.get("test_end")) for x in folds if x.get("test_end")]
            if starts and ends:
                return min(starts), max(ends)
    return "2015-01-01", "2025-12-31"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _parse_years(value: str) -> list[int]:
    years = [int(x.strip()) for x in value.split(",") if x.strip()]
    if not years:
        raise ValueError("year list cannot be empty")
    return years


def _benchmark_total_return(start_date: str, end_date: str) -> float | None:
    return compute_vnindex_total_return(start_date, end_date)


def _compute_curve_metrics(curve: pd.DataFrame, *, top_k: int) -> dict[str, float]:
    if curve is None or len(curve) == 0:
        return {
            "avg_cash_pct": float("nan"),
            "avg_invested_pct": float("nan"),
            "avg_n_holdings": float("nan"),
            "avg_underfill_pct": float("nan"),
            "underfilled_days_pct": float("nan"),
        }

    with np.errstate(divide="ignore", invalid="ignore"):
        cash_pct = (curve["cash"] / curve["portfolio_value"]) * 100.0
        invested_pct = (curve["holdings_value"] / curve["portfolio_value"]) * 100.0
    underfill_pct = ((top_k - curve["n_holdings"]) / top_k) * 100.0
    underfilled_days = (curve["n_holdings"] < top_k).mean() * 100.0

    return {
        "avg_cash_pct": float(cash_pct.mean()),
        "avg_invested_pct": float(invested_pct.mean()),
        "avg_n_holdings": float(curve["n_holdings"].mean()),
        "avg_underfill_pct": float(underfill_pct.mean()),
        "underfilled_days_pct": float(underfilled_days),
    }


def _compute_filter_metrics(filtered_breakdown: pd.DataFrame, *, top_k: int) -> dict[str, float]:
    if filtered_breakdown is None or len(filtered_breakdown) == 0:
        return {
            "rebalance_count": 0.0,
            "avg_selected_per_rebalance": float("nan"),
            "selection_fill_rate": float("nan"),
            "liquidity_rejection_rate": float("nan"),
            "tradability_rejection_rate": float("nan"),
        }

    n_rebalance = float(len(filtered_breakdown))
    total_selected = float(filtered_breakdown["n_selected"].sum())
    total_scan = float(filtered_breakdown["n_candidates"].sum())
    total_liq = float(filtered_breakdown["n_filtered_liquidity"].sum())
    total_trad = float(filtered_breakdown["n_filtered_tradability"].sum())
    denom_fill = n_rebalance * float(top_k) if n_rebalance > 0 else np.nan

    return {
        "rebalance_count": n_rebalance,
        "avg_selected_per_rebalance": float(filtered_breakdown["n_selected"].mean()),
        "selection_fill_rate": float(total_selected / denom_fill) if denom_fill else float("nan"),
        "liquidity_rejection_rate": float(total_liq / total_scan) if total_scan > 0 else float("nan"),
        "tradability_rejection_rate": float(total_trad / total_scan) if total_scan > 0 else float("nan"),
    }


def _compute_fallback_metrics(fallback_log: pd.DataFrame) -> dict[str, float]:
    if fallback_log is None or len(fallback_log) == 0:
        return {"fallback_trigger_rate": float("nan")}
    return {"fallback_trigger_rate": float(fallback_log["fallback_triggered"].mean())}


def _simulate_curve_for_config(
    *,
    config: dict,
    start_date: str,
    end_date: str,
    price_cache: dict,
    liquid_lookup: dict,
    trad_lookup: dict,
    allow_2026: bool,
) -> pd.DataFrame:
    signal_df = prepare_signal_df_from_config(
        config=config,
        start_date=start_date,
        end_date=end_date,
        allow_2026=allow_2026,
    )
    if signal_df is None or len(signal_df) == 0:
        return pd.DataFrame()
    result = bt.simulate_topk_constraint_compliant(
        signal_df,
        price_cache,
        signal_col=str(config["signal_col"]),
        top_k=int(config["top_k"]),
        rebalance_days=int(config["rebalance_days"]),
        min_hold_days=int(config["min_hold_days"]),
        use_filters=True,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        collect_diagnostics=False,
        candidate_scan_multiplier=int(config.get("candidate_scan_multiplier", 3)),
        sizing_mode=str(config.get("sizing_mode", "fixed_initial")),
        fallback_mode=str(config.get("fallback_mode", "none")),
        gate_enabled=bool(config.get("gate_enabled", False)),
        gate_profile=str(config.get("gate_profile", "off")),
        exposure_floor=float(config.get("exposure_floor", 0.20)),
        exposure_ceiling=float(config.get("exposure_ceiling", 1.00)),
        kill_switch_thresholds=config.get("kill_switch_thresholds"),
        cooldown_rebalances=int(config.get("cooldown_rebalances", 2)),
        incumbent_bonus_bps=float(config.get("incumbent_bonus_bps", 0.0)),
        replace_threshold_bps=float(config.get("replace_threshold_bps", 0.0)),
        max_new_positions_per_rebalance=(
            None
            if config.get("max_new_positions_per_rebalance") is None
            else int(config.get("max_new_positions_per_rebalance"))
        ),
        underfill_recovery_days=int(config.get("underfill_recovery_days", 0)),
        recovery_target_slots_mode=str(config.get("recovery_target_slots_mode", "fixed_target")),
        regime_translation=config.get("regime_translation"),
        conviction_mode=str(config.get("conviction_mode", "off")),
        conviction_strength=float(config.get("conviction_strength", 0.0)),
        conviction_cap=float(config.get("conviction_cap", 2.0)),
    )
    return result.curve if result.curve is not None else pd.DataFrame()


def _run_strategy_year(
    *,
    strategy_name: str,
    year: int,
    price_cache: dict,
    liquid_lookup: dict,
    trad_lookup: dict,
    allow_2026: bool,
) -> dict[str, float | int | str]:
    config = strategy_loader.load_strategy_config(strategy_name)
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    signal_df = prepare_signal_df_from_config(
        config,
        start_date,
        end_date,
        allow_2026=allow_2026,
    )

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
        incumbent_bonus_bps=float(config.get("incumbent_bonus_bps", 0.0)),
        replace_threshold_bps=float(config.get("replace_threshold_bps", 0.0)),
        max_new_positions_per_rebalance=(
            None
            if config.get("max_new_positions_per_rebalance") is None
            else int(config.get("max_new_positions_per_rebalance"))
        ),
        underfill_recovery_days=int(config.get("underfill_recovery_days", 0)),
        recovery_target_slots_mode=str(config.get("recovery_target_slots_mode", "fixed_target")),
        regime_translation=config.get("regime_translation"),
        conviction_mode=str(config.get("conviction_mode", "off")),
        conviction_strength=float(config.get("conviction_strength", 0.0)),
        conviction_cap=float(config.get("conviction_cap", 2.0)),
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

    row: dict[str, float | int | str] = {
        "strategy_name": strategy_name,
        "year": year,
        "signal_type": str(config["signal_type"]),
        "signal_col": str(config["signal_col"]),
        "top_k": int(config["top_k"]),
        "rebalance_days": int(config["rebalance_days"]),
        "candidate_scan_multiplier": int(config.get("candidate_scan_multiplier", 3)),
        "sizing_mode": str(config.get("sizing_mode", "fixed_initial")),
        "fallback_mode": str(config.get("fallback_mode", "none")),
        "gate_enabled": bool(config.get("gate_enabled", False)),
        "gate_profile": str(config.get("gate_profile", "off")),
        "exposure_floor": float(config.get("exposure_floor", 0.20)),
        "exposure_ceiling": float(config.get("exposure_ceiling", 1.00)),
        "cooldown_rebalances": int(config.get("cooldown_rebalances", 2)),
        "incumbent_bonus_bps": float(config.get("incumbent_bonus_bps", 0.0)),
        "replace_threshold_bps": float(config.get("replace_threshold_bps", 0.0)),
        "max_new_positions_per_rebalance": (
            None
            if config.get("max_new_positions_per_rebalance") is None
            else int(config.get("max_new_positions_per_rebalance"))
        ),
        "underfill_recovery_days": int(config.get("underfill_recovery_days", 0)),
        "recovery_target_slots_mode": str(config.get("recovery_target_slots_mode", "fixed_target")),
        "conviction_mode": str(config.get("conviction_mode", "off")),
        "conviction_strength": float(config.get("conviction_strength", 0.0)),
        "conviction_cap": float(config.get("conviction_cap", 2.0)),
        "total_return": float(result.total_return),
        "annualized_return": float(result.annualized_return),
        "max_drawdown": float(result.max_drawdown),
        "n_trades": int(result.n_trades),
        "n_filtered": int(result.n_filtered),
        "benchmark_return": float(benchmark_return) if benchmark_return is not None else float("nan"),
        "excess_return": excess_return,
    }
    row.update(curve_metrics)
    row.update(filter_metrics)
    row.update(fallback_metrics)
    return row


def _cohort_label(year: int, *, failure_years: set[int], success_years: set[int]) -> str:
    if year in failure_years:
        return "failure"
    if year in success_years:
        return "success"
    return "other"


def run_autopsy(
    *,
    strategy_name: str,
    failure_years: Iterable[int],
    success_years: Iterable[int],
    output_dir: Path,
    allow_2026: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    failure_set = set(int(y) for y in failure_years)
    success_set = set(int(y) for y in success_years)
    all_years = sorted(failure_set | success_set)

    liquid_lookup, trad_lookup, price_cache = load_caches()
    rows = []
    for year in all_years:
        row = _run_strategy_year(
            strategy_name=strategy_name,
            year=year,
            price_cache=price_cache,
            liquid_lookup=liquid_lookup,
            trad_lookup=trad_lookup,
            allow_2026=allow_2026,
        )
        row["cohort"] = _cohort_label(year, failure_years=failure_set, success_years=success_set)
        rows.append(row)

    yearly_df = pd.DataFrame(rows).sort_values(["year"]).reset_index(drop=True)
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
    cohort_df = (
        yearly_df.groupby("cohort", dropna=False)[numeric_cols]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values("cohort")
    )

    yearly_df.to_csv(output_dir / "autopsy_yearly.csv", index=False)
    cohort_df.to_csv(output_dir / "autopsy_cohort_summary.csv", index=False)

    if set(cohort_df["cohort"]) >= {"failure", "success"}:
        fail = cohort_df[cohort_df["cohort"] == "failure"].iloc[0]
        succ = cohort_df[cohort_df["cohort"] == "success"].iloc[0]
        delta = pd.DataFrame(
            [
                {
                    "metric": c,
                    "failure_minus_success": float(fail[c] - succ[c]),
                }
                for c in numeric_cols
                if c in fail and c in succ
            ]
        )
        delta.to_csv(output_dir / "autopsy_failure_minus_success.csv", index=False)

    return yearly_df, cohort_df


def _write_paper_handoff_bundle(
    *,
    readiness_df: pd.DataFrame,
    canonical_dir: Path,
    output_dir: Path,
    thresholds: ReadinessThresholds,
    fallback_strategy: str = "",
) -> None:
    if readiness_df is None or readiness_df.empty:
        return

    ordered = readiness_df.copy().reset_index(drop=True)
    profit_ready = ordered[ordered["is_profit_ready"] == True]  # noqa: E712
    primary_name = (
        str(profit_ready.iloc[0]["strategy_name"])
        if len(profit_ready) > 0
        else str(ordered.iloc[0]["strategy_name"])
    )
    if fallback_strategy:
        fallback_name = fallback_strategy
    elif len(profit_ready) > 1:
        fallback_name = str(profit_ready.iloc[1]["strategy_name"])
    elif len(ordered) > 1:
        fallback_name = str(ordered.iloc[1]["strategy_name"])
    else:
        fallback_name = primary_name

    primary_cfg, primary_cfg_path = _load_canonical_strategy_config(canonical_dir, primary_name)
    fallback_cfg, fallback_cfg_path = _load_canonical_strategy_config(canonical_dir, fallback_name)
    primary_row = ordered[ordered["strategy_name"] == primary_name].iloc[0]
    fallback_rows = ordered[ordered["strategy_name"] == fallback_name]
    fallback_row = fallback_rows.iloc[0] if len(fallback_rows) > 0 else pd.Series(dtype=object)

    def _row_to_jsonable(row: pd.Series) -> dict:
        if row.empty:
            return {}
        return json.loads(row.to_json())

    def _extract_horizon_block(row: pd.Series) -> dict:
        if row.empty:
            return {}
        out: dict[str, dict] = {}
        for h in ("w", "m", "q", "6m"):
            mean_key = f"h_{h}_mean_return"
            pos_key = f"h_{h}_positive_rate"
            worst_key = f"h_{h}_worst_return"
            n_key = f"h_{h}_n_periods"
            if pd.notna(row.get(mean_key, np.nan)):
                out[h.upper()] = {
                    "mean_return": float(row.get(mean_key)),
                    "positive_period_rate": float(row.get(pos_key)),
                    "worst_period_return": float(row.get(worst_key)),
                    "n_periods": int(row.get(n_key)),
                }
        return out

    bundle = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "horizon_lens": {
            "horizons": ["W", "M", "Q", "6M"],
            "informational_only": True,
        },
        "primary_strategy": {
            "name": primary_name,
            "config_path": str(primary_cfg_path),
            "config_found": primary_cfg is not None,
            "readiness": _row_to_jsonable(primary_row),
            "horizon_metrics": _extract_horizon_block(primary_row),
        },
        "fallback_strategy": {
            "name": fallback_name,
            "config_path": str(fallback_cfg_path),
            "config_found": fallback_cfg is not None,
            "readiness": _row_to_jsonable(fallback_row),
            "horizon_metrics": _extract_horizon_block(fallback_row),
        },
        "rollback_triggers": {
            "mean_drawdown_gt": float(thresholds.max_mean_drawdown),
            "worst_fold_return_lt": float(thresholds.max_worst_fold_return),
            "positive_folds_lt": int(thresholds.min_positive_folds),
            "beating_benchmark_folds_lt": int(thresholds.min_beating_benchmark_folds),
            "mean_excess_return_lt": float(thresholds.min_mean_excess_return),
        },
        "daily_monitoring_fields": [
            "portfolio_value",
            "cash_pct",
            "n_holdings",
            "underfill_pct",
            "selection_fill_rate",
            "liquidity_rejection_rate",
            "tradability_rejection_rate",
            "benchmark_excess_return",
            "kill_switch_active",
            "gate_state",
        ],
    }
    with open(output_dir / "paper_handoff_bundle.json", "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)

    lines = [
        "# Paper Trading Handoff",
        "",
        f"- Primary strategy: `{primary_name}`",
        f"- Fallback strategy: `{fallback_name}`",
        f"- Canonical source: `{canonical_dir}`",
        "",
        "## Rollback Triggers",
        f"- mean_drawdown > {thresholds.max_mean_drawdown:.2f}",
        f"- worst_fold_return < {thresholds.max_worst_fold_return:.2f}",
        f"- positive_folds < {thresholds.min_positive_folds}",
        f"- beating_benchmark_folds < {thresholds.min_beating_benchmark_folds}",
        f"- mean_excess_return < {thresholds.min_mean_excess_return:.4f}",
        "",
        "## Operator Monitoring Fields",
    ]
    for field in bundle["daily_monitoring_fields"]:
        lines.append(f"- `{field}`")
    (output_dir / "paper_handoff_checklist.md").write_text("\n".join(lines), encoding="utf-8")


def run_readiness(
    *,
    canonical_dir: Path,
    thresholds: ReadinessThresholds,
    output_dir: Path,
) -> tuple[pd.DataFrame, dict]:
    leaderboard_path = canonical_dir / "leaderboard.csv"
    if not leaderboard_path.exists():
        raise FileNotFoundError(f"missing canonical leaderboard: {leaderboard_path}")

    leaderboard = pd.read_csv(leaderboard_path)
    if leaderboard.empty:
        raise RuntimeError("canonical leaderboard is empty")

    policy = RiskPolicy(
        min_positive_folds=int(thresholds.min_positive_folds),
        min_beating_benchmark_folds=int(thresholds.min_beating_benchmark_folds),
        min_mean_excess_return=float(thresholds.min_mean_excess_return),
        max_mean_drawdown=float(thresholds.max_mean_drawdown),
        max_worst_fold_return=float(thresholds.max_worst_fold_return),
    )

    rows = []
    horizon_rows: list[dict] = []
    start_date, end_date = _load_canonical_window(canonical_dir)
    allow_2026 = end_date > "2025-12-31"
    liquid_lookup, trad_lookup, price_cache = load_caches()
    for _, row in leaderboard.iterrows():
        strategy_name = str(row["strategy_name"])
        fold_path = canonical_dir / "strategies" / strategy_name / "fold_metrics.csv"
        if not fold_path.exists():
            continue
        fold_df = pd.read_csv(fold_path)
        if fold_df.empty:
            continue

        worst_fold_return = float(fold_df["total_return"].min())
        mean_excess = float(row.get("mean_excess_return", np.nan))
        mean_dd = float(row.get("mean_max_drawdown", np.nan))
        positive_folds = int(row.get("positive_folds", 0))
        beating_folds = int(row.get("beating_benchmark_folds", 0))
        n_folds = int(row.get("n_folds", len(fold_df)))

        checks = evaluate_strategy_row(
            pd.Series(
                {
                    "positive_folds": positive_folds,
                    "beating_benchmark_folds": beating_folds,
                    "mean_excess_return": mean_excess,
                    "mean_max_drawdown": mean_dd,
                    "worst_fold_return": worst_fold_return,
                }
            ),
            policy=policy,
        )
        status, status_warning = derive_execution_status(
            strategy_name=strategy_name,
            checks=checks,
            manual_override=False,
        )

        strategy_cfg, _ = _load_canonical_strategy_config(canonical_dir, strategy_name)
        if strategy_cfg is not None:
            curve = _simulate_curve_for_config(
                config=strategy_cfg,
                start_date=start_date,
                end_date=end_date,
                price_cache=price_cache,
                liquid_lookup=liquid_lookup,
                trad_lookup=trad_lookup,
                allow_2026=allow_2026,
            )
            horizon_rows.extend(
                to_records(
                    strategy_name=strategy_name,
                    stats=compute_horizon_metrics_from_curve(curve),
                )
            )

        rows.append(
            {
                "strategy_name": strategy_name,
                "n_folds": n_folds,
                "mean_annualized_return": float(row.get("mean_annualized_return", np.nan)),
                "mean_excess_return": mean_excess,
                "mean_max_drawdown": mean_dd,
                "positive_folds": positive_folds,
                "beating_benchmark_folds": beating_folds,
                "worst_fold_return": worst_fold_return,
                "gate_positive_folds": bool(checks["gate_positive_folds"]),
                "gate_beating_benchmark": bool(checks["gate_beating_benchmark"]),
                "gate_mean_excess": bool(checks["gate_mean_excess"]),
                "gate_mean_drawdown": bool(checks["gate_mean_drawdown"]),
                "gate_worst_fold": bool(checks["gate_worst_fold"]),
                # backward-compatible alias used by some older notebooks
                "gate_drawdown": bool(checks["gate_mean_drawdown"]),
                "is_profit_ready": bool(checks["all_pass"]),
                "execution_validation_status": status,
                "execution_status_warning": status_warning,
            }
        )

    readiness_df = pd.DataFrame(rows).sort_values(
        ["is_profit_ready", "mean_excess_return", "mean_annualized_return"],
        ascending=[False, False, False],
    )

    horizon_df = pd.DataFrame(horizon_rows)
    if len(horizon_df) > 0:
        horizon_df["window_start"] = start_date
        horizon_df["window_end"] = end_date
        horizon_df["selection_lockbox_max_date"] = "2025-12-31"
        horizon_df["informational_lens_only"] = True
        horizon_df.to_csv(output_dir / "profit_horizon_metrics.csv", index=False)
        horizon_wide = horizon_metrics_to_wide(horizon_df)
        if len(horizon_wide) > 0:
            readiness_df = readiness_df.merge(horizon_wide, on="strategy_name", how="left")

    readiness_df.to_csv(output_dir / "profit_readiness.csv", index=False)
    ready = readiness_df[readiness_df["is_profit_ready"] == True]
    top_ready = ready.iloc[0]["strategy_name"] if len(ready) > 0 else None
    top_candidate = readiness_df.iloc[0]["strategy_name"] if len(readiness_df) > 0 else None
    summary = {
        "thresholds": {
            "min_positive_folds": thresholds.min_positive_folds,
            "min_beating_benchmark_folds": thresholds.min_beating_benchmark_folds,
            "min_mean_excess_return": thresholds.min_mean_excess_return,
            "max_mean_drawdown": thresholds.max_mean_drawdown,
            "max_worst_fold_return": thresholds.max_worst_fold_return,
        },
        "n_strategies": int(len(readiness_df)),
        "n_profit_ready": int(len(ready)),
        "top_profit_ready": top_ready,
        "top_candidate": top_candidate,
        "window_start": start_date,
        "window_end": end_date,
        "informational_horizon_lens_only": True,
    }
    with open(output_dir / "profit_readiness_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return readiness_df, summary


def _write_markdown_report(
    *,
    output_dir: Path,
    readiness_summary: dict | None,
    readiness_df: pd.DataFrame | None,
    autopsy_yearly: pd.DataFrame | None,
    autopsy_cohort: pd.DataFrame | None,
) -> None:
    lines: list[str] = []
    lines.append("# Profit Pipeline Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    if readiness_summary is not None:
        lines.append("## Profit Readiness")
        lines.append(f"- Strategies scanned: {readiness_summary['n_strategies']}")
        lines.append(f"- Profit-ready strategies: {readiness_summary['n_profit_ready']}")
        lines.append(f"- Top profit-ready: {readiness_summary['top_profit_ready']}")
        lines.append(f"- Top candidate: {readiness_summary['top_candidate']}")
        lines.append("- Horizon lens: `W/M/Q/6M` informational diagnostics included")
        lines.append("")

    if readiness_df is not None and len(readiness_df) > 0:
        lines.append("## Non-Annual Lens")
        top = readiness_df.iloc[0]
        for h in ("w", "m", "q", "6m"):
            mr = top.get(f"h_{h}_mean_return", np.nan)
            pr = top.get(f"h_{h}_positive_rate", np.nan)
            wr = top.get(f"h_{h}_worst_return", np.nan)
            npers = top.get(f"h_{h}_n_periods", np.nan)
            if pd.notna(mr):
                lines.append(
                    f"- {h.upper()}: mean={mr:.2%}, positive={pr:.1%}, worst={wr:.2%}, n={int(npers)}"
                )
        lines.append("")

    if autopsy_yearly is not None and len(autopsy_yearly) > 0:
        lines.append("## Autopsy Highlights")
        if autopsy_cohort is not None and set(autopsy_cohort["cohort"]) >= {"failure", "success"}:
            fail = autopsy_cohort[autopsy_cohort["cohort"] == "failure"].iloc[0]
            succ = autopsy_cohort[autopsy_cohort["cohort"] == "success"].iloc[0]
            lines.append(f"- Failure avg excess return: {fail['excess_return']:.2%}")
            lines.append(f"- Success avg excess return: {succ['excess_return']:.2%}")
            lines.append(f"- Failure avg cash: {fail['avg_cash_pct']:.2f}%")
            lines.append(f"- Success avg cash: {succ['avg_cash_pct']:.2f}%")
            lines.append(f"- Failure avg underfill: {fail['avg_underfill_pct']:.2f}%")
            lines.append(f"- Success avg underfill: {succ['avg_underfill_pct']:.2f}%")
        lines.append("")

    lines.append("## Outputs")
    lines.append("- `profit_readiness.csv`")
    lines.append("- `profit_readiness_summary.json`")
    lines.append("- `autopsy_yearly.csv`")
    lines.append("- `autopsy_cohort_summary.csv`")
    lines.append("- `autopsy_failure_minus_success.csv` (if both cohorts present)")
    lines.append("- `profit_horizon_metrics.csv`")
    lines.append("")

    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profit-readiness gating + execution autopsy pipeline"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="blend_70_30_top5",
        help="Strategy used for year-cohort autopsy.",
    )
    parser.add_argument(
        "--failure-years",
        type=str,
        default="2016,2018,2024",
        help="Comma-separated failure years for autopsy cohort.",
    )
    parser.add_argument(
        "--success-years",
        type=str,
        default="2017,2020,2021,2022,2025",
        help="Comma-separated success years for autopsy cohort.",
    )
    parser.add_argument(
        "--canonical-dir",
        type=str,
        default=str(CANONICAL_WFV_DIR),
        help="Canonical walk-forward output root.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Optional explicit output directory.",
    )
    parser.add_argument(
        "--skip-readiness",
        action="store_true",
        help="Skip readiness stage.",
    )
    parser.add_argument(
        "--skip-autopsy",
        action="store_true",
        help="Skip autopsy stage.",
    )
    parser.add_argument(
        "--allow-lockbox",
        action="store_true",
        help="Allow 2026+ data in autopsy signal loading for development runs.",
    )
    parser.add_argument(
        "--emit-paper-handoff",
        action="store_true",
        help="Write primary/fallback paper-trading handoff bundle from readiness outputs.",
    )
    parser.add_argument(
        "--fallback-strategy",
        type=str,
        default="",
        help="Optional explicit fallback strategy name for paper handoff bundle.",
    )
    parser.add_argument("--min-positive-folds", type=int, default=7)
    parser.add_argument("--min-beating-benchmark-folds", type=int, default=5)
    parser.add_argument("--min-mean-excess-return", type=float, default=0.0)
    parser.add_argument("--max-mean-drawdown", type=float, default=0.35)
    parser.add_argument("--max-worst-fold-return", type=float, default=-0.30)
    return parser


def main() -> None:
    parser = create_argument_parser()
    args = parser.parse_args()

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else PROFIT_PIPELINE_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    _ensure_dir(output_dir)

    thresholds = ReadinessThresholds(
        min_positive_folds=int(args.min_positive_folds),
        min_beating_benchmark_folds=int(args.min_beating_benchmark_folds),
        min_mean_excess_return=float(args.min_mean_excess_return),
        max_mean_drawdown=float(args.max_mean_drawdown),
        max_worst_fold_return=float(args.max_worst_fold_return),
    )

    readiness_df: pd.DataFrame | None = None
    readiness_summary: dict | None = None
    if not args.skip_readiness:
        readiness_df, readiness_summary = run_readiness(
            canonical_dir=Path(args.canonical_dir),
            thresholds=thresholds,
            output_dir=output_dir,
        )
        print(f"[readiness] strategies={len(readiness_df)} profit_ready={int(readiness_df['is_profit_ready'].sum())}")

    autopsy_yearly: pd.DataFrame | None = None
    autopsy_cohort: pd.DataFrame | None = None
    if not args.skip_autopsy:
        failure_years = _parse_years(args.failure_years)
        success_years = _parse_years(args.success_years)
        autopsy_yearly, autopsy_cohort = run_autopsy(
            strategy_name=args.strategy,
            failure_years=failure_years,
            success_years=success_years,
            output_dir=output_dir,
            allow_2026=bool(args.allow_lockbox),
        )
        print(
            f"[autopsy] strategy={args.strategy} years={len(autopsy_yearly)} "
            f"failure={len([y for y in failure_years])} success={len([y for y in success_years])}"
        )

    _write_markdown_report(
        output_dir=output_dir,
        readiness_summary=readiness_summary,
        readiness_df=readiness_df,
        autopsy_yearly=autopsy_yearly,
        autopsy_cohort=autopsy_cohort,
    )
    if args.emit_paper_handoff and readiness_df is not None:
        _write_paper_handoff_bundle(
            readiness_df=readiness_df,
            canonical_dir=Path(args.canonical_dir),
            output_dir=output_dir,
            thresholds=thresholds,
            fallback_strategy=str(args.fallback_strategy or "").strip(),
        )
    print(f"[done] artifacts={output_dir}")


if __name__ == "__main__":
    main()
