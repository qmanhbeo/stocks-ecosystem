#!/usr/bin/env python
"""S257: c16_delta - C16 change as independent signal.

Hypothesis: C16 change (today→tomorrow) = momentum signal.
vs Random baseline: IC > 0.05 is REAL.
"""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

def load_data():
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

def wf_ic_by_year(df, signal_col):
    """Walk-forward IC: compare to Random (~0)."""
    results = []
    for year in range(2015, 2023):
        test = df[df['time'].dt.year == year]
        test = test.dropna(subset=[signal_col, 'actual'])
        if len(test) > 50:
            ic, p = spearmanr(test[signal_col], test['actual'])
            if not np.isnan(ic):
                results.append({'year': year, 'ic': ic, 'n': len(test)})
    return results

def main():
    df = load_data()
    
    print("=" * 60)
    print("S257: C16 DELTA SIGNAL TEST")
    print("=" * 60)
    print("Method: IC(C16_delta) vs Random (~0)")
    print()
    
    # Compute: C16_tomorrow - C16_today
    df = df.sort_values(['ticker', 'time'])
    df['c16_next'] = df.groupby('ticker')['c16'].shift(-1)
    df['c16_delta'] = df['c16_next'] - df['c16']
    
    # Test vs Random
    test_df = df.dropna(subset=['c16_delta', 'actual'])
    test_df = test_df[~np.isinf(test_df['c16_delta'])]
    
    print(f"Test samples: {len(test_df)}")
    
    results = wf_ic_by_year(test_df, 'c16_delta')
    
    if results:
        ic_vals = [r['ic'] for r in results]
        mean_ic = np.mean(ic_vals)
        
        print(f"| Year | IC |")
        print(f"|------|-----|")
        for r in results:
            print(f"| {r['year']} | {r['ic']:.4f} |")
        
        print(f"| **Mean** | **{mean_ic:.4f}** |")
        
        # vs Random: IC > 0.05 = REAL
        if mean_ic > 0.05:
            print(f"**VERDICT: PASSED (IC={mean_ic:.4f} > 0.05 vs Random)**")
        else:
            print(f"**VERDICT: FAILED (IC={mean_ic:.4f} <= 0.05)**")

if __name__ == '__main__':
    main()