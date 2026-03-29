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

OUT_DIR = Path("artifacts/portfolio_baselines")


def _pct_rank(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rank(method="average", pct=True).fillna(0.5).astype(float)


def _ge_quantile(series: pd.Series, quantile: float) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    threshold = float(numeric.quantile(float(quantile)))
    return numeric >= threshold


def _coherence_score(meta: pd.DataFrame) -> pd.Series:
    spread = _pct_rank(meta["full_top1_minus_top5_spread"])
    std = _pct_rank(meta["full_top5_score_std"])
    overlap = _pct_rank(meta["full_top5_prev_overlap_ratio"])
    low_entropy = 1.0 - _pct_rank(meta["full_top10_score_entropy"])
    return (spread + std + overlap + low_entropy) / 4.0


def main() -> None:
    setup = load_champion_setup(start_year=2019, end_year=2025)
    meta = setup.meta_state.copy()
    meta_index = pd.to_datetime(meta["time"])
    rel2_on = setup.rel2 > 0.0

    spread = pd.Series(pd.to_numeric(meta["full_top1_minus_top5_spread"], errors="coerce").to_numpy(), index=meta_index)
    std = pd.Series(pd.to_numeric(meta["full_top5_score_std"], errors="coerce").to_numpy(), index=meta_index)
    overlap = pd.Series(pd.to_numeric(meta["full_top5_prev_overlap_ratio"], errors="coerce").to_numpy(), index=meta_index)
    coherence = pd.Series(_coherence_score(meta).to_numpy(dtype=float), index=meta_index)

    gates = {
        "sticky_baseline_rel2_gt0": rel2_on,
        "coh__q50": rel2_on & _ge_quantile(coherence, 0.50),
        "coh__q60": rel2_on & _ge_quantile(coherence, 0.60),
        "coh__q70": rel2_on & _ge_quantile(coherence, 0.70),
        "coh__spread_q60_std_q60": rel2_on & _ge_quantile(spread, 0.60) & _ge_quantile(std, 0.60),
        "coh__spread_q60_overlap_q50": rel2_on & _ge_quantile(spread, 0.60) & _ge_quantile(overlap, 0.50),
        "coh__std_q60_overlap_q50": rel2_on & _ge_quantile(std, 0.60) & _ge_quantile(overlap, 0.50),
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
    results_path = OUT_DIR / f"{ts}_h189_basket_coherence_guard_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h189_basket_coherence_guard_best_daily.parquet"
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
                "avg_daily_turnover",
            ]
        ].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_basket_coherence",
        name="h189_basket_coherence_guard",
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
                "avg_daily_turnover",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
