"""
C2 standalone insider signal backtest.

Goal:
- On days insider signal fires, rank stocks by insider_net_plan_5d.
- Measure next-5d relative return (vs VNINDEX) for top-N picks.

Inputs:
- data/features/xs_insider_features.parquet
- data/stock/gia_lich_su_*_1D.parquet

Outputs:
- console report
- artifacts/run_summaries/*_c2_insider_standalone_standalone_signal.json
"""

from __future__ import annotations

import json
import glob
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_loader import load_data
from src.feature_engineering import generate_features
from src.run_summary import write_run_summary

INSIDER_PATH = ROOT / "data" / "features" / "xs_insider_features.parquet"
STOCK_DIR = ROOT / "data" / "stock"
INDEX_FILE = ROOT / "data" / "stock" / "gia_lich_su_VNINDEX_1D.parquet"
EXCLUDE = {"VNINDEX", "VN30"}


CFG = {
    "data": {
        "target_col": "future_rel_dir_5d",
        "start_date": "2012-01-01",
    },
    "features": {
        "base_cols": [],
        "use_lags": False,
        "use_ma": False,
        "use_ma_dist": True,
        "ma_windows": [5, 10, 20, 50],
        "use_rsi": True,
        "use_macd": True,
        "use_bb": True,
        "use_atr": True,
        "use_candle": True,
        "use_stoch": True,
        "use_willr": False,
        "use_adx": True,
        "use_hist_vol": True,
        "hist_vol_windows": [5, 10, 20],
        "use_cci": False,
        "use_volume_signals": False,
        "use_market_relative": True,
        "index_file": str(INDEX_FILE),
        "rel_lag_days": [1, 2, 3, 5, 10, 20],
        "use_macro": False,
        "use_cross_sectional": False,
        "use_news": False,
    },
    "model": {"type": "xgboost_classifier", "params": {}},
}


def load_future_rel_5d(start_date: str = "2012-01-01") -> pd.DataFrame:
    files = sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet")))
    parts: list[pd.DataFrame] = []
    for path in files:
        ticker = Path(path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        raw = load_data(path, start_date)
        if len(raw) < 300:
            continue
        feat = generate_features(raw, CFG)
        if "future_rel_return_5d" not in feat.columns:
            continue
        parts.append(feat[["time", "future_rel_return_5d"]].assign(ticker=ticker))

    out = pd.concat(parts, ignore_index=True)
    out = out.rename(columns={"time": "trading_day", "future_rel_return_5d": "fwd_rel_5d"})
    out["trading_day"] = pd.to_datetime(out["trading_day"])
    return out


def topn_daily(df: pd.DataFrame, n: int) -> pd.Series:
    return (
        df.sort_values(["trading_day", "insider_net_plan_5d"], ascending=[True, False])
        .groupby("trading_day", sort=True)
        .head(n)
        .groupby("trading_day", sort=True)["fwd_rel_5d"]
        .mean()
    )


def summarize_yearly(daily: pd.Series) -> pd.DataFrame:
    tbl = daily.rename("edge").reset_index()
    tbl["year"] = tbl["trading_day"].dt.year
    by_year = (
        tbl.groupby("year")["edge"]
        .agg(["count", "mean", "std"])
        .rename(columns={"count": "n_days", "mean": "avg_edge", "std": "edge_std"})
        .reset_index()
    )
    by_year["sharpe_proxy"] = np.where(
        by_year["edge_std"] > 0,
        by_year["avg_edge"] / by_year["edge_std"] * np.sqrt(252),
        np.nan,
    )
    return by_year


def main():
    insider = pd.read_parquet(INSIDER_PATH)
    insider["trading_day"] = pd.to_datetime(insider["trading_day"])

    future_rel = load_future_rel_5d()
    df = insider.merge(future_rel, on=["trading_day", "ticker"], how="inner")
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=["insider_net_plan_5d", "fwd_rel_5d"]).copy()

    fire = df[df["insider_net_plan_5d"] != 0].copy()
    fire["year"] = fire["trading_day"].dt.year

    ic_rows = []
    for y, g in fire.groupby("year", sort=True):
        if len(g) < 20:
            continue
        rho, p = spearmanr(g["insider_net_plan_5d"], g["fwd_rel_5d"])
        ic_rows.append({"year": int(y), "n": int(len(g)), "ic": float(rho), "p_value": float(p)})
    ic_df = pd.DataFrame(ic_rows)

    daily_top1 = topn_daily(fire, 1)
    daily_top3 = topn_daily(fire, 3)
    daily_top5 = topn_daily(fire, 5)

    yrs_top5 = summarize_yearly(daily_top5)

    coverage_rows = len(fire)
    coverage_pct = 100.0 * coverage_rows / len(df)
    fire_days = fire["trading_day"].nunique()
    all_days = df["trading_day"].nunique()

    pos_years_top5 = int((yrs_top5["avg_edge"] > 0).sum()) if len(yrs_top5) else 0

    summary = {
        "rows_total": int(len(df)),
        "rows_signal": int(coverage_rows),
        "coverage_pct": float(round(coverage_pct, 4)),
        "days_signal": int(fire_days),
        "days_total": int(all_days),
        "days_signal_pct": float(round(100.0 * fire_days / all_days, 4)),
        "avg_ic_signal_rows": float(ic_df["ic"].mean()) if len(ic_df) else None,
        "ic_pos_years": int((ic_df["ic"] > 0).sum()) if len(ic_df) else 0,
        "ic_years": int(len(ic_df)),
        "top1_avg_edge": float(daily_top1.mean()),
        "top3_avg_edge": float(daily_top3.mean()),
        "top5_avg_edge": float(daily_top5.mean()),
        "top5_sharpe_proxy": float(daily_top5.mean() / daily_top5.std() * np.sqrt(252)),
        "top5_pos_years": int(pos_years_top5),
        "top5_years": int(len(yrs_top5)),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_c2_insider_standalone_details.json"
    details_path.parent.mkdir(parents=True, exist_ok=True)
    details_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "yearly_top5": yrs_top5.to_dict(orient="records"),
                "yearly_ic": ic_df.to_dict(orient="records"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary_path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="c2_insider_standalone",
        summary=summary,
        artifacts={
            "insider_features": str(INSIDER_PATH),
            "details_json": str(details_path),
        },
        metadata={
            "signal_col": "insider_net_plan_5d",
            "target_col": "future_rel_return_5d",
            "topn": [1, 3, 5],
        },
    )

    print("\nC2 STANDALONE INSIDER TEST")
    print("=" * 72)
    print(f"Signal rows: {coverage_rows:,} / {len(df):,} ({coverage_pct:.2f}%)")
    print(f"Signal days: {fire_days:,} / {all_days:,} ({100.0 * fire_days / all_days:.2f}%)")
    if len(ic_df):
        print(
            f"IC avg: {ic_df['ic'].mean():+.4f} | "
            f"positive years: {(ic_df['ic'] > 0).sum()}/{len(ic_df)}"
        )
    print(f"Top1 avg edge (5d rel): {daily_top1.mean()*100:+.3f}%")
    print(f"Top3 avg edge (5d rel): {daily_top3.mean()*100:+.3f}%")
    print(f"Top5 avg edge (5d rel): {daily_top5.mean()*100:+.3f}%")
    print(f"Top5 sharpe proxy: {summary['top5_sharpe_proxy']:+.2f}")
    print(f"Top5 positive years: {pos_years_top5}/{len(yrs_top5)}")
    print(f"\nRun summary: {summary_path}")
    print(f"Details: {details_path}")


if __name__ == "__main__":
    main()
