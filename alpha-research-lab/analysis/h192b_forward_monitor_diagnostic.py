from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.champion_activation_utils import (
    current_champion_variant,
    load_champion_setup,
    run_champion_variant,
)
from src.champion_branch_experiment_utils import (
    jsonable,
    rebalance_monitor_window_days,
    slice_execution_year,
    summarize_daily_slice,
)
from src.deterministic_portfolio import simulate_strategy
from src.run_summary import write_run_summary

OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def _monitor_window(daily: pd.DataFrame, *, days: int) -> pd.DataFrame:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    keep_dates = set(sorted(work["execution_date"].drop_duplicates())[-int(days):])
    return work.loc[work["execution_date"].isin(keep_dates)].reset_index(drop=True)


def _classify(summary: dict[str, object]) -> str:
    activation_on_rate = float(summary["activation_on_rate"])
    avg_cash_weight = float(summary["avg_cash_weight"])
    blocked_extreme_rate = float(summary["blocked_extreme_rate"])
    weak_top5_buyable_rate = float(summary["weak_top5_buyable_rate"])
    delta_relative = float(summary["delta_relative_total_return"])
    activated_relative = float(summary["activated_relative_total_return"])

    if (
        activation_on_rate < 0.10
        and avg_cash_weight > 0.90
        and blocked_extreme_rate >= 0.70
        and weak_top5_buyable_rate >= 0.70
        and delta_relative > 0.0
    ):
        return "case_1_valid_defensive_regime"
    if delta_relative <= 0.0 or (activated_relative < 0.0 and avg_cash_weight > 0.90):
        return "case_3_live_failure"
    if activation_on_rate < 0.10 and avg_cash_weight > 0.90:
        return "case_2_over_defensive_without_clear_regime"
    return "mixed_not_extreme"


def main() -> None:
    spec = current_champion_variant()
    setup = load_champion_setup(start_year=2019, end_year=2026)
    activated = run_champion_variant(setup, spec=spec)

    always_kwargs = dict(setup.common_kwargs)
    always_kwargs["incumbent_score_bonus"] = float(spec.incumbent_score_bonus)
    if spec.max_names_per_sector is not None:
        always_kwargs["sector_labels"] = activated.sector_labels
        always_kwargs["max_names_per_sector"] = int(spec.max_names_per_sector)
    always_on = simulate_strategy(**always_kwargs)

    activated_2026 = slice_execution_year(activated.result.daily, 2026)
    always_2026 = slice_execution_year(always_on.daily, 2026)
    monitor_days = rebalance_monitor_window_days(rebalance_every=int(setup.common_kwargs["rebalance_every"]))
    monitor_daily = _monitor_window(activated_2026, days=monitor_days)

    meta_index = pd.to_datetime(setup.meta_state["time"])
    monitor_index = pd.to_datetime(monitor_daily["signal_date"])
    blocked_extreme = pd.Series(False, index=meta_index)
    if activated.blocked_buy_series is not None and activated.blocked_buy_on_threshold is not None:
        blocked_extreme = pd.to_numeric(activated.blocked_buy_series, errors="coerce") > float(
            activated.blocked_buy_on_threshold
        )
    top5_buyable = pd.Series(
        pd.to_numeric(setup.meta_state["full_top5_buyable_count"], errors="coerce").to_numpy(dtype=np.float64),
        index=meta_index,
    )
    monitor_blocked = blocked_extreme.reindex(monitor_index).fillna(False)
    monitor_top5_buyable = top5_buyable.reindex(monitor_index)

    activated_summary = summarize_daily_slice(activated_2026)
    always_summary = summarize_daily_slice(always_2026)
    summary = {
        "variant": spec.name,
        "monitor_days": int(monitor_days),
        "monitor_window_start": jsonable(pd.to_datetime(monitor_daily["execution_date"]).min())
        if not monitor_daily.empty else None,
        "monitor_window_end": jsonable(pd.to_datetime(monitor_daily["execution_date"]).max())
        if not monitor_daily.empty else None,
        "activation_on_rate": float(pd.to_numeric(monitor_daily["activation_on"], errors="coerce").mean())
        if not monitor_daily.empty else 0.0,
        "avg_cash_weight": float(pd.to_numeric(monitor_daily["cash_weight"], errors="coerce").mean())
        if not monitor_daily.empty else 1.0,
        "active_cycle_count": int(monitor_daily.loc[monitor_daily["activation_on"]].shape[0]),
        "active_cycle_hit_rate": (
            float((pd.to_numeric(monitor_daily.loc[monitor_daily["activation_on"], "relative_return"], errors="coerce") > 0.0).mean())
            if not monitor_daily.loc[monitor_daily["activation_on"]].empty else None
        ),
        "blocked_extreme_rate": float(pd.to_numeric(monitor_blocked, errors="coerce").mean())
        if not monitor_blocked.empty else 0.0,
        "blocked_on_threshold": activated.blocked_buy_on_threshold,
        "top5_buyable_mean": float(pd.to_numeric(monitor_top5_buyable, errors="coerce").mean())
        if not monitor_top5_buyable.empty else None,
        "weak_top5_buyable_rate": float((pd.to_numeric(monitor_top5_buyable, errors="coerce") <= 2.0).mean())
        if not monitor_top5_buyable.empty else 1.0,
        "activated_relative_total_return": activated_summary["relative_total_return"],
        "always_on_relative_total_return": always_summary["relative_total_return"],
        "delta_relative_total_return": (
            None
            if activated_summary["relative_total_return"] is None or always_summary["relative_total_return"] is None
            else float(activated_summary["relative_total_return"] - always_summary["relative_total_return"])
        ),
        "activated_information_ratio_annualized": activated_summary["information_ratio_annualized"],
        "always_on_information_ratio_annualized": always_summary["information_ratio_annualized"],
        "classification": None,
        "latest_activated_day": activated_summary["latest_day"],
        "latest_always_on_day": always_summary["latest_day"],
    }
    summary["classification"] = _classify(summary)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    monitor_path = OUT_DIR / f"{ts}_h192b_forward_monitor_diagnostic_monitor.parquet"
    monitor_export = monitor_daily.copy()
    monitor_export["blocked_extreme"] = monitor_blocked.to_numpy(dtype=bool) if len(monitor_daily) == len(monitor_blocked) else False
    monitor_export["top5_buyable_count"] = monitor_top5_buyable.to_numpy(dtype=np.float64) if len(monitor_daily) == len(monitor_top5_buyable) else np.nan
    monitor_export.to_parquet(monitor_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_activation_forward_monitor_diagnostic",
        name="h192b_forward_monitor_diagnostic",
        summary=summary,
        artifacts={"monitor": str(monitor_path)},
        metadata={"monitor_days": int(monitor_days), "variant": spec.name},
    )

    print("H192B: FORWARD MONITOR DIAGNOSTIC")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
