#!/usr/bin/env python
"""S255: buy_zone_entry_timing - buy zone labels predict T+1 C16 quality.

Data: labels/supervised/
"""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
LABELS = 'data/labels/supervised/'

def load_order_data():
    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    order = order.rename(columns={'date': 'time'})
    return order

def load_returns():
    ret = pd.read_parquet(RETURNS, columns=['time', 'ticker', 'actual'])
    ret['time'] = pd.to_datetime(ret['time'])
    ret = ret[ret['time'].dt.year.isin(range(2015, 2023))]
    return ret

def load_labels():
    """Load label files from labels/supervised/."""
    import glob
    files = glob.glob(f'{LABELS}/*.parquet')
    all_labels = []
    for f in files:
        df = pd.read_parquet(f)
        if 'time' in df.columns and 'ticker' in df.columns:
            all_labels.append(df[['time', 'ticker']], )
    if not all_labels:
        return pd.DataFrame()
    labels = pd.concat(all_labels, ignore_index=True)
    labels['time'] = pd.to_datetime(labels['time'])
    return labels

def wf_ic_by_year(df, signal_col):
    """Walk-forward IC."""
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
    order = load_order_data()
    ret = load_returns()
    labels = load_labels()
    
    print("=" * 60)
    print("S255: BUY ZONE ENTRY TIMING TEST")
    print("=" * 60)
    
    if labels.empty:
        print("NO LABELS DATA in data/labels/supervised/")
        # Check what's actually there
        import os
        if os.path.exists('data/labels/supervised/'):
            files = os.listdir('data/labels/supervised/')
            print(f"Files: {files[:5]}")
        else:
            print("Directory does not exist")
        return
    
    # Merge: get C16 on days WITH labels vs WITHOUT labels
    merged = ret.merge(order[['time', 'ticker', 'c16']], on=['time', 'ticker'], how='inner')
    
    # Merge with labels
    labels['is_label_day'] = True
    merged = merged.merge(labels[['time', 'ticker', 'is_label_day']], on=['time', 'ticker'], how='left')
    merged['is_label_day'] = merged['is_label_day'].fillna(False)
    
    with_label = merged[merged['is_label_day'] == True]
    without_label = merged[merged['is_label_day'] == False]
    
    print(f"With label: {len(with_label)}")
    print(f"Without label: {len(without_label)}")
    
    with_results = wf_ic_by_year(with_label, 'c16')
    without_results = wf_ic_by_year(without_label, 'c16')
    
    if with_results and without_results:
        with_ic = np.mean([r['ic'] for r in with_results])
        without_ic = np.mean([r['ic'] for r in without_results])
        
        print(f"| Year | With Label IC | Without Label IC |")
        print(f"|------|-------------|---------------|")
        for wr, wor in zip(with_results, without_results):
            print(f"| {wr['year']} | {wr['ic']:.4f} | {wor['ic']:.4f} |")
        
        print(f"| **Mean** | **{with_ic:.4f}** | **{without_ic:.4f}** |")
        
        if with_ic > without_ic + 0.02:
            boost = ((with_ic / without_ic) - 1) * 100
            print(f"**VERDICT: PASSED (+{boost:.1f}%)**")
        else:
            print(f"**VERDICT: FAILED**")

if __name__ == '__main__':
    main()