"""
H472: liquidity_adjusted_return

Hypothesis: Return normalized by Amihud illiquidity (|return| / turnover) captures
"quality of flow" better than raw return alone. Stocks that show returns despite
high liquidity (low Amihud) represent real institutional demand. Stocks that only
show returns in illiquid conditions are fragile.

Test: return_5d / Amihud_illiq buckets vs forward IC.
Compare with: random baseline and C23 high_illiq_expansion as reference.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "liquidity_adjusted_return"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Return / Amihud illiquidity captures 'flow quality': high ratio (return despite "
        "liquidity) = institutional demand; low ratio = fragile illiquid returns. "
        "Test 5d return / 20d avg Amihud quintiles vs forward IC."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H472 liquidity_adjusted_return test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def parse_price_change(s):
    if pd.isna(s):
        return np.nan
    try:
        match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
        if match:
            return float(match.group(1).replace(',', '.'))
        return np.nan
    except Exception:
        return np.nan


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    stock_dir = Path("/home/manh/stocks-ecosystem/data/stock")
    ohlcv_dfs = []
    for f in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        if "_1H" in f.stem or "_CAFEF" in f.stem:
            continue
        try:
            df = pd.read_parquet(f)
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
            df["ticker"] = ticker
            ohlcv_dfs.append(df)
        except Exception:
            continue

    if not ohlcv_dfs:
        raise RuntimeError("No OHLCV 1D files found")

    ohlcv = pd.concat(ohlcv_dfs, ignore_index=True)
    ohlcv = ohlcv.rename(columns={"date": "time"}) if "date" in ohlcv.columns else ohlcv
    ohlcv["time"] = pd.to_datetime(ohlcv["time"]).dt.normalize()
    ohlcv = ohlcv[ohlcv["time"].dt.year <= 2025]
    ohlcv = ohlcv.sort_values(["ticker", "time"])

    ohlcv["daily_return"] = ohlcv.groupby("ticker")["close"].pct_change(fill_method=None)
    ohlcv["daily_return_abs"] = ohlcv["daily_return"].abs()
    ohlcv["turnover"] = ohlcv["close"] * ohlcv["volume"] / 1e9
    ohlcv["amihud"] = ohlcv["daily_return_abs"] / (ohlcv["turnover"] + 1e-9)

    ohlcv["amihud_20d_avg"] = ohlcv.groupby("ticker")["amihud"].transform(
        lambda x: x.rolling(window=20, min_periods=10).mean()
    )
    ohlcv["return_5d"] = ohlcv.groupby("ticker")["close"].pct_change(5)

    panel = panel.merge(
        ohlcv[["time", "ticker", "amihud_20d_avg", "return_5d", "daily_return_abs"]],
        on=["time", "ticker"],
        how="inner",
    )

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"]).dt.normalize()
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]
    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume"]],
        on=["time", "ticker"],
        how="inner",
    )

    panel["all_rows"] = True
    panel = panel.sort_values(["ticker", "time"])

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    panel["liquidity_adjusted_return"] = panel["return_5d"] / (panel["amihud_20d_avg"] + 1e-9)
    panel["liquidity_adjusted_return"] = panel["liquidity_adjusted_return"].replace([np.inf, -np.inf], np.nan)

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("high_lar", "High liquidity-adjusted return (Q5)", family="lar", primary=True),
    StateSpec("mid_lar", "Mid liquidity-adjusted return (Q3)", family="lar"),
    StateSpec("low_lar", "Low liquidity-adjusted return (Q1)", family="lar"),
    StateSpec("high_lar_expansion", "High LAR + Vol expansion", family="lar_vol"),
    StateSpec("low_lar_expansion", "Low LAR + Vol expansion", family="lar_vol"),
    StateSpec("return_5d_pos_liq", "Positive 5d return + High liquidity (low Amihud)", family="return_illiq"),
    StateSpec("return_5d_pos_illiq", "Positive 5d return + Low liquidity (high Amihud)", family="return_illiq"),
]


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)

    panel = panel.dropna(subset=["liquidity_adjusted_return", "amihud_20d_avg"])

    lar_rank = panel.groupby("time", sort=False)["liquidity_adjusted_return"].rank(method="average", pct=True)
    panel["high_lar"] = lar_rank >= 0.8
    panel["mid_lar"] = (lar_rank > 0.3) & (lar_rank < 0.7)
    panel["low_lar"] = lar_rank <= 0.2

    panel["high_lar_expansion"] = panel["high_lar"] & panel["vol_expansion"]
    panel["low_lar_expansion"] = panel["low_lar"] & panel["vol_expansion"]

    amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
    panel["high_amihud"] = amihud_rank >= 0.8
    panel["low_amihud"] = amihud_rank <= 0.2

    panel["return_5d_pos"] = panel["return_5d"] > 0
    panel["return_5d_pos_liq"] = panel["return_5d_pos"] & panel["low_amihud"]
    panel["return_5d_pos_illiq"] = panel["return_5d_pos"] & panel["high_amihud"]

    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    baseline_row = results[results["name"] == "all_rows"]
    baseline_ic = float(baseline_row["avg_ic"].iloc[0]) if not baseline_row.empty else 0.0

    def get_ic(name):
        row = results[results["name"] == name]
        return float(row["avg_ic"].iloc[0]) if name in results["name"].values else None

    high_lar_ic = get_ic("high_lar")
    mid_lar_ic = get_ic("mid_lar")
    low_lar_ic = get_ic("low_lar")
    high_lar_exp_ic = get_ic("high_lar_expansion")
    low_lar_exp_ic = get_ic("low_lar_expansion")
    ret_pos_liq_ic = get_ic("return_5d_pos_liq")
    ret_pos_illiq_ic = get_ic("return_5d_pos_illiq")

    high_lar_lift = (high_lar_ic - baseline_ic) if high_lar_ic is not None else None
    high_lar_exp_lift = (high_lar_exp_ic - baseline_ic) if high_lar_exp_ic is not None else None
    ret_pos_liq_lift = (ret_pos_liq_ic - baseline_ic) if ret_pos_liq_ic is not None else None
    ret_pos_illiq_lift = (ret_pos_illiq_ic - baseline_ic) if ret_pos_illiq_ic is not None else None

    c23_reference = 0.2616

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    if high_lar_lift is not None and high_lar_lift > 0.005:
        decision = "PASSED"
    elif high_lar_lift is not None and high_lar_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "high_lar_ic": high_lar_ic,
            "mid_lar_ic": mid_lar_ic,
            "low_lar_ic": low_lar_ic,
            "high_lar_lift": high_lar_lift,
            "high_lar_expansion_ic": high_lar_exp_ic,
            "low_lar_expansion_ic": low_lar_exp_ic,
            "high_lar_expansion_lift": high_lar_exp_lift,
            "return_5d_pos_liq_ic": ret_pos_liq_ic,
            "return_5d_pos_illiq_ic": ret_pos_illiq_ic,
            "ret_pos_liq_lift": ret_pos_liq_lift,
            "ret_pos_illiq_lift": ret_pos_illiq_lift,
            "c23_reference_ic": c23_reference,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\nLAR alone:")
    print(f"  high_lar (Q5): {high_lar_ic:.4f} (lift: {high_lar_lift:+.4f})")
    print(f"  mid_lar (Q3): {mid_lar_ic:.4f}")
    print(f"  low_lar (Q1): {low_lar_ic:.4f}")
    print(f"\nLAR × Vol regime:")
    print(f"  high_lar_expansion: {high_lar_exp_ic:.4f} (lift: {high_lar_exp_lift:+.4f})")
    print(f"  low_lar_expansion: {low_lar_exp_ic:.4f}")
    print(f"\nReturn × Amihud:")
    print(f"  return_5d_pos_liq: {ret_pos_liq_ic:.4f} (lift: {ret_pos_liq_lift:+.4f})")
    print(f"  return_5d_pos_illiq: {ret_pos_illiq_ic:.4f} (lift: {ret_pos_illiq_lift:+.4f})")
    print(f"\nC23 reference IC: {c23_reference:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()