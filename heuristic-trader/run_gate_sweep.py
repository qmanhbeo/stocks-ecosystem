#!/usr/bin/env python3
"""
Sweep tail-first gate parameters over candidate strategies.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import backtest as bt
from risk_policy import DEFAULT_RISK_POLICY, evaluate_strategy_row, policy_dict
from signal_factory import prepare_signal_df_from_config
from walk_forward_validate import FOLDS, get_benchmark


ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = ROOT / "artifacts"
OUT_ROOT = ARTIFACTS_DIR / "gate_sweeps"
SWEEP_DIR = ARTIFACTS_DIR / "signal_sweeps"
DEFAULT_SWEEP_RUN = SWEEP_DIR / "20260519_211758"


@dataclass
class GateVariant:
    name: str
    gate_enabled: bool
    gate_profile: str
    exposure_floor: float
    exposure_ceiling: float
    cooldown_rebalances: int
    kill_switch_thresholds: dict[str, float] | None


def _parse_strategy_list(value: str) -> list[str]:
    out = [v.strip() for v in value.split(",") if v.strip()]
    if not out:
        raise ValueError("strategy list cannot be empty")
    return out


def _load_configs_from_sweep(sweep_dir: Path, strategies: list[str]) -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for strategy_name in strategies:
        path = sweep_dir / "canonical_wfv" / "strategies" / strategy_name / "config_effective.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing strategy config: {path}")
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        configs.append(cfg)
    return configs


def _build_variants() -> list[GateVariant]:
    return [
        GateVariant("off", False, "off", 0.20, 1.00, 2, None),
        GateVariant("tail_soft_f20_cd2", True, "tail_first_v1", 0.20, 1.00, 2, {"drawdown": 0.33, "volatility": 0.65, "underfill_ratio": 0.85, "reject_ratio": 0.93}),
        GateVariant("tail_med_f20_cd2", True, "tail_first_v1", 0.20, 1.00, 2, {"drawdown": 0.30, "volatility": 0.60, "underfill_ratio": 0.80, "reject_ratio": 0.90}),
        GateVariant("tail_hard_f20_cd2", True, "tail_first_v1", 0.20, 1.00, 2, {"drawdown": 0.27, "volatility": 0.55, "underfill_ratio": 0.75, "reject_ratio": 0.88}),
        GateVariant("tail_med_f10_cd2", True, "tail_first_v1", 0.10, 1.00, 2, {"drawdown": 0.30, "volatility": 0.60, "underfill_ratio": 0.80, "reject_ratio": 0.90}),
        GateVariant("tail_med_f30_cd2", True, "tail_first_v1", 0.30, 1.00, 2, {"drawdown": 0.30, "volatility": 0.60, "underfill_ratio": 0.80, "reject_ratio": 0.90}),
        GateVariant("tail_med_f20_cd1", True, "tail_first_v1", 0.20, 1.00, 1, {"drawdown": 0.30, "volatility": 0.60, "underfill_ratio": 0.80, "reject_ratio": 0.90}),
        GateVariant("tail_med_f20_cd3", True, "tail_first_v1", 0.20, 1.00, 3, {"drawdown": 0.30, "volatility": 0.60, "underfill_ratio": 0.80, "reject_ratio": 0.90}),
    ]


def _compute_summary(df: pd.DataFrame) -> dict[str, float | int]:
    total_returns = df["total_return"]
    ann_returns = df["annualized_return"]
    mdd = df["max_drawdown"].abs()
    excess = df["excess_return"]
    return {
        "n_folds": int(len(df)),
        "mean_total_return": float(total_returns.mean()),
        "mean_annualized_return": float(ann_returns.mean()),
        "mean_excess_return": float(excess.mean()),
        "mean_max_drawdown": float(mdd.mean()),
        "worst_fold_return": float(total_returns.min()),
        "positive_folds": int((total_returns > 0).sum()),
        "beating_benchmark_folds": int((excess > 0).sum()),
        "mean_trades": float(df["n_trades"].mean()),
        "mean_filtered": float(df["n_filtered"].mean()),
    }


def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sweep risk-gate configs over candidate strategies")
    p.add_argument(
        "--strategies",
        type=str,
        default="s1b_c11_ret_60d_lag_rank_70_30_depth5,m_c11_ret_60d_lag_rank_depth5,m_c8_vol_zscore_5d_depth5,ctrl_blend_70_30_depth5",
        help="Comma-separated strategy names",
    )
    p.add_argument("--sweep-dir", type=str, default=str(DEFAULT_SWEEP_RUN))
    p.add_argument(
        "--translation-best-csv",
        type=str,
        default="",
        help="Optional exp2_translation_best_per_strategy.csv to override top_k/rebalance/min_hold/scan/sizing per strategy",
    )
    p.add_argument("--output-dir", type=str, default="")
    return p


def main() -> None:
    args = create_parser().parse_args()
    strategies = _parse_strategy_list(args.strategies)
    sweep_dir = Path(args.sweep_dir)
    out_dir = Path(args.output_dir) if args.output_dir else OUT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[setup] sweep={sweep_dir}")
    print(f"[setup] out={out_dir}")
    print(f"[setup] strategies={strategies}")

    configs = _load_configs_from_sweep(sweep_dir, strategies)
    if args.translation_best_csv:
        tbest = pd.read_csv(args.translation_best_csv)
        by_name = {str(r["strategy_name"]): r for _, r in tbest.iterrows()}
        for cfg in configs:
            name = str(cfg["name"])
            if name not in by_name:
                continue
            r = by_name[name]
            cfg["top_k"] = int(r["top_k"])
            cfg["rebalance_days"] = int(r["rebalance_days"])
            cfg["min_hold_days"] = int(r["min_hold_days"])
            cfg["candidate_scan_multiplier"] = int(r["candidate_scan_multiplier"])
            cfg["sizing_mode"] = str(r["sizing_mode"])
            print(
                "[translation-override] "
                f"{name}: k={cfg['top_k']} rb={cfg['rebalance_days']} h={cfg['min_hold_days']} "
                f"scan={cfg['candidate_scan_multiplier']} sizing={cfg['sizing_mode']}"
            )
    variants = _build_variants()

    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()

    fold_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    total_runs = len(configs) * len(variants) * len(FOLDS)
    run_idx = 0
    for cfg in configs:
        for variant in variants:
            rows_for_summary: list[dict[str, Any]] = []
            for fold in FOLDS:
                run_idx += 1
                signal_df = prepare_signal_df_from_config(
                    config=cfg,
                    start_date=fold["test_start"],
                    end_date=fold["test_end"],
                    allow_2026=False,
                )
                result = bt.simulate_topk_constraint_compliant(
                    signal_df=signal_df,
                    cache=price_cache,
                    signal_col=str(cfg["signal_col"]),
                    top_k=int(cfg["top_k"]),
                    rebalance_days=int(cfg["rebalance_days"]),
                    min_hold_days=int(cfg["min_hold_days"]),
                    use_filters=True,
                    liquid_lookup=liquid_lookup,
                    trad_lookup=trad_lookup,
                    candidate_scan_multiplier=int(cfg.get("candidate_scan_multiplier", 3)),
                    sizing_mode=str(cfg.get("sizing_mode", "fixed_initial")),
                    fallback_mode=str(cfg.get("fallback_mode", "none")),
                    gate_enabled=variant.gate_enabled,
                    gate_profile=variant.gate_profile,
                    exposure_floor=variant.exposure_floor,
                    exposure_ceiling=variant.exposure_ceiling,
                    kill_switch_thresholds=variant.kill_switch_thresholds,
                    cooldown_rebalances=variant.cooldown_rebalances,
                )
                bench = get_benchmark(fold["test_start"], fold["test_end"])
                benchmark_return = float(bench["total_return"]) if bench is not None else 0.0
                excess = float(result.total_return) - benchmark_return

                row = {
                    "strategy_name": str(cfg["name"]),
                    "variant_name": variant.name,
                    "fold_name": fold["name"],
                    "test_year": int(fold["test_start"][:4]),
                    "total_return": float(result.total_return),
                    "annualized_return": float(result.annualized_return),
                    "max_drawdown": float(result.max_drawdown),
                    "n_trades": int(result.n_trades),
                    "n_filtered": int(result.n_filtered),
                    "benchmark_return": benchmark_return,
                    "excess_return": excess,
                }
                fold_rows.append(row)
                rows_for_summary.append(row)
                if run_idx % 40 == 0 or run_idx == total_runs:
                    print(f"  progress {run_idx}/{total_runs}")

            s = _compute_summary(pd.DataFrame(rows_for_summary))
            s.update(
                {
                    "strategy_name": str(cfg["name"]),
                    "variant_name": variant.name,
                    "gate_enabled": variant.gate_enabled,
                    "gate_profile": variant.gate_profile,
                    "exposure_floor": variant.exposure_floor,
                    "exposure_ceiling": variant.exposure_ceiling,
                    "cooldown_rebalances": variant.cooldown_rebalances,
                    "kill_switch_thresholds": json.dumps(variant.kill_switch_thresholds or {}, sort_keys=True),
                }
            )
            gates = evaluate_strategy_row(pd.Series(s), policy=DEFAULT_RISK_POLICY)
            s.update(gates)
            summary_rows.append(s)

    fold_df = pd.DataFrame(fold_rows)
    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values(
        ["all_pass", "mean_excess_return", "worst_fold_return", "mean_max_drawdown"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    fold_df.to_csv(out_dir / "gate_sweep_fold_metrics.csv", index=False)
    summary_df.to_csv(out_dir / "gate_sweep_summary.csv", index=False)
    best_df = summary_df.groupby("strategy_name", as_index=False).head(1).reset_index(drop=True)
    best_df.to_csv(out_dir / "gate_sweep_best_per_strategy.csv", index=False)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sweep_source_dir": str(sweep_dir),
        "risk_policy": policy_dict(DEFAULT_RISK_POLICY),
        "strategies": strategies,
        "variants": [v.__dict__ for v in variants],
        "profit_ready_count": int(summary_df["all_pass"].sum()) if "all_pass" in summary_df.columns else 0,
        "best_rows": best_df.to_dict(orient="records"),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    lines = [
        "# Gate Sweep",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Sweep source: `{payload['sweep_source_dir']}`",
        f"- Strategies: `{', '.join(strategies)}`",
        f"- Variants tested: `{len(variants)}`",
        f"- Profit-ready rows: `{payload['profit_ready_count']}`",
        "",
        "## Files",
        "- `gate_sweep_fold_metrics.csv`",
        "- `gate_sweep_summary.csv`",
        "- `gate_sweep_best_per_strategy.csv`",
        "- `summary.json`",
    ]
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[done] out={out_dir}")


if __name__ == "__main__":
    main()
