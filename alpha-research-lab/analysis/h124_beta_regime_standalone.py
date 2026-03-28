"""
H124 — Beta Regime Signal (Session 42)

Tests whether rolling 60d beta vs VNINDEX predicts next-day cross-sectional
returns, and whether the effect is stronger for low-beta or high-beta names.

Background:
- Beta captures market co-movement rather than absolute momentum.
- In a retail-led market, lower-beta names may behave as defensive shelters,
  while higher-beta names may get more speculative flow.
- This test checks which side of the beta spectrum is rewarded cross-sectionally.

Signals tested:
1. xs_beta_60d_rank      — cross-sectional rank of 60d beta vs VNINDEX
2. xs_low_beta_60d       — 1 - xs_beta_60d_rank (low-beta orientation)

Target: actual (1-day barrier label from S1) — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h124_beta_regime_standalone.py
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
BETA_WINDOW = 60
BETA_MIN_DAYS = 40


def load_returns_panel() -> tuple[pd.DataFrame, pd.Series]:
    vni = pd.read_parquet(STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet", columns=["time", "close"])
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time")
    vni["vni_ret1"] = vni["close"].pct_change(1)
    vni = vni.set_index("time")
    vni_ret1 = vni["vni_ret1"]

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
        if len(df) < BETA_WINDOW + 10:
            continue
        df["ticker"] = ticker
        df["ret1"] = df["close"].pct_change(1)
        parts.append(df[["time", "ticker", "ret1"]])

    long = pd.concat(parts, ignore_index=True)
    print(f"  Loaded {len(long):,} rows, {long['ticker'].nunique()} tickers")
    return long, vni_ret1


def build_features(long: pd.DataFrame, vni_ret1: pd.Series) -> pd.DataFrame:
    wide = long.pivot_table(index="time", columns="ticker", values="ret1").sort_index()
    vni = vni_ret1.reindex(wide.index)

    vni_mean = vni.rolling(BETA_WINDOW, min_periods=BETA_MIN_DAYS).mean()
    vni_var = vni.rolling(BETA_WINDOW, min_periods=BETA_MIN_DAYS).var(ddof=0)
    stock_mean = wide.rolling(BETA_WINDOW, min_periods=BETA_MIN_DAYS).mean()
    stock_xy_mean = wide.mul(vni, axis=0).rolling(BETA_WINDOW, min_periods=BETA_MIN_DAYS).mean()

    beta = (stock_xy_mean - stock_mean.mul(vni_mean, axis=0)).div(vni_var.replace(0, np.nan), axis=0)
    xs_rank = beta.rank(axis=1, method="average", ascending=True, pct=True)
    xs_low = 1.0 - xs_rank

    def to_long(wide_df: pd.DataFrame, col_name: str) -> pd.DataFrame:
        return wide_df.reset_index().melt(id_vars="time", var_name="ticker", value_name=col_name)

    feat = (
        to_long(xs_rank, "xs_beta_60d_rank")
        .merge(to_long(xs_low, "xs_low_beta_60d"), on=["time", "ticker"])
    )
    feat = feat.dropna(subset=["xs_beta_60d_rank"])
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

    print("Loading OHLCV data for beta regime...")
    long, vni_ret1 = load_returns_panel()
    feat = build_features(long, vni_ret1)
    feat["time"] = pd.to_datetime(feat["time"])

    merged = s1.merge(feat, on=["time", "ticker"], how="inner")
    merged = merged.dropna(subset=["xs_beta_60d_rank", "actual"])
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    features = ["xs_beta_60d_rank", "xs_low_beta_60d"]
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
    high_ic = results.get("xs_beta_60d_rank", {}).get("avg_ic") or 0
    low_ic = results.get("xs_low_beta_60d", {}).get("avg_ic") or 0

    if "xs_low_beta_60d" in passing:
        verdict = "PASS"
        reason = (
            f"60d beta regime favors low-beta names: xs_beta_60d_rank IC={high_ic:+.4f}, "
            f"xs_low_beta_60d IC={low_ic:+.4f}."
        )
    elif "xs_beta_60d_rank" in passing:
        verdict = "PASS"
        reason = (
            f"60d beta regime favors high-beta names: xs_beta_60d_rank IC={high_ic:+.4f}, "
            f"xs_low_beta_60d IC={low_ic:+.4f}."
        )
    elif passing:
        verdict = "PASS"
        reason = f"Gate passed by: {', '.join(passing)}"
    else:
        verdict = "FAIL"
        reason = (
            f"No beta-regime feature passes gate. xs_beta_60d_rank IC={high_ic:+.4f}, "
            f"xs_low_beta_60d IC={low_ic:+.4f}. Beta does not create a useful cross-sectional edge."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": "xs_beta_60d_rank",
        "passing_features": passing,
        "features": results,
    }

    print("\nH124 BETA REGIME RESULTS")
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
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h124_beta_regime_details.json"
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h124_beta_regime",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 42, "signal": "H124"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
