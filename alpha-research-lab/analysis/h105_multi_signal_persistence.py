"""
H105: Multi-Signal × Persistence Stacking

Hypothesis: F445 (composite_2+ = IC 0.2445) + F441/F442 (persistence/accumulation)
Are sustained multi-signal stocks even stronger?

Test: composite_2plus with persistence/accumulation filter vs composite_2plus alone

Pass criterion: composite_2plus × persistence/accumulation beats composite_2plus alone by > +0.01 IC
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import re

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


BRANCH_NAME = "multi_signal_persistence_stacking"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "F445 (composite_2+ = IC 0.2445) + F441/F442 (persistence/accumulation). "
        "Are sustained multi-signal stocks even stronger?"
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H105: Multi-Signal × Persistence Stacking")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_amihud(df):
    """Compute Amihud illiquidity: |return| / (volume * price) in billions VND."""
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

    # Load OHLCV for Amihud (C23)
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

    # Load order_stats for vol regime and signals
    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

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
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_order_volume", "sell_order_volume"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    panel = panel.sort_values(["ticker", "time"])

    # Volatility regime
    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])

    # Vol regime (top 20% = expansion)
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    # Amihud quintiles (high = illiquid)
    amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
    panel["high_illiq"] = amihud_rank >= 0.8

    # Buy-sell imbalance
    panel["buy_sell_imbalance"] = (
        (panel["buy_order_volume"] - panel["sell_order_volume"]) /
        (panel["buy_order_volume"] + panel["sell_order_volume"] + 1)
    )
    panel = panel.dropna(subset=["buy_sell_imbalance"])
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8

    # Individual signal flags (C23/C24/C25/C26)
    panel["c23_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["c24_ceiling_expansion"] = (panel["pct_change"] >= 5.0) & panel["vol_expansion"]
    panel["c25_vwap_expansion"] = (panel["pct_change"] <= -2.0) & panel["vol_expansion"]
    panel["c26_buy_heavy_illiq_exp"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]

    # Count signals per ticker-day
    panel["signal_count"] = (
        panel["c23_illiq_expansion"].astype(int) +
        panel["c24_ceiling_expansion"].astype(int) +
        panel["c25_vwap_expansion"].astype(int) +
        panel["c26_buy_heavy_illiq_exp"].astype(int)
    )

    # Composite 2+ (AND): 2+ signals
    panel["composite_2plus"] = panel["signal_count"] >= 2

    # Active state: C16 <= 0.2 (from order pressure panel)
    order_pressure_path = data_path("features/xs_order_pressure_daily.parquet")
    try:
        order_pressure = pd.read_parquet(order_pressure_path)
        order_pressure = order_pressure.rename(columns={"date": "time"})
        order_pressure["time"] = pd.to_datetime(order_pressure["time"])
        order_pressure = order_pressure[order_pressure["time"].dt.year <= 2025]
        
        if "order_volume_ratio_rank" in order_pressure.columns:
            panel = panel.merge(
                order_pressure[["time", "ticker", "order_volume_ratio_rank"]],
                on=["time", "ticker"],
                how="left",
            )
            
            # Active state: low C16 (rank <= 0.2)
            panel["active_state"] = panel["order_volume_ratio_rank"] <= 0.2
            
            # Persistence: active days in last 10 days (from F441)
            panel = panel.sort_values(["ticker", "time"])
            panel["active_1d_lag"] = panel.groupby("ticker")["active_state"].shift(1)
            
            # Rolling 9-day count of active days
            panel["active_9d_count"] = panel.groupby("ticker")["active_1d_lag"].transform(
                lambda x: x.rolling(window=9, min_periods=5).sum()
            )
            panel["persistence_ratio"] = panel["active_9d_count"] / 9.0
            
            # Persistence quintiles
            persist_rank = panel.groupby("time", sort=False)["persistence_ratio"].rank(method="average", pct=True)
            panel["persist_q4"] = persist_rank >= 0.75  # sustained
            
            # Accumulation (from F442): cumulative days in active state in last 30 days
            panel["active_30d_count"] = panel.groupby("ticker")["active_1d_lag"].transform(
                lambda x: x.rolling(window=30, min_periods=10).sum()
            )
            panel["accumulation_q4"] = panel["active_30d_count"] >= 20  # 20+ days in last 30
            
            # Duration filter (from H534): 8+ consecutive days
            panel["consecutive_active"] = panel.groupby("ticker")["active_state"].transform(
                lambda x: x.groupby((~x).cumsum()).cumsum()
            )
            panel["duration_8pl"] = panel["consecutive_active"] >= 8
            
    except Exception as e:
        print(f"Warning: Could not load order pressure data: {e}")
        panel["active_state"] = False
        panel["persist_q4"] = False
        panel["accumulation_q4"] = False
        panel["duration_8pl"] = False

    # Multi-signal × persistence combinations
    panel["composite_2plus_persist_q4"] = panel["composite_2plus"] & panel["persist_q4"]
    panel["composite_2plus_accum_q4"] = panel["composite_2plus"] & panel["accumulation_q4"]
    panel["composite_2plus_duration_8pl"] = panel["composite_2plus"] & panel["duration_8pl"]

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"Composite 2+: {panel['composite_2plus'].sum()}")
    print(f"Composite 2+ + persist Q4: {panel['composite_2plus_persist_q4'].sum()}")
    print(f"Composite 2+ + accum Q4: {panel['composite_2plus_accum_q4'].sum()}")
    print(f"Composite 2+ + duration 8+: {panel['composite_2plus_duration_8pl'].sum()}")

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("composite_2plus", "2+ signals (AND) - from F445", family="multi_signal"),
    StateSpec("persist_q4", "Persistence Q4 (sustained 75%+)", family="persistence"),
    StateSpec("accumulation_q4", "Accumulation Q4 (20+ days in 30)", family="persistence"),
    StateSpec("duration_8pl", "Duration 8+ consecutive days", family="persistence"),
    StateSpec("composite_2plus_persist_q4", "Multi-signal + persistence Q4", family="combo"),
    StateSpec("composite_2plus_accum_q4", "Multi-signal + accumulation Q4", family="combo"),
    StateSpec("composite_2plus_duration_8pl", "Multi-signal + duration 8+", family="combo"),
]


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")
    panel = load_panel(args, spec)

    available_cols = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS_FILTERED = [s for s in STATE_SPECS if s.name in available_cols]

    validate_state_columns(panel, [state.name for state in STATE_SPECS_FILTERED], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS_FILTERED,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    print("\n=== H105: Multi-Signal × Persistence Stacking ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0
    composite_2plus_ic = results[results["name"] == "composite_2plus"]["avg_ic"].iloc[0] if "composite_2plus" in results["name"].values else 0
    
    # Combo results
    combo_persist_q4_ic = results[results["name"] == "composite_2plus_persist_q4"]["avg_ic"].iloc[0] if "composite_2plus_persist_q4" in results["name"].values else np.nan
    combo_accum_q4_ic = results[results["name"] == "composite_2plus_accum_q4"]["avg_ic"].iloc[0] if "composite_2plus_accum_q4" in results["name"].values else np.nan
    combo_duration_ic = results[results["name"] == "composite_2plus_duration_8pl"]["avg_ic"].iloc[0] if "composite_2plus_duration_8pl" in results["name"].values else np.nan

    # Lifts
    lift_persist = combo_persist_q4_ic - composite_2plus_ic if pd.notna(combo_persist_q4_ic) else 0
    lift_accum = combo_accum_q4_ic - composite_2plus_ic if pd.notna(combo_accum_q4_ic) else 0
    lift_duration = combo_duration_ic - composite_2plus_ic if pd.notna(combo_duration_ic) else 0

    best_lift = max(lift_persist, lift_accum, lift_duration)

    # Decision
    if best_lift > 0.01:
        decision = "PASSED"
    elif best_lift > 0.005:
        decision = "MIXED"
    elif best_lift > 0:
        decision = "MIXED (marginal)"
    else:
        decision = "FAILED"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "composite_2plus_ic": float(composite_2plus_ic),
            "combo_persist_q4_ic": float(combo_persist_q4_ic) if pd.notna(combo_persist_q4_ic) else None,
            "combo_accum_q4_ic": float(combo_accum_q4_ic) if pd.notna(combo_accum_q4_ic) else None,
            "combo_duration_8pl_ic": float(combo_duration_ic) if pd.notna(combo_duration_ic) else None,
            "lift_persist_q4": float(lift_persist),
            "lift_accum_q4": float(lift_accum),
            "lift_duration_8pl": float(lift_duration),
            "best_lift": float(best_lift),
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS_FILTERED],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(f"\nBaseline IC: {baseline_ic:.4f}")
    print(f"Composite 2+ (F445): {composite_2plus_ic:.4f}")
    print(f"Composite 2+ + persist Q4: {combo_persist_q4_ic:.4f} (lift: {lift_persist:+.4f})")
    print(f"Composite 2+ + accum Q4: {combo_accum_q4_ic:.4f} (lift: {lift_accum:+.4f})")
    print(f"Composite 2+ + duration 8+: {combo_duration_ic:.4f} (lift: {lift_duration:+.4f})")
    print(f"\nBest lift: {best_lift:.4f}")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()