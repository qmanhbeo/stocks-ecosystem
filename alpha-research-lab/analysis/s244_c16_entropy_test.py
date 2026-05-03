#!/usr/bin/env python
"""S244 c16_entropy_signal - sector dispersion test.
Smallest honest test: Compute sector-level C16 std (proxy for entropy).
Test: IC(C16) in high vs low dispersion environments.
"""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import glob

# Paths
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

def load_data():
    """Load order pressure + returns."""
    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    order = order.rename(columns={'date': 'time'})
    
    ret = pd.read_parquet(RETURNS, columns=['time', 'ticker', 'actual'])
    ret['time'] = pd.to_datetime(ret['time'])
    ret = ret[ret['time'].dt.year.isin(range(2015, 2023))]
    
    merged = ret.merge(order[['time', 'ticker', 'c16']], on=['time', 'ticker'], how='inner')
    merged = merged.dropna(subset=['actual', 'c16'])
    return merged

def wf_ic_by_year(df, signal):
    """Walk-forward IC by year."""
    results = []
    for year in range(2015, 2023):
        test = df[df['time'].dt.year == year].copy()
        test = test.dropna(subset=[signal, 'actual'])
        if len(test) > 50:
            ic, p = spearmanr(test[signal], test['actual'])
            results.append({'year': year, 'ic': ic})
    return results

def main():
    print("=" * 60)
    print("Test: c16_entropy_signal")
    print("=" * 60)
    print("Claim: Sector dispersion amplifies C16 signal.")
    print("Test: IC(C16) in high-dispersion vs low-dispersion environments.")
    print()
    
    df = load_data()
    print(f"Loaded: {len(df):,} records")
    
    # Compute sector-level C16 dispersion (std of c16 per day)
    sector_stats = df.groupby('time')['c16'].agg(['std', 'mean']).reset_index()
    sector_stats = sector_stats.rename(columns={'time': 'time', 'std': 'c16_entropy'})
    
    df = df.merge(sector_stats[['time', 'c16_entropy']], on='time')
    
    median_entropy = df['c16_entropy'].median()
    print(f"Median sector dispersion: {median_entropy:.4f}")
    
    # Split into high vs low dispersion
    high = df[df['c16_entropy'] > median_entropy]
    low = df[df['c16_entropy'] <= median_entropy]
    
    print(f"High dispersion: n={len(high):,}")
    print(f"Low dispersion: n={len(low):,}")
    
    # Standard IC
    ic_all, _ = spearmanr(df['c16'], df['actual'])
    ic_high, p_high = spearmanr(high['c16'], high['actual'])
    ic_low, p_low = spearmanr(low['c16'], low['actual'])
    
    print()
    print("Results:")
    print(f"  IC (all): {ic_all:.4f}")
    print(f"  IC (high dispersion): {ic_high:.4f}")
    print(f"  IC (low dispersion): {ic_low:.4f}")
    print()
    
    if ic_high > ic_low:
        boost = ((ic_high / ic_low) - 1) * 100
        print(f"  **Boost: +{boost:.1f}%**")
        print("  Verdict: REAL - sector dispersion modulates C16 signal")
    else:
        boost = ((ic_low / ic_high) - 1) * 100
        print(f"  Boost: -{boost:.1f}%")
        print("  Verdict: WEAK or INVERSE")
    
    # Walk-forward by year
    print()
    print("Walk-Forward IC by Year:")
    print("| Year | High Disp | Low Disp |")
    print("|------|-----------|---------|")
    
    high_results = wf_ic_by_year(high, 'c16')
    low_results = wf_ic_by_year(low, 'c16')
    
    for i, year in enumerate(range(2015, 2023)):
        h = high_results[i]['ic'] if i < len(high_results) else np.nan
        l = low_results[i]['ic'] if i < len(low_results) else np.nan
        print(f"| {year} | {h:.4f} | {l:.4f} |")
    
    # Average
    h_avg = np.nanmean([r['ic'] for r in high_results])
    l_avg = np.nanmean([r['ic'] for r in low_results])
    print(f"| **AVG** | **{h_avg:.4f}** | **{l_avg:.4f}** |")

if __name__ == '__main__':
    main()