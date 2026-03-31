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


def _le_quantile(series: pd.Series, quantile: float) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    threshold = float(numeric.quantile(float(quantile)))
    return numeric <= threshold


def main() -> None:
    setup = load_champion_setup(start_year=2019, end_year=2025)
    meta_index = pd.to_datetime(setup.meta_state["time"])
    rel2_on = setup.rel2 > 0.0
    blocked3 = pd.Series(
        pd.to_numeric(setup.meta_state["full_recent_blocked_buy_ewm3"], errors="coerce").to_numpy(),
        index=meta_index,
    )
    blocked5 = pd.Series(
        pd.to_numeric(setup.meta_state["full_recent_blocked_buy_ewm5"], errors="coerce").to_numpy(),
        index=meta_index,
    )

    sectors = pd.read_parquet(SECTOR_PATH)[["symbol", "icb_name2"]].drop_duplicates("symbol")
    sector_map = dict(zip(sectors["symbol"], sectors["icb_name2"]))
    sector_labels = tuple(sector_map.get(ticker) for ticker in setup.inputs.market_inputs.tickers)

    gates = {
        "sticky_baseline_rel2_gt0": rel2_on,
        "impl__blocked3_q80": rel2_on & _le_quantile(blocked3, 0.80),
        "impl__blocked5_q80": rel2_on & _le_quantile(blocked5, 0.80),
    }
    candidates = [
        ("sticky_baseline_rel2_gt0", 0.015, None),
        ("impl__blocked3_q80", 0.015, None),
        ("impl__blocked3_q80_sector_cap_3", 0.015, 3),
        ("impl__blocked5_q80", 0.015, None),
        ("impl__blocked5_q80_sector_cap_3", 0.015, 3),
    ]

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for name, bonus, cap in candidates:
        gate_key = name.replace("_sector_cap_3", "")
        activation_scale = align_series_to_market_dates(gates[gate_key].astype(float), setup.inputs.market_inputs.dates, fill_value=0.0)
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
    results_path = OUT_DIR / f"{ts}_h190_impl_pain_sector_combo_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h190_impl_pain_sector_combo_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[best_name].to_parquet(best_daily_path, index=False)

    summary = {
        "selector": setup.selector_name,
        "activation_rule": "h175__rel2_gt0 + sticky_bonus_0p015 + implementation_pain family",
        "winner": results.iloc[0].to_dict(),
        "current_champion": results.loc[results["variant"] == "impl__blocked5_q80"].iloc[0].to_dict(),
        "sticky_baseline": results.loc[results["variant"] == "sticky_baseline_rel2_gt0"].iloc[0].to_dict(),
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
        mode="portfolio_activation_impl_pain_sector_combo",
        name="h190_impl_pain_sector_combo",
        summary=summary,
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path)},
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
