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
SECTOR_PATH = Path("data/features/sector_classification.parquet")


def main() -> None:
    setup = load_champion_setup(start_year=2019, end_year=2025)
    base_gate = (setup.rel2 > 0.0).astype(float)
    activation_scale = align_series_to_market_dates(base_gate, setup.inputs.market_inputs.dates, fill_value=0.0)

    sectors = pd.read_parquet(SECTOR_PATH)[["symbol", "icb_name2"]].drop_duplicates("symbol")
    sector_map = dict(zip(sectors["symbol"], sectors["icb_name2"]))
    sector_labels = tuple(sector_map.get(ticker) for ticker in setup.inputs.market_inputs.tickers)

    candidates = [
        ("baseline_rel2_gt0", 0.000, None),
        ("sticky_bonus_0p015", 0.015, None),
        ("sector_cap_3", 0.000, 3),
        ("sticky_bonus_0p015_sector_cap_3", 0.015, 3),
        ("sticky_bonus_0p015_sector_cap_2", 0.015, 2),
    ]

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for name, bonus, cap in candidates:
        kwargs = dict(setup.common_kwargs)
        kwargs["activation_scale"] = activation_scale
        kwargs["incumbent_score_bonus"] = float(bonus)
        if cap is not None:
            kwargs["sector_labels"] = sector_labels
            kwargs["max_names_per_sector"] = int(cap)
        result = simulate_strategy(**kwargs)
        row = {
            "variant": name,
            "incumbent_score_bonus": float(bonus),
            "max_names_per_sector": None if cap is None else int(cap),
        }
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
    results_path = OUT_DIR / f"{ts}_h187_sticky_sector_combo_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h187_sticky_sector_combo_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[best_name].to_parquet(best_daily_path, index=False)

    summary = {
        "selector": setup.selector_name,
        "activation_rule": "h175__rel2_gt0",
        "winner": results.iloc[0].to_dict(),
        "sticky_baseline": results.loc[results["variant"] == "sticky_bonus_0p015"].iloc[0].to_dict(),
        "plain_baseline": results.loc[results["variant"] == "baseline_rel2_gt0"].iloc[0].to_dict(),
        "tested_variants": results[
            [
                "variant",
                "relative_total_return",
                "information_ratio_annualized",
                "avg_daily_turnover",
                "avg_num_holdings",
            ]
        ].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_sticky_sector_combo",
        name="h187_sticky_sector_combo",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
        },
        metadata={"start_year": 2019, "end_year": 2025},
    )
    print(
        results[
            [
                "variant",
                "relative_total_return",
                "information_ratio_annualized",
                "avg_daily_turnover",
                "avg_num_holdings",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
