"""
H294 - LLM News Standalone Gate (1d Barrier).

Question:
- Do LLM news sentiment features pass the canonical standalone signal gate
  when evaluated against the 1d barrier label (same contract as C4-C14)?

Design:
- Use xs_barrier_vol_1d_hose_full.parquet as the target (column: actual, the
  1d barrier binary outcome; use xs_proba for S1 correlation).
- Restrict to nonzero LLM news rows (2016-2017 window, ~874 rows).
- Test three pooled features: llm_sentiment_raw, llm_sentiment_5d,
  llm_sentiment_conf_weighted.
- Also test the best state-gated variants from H290 (novelty: follow/new,
  alignment: miss/beat) but against the 1d barrier label.
- Compute: daily IC, year-by-year consistency, coverage vs C1 (0.8%), corr vs S1.

Gate criteria (adapted to 2 available years):
- IC > 0.01 AND 2/2 years positive → PASS
- IC 0..0.01 but state-gated IC > 0.01 → MIXED (offline evidence, same as C15)
- IC < 0 and no state gate helps → FAIL

Usage:
    conda run -n stocks python analysis/h294_llm_news_standalone_gate.py
"""

from __future__ import annotations

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

from path_utils import data_path
from src.run_summary import write_run_summary

LLM_PATH = data_path("features/xs_llm_news_ticker_day.parquet")
BARRIER_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")

POOLED_FEATURES = [
    "llm_sentiment_raw",
    "llm_sentiment_5d",
    "llm_sentiment_conf_weighted",
]

STATE_COLS = [
    "llm_expectation_beats_5d",
    "llm_expectation_misses_5d",
    "llm_new_info_5d",
    "llm_followup_info_5d",
]

# C1 baseline for comparison
C1_IC = 0.043
C1_COVERAGE_PCT = 0.8
C1_POSITIVE_YEARS = 5
C1_TOTAL_YEARS = 8


def _daily_ic(df: pd.DataFrame, feature_col: str, target_col: str) -> pd.Series:
    rows = []
    for time, g in df.groupby("time", sort=True):
        gg = g[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 3 or gg[feature_col].nunique() < 2:
            continue
        rho, _ = spearmanr(gg[feature_col], gg[target_col])
        if np.isfinite(rho):
            rows.append({"time": pd.to_datetime(time), "ic": float(rho)})
    return pd.DataFrame(rows)


def _summarize(ic_df: pd.DataFrame) -> dict:
    if ic_df.empty:
        return {"mean_ic": float("nan"), "hit_rate": float("nan"), "pos_years": 0, "n_years": 0, "n_days": 0}
    yearly = ic_df.assign(year=ic_df["time"].dt.year).groupby("year")["ic"].mean()
    return {
        "mean_ic": float(ic_df["ic"].mean()),
        "hit_rate": float((ic_df["ic"] > 0).mean()),
        "pos_years": int((yearly > 0).sum()),
        "n_years": int(len(yearly)),
        "n_days": int(len(ic_df)),
    }


def _bucket_label(frame: pd.DataFrame, kind: str) -> pd.Series:
    if kind == "novelty":
        return pd.Series(
            np.where(frame["llm_new_info_5d"] > frame["llm_followup_info_5d"], "new",
            np.where(frame["llm_new_info_5d"] < frame["llm_followup_info_5d"], "follow", "flat")),
            index=frame.index,
        )
    if kind == "alignment":
        return pd.Series(
            np.where(frame["llm_expectation_beats_5d"] > frame["llm_expectation_misses_5d"], "beat",
            np.where(frame["llm_expectation_beats_5d"] < frame["llm_expectation_misses_5d"], "miss", "flat")),
            index=frame.index,
        )
    raise ValueError(kind)


def main() -> None:
    print("H294 - LLM News Standalone Gate (1d Barrier)")
    print("=" * 70)

    # --- Load LLM surface (nonzero window only) ---
    llm_cols = ["time", "ticker"] + POOLED_FEATURES + STATE_COLS
    llm = pd.read_parquet(LLM_PATH, columns=llm_cols)
    llm["time"] = pd.to_datetime(llm["time"])
    nonzero_mask = llm[POOLED_FEATURES].abs().max(axis=1) > 0
    llm_nz = llm[nonzero_mask].copy()
    print(f"LLM nonzero rows: {len(llm_nz)} | years: {sorted(llm_nz['time'].dt.year.unique().tolist())}")

    # --- Load 1d barrier target ---
    barrier = pd.read_parquet(BARRIER_PATH, columns=["time", "ticker", "actual", "xs_proba"])
    barrier["time"] = pd.to_datetime(barrier["time"])

    # Total tickers×days for coverage denominator
    total_ticker_days = len(barrier)
    coverage_pct = round(len(llm_nz) / total_ticker_days * 100, 3)
    print(f"Coverage: {len(llm_nz)} / {total_ticker_days} = {coverage_pct}% (C1 baseline: {C1_COVERAGE_PCT}%)")

    # --- Join nonzero LLM rows with barrier ---
    panel = llm_nz.merge(barrier, on=["time", "ticker"], how="inner")
    panel = panel.dropna(subset=["actual"])
    print(f"Panel after join: {len(panel)} rows, {panel['time'].nunique()} dates")

    # --- Pooled IC per feature ---
    print("\n--- Pooled standalone IC vs 1d barrier ---")
    pooled_results = {}
    for feat in POOLED_FEATURES:
        ic_df = _daily_ic(panel[["time", feat, "actual"]], feat, "actual")
        stats = _summarize(ic_df)
        pooled_results[feat] = stats
        print(f"  {feat}: IC={stats['mean_ic']:.4f}, hit={stats['hit_rate']:.2f}, "
              f"pos_years={stats['pos_years']}/{stats['n_years']}, n_days={stats['n_days']}")

    # --- S1 correlation (xs_proba vs best sentiment feature) ---
    best_feat = max(pooled_results, key=lambda f: pooled_results[f]["mean_ic"])
    corr_rows = panel[["xs_proba", best_feat]].dropna()
    s1_corr = float(spearmanr(corr_rows["xs_proba"], corr_rows[best_feat])[0]) if len(corr_rows) > 3 else float("nan")
    print(f"\nS1 correlation (xs_proba vs {best_feat}): {s1_corr:.4f}")

    # --- State-gated IC (novelty and alignment) vs 1d barrier ---
    print("\n--- State-gated IC vs 1d barrier ---")
    gated_results = []
    for state_kind in ["novelty", "alignment"]:
        panel_copy = panel.copy()
        panel_copy["bucket"] = _bucket_label(panel_copy, state_kind)
        for bucket in sorted(panel_copy["bucket"].unique()):
            sub = panel_copy[panel_copy["bucket"] == bucket]
            ic_df = _daily_ic(sub[["time", best_feat, "actual"]], best_feat, "actual")
            stats = _summarize(ic_df)
            stats["state_kind"] = state_kind
            stats["bucket"] = bucket
            stats["n_rows"] = int(len(sub))
            gated_results.append(stats)
            print(f"  {state_kind}/{bucket}: IC={stats['mean_ic']:.4f}, hit={stats['hit_rate']:.2f}, "
                  f"pos_years={stats['pos_years']}/{stats['n_years']}, n_rows={stats['n_rows']}")

    # --- Year-by-year breakdown for best feature ---
    print(f"\n--- Year breakdown for {best_feat} ---")
    for year, g in panel.groupby(panel["time"].dt.year):
        ic_df = _daily_ic(g[["time", best_feat, "actual"]], best_feat, "actual")
        if ic_df.empty:
            print(f"  {year}: no data")
        else:
            print(f"  {year}: IC={ic_df['ic'].mean():.4f} ({len(ic_df)} days)")

    # --- Verdict ---
    best_pooled = pooled_results[best_feat]
    best_gated = max(gated_results, key=lambda r: r["mean_ic"]) if gated_results else {}

    pooled_passes_ic = best_pooled["mean_ic"] > 0.01
    pooled_consistent = best_pooled["pos_years"] >= best_pooled["n_years"]  # 2/2 years
    gated_passes = best_gated.get("mean_ic", 0.0) > 0.01

    if pooled_passes_ic and pooled_consistent:
        verdict = "PASS"
    elif gated_passes or best_pooled["mean_ic"] > 0:
        verdict = "MIXED"
    else:
        verdict = "FAIL"

    print(f"\nVERDICT: {verdict}")
    print(f"  Best pooled IC: {best_pooled['mean_ic']:.4f} ({best_feat})")
    print(f"  Best gated IC:  {best_gated.get('mean_ic', float('nan')):.4f} "
          f"({best_gated.get('state_kind','?')}/{best_gated.get('bucket','?')})")
    print(f"  Coverage: {coverage_pct}% vs C1 {C1_COVERAGE_PCT}%")
    print(f"  S1 corr: {s1_corr:.4f}")

    # --- Save artifacts ---
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "verdict": verdict,
        "best_pooled_feature": best_feat,
        "best_pooled_ic": best_pooled["mean_ic"],
        "best_pooled_hit_rate": best_pooled["hit_rate"],
        "best_pooled_pos_years": best_pooled["pos_years"],
        "best_pooled_n_years": best_pooled["n_years"],
        "coverage_pct": coverage_pct,
        "s1_corr": s1_corr,
        "c1_baseline_ic": C1_IC,
        "c1_baseline_coverage_pct": C1_COVERAGE_PCT,
        "best_gated_ic": best_gated.get("mean_ic", float("nan")),
        "best_gated_state": best_gated.get("state_kind", ""),
        "best_gated_bucket": best_gated.get("bucket", ""),
        "pooled_table": [{"feature": f, **pooled_results[f]} for f in POOLED_FEATURES],
        "gated_table": gated_results,
        "nonzero_rows": len(llm_nz),
        "panel_rows": len(panel),
        "window_years": sorted(int(y) for y in panel["time"].dt.year.unique().tolist()),
        "data_constraint": "cache covers 2016-2017 only; 6/8 year gate cannot be applied",
    }

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h294_llm_news_standalone_gate",
        summary=summary,
        artifacts={},
        metadata={"signal": "H294"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
