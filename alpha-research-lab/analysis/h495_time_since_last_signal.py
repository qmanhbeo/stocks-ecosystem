"""
BR9: time_since_last_signal

Hypothesis: C23/C24/C26 fire on different days. Time since last signal fire might
matter. Test: C23 fires TODAY vs C23 fired YESTERDAY vs C23 fired 3d ago.
Mechanism: signal persistence vs mean-reversion after signal fires.

First test: C23 (high_illiq × vol_expansion) × days_since_last_fire buckets
(0=fire today, 1=yesterday, 2=2d ago, 3+=stale) vs forward IC.
Compare: fresh signal (today) vs stale signal (3d+) vs no signal.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd
import numpy as np

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


BRANCH_NAME = "time_since_last_signal"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23/C24/C26 fire on different days. Time since last signal fire might matter. "
        "Test: C23 fires TODAY vs YESTERDAY vs 3d ago. "
        "Mechanism: signal persistence vs mean-reversion after signal fires."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR9 time_since_last_signal test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_amihud(df):
    if 'close' not in df.columns or 'volume' not in df.columns:
        return df
    df = df.copy()
    if 'ticker' in df.columns:
        df['daily_return'] = df.groupby('ticker')['close'].pct_change()
    else:
        df['daily_return'] = df['close'].pct_change()
    df['daily_return_abs'] = df['daily_return'].abs()
    df['turnover'] = df['close'] * df['volume'] / 1e9
    df['amihud'] = df['daily_return_abs'] / (df['turnover'] + 1e-9)
    return df


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    stock_dir = Path("/home/manh/stocks-ecosystem/data/stock")
    ohlcv_dfs = []
    for f in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            df = pd.read_parquet(f)
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
            df["ticker"] = ticker
            ohlcv_dfs.append(df)
        except:
            continue

    if ohlcv_dfs:
        ohlcv = pd.concat(ohlcv_dfs, ignore_index=True)
        ohlcv = ohlcv.rename(columns={"date": "time"})
        ohlcv["time"] = pd.to_datetime(ohlcv["time"])
        ohlcv = ohlcv[ohlcv["time"].dt.year <= 2025]
        ohlcv = compute_amihud(ohlcv)
        ohlcv = ohlcv.sort_values(["ticker", "time"])
        ohlcv["amihud_20d_avg"] = ohlcv.groupby("ticker")["amihud"].transform(
            lambda x: x.rolling(window=20, min_periods=10).mean()
        )
        panel = panel.merge(
            ohlcv[["time", "ticker", "amihud_20d_avg"]],
            on=["time", "ticker"],
            how="left",
        )
    else:
        panel["amihud_20d_avg"] = np.nan

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    import re
    def parse_price_change(s):
        if pd.isna(s):
            return np.nan
        try:
            match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
            if match:
                return float(match.group(1).replace(',', '.'))
            return np.nan
        except:
            return np.nan

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
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

    if "amihud_20d_avg" in panel.columns and panel["amihud_20d_avg"].notna().any():
        amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
        panel["high_illiq"] = amihud_rank >= 0.8
    else:
        panel["high_illiq"] = False

    panel["high_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]

    signal_fired = panel["high_illiq_expansion"].fillna(False).astype(int)
    signal_fired = signal_fired.groupby(panel["ticker"]).shift(1)
    panel["signal_fired_yesterday"] = signal_fired.fillna(0).astype(bool)
    panel["signal_fired_yesterday"] = panel.groupby("ticker")["high_illiq_expansion"].shift(1).fillna(False)

    panel["c23_fire_series"] = panel.groupby("ticker")["high_illiq_expansion"].cumsum()
    panel["c23_fire_series_prior"] = panel.groupby("ticker")["c23_fire_series"].shift(1).fillna(0)
    panel["c23_days_since"] = panel["c23_fire_series"] - panel["c23_fire_series_prior"]
    panel["c23_days_since"] = panel["c23_days_since"].replace(0, np.nan)
    panel["c23_days_since"] = panel.groupby("ticker")["c23_days_since"].transform(
        lambda x: x.where(x > 0).ffill()
    ).fillna(0)
    panel["c23_fresh"] = panel["high_illiq_expansion"]
    panel["c23_yesterday"] = panel.groupby("ticker")["high_illiq_expansion"].shift(1).fillna(False)
    panel["c23_2days"] = panel.groupby("ticker")["high_illiq_expansion"].shift(2).fillna(False)
    panel["c23_stale"] = panel["high_illiq_expansion"] == False

    panel["c23_fresh_not_yesterday"] = panel["high_illiq_expansion"] & ~panel["c23_yesterday"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("high_illiq_expansion", "C23: illiq × vol expansion (fresh)", family="signal", primary=True),
    StateSpec("c23_fresh", "C23 fires today", family="temporal"),
    StateSpec("c23_yesterday", "C23 fired yesterday (signal carry)", family="temporal"),
    StateSpec("c23_2days", "C23 fired 2d ago", family="temporal"),
    StateSpec("c23_stale", "C23 has NOT fired recently (stale)", family="temporal"),
    StateSpec("c23_fresh_not_yesterday", "C23 fires today AND not yesterday", family="temporal"),
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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0

    c23_ic = results[results["name"] == "high_illiq_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c23_lift = c23_ic - baseline_ic

    fresh_ic = results[results["name"] == "c23_fresh"]["avg_ic"].iloc[0] if not results.empty else 0
    yesterday_ic = results[results["name"] == "c23_yesterday"]["avg_ic"].iloc[0] if not results.empty else 0
    stale_ic = results[results["name"] == "c23_stale"]["avg_ic"].iloc[0] if not results.empty else 0
    fresh_lift = fresh_ic - baseline_ic
    yesterday_lift = yesterday_ic - baseline_ic
    stale_lift = stale_ic - baseline_ic

    fresh_not_yesterday_ic = results[results["name"] == "c23_fresh_not_yesterday"]["avg_ic"].iloc[0] if not results.empty else 0
    fresh_not_yesterday_lift = fresh_not_yesterday_ic - baseline_ic

    carry_ic = yesterday_ic - c23_ic
    persistence = fresh_ic > yesterday_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    if carry_ic > 0.01:
        decision = "PASSED"
    elif persistence and fresh_lift > 0.05:
        decision = "MIXED"
    elif stale_lift > -0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "c23_ic": float(c23_ic),
            "c23_lift": float(c23_lift),
            "c23_fresh_ic": float(fresh_ic),
            "c23_fresh_lift": float(fresh_lift),
            "c23_yesterday_ic": float(yesterday_ic),
            "c23_yesterday_lift": float(yesterday_lift),
            "c23_2days_ic": float(results[results["name"] == "c23_2days"]["avg_ic"].iloc[0]) if not results.empty else 0,
            "c23_stale_ic": float(stale_ic),
            "c23_stale_lift": float(stale_lift),
            "c23_fresh_not_yesterday_ic": float(fresh_not_yesterday_ic),
            "c23_fresh_not_yesterday_lift": float(fresh_not_yesterday_lift),
            "carry_ic": float(carry_ic),
            "persistence": persistence,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": str(results_path),
            "yearly": str(yearly_path),
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"C23 (all): IC={c23_ic:.4f}, lift={c23_lift:+.4f}")
    print(f"\nTemporal states:")
    print(f"  c23_fresh (today): IC={fresh_ic:.4f}, lift={fresh_lift:+.4f}")
    print(f"  c23_yesterday: IC={yesterday_ic:.4f}, lift={yesterday_lift:+.4f}")
    print(f"  c23_stale: IC={stale_ic:.4f}, lift={stale_lift:+.4f}")
    print(f"  c23_fresh_not_yesterday: IC={fresh_not_yesterday_ic:.4f}, lift={fresh_not_yesterday_lift:+.4f}")
    print(f"\nCarry (yesterday - today): {carry_ic:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
