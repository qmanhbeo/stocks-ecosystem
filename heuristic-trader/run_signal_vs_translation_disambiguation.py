#!/usr/bin/env python3
"""
Disambiguation pass: signal weakness vs strategy translation weakness.

Runs three experiments on top strategies from the latest signal sweep:
1) Oracle execution ablation (remove filters / relax execution frictions)
2) Translation parameter sweep (K/rebalance/hold/depth/sizing)
3) Train-only regime router gate (year-state-conditioned ON/OFF)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import backtest as bt
import constraints as cn
from signal_factory import prepare_signal_df_from_config
from walk_forward_validate import FOLDS, get_benchmark


ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = ROOT / "artifacts"
SWEEPS_DIR = ARTIFACTS_DIR / "signal_sweeps"
OUT_ROOT = ARTIFACTS_DIR / "signal_translation_disambiguation"


@dataclass
class FoldRun:
    strategy_name: str
    variant: str
    fold_name: str
    test_year: int
    total_return: float
    annualized_return: float
    max_drawdown: float
    n_trades: int
    n_filtered: int
    benchmark_return: float
    excess_return: float


def _find_latest_sweep() -> Path:
    runs = sorted([p for p in SWEEPS_DIR.glob("20*") if p.is_dir()], reverse=True)
    if not runs:
        raise FileNotFoundError(f"No sweep runs found under {SWEEPS_DIR}")
    return runs[0]


def _load_top_strategy_configs(sweep_dir: Path, top_n: int) -> list[dict[str, Any]]:
    decisions_path = sweep_dir / "signal_sweep_decisions.csv"
    if not decisions_path.exists():
        raise FileNotFoundError(f"Missing decisions file: {decisions_path}")
    decisions = pd.read_csv(decisions_path)
    decisions = decisions.sort_values(
        ["mean_excess_return", "mean_annualized_return"],
        ascending=[False, False],
    )
    top = decisions.head(top_n).copy()

    configs: list[dict[str, Any]] = []
    for strategy_name in top["strategy_name"]:
        cfg_path = (
            sweep_dir
            / "canonical_wfv"
            / "strategies"
            / str(strategy_name)
            / "config_effective.json"
        )
        if not cfg_path.exists():
            raise FileNotFoundError(f"Missing config: {cfg_path}")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        configs.append(cfg)
    return configs


def _aggregate_rows(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, g in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {k: v for k, v in zip(group_cols, keys)}
        row.update(
            {
                "n_folds": int(len(g)),
                "mean_total_return": float(g["total_return"].mean()),
                "mean_annualized_return": float(g["annualized_return"].mean()),
                "mean_excess_return": float(g["excess_return"].mean()),
                "positive_folds": int((g["total_return"] > 0).sum()),
                "beating_benchmark_folds": int((g["excess_return"] > 0).sum()),
                "worst_fold_return": float(g["total_return"].min()),
                "mean_max_drawdown": float(g["max_drawdown"].abs().mean()),
                "mean_trades": float(g["n_trades"].mean()),
                "mean_filtered": float(g["n_filtered"].mean()),
            }
        )
        rows.append(row)
    out = pd.DataFrame(rows)
    sort_cols = [c for c in ["mean_excess_return", "mean_annualized_return"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, ascending=[False] * len(sort_cols)).reset_index(drop=True)
    return out


def _run_config_fold(
    config: dict[str, Any],
    fold: dict[str, str],
    *,
    liquid_lookup: dict,
    trad_lookup: dict,
    price_cache: dict,
    use_filters: bool,
    top_k: int,
    rebalance_days: int,
    min_hold_days: int,
    candidate_scan_multiplier: int,
    sizing_mode: str,
) -> FoldRun:
    signal_df = prepare_signal_df_from_config(
        config=config,
        start_date=fold["test_start"],
        end_date=fold["test_end"],
        allow_2026=False,
    )
    result = bt.simulate_topk_constraint_compliant(
        signal_df=signal_df,
        cache=price_cache,
        signal_col=config["signal_col"],
        top_k=top_k,
        rebalance_days=rebalance_days,
        min_hold_days=min_hold_days,
        use_filters=use_filters,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        candidate_scan_multiplier=candidate_scan_multiplier,
        sizing_mode=sizing_mode,
        fallback_mode="none",
    )
    bench = get_benchmark(fold["test_start"], fold["test_end"])
    benchmark_return = float(bench["total_return"]) if bench is not None else 0.0
    excess = float(result.total_return) - benchmark_return
    return FoldRun(
        strategy_name=str(config["name"]),
        variant="",
        fold_name=fold["name"],
        test_year=int(fold["test_start"][:4]),
        total_return=float(result.total_return),
        annualized_return=float(result.annualized_return),
        max_drawdown=float(result.max_drawdown),
        n_trades=int(result.n_trades),
        n_filtered=int(result.n_filtered),
        benchmark_return=benchmark_return,
        excess_return=excess,
    )


def _to_frame(runs: list[FoldRun]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strategy_name": r.strategy_name,
                "variant": r.variant,
                "fold_name": r.fold_name,
                "test_year": r.test_year,
                "total_return": r.total_return,
                "annualized_return": r.annualized_return,
                "max_drawdown": r.max_drawdown,
                "n_trades": r.n_trades,
                "n_filtered": r.n_filtered,
                "benchmark_return": r.benchmark_return,
                "excess_return": r.excess_return,
            }
            for r in runs
        ]
    )


def _load_yearly_benchmark_returns() -> dict[int, float]:
    vn = cn.load_vnindex(start="2014-01-01", end="2025-12-31")
    vn["time"] = pd.to_datetime(vn["time"], errors="coerce").dt.normalize()
    vn["year"] = vn["time"].dt.year
    out: dict[int, float] = {}
    for year, g in vn.groupby("year"):
        if len(g) < 2:
            continue
        open_0 = float(g["open"].iloc[0])
        close_n = float(g["close"].iloc[-1])
        if open_0 <= 0:
            continue
        out[int(year)] = (close_n / open_0) - 1.0
    return out


def _state_from_prev_year(year: int, bench_by_year: dict[int, float]) -> str | None:
    prev = year - 1
    if prev not in bench_by_year:
        return None
    return "bull" if bench_by_year[prev] > 0 else "bear"


def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Signal vs translation disambiguation run")
    p.add_argument("--sweep-dir", type=str, default="", help="Optional explicit sweep dir")
    p.add_argument("--top-n", type=int, default=3, help="Top-N strategies from sweep by mean_excess")
    p.add_argument("--max-translation-configs", type=int, default=0, help="Optional per-strategy cap (0=all)")
    p.add_argument("--min-router-train-years", type=int, default=2, help="Minimum state-matched train years")
    p.add_argument("--output-dir", type=str, default="", help="Optional explicit output dir")
    return p


def main() -> None:
    args = create_parser().parse_args()
    sweep_dir = Path(args.sweep_dir) if args.sweep_dir else _find_latest_sweep()
    out_dir = (
        Path(args.output_dir)
        if args.output_dir
        else OUT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[setup] sweep={sweep_dir}")
    print(f"[setup] out={out_dir}")

    configs = _load_top_strategy_configs(sweep_dir, top_n=int(args.top_n))
    strategy_names = [str(c["name"]) for c in configs]
    print(f"[setup] top strategies={strategy_names}")

    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()

    # ------------------------------------------------------------------
    # Experiment 1: Oracle execution ablation
    # ------------------------------------------------------------------
    print("[exp1] oracle execution ablation")
    exp1_runs: list[FoldRun] = []
    exp1_variants = [
        ("canonical", True, "fixed_initial", None),
        ("oracle_no_filters_fixed", False, "fixed_initial", None),
        ("oracle_no_filters_dynamic", False, "dynamic_portfolio", None),
    ]
    for cfg in configs:
        for variant, use_filters, sizing_mode, scan_override in exp1_variants:
            scan = int(scan_override) if scan_override is not None else int(cfg.get("candidate_scan_multiplier", 3))
            for fold in FOLDS:
                fr = _run_config_fold(
                    cfg,
                    fold,
                    liquid_lookup=liquid_lookup,
                    trad_lookup=trad_lookup,
                    price_cache=price_cache,
                    use_filters=use_filters,
                    top_k=int(cfg["top_k"]),
                    rebalance_days=int(cfg["rebalance_days"]),
                    min_hold_days=int(cfg["min_hold_days"]),
                    candidate_scan_multiplier=scan,
                    sizing_mode=sizing_mode,
                )
                fr.variant = variant
                exp1_runs.append(fr)
            print(f"  done {cfg['name']} :: {variant}")

    exp1_fold_df = _to_frame(exp1_runs)
    exp1_fold_df.to_csv(out_dir / "exp1_oracle_fold_metrics.csv", index=False)
    exp1_summary_df = _aggregate_rows(exp1_fold_df, ["strategy_name", "variant"])
    exp1_summary_df.to_csv(out_dir / "exp1_oracle_summary.csv", index=False)

    # ------------------------------------------------------------------
    # Experiment 2: Translation sweep
    # ------------------------------------------------------------------
    print("[exp2] translation sweep")
    k_grid = [3, 5, 7]
    rebal_grid = [5, 10]
    hold_grid = [2, 3, 5]
    scan_grid = [3, 5, 10, 20]
    sizing_grid = ["fixed_initial", "dynamic_portfolio"]

    exp2_rows: list[dict[str, Any]] = []
    exp2_fold_rows: list[dict[str, Any]] = []
    for cfg in configs:
        combos: list[tuple[int, int, int, int, str]] = []
        for k in k_grid:
            for rb in rebal_grid:
                for mh in hold_grid:
                    for sc in scan_grid:
                        for sm in sizing_grid:
                            combos.append((k, rb, mh, sc, sm))
        if int(args.max_translation_configs) > 0:
            combos = combos[: int(args.max_translation_configs)]
        print(f"  strategy={cfg['name']} combos={len(combos)}")

        for i, (k, rb, mh, sc, sm) in enumerate(combos, start=1):
            variant = f"k{k}_rb{rb}_h{mh}_scan{sc}_{sm}"
            fold_runs: list[FoldRun] = []
            for fold in FOLDS:
                fr = _run_config_fold(
                    cfg,
                    fold,
                    liquid_lookup=liquid_lookup,
                    trad_lookup=trad_lookup,
                    price_cache=price_cache,
                    use_filters=True,
                    top_k=k,
                    rebalance_days=rb,
                    min_hold_days=mh,
                    candidate_scan_multiplier=sc,
                    sizing_mode=sm,
                )
                fr.variant = variant
                fold_runs.append(fr)
                exp2_fold_rows.append(
                    {
                        "strategy_name": fr.strategy_name,
                        "variant": fr.variant,
                        "fold_name": fr.fold_name,
                        "test_year": fr.test_year,
                        "total_return": fr.total_return,
                        "annualized_return": fr.annualized_return,
                        "max_drawdown": fr.max_drawdown,
                        "n_trades": fr.n_trades,
                        "n_filtered": fr.n_filtered,
                        "benchmark_return": fr.benchmark_return,
                        "excess_return": fr.excess_return,
                    }
                )
            fd = _to_frame(fold_runs)
            summary = _aggregate_rows(fd, ["strategy_name", "variant"]).iloc[0].to_dict()
            summary.update(
                {
                    "top_k": k,
                    "rebalance_days": rb,
                    "min_hold_days": mh,
                    "candidate_scan_multiplier": sc,
                    "sizing_mode": sm,
                }
            )
            exp2_rows.append(summary)
            if i % 24 == 0 or i == len(combos):
                print(f"    {cfg['name']}: {i}/{len(combos)}")

    exp2_summary_df = pd.DataFrame(exp2_rows)
    exp2_summary_df = exp2_summary_df.sort_values(
        ["strategy_name", "mean_excess_return", "mean_annualized_return"],
        ascending=[True, False, False],
    ).reset_index(drop=True)
    exp2_summary_df.to_csv(out_dir / "exp2_translation_summary.csv", index=False)
    pd.DataFrame(exp2_fold_rows).to_csv(out_dir / "exp2_translation_fold_metrics.csv", index=False)

    exp2_best_df = (
        exp2_summary_df.sort_values(
            ["strategy_name", "mean_excess_return", "mean_annualized_return"],
            ascending=[True, False, False],
        )
        .groupby("strategy_name", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    exp2_best_df.to_csv(out_dir / "exp2_translation_best_per_strategy.csv", index=False)

    # ------------------------------------------------------------------
    # Experiment 3: Train-only regime router
    # ------------------------------------------------------------------
    print("[exp3] train-only regime router")
    bench_by_year = _load_yearly_benchmark_returns()

    canonical_df = exp1_fold_df[exp1_fold_df["variant"] == "canonical"].copy()
    canonical_year_map: dict[str, dict[int, dict[str, float]]] = {}
    for strategy_name, g in canonical_df.groupby("strategy_name"):
        canonical_year_map[strategy_name] = {}
        for _, row in g.iterrows():
            canonical_year_map[strategy_name][int(row["test_year"])] = {
                "total_return": float(row["total_return"]),
                "excess_return": float(row["excess_return"]),
                "benchmark_return": float(row["benchmark_return"]),
                "max_drawdown": float(row["max_drawdown"]),
                "n_trades": float(row["n_trades"]),
                "n_filtered": float(row["n_filtered"]),
            }

    router_rows: list[dict[str, Any]] = []
    for cfg in configs:
        strategy_name = str(cfg["name"])
        for fold in FOLDS:
            year = int(fold["test_start"][:4])
            state = _state_from_prev_year(year, bench_by_year)
            if state is None:
                continue

            train_years = [int(f["test_start"][:4]) for f in FOLDS if int(f["test_start"][:4]) < year]
            state_train_excess: list[float] = []
            for ty in train_years:
                s_ty = _state_from_prev_year(ty, bench_by_year)
                if s_ty != state:
                    continue
                m = canonical_year_map.get(strategy_name, {}).get(ty)
                if m is None:
                    continue
                state_train_excess.append(float(m["excess_return"]))

            state_mean_excess = float(np.mean(state_train_excess)) if state_train_excess else float("nan")
            router_on = len(state_train_excess) >= int(args.min_router_train_years) and state_mean_excess > 0.0

            year_metrics = canonical_year_map[strategy_name][year]
            benchmark_return = float(year_metrics["benchmark_return"])
            if router_on:
                router_total_return = float(year_metrics["total_return"])
                router_excess = float(year_metrics["excess_return"])
                router_trades = float(year_metrics["n_trades"])
            else:
                router_total_return = 0.0
                router_excess = -benchmark_return
                router_trades = 0.0

            router_rows.append(
                {
                    "strategy_name": strategy_name,
                    "fold_name": fold["name"],
                    "test_year": year,
                    "state": state,
                    "state_train_count": len(state_train_excess),
                    "state_train_mean_excess": state_mean_excess,
                    "router_on": bool(router_on),
                    "canonical_total_return": float(year_metrics["total_return"]),
                    "canonical_excess_return": float(year_metrics["excess_return"]),
                    "router_total_return": router_total_return,
                    "router_excess_return": router_excess,
                    "benchmark_return": benchmark_return,
                    "router_minus_canonical_excess": router_excess - float(year_metrics["excess_return"]),
                    "canonical_n_trades": float(year_metrics["n_trades"]),
                    "router_n_trades": router_trades,
                }
            )

    exp3_fold_df = pd.DataFrame(router_rows)
    exp3_fold_df.to_csv(out_dir / "exp3_router_fold_metrics.csv", index=False)

    exp3_summary_rows: list[dict[str, Any]] = []
    for strategy_name, g in exp3_fold_df.groupby("strategy_name"):
        exp3_summary_rows.append(
            {
                "strategy_name": strategy_name,
                "n_folds": int(len(g)),
                "router_on_folds": int(g["router_on"].sum()),
                "canonical_mean_excess": float(g["canonical_excess_return"].mean()),
                "router_mean_excess": float(g["router_excess_return"].mean()),
                "router_minus_canonical_mean_excess": float(
                    g["router_excess_return"].mean() - g["canonical_excess_return"].mean()
                ),
                "canonical_positive_excess_folds": int((g["canonical_excess_return"] > 0).sum()),
                "router_positive_excess_folds": int((g["router_excess_return"] > 0).sum()),
            }
        )
    exp3_summary_df = pd.DataFrame(exp3_summary_rows).sort_values(
        "router_minus_canonical_mean_excess", ascending=False
    )
    exp3_summary_df.to_csv(out_dir / "exp3_router_summary.csv", index=False)

    # ------------------------------------------------------------------
    # Meta summary + README
    # ------------------------------------------------------------------
    oracle_best = (
        exp1_summary_df.sort_values(
            ["strategy_name", "mean_excess_return", "mean_annualized_return"],
            ascending=[True, False, False],
        )
        .groupby("strategy_name", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )

    master = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_sweep_dir": str(sweep_dir),
        "strategies_tested": strategy_names,
        "experiment_1": {
            "oracle_summary_file": "exp1_oracle_summary.csv",
            "best_variant_per_strategy": oracle_best.to_dict(orient="records"),
        },
        "experiment_2": {
            "translation_summary_file": "exp2_translation_summary.csv",
            "best_translation_per_strategy": exp2_best_df.to_dict(orient="records"),
        },
        "experiment_3": {
            "router_summary_file": "exp3_router_summary.csv",
            "router_summary": exp3_summary_df.to_dict(orient="records"),
        },
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2)

    lines = [
        "# Signal vs Translation Disambiguation",
        "",
        f"- Generated: {master['generated_at']}",
        f"- Source sweep: `{master['source_sweep_dir']}`",
        f"- Strategies tested: `{', '.join(strategy_names)}`",
        "",
        "## Experiment 1: Oracle Execution Ablation",
        "- Files: `exp1_oracle_fold_metrics.csv`, `exp1_oracle_summary.csv`",
        "- Question: if filters/execution friction are removed, does benchmark-relative edge turn positive?",
        "",
        "## Experiment 2: Translation Sweep",
        "- Files: `exp2_translation_fold_metrics.csv`, `exp2_translation_summary.csv`, `exp2_translation_best_per_strategy.csv`",
        "- Question: can parameterization of the same signal family convert to stable positive excess?",
        "",
        "## Experiment 3: Train-Only Regime Router",
        "- Files: `exp3_router_fold_metrics.csv`, `exp3_router_summary.csv`",
        "- Router state: prior-year VNINDEX sign (bull/bear), trained only on earlier folds",
        "- Question: does simple ex-ante regime gating improve mean excess vs always-on canonical?",
        "",
        "## Programmatic Summary",
        "- See `summary.json`.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[done] out={out_dir}")


if __name__ == "__main__":
    main()
