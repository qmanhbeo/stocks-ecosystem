from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.champion_activation_utils import align_series_to_market_dates, load_champion_setup
from src.deterministic_portfolio import simulate_strategy
from src.run_summary import write_run_summary

OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def scale_scenarios(rel2: pd.Series) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    out["baseline_rel2_gt0"] = (rel2 > 0.0).astype(float)
    out["half_full_0_1bp"] = pd.Series(
        np.where(rel2 <= 0.0, 0.0, np.where(rel2 <= 0.01, 0.5, 1.0)),
        index=rel2.index,
        dtype=float,
    )
    out["half_full_0_2bp"] = pd.Series(
        np.where(rel2 <= 0.0, 0.0, np.where(rel2 <= 0.02, 0.5, 1.0)),
        index=rel2.index,
        dtype=float,
    )
    out["quarter_half_full"] = pd.Series(
        np.where(rel2 <= -0.01, 0.0, np.where(rel2 <= 0.0, 0.25, np.where(rel2 <= 0.01, 0.5, 1.0))),
        index=rel2.index,
        dtype=float,
    )
    out["continuous_clip_1bp"] = pd.Series(np.clip(rel2 / 0.01, 0.0, 1.0), index=rel2.index, dtype=float)
    out["continuous_clip_2bp"] = pd.Series(np.clip(rel2 / 0.02, 0.0, 1.0), index=rel2.index, dtype=float)
    return out


def main() -> None:
    setup = load_champion_setup(start_year=2019, end_year=2025)
    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}

    for name, scale in scale_scenarios(setup.rel2).items():
        aligned = align_series_to_market_dates(scale, setup.inputs.market_inputs.dates, fill_value=0.0)
        result = simulate_strategy(**setup.common_kwargs, activation_scale=aligned)
        row = {"variant": name, "avg_activation_scale_input": float(np.mean(aligned))}
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
    results_path = OUT_DIR / f"{ts}_h186_local_exposure_control_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h186_local_exposure_control_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[best_name].to_parquet(best_daily_path, index=False)

    summary = {
        "selector": setup.selector_name,
        "winner": results.iloc[0].to_dict(),
        "baseline": results.loc[results["variant"] == "baseline_rel2_gt0"].iloc[0].to_dict(),
        "tested_variants": results[["variant", "relative_total_return", "information_ratio_annualized", "avg_cash_weight"]].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_local_refinement",
        name="h186_local_exposure_control",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
        },
        metadata={"start_year": 2019, "end_year": 2025},
    )
    print(results[["variant", "relative_total_return", "information_ratio_annualized", "avg_cash_weight"]].to_string(index=False))


if __name__ == "__main__":
    main()
