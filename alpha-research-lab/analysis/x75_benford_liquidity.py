"""
X75 - Benford's Law Liquidity Proxy

Test: First-digit distribution of order volume deviates from Benford's Law → smart money signal.

Benford's Law: P(d) = log10(1 + 1/d) for d in 1-9
"""

from __future__ import annotations
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, chi2

ROOT = Path(__file__).resolve().parents[1]


def first_digit(n):
    """Extract first non-zero digit."""
    if n == 0:
        return np.nan
    n = abs(n)
    while n < 1:
        n *= 10
    while n >= 10:
        n //= 10
    return int(n)


def benford_expected(n):
    """Expected Benford distribution for n samples."""
    p = []
    for d in range(1, 10):
        p.append(np.log10(1 + 1 / d) * n)
    return np.array(p)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("Loading order stats...")
    order = pd.read_parquet(ROOT / "data/order_stats/cafef/order_stats_daily.parquet")
    order["date"] = pd.to_datetime(order["date"])
    order = order.rename(columns={"date": "time"})
    
    # Total order volume
    order["total_volume"] = order["buy_order_volume"] + order["sell_order_volume"]
    
    # Filter to 2015-2022
    order = order[order["time"].dt.year.isin(range(2015, 2023))]
    print(f"Order rows: {len(order):,}")
    
    # Extract first digits per year
    years = list(range(2015, 2023))
    results = {}
    
    print("\n--- Benford Deviation by Year ---")
    
    for year in years:
        year_data = order[order["time"].dt.year == year].copy()
        year_data = year_data[year_data["total_volume"] > 0]
        
        digits = year_data["total_volume"].apply(first_digit).dropna()
        digits = digits[digits > 0]
        
        if len(digits) < 100:
            continue
        
        # Observed distribution
        observed = np.zeros(9)
        for d in range(1, 10):
            observed[d - 1] = (digits == d).sum()
        
        # Expected distribution
        expected = benford_expected(len(digits))
        
        # Chi-square test
        chi2_stat = ((observed - expected) ** 2 / expected).sum()
        p_value = 1 - chi2.cdf(chi2_stat, 8)
        
        # Deviation: sum of absolute differences
        deviation = np.abs(observed / len(digits) - expected / len(digits)).sum()
        
        print(f"{year}: n={len(digits):,}, deviation={deviation:.4f}, chi2={chi2_stat:.1f}, p={p_value:.4f}")
        
        results[year] = {
            "n": int(len(digits)),
            "deviation": float(deviation),
            "chi2": float(chi2_stat),
            "p_value": float(p_value),
        }
    
    # Now test if Benford deviation predicts returns
    print("\n--- IC Test: Benford Deviation → Future Return ---")
    
    # Compute daily Benford deviation signal
    order["digit"] = order["total_volume"].apply(first_digit)
    
    # Build daily signal: deviation from Benford (spread of digit distribution)
    daily = order.groupby("time").apply(
        lambda g: g[g["total_volume"] > 0]["digit"].value_counts(normalize=True).std()
    ).reset_index()
    daily.columns = ["time", "benford_deviation"]
    
    # Merge onto matrix
    matrix = pd.read_parquet(ROOT / "data/features/xs_rl_signal_matrix.parquet")
    merged = matrix.merge(daily, on="time", how="inner")
    merged = merged[merged["time"].dt.year.isin(years)]
    
    # For each year, rank stocks by benford_deviation
    merged["benford_rank"] = merged.groupby("time")["benford_deviation"].rank(pct=True)
    
    # IC test
    def yearly_ic(df, col):
        ics = {}
        for year in years:
            year_data = df[df["time"].dt.year == year].dropna(subset=[col, "actual"])
            if len(year_data) > 30:
                ic, _ = spearmanr(year_data[col], year_data["actual"])
                if not np.isnan(ic):
                    ics[year] = ic
        return ics
    
    ics = yearly_ic(merged, "benford_rank")
    ic_mean = np.mean(list(ics.values()))
    ic_pos = sum(1 for v in ics.values() if v > 0)
    
    print(f"\nBenford Deviation IC: {ic_mean:+.4f}")
    print(f"Positive years: {ic_pos}/{len(ics)}")
    
    # Also test: inverse (conformity to Benford = no wash trading)
    merged["benford_conformity"] = 1 - merged["benford_deviation"]
    merged["conformity_rank"] = merged.groupby("time")["benford_conformity"].rank(pct=True)
    
    conf_ics = yearly_ic(merged, "conformity_rank")
    conf_ic_mean = np.mean(list(conf_ics.values()))
    conf_pos = sum(1 for v in conf_ics.values() if v > 0)
    
    print(f"Benford Conformity IC: {conf_ic_mean:+.4f}")
    print(f"Positive years: {conf_pos}/{len(conf_ics)}")
    
    # Decision
    best_ic = max(ic_mean, conf_ic_mean)
    best_name = "deviation" if ic_mean > conf_ic_mean else "conformity"
    
    result = {
        "benford_deviation_ic": ic_mean,
        "benford_deviation_pos_years": ic_pos,
        "benford_conformity_ic": conf_ic_mean,
        "benford_conformity_pos_years": conf_pos,
        "best": best_name,
        "best_ic": best_ic,
    }
    
    if best_ic > 0.02 and (ic_pos if best_name == "deviation" else conf_pos) >= 6:
        verdict = "PASSED"
    else:
        verdict = "FAILED"
    
    print(f"\nVerdict: {verdict}")
    print(f"Best: {best_name} with IC {best_ic:+.4f}")
    
    # Save
    out_path = ROOT / f"alpha-research-lab/artifacts/run_summaries/{ts}_x75_benford_liquidity.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"mode": "x75", "results": result, "verdict": verdict}, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()