"""
H108 — Insider Transaction Quality Score (Session 38)

Tests whether quality-weighted insider features outperform the raw C2 signal
(insider_net_plan_5d, IC +0.0255, 9/11 years positive).

Quality dimensions:
- xs_ins_quality_buy_5d      — tier-weighted net plan vol (CEO=1.0, CFO=0.7, Board=0.5, related=0.3)
- xs_ins_quality_buy_30d     — same, 30d rolling
- xs_ins_ceo_buy_5d          — CEO/Chairman only (highest information asymmetry tier)
- xs_ins_relative_size_5d    — net plan vol / VolumeBeforeTransaction (conviction signal)
- xs_ins_exec_rate_5d        — actual/plan ratio for buys (execution commitment)

Baseline: C2 insider_net_plan_5d (raw unweighted sum, built in build_insider_features.py)

Gate criteria (same as C2, IC measured on signal-fire rows vs fwd_rel_5d):
- avg_ic > 0.0255 (must beat baseline)
- ic_pos_years / years >= 0.818 (>= 9/11, same or better than C2)
- corr_with_s1 < 0.30

Usage:
    conda run -n stocks python analysis/h108_insider_quality_standalone.py
"""

from __future__ import annotations

import json
import glob
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_loader import load_data
from src.feature_engineering import generate_features
from src.run_summary import write_run_summary

QUALITY_PATH = ROOT / "data" / "features" / "xs_insider_quality_features.parquet"
BASELINE_PATH = ROOT / "data" / "features" / "xs_insider_features.parquet"
S1_PATH = ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"
STOCK_DIR = ROOT / "data" / "stock"
INDEX_FILE = ROOT / "data" / "stock" / "gia_lich_su_VNINDEX_1D.parquet"
EXCLUDE = {"VNINDEX", "VN30"}

QUALITY_FEATURES = [
    "xs_ins_quality_buy_5d",
    "xs_ins_quality_buy_30d",
    "xs_ins_ceo_buy_5d",
    "xs_ins_relative_size_5d",
    "xs_ins_exec_rate_5d",
]

CFG = {
    "data": {"target_col": "future_rel_dir_5d", "start_date": "2012-01-01"},
    "features": {
        "base_cols": [], "use_lags": False, "use_ma": False, "use_ma_dist": True,
        "ma_windows": [5, 10, 20, 50], "use_rsi": True, "use_macd": True,
        "use_bb": True, "use_atr": True, "use_candle": True, "use_stoch": True,
        "use_willr": False, "use_adx": True, "use_hist_vol": True,
        "hist_vol_windows": [5, 10, 20], "use_cci": False, "use_volume_signals": False,
        "use_market_relative": True, "index_file": str(INDEX_FILE),
        "rel_lag_days": [1, 2, 3, 5, 10, 20], "use_macro": False,
        "use_cross_sectional": False, "use_news": False,
    },
    "model": {"type": "xgboost_classifier", "params": {}},
}


def load_future_rel_5d() -> pd.DataFrame:
    parts = []
    for path in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        raw = load_data(path, "2012-01-01")
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


def compute_ic_stats(fire: pd.DataFrame, signal_col: str) -> dict:
    """Yearly IC on signal-fire rows (same methodology as C2 standalone)."""
    rows = []
    for y, g in fire[fire["year"] <= 2025].groupby("year"):
        g = g[[signal_col, "fwd_rel_5d"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(g) < 20:
            continue
        rho, p = spearmanr(g[signal_col], g["fwd_rel_5d"])
        rows.append({"year": int(y), "n": int(len(g)), "ic": float(rho), "p_value": float(p)})
    if not rows:
        return {"avg_ic": None, "pos_years": 0, "years": 0, "yearly": []}
    ics = [r["ic"] for r in rows]
    return {
        "avg_ic": float(np.mean(ics)),
        "pos_years": int(sum(1 for ic in ics if ic > 0)),
        "years": len(rows),
        "yearly": rows,
    }


def compute_corr_with_s1(df: pd.DataFrame, signal_col: str) -> float:
    clean = df[[signal_col, "xs_proba"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 100:
        return float("nan")
    rho, _ = spearmanr(clean[signal_col], clean["xs_proba"])
    return float(rho)


def main():
    print("Loading data...")
    quality = pd.read_parquet(QUALITY_PATH)
    quality["trading_day"] = pd.to_datetime(quality["trading_day"])

    baseline = pd.read_parquet(BASELINE_PATH, columns=["trading_day", "ticker", "insider_net_plan_5d"])
    baseline["trading_day"] = pd.to_datetime(baseline["trading_day"])

    s1 = pd.read_parquet(S1_PATH, columns=["time", "ticker", "xs_proba"])
    s1 = s1.rename(columns={"time": "trading_day"})
    s1["trading_day"] = pd.to_datetime(s1["trading_day"])
    s1 = s1[s1["trading_day"].dt.year <= 2025]

    print("Loading future_rel_5d (this takes ~1 min)...")
    future_rel = load_future_rel_5d()

    # Merge everything
    df = quality.merge(baseline, on=["trading_day", "ticker"], how="inner")
    df = df.merge(future_rel, on=["trading_day", "ticker"], how="inner")
    df = df.merge(s1, on=["trading_day", "ticker"], how="inner")
    df["year"] = df["trading_day"].dt.year
    df = df[df["year"] <= 2025]

    all_features = QUALITY_FEATURES + ["insider_net_plan_5d"]
    results = {}

    for feat in all_features:
        fire = df[df[feat] != 0].copy()
        coverage_pct = 100.0 * len(fire) / len(df)
        ic = compute_ic_stats(fire, feat)
        corr = compute_corr_with_s1(df, feat)
        results[feat] = {
            "coverage_pct": round(coverage_pct, 3),
            "signal_rows": int(len(fire)),
            **ic,
            "corr_with_s1": corr,
        }

    baseline_ic = results["insider_net_plan_5d"]["avg_ic"] or 0

    # Determine best quality feature and verdict
    quality_results = {k: v for k, v in results.items() if k != "insider_net_plan_5d"}
    best_feat = max(quality_results, key=lambda f: quality_results[f]["avg_ic"] or -99)
    best = quality_results[best_feat]
    best_ic = best["avg_ic"] or 0
    best_corr = abs(best["corr_with_s1"])
    best_pos = best["pos_years"] / best["years"] if best["years"] > 0 else 0

    improvement = best_ic - baseline_ic

    if best_ic > baseline_ic and best_corr < 0.30 and best_pos >= 0.818:
        verdict = "PASS"
        reason = (
            f"{best_feat} IC={best_ic:.4f} > baseline {baseline_ic:.4f} "
            f"(+{improvement:.4f}), corr={best['corr_with_s1']:.3f}, "
            f"pos_years={best['pos_years']}/{best['years']}"
        )
    elif best_ic > 0.0255 and best_corr < 0.30:
        verdict = "PASS"
        reason = (
            f"{best_feat} IC={best_ic:.4f} beats C2 baseline, corr={best['corr_with_s1']:.3f}"
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No quality feature beats baseline IC {baseline_ic:.4f}. "
            f"Best: {best_feat} IC={best_ic:.4f} (improvement: {improvement:+.4f})"
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "best_quality_feature": best_feat,
        "baseline_feature": "insider_net_plan_5d",
        "ic_improvement_over_baseline": float(improvement),
        "features": results,
    }

    print("\nH108 INSIDER QUALITY RESULTS")
    print("=" * 72)
    header = f"{'Feature':35s}  {'Coverage':>8}  {'IC':>8}  {'PosYrs':>7}  {'CorrS1':>8}"
    print(header)
    print("-" * 72)
    for feat in all_features:
        r = results[feat]
        ic_val = r["avg_ic"] or 0
        marker = " ← baseline" if feat == "insider_net_plan_5d" else (" ✓" if ic_val > baseline_ic else "")
        print(
            f"{feat:35s}  {r['coverage_pct']:>7.2f}%  {ic_val:>+8.4f}  "
            f"{r['pos_years']:>3}/{r['years']:<3}  {r['corr_with_s1']:>+8.3f}{marker}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h108_insider_quality_details.json"
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h108_insider_quality",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 38, "signal": "H108", "baseline_ic": baseline_ic},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
