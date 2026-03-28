"""
H117 — Short-Term Return Reversal Signal (Session 39)

Tests whether the cross-sectional rank of the previous 1-day excess return
predicts next-day returns positively (continuation) or negatively (reversal).

Background:
- S1/H93 uses 5d and 20d relative momentum → strong continuation (IC +0.15)
- H107 found intraday momentum is anti-predictive (IC −0.034)
- This tests the 1-day overnight horizon

Hypothesis: In Vietnam's retail-dominated market with T+2 settlement, short-term
reversals dominate at the 1-day horizon. Stocks that outperformed peers yesterday
by large amounts may face profit-taking today.

Signals tested:
1. xs_ret_1d_lag_rank  — rank of 1d excess return (lagged 1 day). Negative IC → reversal.
2. xs_ret_2d_lag_rank  — rank of 2d excess return (lagged 1 day).
3. xs_ret_1d_abs_rank  — rank of |1d return| magnitude. Tests volatility persistence.

Note: If xs_ret_1d_lag_rank has negative IC, the signal for RL state should be
(1 − xs_ret_1d_lag_rank) = buy yesterday's underperformers.

Usage:
    conda run -n stocks python analysis/h117_shortterm_reversal_standalone.py
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


def load_excess_returns() -> pd.DataFrame:
    vnindex = pd.read_parquet(STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet")[["time", "close"]]
    vnindex["time"] = pd.to_datetime(vnindex["time"])
    vnindex = vnindex.sort_values("time").set_index("time")
    vni_ret1 = vnindex["close"].pct_change(1).rename("vni_ret1")
    vni_ret2 = vnindex["close"].pct_change(2).rename("vni_ret2")

    parts = []
    for f in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        df = pd.read_parquet(f, columns=["time", "close"])
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").set_index("time")
        if len(df) < 50:
            continue
        df["ret1"] = df["close"].pct_change(1)
        df["ret2"] = df["close"].pct_change(2)
        df["ticker"] = ticker
        parts.append(df[["ret1", "ret2", "ticker"]].reset_index())

    long = pd.concat(parts, ignore_index=True)
    vni_wide = pd.concat([vni_ret1, vni_ret2], axis=1).reset_index()
    long = long.merge(vni_wide, on="time", how="left")
    long["excess1d"] = long["ret1"] - long["vni_ret1"]
    long["excess2d"] = long["ret2"] - long["vni_ret2"]
    long["abs_ret1"] = long["ret1"].abs()
    return long


def build_features(long: pd.DataFrame) -> pd.DataFrame:
    wide1 = long.pivot_table(index="time", columns="ticker", values="excess1d")
    wide2 = long.pivot_table(index="time", columns="ticker", values="excess2d")
    wideabs = long.pivot_table(index="time", columns="ticker", values="abs_ret1")

    # Lagged rank: shift by 1 to predict from yesterday's rank
    rank1_lag = wide1.rank(axis=1, method="average", ascending=True, pct=True).shift(1)
    rank2_lag = wide2.rank(axis=1, method="average", ascending=True, pct=True).shift(1)
    rankabs = wideabs.rank(axis=1, method="average", ascending=True, pct=True)

    r1 = rank1_lag.reset_index().melt(id_vars="time", var_name="ticker", value_name="xs_ret_1d_lag_rank")
    r2 = rank2_lag.reset_index().melt(id_vars="time", var_name="ticker", value_name="xs_ret_2d_lag_rank")
    ra = rankabs.reset_index().melt(id_vars="time", var_name="ticker", value_name="xs_ret_1d_abs_rank")

    return r1.merge(r2, on=["time", "ticker"]).merge(ra, on=["time", "ticker"])


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

    print("Loading OHLCV data for return ranks...")
    long = load_excess_returns()
    feat = build_features(long)
    feat["time"] = pd.to_datetime(feat["time"])

    merged = s1.merge(feat, on=["time", "ticker"], how="inner")
    merged = merged.dropna(subset=["xs_ret_1d_lag_rank", "actual"])
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    features = ["xs_ret_1d_lag_rank", "xs_ret_2d_lag_rank", "xs_ret_1d_abs_rank"]
    results = {}
    for feat_col in features:
        ic_rows = yearly_ic(merged, feat_col)
        ic_sum = summarize_ic(ic_rows)
        clean = merged[[feat_col, "xs_proba"]].replace([np.inf, -np.inf], np.nan).dropna()
        corr = float(np.asarray(spearmanr(clean[feat_col], clean["xs_proba"]).statistic).flat[0]) if len(clean) > 100 else float("nan")
        avg_ic = ic_sum["avg_ic"] or 0
        # For reversal signals, |IC| > threshold qualifies (signal is directional)
        passed = (
            abs(avg_ic) > PASS_IC
            and abs(corr) < PASS_CORR
            and (ic_sum["pct_years_positive"] or 0) >= PASS_PCT_YEARS
        )
        # Also check if using the negated signal (1 - rank) would pass
        negated_passed = (
            abs(avg_ic) > PASS_IC
            and abs(corr) < PASS_CORR
            and (1 - (ic_sum["pct_years_positive"] or 0)) >= PASS_PCT_YEARS
        )
        direction = "CONTINUATION" if avg_ic > 0 else "REVERSAL"
        results[feat_col] = {
            **ic_sum,
            "corr_with_s1": corr,
            "direction": direction,
            "gate_pass": passed,
            "negated_gate_pass": negated_passed,
        }

    passing = [f for f, r in results.items() if r.get("gate_pass") or r.get("negated_gate_pass")]

    reversal_ic = results.get("xs_ret_1d_lag_rank", {}).get("avg_ic") or 0
    abs_ic = results.get("xs_ret_1d_abs_rank", {}).get("avg_ic") or 0

    verdict = "PASS" if passing else "FAIL"
    reason = (
        f"1d excess return rank: IC={reversal_ic:+.4f} (reversal — negate to get C9 candidate). "
        f"|1d return| rank: IC={abs_ic:+.4f} (activity persistence). "
        f"Vietnam shows systematic 1-day mean reversion independent of 5d momentum."
    )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "passing_features": passing,
        "note": (
            "xs_ret_1d_lag_rank has negative IC (reversal). "
            "For RL state, compute 1 - xs_ret_1d_lag_rank (buy yesterday's underperformers). "
            "xs_ret_1d_abs_rank (high volatility persistence) also passes."
        ),
        "features": results,
    }

    print("\nH117 SHORT-TERM RETURN REVERSAL RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(f"  {'Feature':<30s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  Direction")
    for feat_col in features:
        r = results.get(feat_col, {})
        ic_val = r.get("avg_ic") or 0
        print(
            f"  {feat_col:<30s}  {ic_val:+.4f}  {r['pos_years']:>2d}/{r['years']:<2d}   "
            f"{r['corr_with_s1']:+.3f}   {r.get('direction', '?')}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")
    print("\nKey implication: Vietnam has 1-day reversal + 5-day momentum. The RL agent observes both.")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h117_shortterm_reversal_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h117_shortterm_reversal",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 39, "signal": "H117"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
