#!/usr/bin/env python3
"""
Run baseline vs challenger in frozen shadow mode (no retuning).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import backtest as bt
from profit_pipeline import _benchmark_total_return, _compute_curve_metrics
from run_backtest import load_caches
from signal_factory import prepare_signal_df_from_config


ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = ROOT / "artifacts"
CHALLENGE_DIR = ARTIFACTS_DIR / "challenge_sets"
SHADOW_DIR = ARTIFACTS_DIR / "shadow_phase"


def _find_latest_challenge_set() -> Path:
    runs = sorted([p for p in CHALLENGE_DIR.glob("20*") if p.is_dir()], reverse=True)
    if not runs:
        raise FileNotFoundError(f"No challenge sets found under {CHALLENGE_DIR}")
    return runs[0]


def _load_strategy_config_from_sweep(sweep_dir: Path, strategy_name: str) -> dict:
    cfg_path = sweep_dir / "canonical_wfv" / "strategies" / strategy_name / "config_effective.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing strategy config: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_one(
    *,
    strategy_name: str,
    config: dict,
    start_date: str,
    end_date: str,
    liquid_lookup: dict,
    trad_lookup: dict,
    price_cache: dict,
) -> dict:
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
        collect_diagnostics=False,
        candidate_scan_multiplier=int(config.get("candidate_scan_multiplier", 3)),
        sizing_mode=str(config.get("sizing_mode", "fixed_initial")),
        fallback_mode=str(config.get("fallback_mode", "none")),
    )
    benchmark_return = _benchmark_total_return(start_date, end_date)
    excess = (
        float(result.total_return - benchmark_return)
        if benchmark_return is not None
        else float("nan")
    )
    curve_metrics = _compute_curve_metrics(result.curve, top_k=int(config["top_k"]))
    return {
        "strategy_name": strategy_name,
        "start_date": start_date,
        "end_date": end_date,
        "total_return": float(result.total_return),
        "annualized_return": float(result.annualized_return),
        "max_drawdown": float(result.max_drawdown),
        "n_trades": int(result.n_trades),
        "n_filtered": int(result.n_filtered),
        "benchmark_return": float(benchmark_return) if benchmark_return is not None else float("nan"),
        "excess_return": excess,
        **curve_metrics,
    }


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run frozen baseline/challenger shadow phase.")
    parser.add_argument("--challenge-dir", type=str, default="", help="Optional explicit challenge-set directory.")
    parser.add_argument("--start-date", type=str, default="2025-01-01")
    parser.add_argument("--end-date", type=str, default="2025-12-31")
    parser.add_argument("--output-dir", type=str, default="", help="Optional explicit output directory.")
    return parser


def main() -> None:
    args = create_argument_parser().parse_args()
    challenge_dir = Path(args.challenge_dir) if args.challenge_dir else _find_latest_challenge_set()
    with open(challenge_dir / "challenge_set.json", "r", encoding="utf-8") as f:
        challenge = json.load(f)

    if challenge.get("ready_for_shadow", True) is False:
        raise RuntimeError(
            "Challenge set is not ready_for_shadow=false; strict challenger was not selected. "
            "Run select_challenge_set.py with a compatible selection mode first."
        )

    source_sweep = Path(challenge["source_sweep_dir"])
    baseline_name = challenge["baseline_strategy"]
    challenger_name = challenge.get("challenger_strategy")
    if not challenger_name:
        raise RuntimeError("Challenge set has no challenger_strategy")

    baseline_cfg = _load_strategy_config_from_sweep(source_sweep, baseline_name)
    challenger_cfg = _load_strategy_config_from_sweep(source_sweep, challenger_name)

    liquid_lookup, trad_lookup, price_cache = load_caches()
    baseline_row = _run_one(
        strategy_name=baseline_name,
        config=baseline_cfg,
        start_date=args.start_date,
        end_date=args.end_date,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        price_cache=price_cache,
    )
    challenger_row = _run_one(
        strategy_name=challenger_name,
        config=challenger_cfg,
        start_date=args.start_date,
        end_date=args.end_date,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        price_cache=price_cache,
    )

    out_dir = Path(args.output_dir) if args.output_dir else SHADOW_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    result_df = pd.DataFrame([baseline_row, challenger_row])
    result_df.to_csv(out_dir / "shadow_results.csv", index=False)

    winner = result_df.sort_values("excess_return", ascending=False).iloc[0]["strategy_name"]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "challenge_dir": str(challenge_dir),
        "window": {"start_date": args.start_date, "end_date": args.end_date},
        "winner_by_excess_return": winner,
    }
    with open(out_dir / "shadow_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[done] shadow_phase={out_dir}")


if __name__ == "__main__":
    main()
