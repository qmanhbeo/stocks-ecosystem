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


def _frontier_variants(aggregate: pd.DataFrame) -> list[str]:
    frontier: list[str] = []
    for _, row in aggregate.iterrows():
        dominated = aggregate.loc[
            (aggregate["mean_relative_total_return"] >= row["mean_relative_total_return"])
            & (aggregate["mean_information_ratio_annualized"] >= row["mean_information_ratio_annualized"])
            & (
                (aggregate["mean_relative_total_return"] > row["mean_relative_total_return"])
                | (aggregate["mean_information_ratio_annualized"] > row["mean_information_ratio_annualized"])
            )
        ]
        if dominated.empty:
            frontier.append(str(row["variant"]))
    return frontier


def main() -> None:
    candidates = [
        ChampionVariantSpec(name="sticky_bonus_0p015", incumbent_score_bonus=0.015),
        ChampionVariantSpec(
            name="impl__blocked3_q80",
            incumbent_score_bonus=0.015,
            blocked_buy_span=3,
            blocked_buy_max_quantile=0.80,
        ),
        ChampionVariantSpec(
            name="impl__blocked5_q80",
            incumbent_score_bonus=0.015,
            blocked_buy_span=5,
            blocked_buy_max_quantile=0.80,
        ),
        current_champion_variant(),
    ]
    current_name = current_champion_variant().name
    test_years = [2023, 2024, 2025]

    rows: list[dict[str, object]] = []
    best_daily_by_variant: dict[str, pd.DataFrame] = {}
    for test_year in test_years:
        setup = load_champion_setup(start_year=2019, end_year=int(test_year))
        train_mask = calibration_mask_before_year(setup.meta_state, test_year)
        for spec in candidates:
            run = run_champion_variant(setup, spec=spec, calibration_mask=train_mask)
            year_daily = run.result.daily.copy()
            year_daily["execution_date"] = pd.to_datetime(year_daily["execution_date"])
            year_daily = year_daily.loc[year_daily["execution_date"].dt.year == int(test_year)].reset_index(drop=True)
            summary = summarize_daily_slice(year_daily)
            cycle_metrics = summary["cycle_metrics"]
            rows.append(
                {
                    "variant": spec.name,
                    "test_year": int(test_year),
                    "blocked_buy_on_threshold": run.blocked_buy_on_threshold,
                    "blocked_buy_off_threshold": run.blocked_buy_off_threshold,
                    "portfolio_total_return": summary["portfolio_total_return"],
                    "relative_total_return": summary["relative_total_return"],
                    "information_ratio_annualized": summary["information_ratio_annualized"],
                    "max_drawdown": summary["max_drawdown"],
                    "avg_cash_weight": summary["avg_cash_weight"],
                    "avg_num_holdings": summary["avg_num_holdings"],
                    "activation_on_rate": cycle_metrics["activation_on_rate"],
                    "active_cycle_count": cycle_metrics["active_cycle_count"],
                    "active_cycle_hit_rate": cycle_metrics["active_cycle_hit_rate"],
                }
            )
            best_daily_by_variant[f"{spec.name}_{test_year}"] = year_daily.copy()

    results = pd.DataFrame(rows)
    aggregate = (
        results.groupby("variant", as_index=False)
        .agg(
            mean_relative_total_return=("relative_total_return", "mean"),
            mean_information_ratio_annualized=("information_ratio_annualized", "mean"),
            mean_max_drawdown=("max_drawdown", "mean"),
            mean_avg_cash_weight=("avg_cash_weight", "mean"),
            mean_activation_on_rate=("activation_on_rate", "mean"),
            positive_years=("relative_total_return", lambda s: int((pd.to_numeric(s, errors="coerce") > 0.0).sum())),
        )
        .sort_values(
            by=[
                "mean_relative_total_return",
                "mean_information_ratio_annualized",
                "positive_years",
            ],
            ascending=[False, False, False],
            ignore_index=True,
        )
    )
    frontier = _frontier_variants(aggregate)
    aggregate["on_efficient_frontier"] = aggregate["variant"].isin(frontier)
    winner = aggregate.iloc[0].to_dict()
    current_row = aggregate.loc[aggregate["variant"] == current_name].iloc[0].to_dict()
    current_alive = bool(current_row["on_efficient_frontier"])

    summary = {
        "test_years": test_years,
        "winner": winner,
        "current_variant": current_row,
        "current_variant_on_frontier": current_alive,
        "efficient_frontier": frontier,
        "recommended_rollback_variant": None if current_alive else str(winner["variant"]),
        "yearly_results": results.sort_values(["test_year", "variant"]).to_dict("records"),
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h193_pseudo_live_robustness_ladder_results.parquet"
    aggregate_path = OUT_DIR / f"{ts}_h193_pseudo_live_robustness_ladder_aggregate.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h193_pseudo_live_robustness_ladder_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    aggregate.to_parquet(aggregate_path, index=False)
    best_variant = str(winner["variant"])
    best_year = int(
        results.loc[results["variant"] == best_variant]
        .sort_values("relative_total_return", ascending=False)
        .iloc[0]["test_year"]
    )
    best_daily_by_variant[f"{best_variant}_{best_year}"].to_parquet(best_daily_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_activation_pseudo_live_robustness_ladder",
        name="h193_pseudo_live_robustness_ladder",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "aggregate": str(aggregate_path),
            "best_daily": str(best_daily_path),
        },
        metadata={"test_years": test_years, "current_variant": current_name},
    )

    print("H193: PSEUDO-LIVE ROBUSTNESS LADDER")
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
