"""
H122 — Bid-Ask Spread Proxy Signal (Session 40)

Tests whether the effective bid-ask spread estimated from daily OHLCV data
(using the Corwin-Schultz 2012 high-low estimator) predicts next-day
cross-sectional returns.

Background:
- Corwin & Schultz (2012): effective spread = 2*(exp(α)-1)/(1+exp(α)) where
  α depends on consecutive-day high-low ranges.
- Low spread = liquid = easy to trade = more efficiently priced.
- High spread = illiquid = price impact costs = slower information incorporation.

In Vietnamese market context:
- ±7% price limits can create extremely wide H-L ranges on limit-hit days,
  artificially inflating spread estimates → xs_spread_spike detects these events.
- Stocks transitioning from high-spread to low-spread may be attracting new capital.

Features tested:
1. xs_spread_level_rank  — rank of 20d avg spread (high = illiquid)
2. xs_spread_spike_rank  — rank of today's spread / 20d avg spread
3. xs_spread_change_5d   — rank change in spread over 5 days (tightening = inflow)

Corwin-Schultz estimator details (two-day adjacent window):
  β_t = (ln H_t/L_t)² + (ln H_{t+1}/L_{t+1})²
  γ_t = (ln max(H_t,H_{t+1}) / min(L_t,L_{t+1}))²
  α_t = (√(2β_t) - √β_t) / (3 - 2√2) - √(γ_t / (3 - 2√2))
  spread_t = max(0, 2*(exp(α_t)-1)/(1+exp(α_t)))

Usage:
    conda run -n stocks python analysis/h122_bid_ask_spread_standalone.py
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
SPREAD_WINDOW = 20
SPREAD_MIN_DAYS = 10
C_CONST = 3.0 - 2.0 * np.sqrt(2.0)  # ≈ 0.1716


def corwin_schultz_spread(high: pd.Series, low: pd.Series) -> pd.Series:
    """Compute daily Corwin-Schultz two-day spread estimates."""
    ln_hl = np.log(high / low.replace(0, np.nan))
    # β uses current and next day's HL range² sum
    beta = ln_hl ** 2 + ln_hl.shift(-1) ** 2
    # γ uses the 2-day spanning high and low
    high2 = np.maximum(high, high.shift(-1))
    low2 = np.minimum(low, low.shift(-1))
    gamma = np.log(high2 / low2.replace(0, np.nan)) ** 2
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / C_CONST - np.sqrt(gamma / C_CONST)
    spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    # Clamp to [0, 1]: negative estimates = artifact, cap at 1
    return spread.clip(lower=0.0, upper=1.0)


def load_spread_panel() -> pd.DataFrame:
    parts = []
    for f in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "high", "low", "close"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 50:
            continue
        df["spread"] = corwin_schultz_spread(df["high"], df["low"])
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "spread"]])

    long = pd.concat(parts, ignore_index=True)
    print(f"  Loaded {len(long):,} rows, {long['ticker'].nunique()} tickers")
    return long


def build_spread_features(long: pd.DataFrame) -> pd.DataFrame:
    wide = long.pivot_table(index="time", columns="ticker", values="spread")

    spread_20d = wide.rolling(SPREAD_WINDOW, min_periods=SPREAD_MIN_DAYS).mean()
    spread_spike = wide / spread_20d.replace(0, np.nan)

    rank_today = spread_20d.rank(axis=1, method="average", ascending=True, pct=True)
    rank_5d_ago = rank_today.shift(5)
    rank_change_5d = rank_today - rank_5d_ago

    xs_level = spread_20d.rank(axis=1, method="average", ascending=True, pct=True)
    xs_spike = spread_spike.rank(axis=1, method="average", ascending=True, pct=True)
    xs_change = rank_change_5d.rank(axis=1, method="average", ascending=True, pct=True)

    def to_long(wide_df, col_name):
        return wide_df.reset_index().melt(id_vars="time", var_name="ticker", value_name=col_name)

    feat = (
        to_long(xs_level, "xs_spread_level_rank")
        .merge(to_long(xs_spike, "xs_spread_spike_rank"), on=["time", "ticker"])
        .merge(to_long(xs_change, "xs_spread_change_5d"), on=["time", "ticker"])
    )
    feat = feat.dropna(subset=["xs_spread_level_rank"])
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

    print("Loading OHLCV data for bid-ask spread proxy...")
    long = load_spread_panel()
    feat = build_spread_features(long)
    feat["time"] = pd.to_datetime(feat["time"])

    merged = s1.merge(feat, on=["time", "ticker"], how="inner")
    merged = merged.dropna(subset=["xs_spread_level_rank", "actual"])
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    features = ["xs_spread_level_rank", "xs_spread_spike_rank", "xs_spread_change_5d"]
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
    level_ic = results.get("xs_spread_level_rank", {}).get("avg_ic") or 0
    spike_ic = results.get("xs_spread_spike_rank", {}).get("avg_ic") or 0
    change_ic = results.get("xs_spread_change_5d", {}).get("avg_ic") or 0

    verdict = "PASS" if passing else "FAIL"
    reason = (
        f"Spread level rank: IC={level_ic:+.4f}. "
        f"Spread spike: IC={spike_ic:+.4f}. "
        f"Spread change 5d: IC={change_ic:+.4f}. "
        f"Corwin-Schultz estimator from daily H/L."
    )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "passing_features": passing,
        "features": results,
    }

    print("\nH122 BID-ASK SPREAD PROXY RESULTS")
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
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h122_bid_ask_spread_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h122_bid_ask_spread",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 40, "signal": "H122"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
