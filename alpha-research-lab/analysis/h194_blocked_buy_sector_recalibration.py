from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.champion_activation_utils import (
    ChampionVariantSpec,
    calibration_mask_before_year,
    current_champion_variant,
    load_champion_setup,
    run_champion_variant,
)
from src.champion_branch_experiment_utils import summarize_daily_slice
from src.run_summary import write_run_summary

OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def main() -> None:
    variants = [
        ChampionVariantSpec(
            name="impl__blocked5_q75_sector_cap_3",
            incumbent_score_bonus=0.015,
            blocked_buy_span=5,
            blocked_buy_max_quantile=0.75,
            max_names_per_sector=3,
        ),
        current_champion_variant(),
        ChampionVariantSpec(
            name="impl__blocked5_q85_sector_cap_3",
            incumbent_score_bonus=0.015,
            blocked_buy_span=5,
            blocked_buy_max_quantile=0.85,
            max_names_per_sector=3,
        ),
        ChampionVariantSpec(
            name="impl__blocked3_q80_sector_cap_3",
            incumbent_score_bonus=0.015,
            blocked_buy_span=3,
            blocked_buy_max_quantile=0.80,
            max_names_per_sector=3,
        ),
    ]
    current_name = current_champion_variant().name
    test_years = [2023, 2024, 2025]

    rows: list[dict[str, object]] = []
    for test_year in test_years:
        setup = load_champion_setup(start_year=2019, end_year=int(test_year))
        train_mask = calibration_mask_before_year(setup.meta_state, test_year)
        for spec in variants:
            run = run_champion_variant(setup, spec=spec, calibration_mask=train_mask)
            daily = run.result.daily.copy()
            daily["execution_date"] = pd.to_datetime(daily["execution_date"])
            daily = daily.loc[daily["execution_date"].dt.year == int(test_year)].reset_index(drop=True)
            summary = summarize_daily_slice(daily)
            cycle_metrics = summary["cycle_metrics"]
            rows.append(
                {
                    "variant": spec.name,
                    "test_year": int(test_year),
                    "blocked_buy_on_threshold": run.blocked_buy_on_threshold,
                    "portfolio_total_return": summary["portfolio_total_return"],
                    "relative_total_return": summary["relative_total_return"],
                    "information_ratio_annualized": summary["information_ratio_annualized"],
                    "max_drawdown": summary["max_drawdown"],
                    "avg_cash_weight": summary["avg_cash_weight"],
                    "activation_on_rate": cycle_metrics["activation_on_rate"],
                    "active_cycle_count": cycle_metrics["active_cycle_count"],
                }
            )

    results = pd.DataFrame(rows)
    aggregate = (
        results.groupby("variant", as_index=False)
        .agg(
            mean_relative_total_return=("relative_total_return", "mean"),
            mean_information_ratio_annualized=("information_ratio_annualized", "mean"),
            mean_max_drawdown=("max_drawdown", "mean"),
            mean_avg_cash_weight=("avg_cash_weight", "mean"),
            mean_activation_on_rate=("activation_on_rate", "mean"),
        )
        .sort_values(
            by=["mean_relative_total_return", "mean_information_ratio_annualized"],
            ascending=[False, False],
            ignore_index=True,
        )
    )
    current_row = aggregate.loc[aggregate["variant"] == current_name].iloc[0]
    accepted = aggregate.loc[
        (aggregate["mean_relative_total_return"] >= float(current_row["mean_relative_total_return"]) - 0.05)
        & (aggregate["mean_information_ratio_annualized"] >= float(current_row["mean_information_ratio_annualized"]) - 0.03)
        & (
            (aggregate["mean_activation_on_rate"] > float(current_row["mean_activation_on_rate"]))
            | (aggregate["mean_avg_cash_weight"] < float(current_row["mean_avg_cash_weight"]))
        )
    ].copy()
    accepted = accepted.sort_values(
        by=[
            "mean_activation_on_rate",
            "mean_avg_cash_weight",
            "mean_relative_total_return",
        ],
        ascending=[False, True, False],
        ignore_index=True,
    )
    promoted_variant = None if accepted.empty else str(accepted.iloc[0]["variant"])

    summary = {
        "test_years": test_years,
        "current_variant": current_row.to_dict(),
        "accepted_candidates": accepted.to_dict("records"),
        "promoted_variant": promoted_variant,
        "yearly_results": results.sort_values(["test_year", "variant"]).to_dict("records"),
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h194_blocked_buy_sector_recalibration_results.parquet"
    aggregate_path = OUT_DIR / f"{ts}_h194_blocked_buy_sector_recalibration_aggregate.parquet"
    results.to_parquet(results_path, index=False)
    aggregate.to_parquet(aggregate_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_activation_blocked_buy_sector_recalibration",
        name="h194_blocked_buy_sector_recalibration",
        summary=summary,
        artifacts={"results": str(results_path), "aggregate": str(aggregate_path)},
        metadata={"test_years": test_years, "current_variant": current_name},
    )

    print("H194: BLOCKED-BUY SECTOR RECALIBRATION")
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
