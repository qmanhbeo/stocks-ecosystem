from __future__ import annotations

from pathlib import Path

from src.repo_paths import artifact_path
from typing import Mapping

import pandas as pd


OUT_DIR = artifact_path("portfolio_baselines")


def print_top_activation_results(results: pd.DataFrame, *, title: str, top_n: int = 20) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 208)
    print(title)
    print("=" * 208)
    print(
        f"{'rank':<5} {'selector':<24} {'gate':<36} {'tot_ret':>10} {'rel_ret':>10} {'IR':>8} "
        f"{'max_dd':>9} {'cash':>8} {'act_on':>8} {'act_sc':>8} {'act_hit':>8} {'cycles':>8} {'yrs+':>7}"
    )
    print("-" * 208)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        info_ratio = float("nan") if row.information_ratio_annualized is None else row.information_ratio_annualized
        hit_rate = float("nan") if row.active_cycle_hit_rate is None else row.active_cycle_hit_rate
        on_rate = float("nan") if row.activation_on_rate is None else row.activation_on_rate
        scale = float("nan") if getattr(row, "avg_activation_scale", None) is None else row.avg_activation_scale
        print(
            f"{i:<5} {row.selector_name:<24} {row.gate_name:<36} "
            f"{row.portfolio_total_return*100:>+9.2f}% {row.relative_total_return*100:>+9.2f}% {info_ratio:>8.2f} "
            f"{row.max_drawdown*100:>8.2f}% {row.avg_cash_weight*100:>7.2f}% {on_rate*100:>7.2f}% {scale*100:>7.2f}% "
            f"{hit_rate*100:>7.2f}% {row.active_cycle_count:>8} {row.positive_years:>3}/{row.total_years:<3}"
        )


def persist_activation_outputs(
    *,
    ts: str,
    stem: str,
    results: pd.DataFrame,
    daily_outputs: Mapping[tuple[str, str], pd.DataFrame],
) -> tuple[Path, Path | None]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_{stem}_results.parquet"
    results.to_parquet(results_path, index=False)

    best_daily_path: Path | None = None
    non_baseline = results.loc[results["gate_name"] != "always_on"].reset_index(drop=True)
    best_row = non_baseline.head(1)
    if not best_row.empty:
        key = (str(best_row.iloc[0]["selector_name"]), str(best_row.iloc[0]["gate_name"]))
        best_daily = daily_outputs.get(key)
        if best_daily is not None and not best_daily.empty:
            best_daily_path = OUT_DIR / f"{ts}_{stem}_best_daily.parquet"
            best_daily.to_parquet(best_daily_path, index=False)
    return results_path, best_daily_path
