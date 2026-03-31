from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.champion_activation_utils import align_series_to_market_dates, load_champion_setup
from src.deterministic_portfolio import simulate_strategy
from src.run_summary import write_run_summary

OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def main() -> None:
    setup = load_champion_setup(start_year=2019, end_year=2025)
    base_gate = (setup.rel2 > 0.0).astype(float)
    activation_scale = align_series_to_market_dates(base_gate, setup.inputs.market_inputs.dates, fill_value=0.0)

    candidates = [
        ("baseline_rel2_gt0", 0.0),
        ("sticky_bonus_0p005", 0.005),
        ("sticky_bonus_0p010", 0.010),
        ("sticky_bonus_0p015", 0.015),
        ("sticky_bonus_0p020", 0.020),
        ("sticky_bonus_0p030", 0.030),
    ]

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for name, bonus in candidates:
        result = simulate_strategy(
            **setup.common_kwargs,
            activation_scale=activation_scale,
            incumbent_score_bonus=float(bonus),
        )
        row = {"variant": name, "incumbent_score_bonus": float(bonus)}
        row.update(result.summary)
        rows.append(row)
        daily_outputs[name] = result.daily.copy()

    results = pd.DataFrame(rows).sort_values(
        by=[
            "relative_total_return",
            "information_ratio_annualized",
            "portfolio_total_return",
            "max_drawdown",
        ],
        ascending=[False, False, False, False],
        ignore_index=True,
    )

    best_name = str(results.iloc[0]["variant"])
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h184_sticky_holdings_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h184_sticky_holdings_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[best_name].to_parquet(best_daily_path, index=False)

    summary = {
        "selector": setup.selector_name,
        "activation_rule": "h175__rel2_gt0",
        "winner": results.iloc[0].to_dict(),
        "baseline": results.loc[results["variant"] == "baseline_rel2_gt0"].iloc[0].to_dict(),
        "tested_variants": results[["variant", "relative_total_return", "information_ratio_annualized", "avg_daily_turnover"]].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_local_refinement",
        name="h184_sticky_holdings_displacement_margin",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
        },
        metadata={"start_year": 2019, "end_year": 2025},
    )
    print(results[["variant", "relative_total_return", "information_ratio_annualized", "avg_daily_turnover"]].to_string(index=False))


if __name__ == "__main__":
    main()
