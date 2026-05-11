#!/usr/bin/env python3
"""
Regime decomposition analysis for heuristic-trader strategies.

Goal: Explain why current strategies fail in bull regimes (2017, 2025)
while performing better in years like 2021 and 2022.

Uses existing fold_metrics.csv from walk-forward validation.

Usage:
    python analyze_regime_failures.py
    python analyze_regime_failures.py --walk-forward-dir artifacts/walk_forward/20260511_164519
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ARTIFACTS_DIR = Path("artifacts")
REGIME_ARTIFACTS_DIR = ARTIFACTS_DIR / "regime_decomposition"

FOCUS_YEARS = [2017, 2021, 2022, 2025]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_strategies_list() -> list[str]:
    """Load all strategies from strategies.json."""
    from strategies.loader import load_strategies
    return list(load_strategies().keys())


def find_full_walk_forward_artifact() -> tuple[Path | None, str]:
    """Find the latest walk-forward artifact with all strategies (66 rows)."""
    wf_dirs = sorted(ARTIFACTS_DIR.glob("walk_forward/2026*"), reverse=True)
    
    for wf_dir in wf_dirs:
        fold_csv = wf_dir / "fold_metrics.csv"
        if not fold_csv.exists():
            continue
        df = pd.read_csv(fold_csv)
        n_rows = len(df)
        
        if n_rows == 66:
            return wf_dir, f"Found full artifact with {n_rows} rows"
    
    if wf_dirs:
        return wf_dirs[0], f"No full (66-row) artifact found, using latest: {wf_dirs[0].name}"
    return None, "No walk-forward artifacts found"


def load_fold_metrics(wf_dir: Path | None = None) -> pd.DataFrame:
    """Load fold metrics from specified or auto-detected walk-forward run."""
    if wf_dir is not None:
        fold_csv = wf_dir / "fold_metrics.csv"
        if not fold_csv.exists():
            raise FileNotFoundError(f"fold_metrics.csv not found in {wf_dir}")
        return pd.read_csv(fold_csv), wf_dir.name
    
    wf_path, note = find_full_walk_forward_artifact()
    if wf_path is None:
        raise FileNotFoundError(note)
    
    fold_csv = wf_path / "fold_metrics.csv"
    df = pd.read_csv(fold_csv)
    return df, wf_path.name


def main() -> None:
    parser = argparse.ArgumentParser(description="Regime decomposition analysis")
    parser.add_argument(
        "--walk-forward-dir",
        type=str,
        default=None,
        help="Path to walk-forward artifact directory",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("REGIME DECOMPOSITION ANALYSIS")
    print("=" * 80)

    wf_dir = Path(args.walk_forward_dir) if args.walk_forward_dir else None
    fold_metrics, wf_name = load_fold_metrics(wf_dir)
    
    print(f"\nUsing walk-forward artifact: {wf_name}")
    print(f"Loaded fold metrics: {len(fold_metrics)} rows")
    
    strategies = load_strategies_list()
    print(f"Available strategies: {strategies}")
    
    n_strategies = len(strategies)
    n_folds = len(fold_metrics) // n_strategies
    expected_rows = n_strategies * n_folds
    
    print(f"Expected rows: {n_strategies} strategies × {n_folds} folds = {expected_rows}")
    
    if len(fold_metrics) != expected_rows:
        print(f"WARNING: Expected {expected_rows} rows but got {len(fold_metrics)}")
        if len(fold_metrics) < expected_rows:
            print(f"  -> This appears to be a SINGLE-STRATEGY debug run")
            print(f"  -> Results may not be representative of all strategies")
    
    all_results = []
    for strategy in strategies:
        strategy_data = fold_metrics[fold_metrics["strategy_name"] == strategy]
        if len(strategy_data) == 0:
            print(f"  WARNING: {strategy} not found in fold metrics")
            continue

        for _, row in strategy_data.iterrows():
            year = int(row["fold_name"].replace("fold_", ""))
            result = {
                "strategy": strategy,
                "year": year,
                "total_return": row["total_return"],
                "annualized_return": row["annualized_return"],
                "sharpe": row["sharpe"],
                "max_drawdown": row["max_drawdown"],
                "n_trades": row["n_trades"],
                "n_filtered": row["n_filtered"],
                "benchmark_return": row["benchmark_return"],
                "excess_return": row["excess_return_vs_benchmark"],
            }
            all_results.append(result)

    year_strategy_df = pd.DataFrame(all_results)
    year_strategy_df = year_strategy_df.sort_values(["strategy", "year"])
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = REGIME_ARTIFACTS_DIR / timestamp
    ensure_dir(output_dir)
    
    year_strategy_df.to_csv(output_dir / "year_strategy_metrics.csv", index=False)
    print(f"\nSaved year_strategy_metrics.csv: {len(year_strategy_df)} rows")

    focus_df = year_strategy_df[year_strategy_df["year"].isin(FOCUS_YEARS)]
    
    diagnostics = []
    for strategy in strategies:
        strategy_focus = focus_df[focus_df["strategy"] == strategy]
        if len(strategy_focus) == 0:
            continue

        for _, row in strategy_focus.iterrows():
            year = row["year"]
            regime = "FAILURE_BULL" if year in [2017, 2025] else "SUCCESS"

            diagnostics.append({
                "strategy": strategy,
                "year": year,
                "regime": regime,
                "strategy_return": round(row["total_return"] * 100, 2),
                "benchmark_return": round(row["benchmark_return"] * 100, 2),
                "excess_return": round(row["excess_return"] * 100, 2),
                "max_drawdown": round(row["max_drawdown"] * 100, 2),
                "sharpe": round(row["sharpe"], 2),
                "n_trades": int(row["n_trades"]),
                "n_filtered": int(row["n_filtered"]),
            })

    focus_diag_df = pd.DataFrame(diagnostics)
    focus_diag_df.to_csv(output_dir / "focus_year_diagnostics.csv", index=False)
    print(f"Saved focus_year_diagnostics.csv: {len(focus_diag_df)} rows")

    strategy_summary = []
    for strategy in strategies:
        strat_df = year_strategy_df[year_strategy_df["strategy"] == strategy]
        
        failure_years = strat_df[strat_df["year"].isin([2017, 2025])]
        success_years = strat_df[strat_df["year"].isin([2021, 2022])]
        
        avg_failure_excess = failure_years["excess_return"].mean() if len(failure_years) > 0 else None
        avg_success_excess = success_years["excess_return"].mean() if len(success_years) > 0 else None
        
        pos_folds = len(strat_df[strat_df["excess_return"] > 0])
        total_folds = len(strat_df)
        
        strategy_summary.append({
            "strategy": strategy,
            "avg_excess_failure_years": round(avg_failure_excess * 100, 2) if avg_failure_excess else None,
            "avg_excess_success_years": round(avg_success_excess * 100, 2) if avg_success_excess else None,
            "positive_folds": f"{pos_folds}/{total_folds}",
            "behavior": "REGIME-SENSITIVE" if (avg_failure_excess < -0.2 and avg_success_excess > 0.1) else "MIXED",
        })

    strategy_summary_df = pd.DataFrame(strategy_summary)
    strategy_summary_df.to_csv(output_dir / "strategy_regime_summary.csv", index=False)
    print(f"Saved strategy_regime_summary.csv: {len(strategy_summary_df)} rows")

    analysis_summary = {
        "walk_forward_artifact": wf_name,
        "n_rows_in_artifact": len(fold_metrics),
        "n_strategies_analyzed": len(strategies),
        "n_folds": n_folds,
        "all_strategies_analyzed": len(fold_metrics) >= 66,
        "focus_years": FOCUS_YEARS,
        "strategies": strategies,
    }

    reg_2017_all = year_strategy_df[(year_strategy_df["year"] == 2017)].sort_values("excess_return", ascending=False)
    reg_2025_all = year_strategy_df[(year_strategy_df["year"] == 2025)].sort_values("excess_return", ascending=False)
    succ_2021_all = year_strategy_df[(year_strategy_df["year"] == 2021)].sort_values("excess_return", ascending=False)
    succ_2022_all = year_strategy_df[(year_strategy_df["year"] == 2022)].sort_values("excess_return", ascending=False)

    analysis_summary["focus_year_comparisons"] = {
        "2017": {
            "best_strategy": reg_2017_all.iloc[0]["strategy"] if len(reg_2017_all) > 0 else None,
            "best_excess": float(reg_2017_all.iloc[0]["excess_return"]) if len(reg_2017_all) > 0 else None,
            "worst_strategy": reg_2017_all.iloc[-1]["strategy"] if len(reg_2017_all) > 0 else None,
            "worst_excess": float(reg_2017_all.iloc[-1]["excess_return"]) if len(reg_2017_all) > 0 else None,
        },
        "2025": {
            "best_strategy": reg_2025_all.iloc[0]["strategy"] if len(reg_2025_all) > 0 else None,
            "best_excess": float(reg_2025_all.iloc[0]["excess_return"]) if len(reg_2025_all) > 0 else None,
            "worst_strategy": reg_2025_all.iloc[-1]["strategy"] if len(reg_2025_all) > 0 else None,
            "worst_excess": float(reg_2025_all.iloc[-1]["excess_return"]) if len(reg_2025_all) > 0 else None,
        },
        "2021": {
            "best_strategy": succ_2021_all.iloc[0]["strategy"] if len(succ_2021_all) > 0 else None,
            "best_excess": float(succ_2021_all.iloc[0]["excess_return"]) if len(succ_2021_all) > 0 else None,
            "worst_strategy": succ_2021_all.iloc[-1]["strategy"] if len(succ_2021_all) > 0 else None,
            "worst_excess": float(succ_2021_all.iloc[-1]["excess_return"]) if len(succ_2021_all) > 0 else None,
        },
        "2022": {
            "best_strategy": succ_2022_all.iloc[0]["strategy"] if len(succ_2022_all) > 0 else None,
            "best_excess": float(succ_2022_all.iloc[0]["excess_return"]) if len(succ_2022_all) > 0 else None,
            "worst_strategy": succ_2022_all.iloc[-1]["strategy"] if len(succ_2022_all) > 0 else None,
            "worst_excess": float(succ_2022_all.iloc[-1]["excess_return"]) if len(succ_2022_all) > 0 else None,
        },
    }

    with open(output_dir / "summary.json", "w") as f:
        json.dump(analysis_summary, f, indent=2)
    print("Saved summary.json")

    print("\n" + "=" * 80)
    print("STRATEGY REGIME SUMMARY")
    print("=" * 80)
    print(strategy_summary_df.to_string(index=False))

    print("\n" + "=" * 80)
    print("FOCUS YEAR: 2017 (FAILURE BULL)")
    print("=" * 80)
    print(f"{'Strategy':<20} {'Return':<10} {'Benchmark':<10} {'Excess':<10} {'Trades':<8}")
    for _, row in reg_2017_all.iterrows():
        print(f"{row['strategy']:<20} {row['total_return']*100:>8.1f}% {row['benchmark_return']*100:>8.1f}% {row['excess_return']*100:>8.1f}% {int(row['n_trades']):<8}")

    print("\n" + "=" * 80)
    print("FOCUS YEAR: 2025 (FAILURE BULL)")
    print("=" * 80)
    print(f"{'Strategy':<20} {'Return':<10} {'Benchmark':<10} {'Excess':<10} {'Trades':<8}")
    for _, row in reg_2025_all.iterrows():
        print(f"{row['strategy']:<20} {row['total_return']*100:>8.1f}% {row['benchmark_return']*100:>8.1f}% {row['excess_return']*100:>8.1f}% {int(row['n_trades']):<8}")

    print("\n" + "=" * 80)
    print("FOCUS YEAR: 2021 (SUCCESS)")
    print("=" * 80)
    print(f"{'Strategy':<20} {'Return':<10} {'Benchmark':<10} {'Excess':<10} {'Trades':<8}")
    for _, row in succ_2021_all.iterrows():
        print(f"{row['strategy']:<20} {row['total_return']*100:>8.1f}% {row['benchmark_return']*100:>8.1f}% {row['excess_return']*100:>8.1f}% {int(row['n_trades']):<8}")

    print("\n" + "=" * 80)
    print("FOCUS YEAR: 2022 (SUCCESS)")
    print("=" * 80)
    print(f"{'Strategy':<20} {'Return':<10} {'Benchmark':<10} {'Excess':<10} {'Trades':<8}")
    for _, row in succ_2022_all.iterrows():
        print(f"{row['strategy']:<20} {row['total_return']*100:>8.1f}% {row['benchmark_return']*100:>8.1f}% {row['excess_return']*100:>8.1f}% {int(row['n_trades']):<8}")

    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)
    
    all_regime_sensitive = all(s["behavior"] == "REGIME-SENSITIVE" for _, s in strategy_summary_df.iterrows())
    
    if all_regime_sensitive:
        print("""
All strategies show REGIME-SENSITIVE behavior:
- Negative average excess in failure years (2017, 2025)
- Positive average excess in success years (2021, 2022)

This is CONSISTENT WITH defensive/regime-sensitive behavior across the strategy family.
However, fold-level metrics CANNOT PROVE the exact cause:
- Cannot confirm ticker selection (what stocks were bought/sold)
- Cannot confirm cash exposure (how much was in cash vs invested)
- Cannot confirm sector tilt (which sectors were overweight/underweight)
- Cannot confirm signal composition effect (which component drives behavior)

Further research would require:
1. Trade-level logs with ticker-level PnL
2. Daily equity curves with cash/holdings breakdown
3. Sector exposure analysis over time
""")
    else:
        print("""
Mixed behavior observed across strategies. Some show regime-sensitivity, others do not.
Further analysis needed to understand differentiated performance.
""")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Artifacts saved to: {output_dir}")
    print(f"Input artifact: {wf_name}")


if __name__ == "__main__":
    main()