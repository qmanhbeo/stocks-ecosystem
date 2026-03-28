"""
H123 — 3-Month Reversal Signal (Session 42)

Tests whether the cross-sectional rank of 60d excess return, lagged by 1 day,
predicts next-day returns positively (continuation) or negatively (reversal).

Background:
- H93 captures medium-term continuation at 5d/20d horizons.
- Global equity literature often finds 3-12 month reversal.
- This tests whether Vietnam has a medium-horizon reversal pocket beneath the
  stronger short-term reversal and medium-term momentum structure.

Signals tested:
1. xs_ret_60d_lag_rank     — rank of 60d excess return vs VNINDEX, lagged 1 day
2. xs_reversal_60d         — 1 - xs_ret_60d_lag_rank (reversal orientation)

Target: actual (1-day barrier label from S1) — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h123_3m_reversal_standalone.py
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
LOOKBACK_DAYS = 60
MIN_DAYS = 50


def load_60d_excess_panel() -> pd.DataFrame:
    vni = pd.read_parquet(STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet", columns=["time", "close"])
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time")
    vni["vni_ret60"] = vni["close"].pct_change(LOOKBACK_DAYS)
    vni = vni[["time", "vni_ret60"]]

    parts = []
    for f in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "close"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < LOOKBACK_DAYS + 10:
            continue
        df["ticker"] = ticker
        df["ret60"] = df["close"].pct_change(LOOKBACK_DAYS)
        parts.append(df[["time", "ticker", "ret60"]])

    long = pd.concat(parts, ignore_index=True)
    long = long.merge(vni, on="time", how="left")
    long["excess60"] = long["ret60"] - long["vni_ret60"]
    print(f"  Loaded {len(long):,} rows, {long['ticker'].nunique()} tickers")
    return long


def build_features(long: pd.DataFrame) -> pd.DataFrame:
    wide = long.pivot_table(index="time", columns="ticker", values="excess60")
    xs_rank = wide.rank(axis=1, method="average", ascending=True, pct=True).shift(1)
    xs_rev = 1.0 - xs_rank

    def to_long(wide_df: pd.DataFrame, col_name: str) -> pd.DataFrame:
        return wide_df.reset_index().melt(id_vars="time", var_name="ticker", value_name=col_name)

    feat = (
        to_long(xs_rank, "xs_ret_60d_lag_rank")
        .merge(to_long(xs_rev, "xs_reversal_60d"), on=["time", "ticker"])
    )
    feat = feat.dropna(subset=["xs_ret_60d_lag_rank"])
    return feat


def yearly_ic(df: pd.DataFrame, score_col: str, target_col: str = "actual") -> list[dict]:
    rows = []
    for y, g in df.groupby(df["time"].dt.year):
        gg = g[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 500:
            continue
        rho, p = spearmanr(gg[score_col], gg[target_col])
        rows.append(
            {
                "year": int(y),
                "n": int(len(gg)),
                "ic": float(np.asarray(rho).flat[0]),
                "p_value": float(np.asarray(p).flat[0]),
            }
        )
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

    print("Loading OHLCV data for 60d reversal...")
    long = load_60d_excess_panel()
    feat = build_features(long)
    feat["time"] = pd.to_datetime(feat["time"])

    merged = s1.merge(feat, on=["time", "ticker"], how="inner")
    merged = merged.dropna(subset=["xs_ret_60d_lag_rank", "actual"])
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    features = ["xs_ret_60d_lag_rank", "xs_reversal_60d"]
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
    raw_ic = results.get("xs_ret_60d_lag_rank", {}).get("avg_ic") or 0
    rev_ic = results.get("xs_reversal_60d", {}).get("avg_ic") or 0

    if "xs_reversal_60d" in passing:
        verdict = "PASS"
        reason = (
            f"60d excess-return rank reverses: xs_ret_60d_lag_rank IC={raw_ic:+.4f}, "
            f"xs_reversal_60d IC={rev_ic:+.4f}. Medium-horizon reversal exists."
        )
    elif passing:
        verdict = "PASS"
        reason = f"Gate passed by: {', '.join(passing)}"
    else:
        verdict = "FAIL"
        reason = (
            f"No 60d reversal feature passes gate. xs_ret_60d_lag_rank IC={raw_ic:+.4f}, "
            f"xs_reversal_60d IC={rev_ic:+.4f}. Medium-horizon reversal not robust."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": "xs_ret_60d_lag_rank",
        "passing_features": passing,
        "features": results,
    }

    print("\nH123 3-MONTH REVERSAL RESULTS")
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
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h123_3m_reversal_details.json"
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h123_3m_reversal",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 42, "signal": "H123"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
