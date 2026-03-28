"""
H121 — Amihud Illiquidity Signal (Session 40)

Tests whether a stock's recent illiquidity (price impact per unit of trading
value) predicts next-day returns cross-sectionally.

Background:
- Amihud (2002): ILLIQ = |r_t| / V_t predicts expected returns.
  High illiquidity → high expected return (compensation for price impact risk).
- In Vietnam's retail market: small/illiquid stocks may be under-followed,
  providing alpha when they start attracting attention.
- Alternatively: stocks with UNUSUAL illiquidity (deviation from own baseline)
  may be experiencing microstructure stress → predictable the next day.

Features tested:
1. xs_illiq_level_rank  — rank of 20d avg ILLIQ (high = illiquid)
2. xs_illiq_spike_rank  — rank of (1d ILLIQ / 20d avg ILLIQ) [today's deviation]
3. xs_illiq_change_5d   — rank change in illiquidity over 5 days (improving liquidity)

ILLIQ units: |return_%| / (daily trading value in VND billions)

Hypotheses:
- H_level: High-ILLIQ stocks (small, illiquid) outperform on next day (less efficient)
- H_spike: Illiquidity spike today (unusual price impact) → reversal tomorrow
- H_change: Improving liquidity (capital inflow) → continuation

Usage:
    conda run -n stocks python analysis/h121_amihud_illiquidity_standalone.py
"""

from __future__ import annotations

import glob
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary

S1_PATH = REPO_ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"
STOCK_DIR = REPO_ROOT / "data" / "stock"
EXCLUDE = {"VNINDEX", "VN30"}

PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.60
ILLIQ_WINDOW = 20
ILLIQ_MIN_DAYS = 10  # minimum days of history for illiq rolling calc
VALUE_SCALE = 1e9    # scale daily value to VND billions


def load_ohlcv_panel() -> pd.DataFrame:
    parts = []
    for f in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "close", "volume"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 50:
            continue
        df["ticker"] = ticker
        # Daily trading value proxy: close × volume (in VND, scale to billions)
        df["daily_value"] = df["close"] * df["volume"] / VALUE_SCALE
        df["ret1"] = df["close"].pct_change(1)
        parts.append(df[["time", "ticker", "ret1", "daily_value"]])

    long = pd.concat(parts, ignore_index=True)
    print(f"  Loaded {len(long):,} rows, {long['ticker'].nunique()} tickers")
    return long


def build_illiq_features(long: pd.DataFrame) -> pd.DataFrame:
    """Compute Amihud illiquidity features via vectorized pivot operations."""
    # Raw ILLIQ = |ret| / value (avoid divide by zero)
    long = long.copy()
    long["illiq_raw"] = long["ret1"].abs() / long["daily_value"].replace(0, np.nan)

    # Wide pivot per-metric
    wide_illiq = long.pivot_table(index="time", columns="ticker", values="illiq_raw")
    wide_value = long.pivot_table(index="time", columns="ticker", values="daily_value")

    # Rolling 20d averages
    illiq_20d = wide_illiq.rolling(ILLIQ_WINDOW, min_periods=ILLIQ_MIN_DAYS).mean()
    value_20d = wide_value.rolling(ILLIQ_WINDOW, min_periods=ILLIQ_MIN_DAYS).mean()

    # 1d ILLIQ normalized by own 20d baseline (spike)
    illiq_spike = wide_illiq / illiq_20d

    # 5d rank change: rank today vs rank 5 days ago
    illiq_rank_today = illiq_20d.rank(axis=1, method="average", ascending=True, pct=True)
    illiq_rank_5d_ago = illiq_rank_today.shift(5)
    illiq_rank_change_5d = illiq_rank_today - illiq_rank_5d_ago

    # Cross-sectional ranks
    xs_level = illiq_20d.rank(axis=1, method="average", ascending=True, pct=True)
    xs_spike = illiq_spike.rank(axis=1, method="average", ascending=True, pct=True)
    xs_change = illiq_rank_change_5d.rank(axis=1, method="average", ascending=True, pct=True)

    # Melt to long form
    def to_long(wide, col_name):
        return wide.reset_index().melt(id_vars="time", var_name="ticker", value_name=col_name)

    feat = (
        to_long(xs_level, "xs_illiq_level_rank")
        .merge(to_long(xs_spike, "xs_illiq_spike_rank"), on=["time", "ticker"])
        .merge(to_long(xs_change, "xs_illiq_change_5d"), on=["time", "ticker"])
    )
    feat = feat.dropna(subset=["xs_illiq_level_rank"])
    return feat


def yearly_ic(df: pd.DataFrame, score_col: str, target_col: str = "actual") -> list[dict]:
    rows = []
    for y, g in df.groupby(df["time"].dt.year):
        gg = g[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 500:
            continue
        rho, p = spearmanr(gg[score_col], gg[target_col])
        rows.append({
            "year": int(y),
            "n": int(len(gg)),
            "ic": float(np.asarray(rho).flat[0]),
            "p_value": float(np.asarray(p).flat[0]),
        })
    return rows


def summarize_ic(rows: list[dict]) -> dict:
    if not rows:
        return {"avg_ic": None, "pos_years": 0, "years": 0, "pct_years_positive": None}
    ics = [r["ic"] for r in rows]
    pos = sum(1 for ic in ics if ic > 0)
    return {
        "avg_ic": float(np.mean(ics)),
        "pos_years": pos,
        "years": len(rows),
        "pct_years_positive": float(pos / len(rows)),
        "yearly": rows,
    }


def main():
    s1 = pd.read_parquet(S1_PATH)
    s1["time"] = pd.to_datetime(s1["time"])
    s1 = s1[s1["time"].dt.year <= 2025]

    print("Loading OHLCV data for Amihud illiquidity...")
    long = load_ohlcv_panel()
    feat = build_illiq_features(long)
    feat["time"] = pd.to_datetime(feat["time"])

    merged = s1.merge(feat, on=["time", "ticker"], how="inner")
    merged = merged.dropna(subset=["xs_illiq_level_rank", "actual"])
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    features = ["xs_illiq_level_rank", "xs_illiq_spike_rank", "xs_illiq_change_5d"]
    results = {}
    for feat_col in features:
        ic_rows = yearly_ic(merged, feat_col)
        ic_sum = summarize_ic(ic_rows)
        clean = merged[[feat_col, "xs_proba"]].replace([np.inf, -np.inf], np.nan).dropna()
        corr = (
            float(np.asarray(spearmanr(clean[feat_col], clean["xs_proba"]).statistic).flat[0])
            if len(clean) > 100
            else float("nan")
        )
        avg_ic = ic_sum["avg_ic"] or 0
        passed = (
            abs(avg_ic) > PASS_IC
            and abs(corr) < PASS_CORR
            and (ic_sum["pct_years_positive"] or 0) >= PASS_PCT_YEARS
        )
        results[feat_col] = {
            **ic_sum,
            "corr_with_s1": corr,
            "gate_pass": passed,
        }

    passing = [f for f, r in results.items() if r.get("gate_pass")]
    level_ic = results.get("xs_illiq_level_rank", {}).get("avg_ic") or 0
    spike_ic = results.get("xs_illiq_spike_rank", {}).get("avg_ic") or 0
    change_ic = results.get("xs_illiq_change_5d", {}).get("avg_ic") or 0

    verdict = "PASS" if passing else "FAIL"
    reason = (
        f"Illiquidity level rank: IC={level_ic:+.4f}. "
        f"Illiquidity spike: IC={spike_ic:+.4f}. "
        f"Illiquidity change 5d: IC={change_ic:+.4f}. "
        f"Amihud ILLIQ = |return| / trading_value (VND billions)."
    )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "passing_features": passing,
        "features": results,
    }

    print("\nH121 AMIHUD ILLIQUIDITY RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(f"  {'Feature':<30s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  Gate")
    for feat_col in features:
        r = results.get(feat_col, {})
        ic_val = r.get("avg_ic") or 0
        gate = "PASS" if r.get("gate_pass") else "fail"
        print(
            f"  {feat_col:<30s}  {ic_val:+.4f}  {r['pos_years']:>2d}/{r['years']:<2d}   "
            f"{r['corr_with_s1']:+.3f}   {gate}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h121_amihud_illiquidity_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h121_amihud_illiquidity",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 40, "signal": "H121"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
