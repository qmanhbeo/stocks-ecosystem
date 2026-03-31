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


def _pct_rank(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rank(method="average", pct=True).fillna(0.5).astype(float)


def _le_quantile(series: pd.Series, quantile: float) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    threshold = float(numeric.quantile(float(quantile)))
    return numeric <= threshold


def main() -> None:
    setup = load_champion_setup(start_year=2019, end_year=2025)
    meta = setup.meta_state.copy()
    meta_index = pd.to_datetime(meta["time"])
    rel2_on = setup.rel2 > 0.0

    blocked3 = pd.Series(pd.to_numeric(meta["full_recent_blocked_buy_ewm3"], errors="coerce").to_numpy(), index=meta_index)
    blocked5 = pd.Series(pd.to_numeric(meta["full_recent_blocked_buy_ewm5"], errors="coerce").to_numpy(), index=meta_index)
    cash3 = pd.Series(pd.to_numeric(meta["full_recent_cash_weight_ewm3"], errors="coerce").to_numpy(), index=meta_index)
    cash5 = pd.Series(pd.to_numeric(meta["full_recent_cash_weight_ewm5"], errors="coerce").to_numpy(), index=meta_index)
    current_blocked = pd.Series(pd.to_numeric(meta["full_top5_blocked_buy_count"], errors="coerce").to_numpy(), index=meta_index)
    current_buyable = pd.Series(
        pd.to_numeric(meta["full_top5_buyable_count"], errors="coerce").clip(0.0, 5.0).to_numpy(),
        index=meta_index,
    )

    pain_score = (
        _pct_rank(blocked3)
        + _pct_rank(cash3)
        + _pct_rank(current_blocked)
        + (1.0 - current_buyable.fillna(0.0) / 5.0)
    ) / 4.0

    gates = {
        "sticky_baseline_rel2_gt0": rel2_on,
        "impl__blocked3_q70": rel2_on & _le_quantile(blocked3, 0.70),
        "impl__blocked3_q80": rel2_on & _le_quantile(blocked3, 0.80),
        "impl__cash3_q70": rel2_on & _le_quantile(cash3, 0.70),
        "impl__cash3_q80": rel2_on & _le_quantile(cash3, 0.80),
        "impl__combo_q70": rel2_on & _le_quantile(blocked3, 0.70) & _le_quantile(cash3, 0.70),
        "impl__combo_q80": rel2_on & _le_quantile(blocked5, 0.80) & _le_quantile(cash5, 0.80),
        "impl__pain_q60": rel2_on & _le_quantile(pain_score, 0.60),
        "impl__pain_q70": rel2_on & _le_quantile(pain_score, 0.70),
        "impl__pain_q80": rel2_on & _le_quantile(pain_score, 0.80),
    }

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for name, gate in gates.items():
        activation_scale = align_series_to_market_dates(gate.astype(float), setup.inputs.market_inputs.dates, fill_value=0.0)
        result = simulate_strategy(
            **setup.common_kwargs,
            activation_scale=activation_scale,
            incumbent_score_bonus=0.015,
        )
        row = {"variant": name}
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
    results_path = OUT_DIR / f"{ts}_h188_implementation_pain_veto_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h188_implementation_pain_veto_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[best_name].to_parquet(best_daily_path, index=False)

    summary = {
        "selector": setup.selector_name,
        "activation_rule": "h175__rel2_gt0 + sticky_bonus_0p015",
        "winner": results.iloc[0].to_dict(),
        "sticky_baseline": results.loc[results["variant"] == "sticky_baseline_rel2_gt0"].iloc[0].to_dict(),
        "tested_variants": results[
            [
                "variant",
                "relative_total_return",
                "information_ratio_annualized",
                "avg_cash_weight",
                "blocked_buy_events",
            ]
        ].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_implementation_pain",
        name="h188_implementation_pain_veto",
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
                "avg_cash_weight",
                "blocked_buy_events",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
