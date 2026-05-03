#!/usr/bin/env python
"""S244 insider_pressure_coherence - LEADING LAG test v2."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import glob

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
INSIDER = 'data/insider_cache/*.parquet'

def load_insider_data():
    files = glob.glob(INSIDER)
    all_insider = []
    for f in files:
        df = pd.read_parquet(f)
        if 'RealBuyVolume' in df.columns:
            df['net_buy'] = df['RealBuyVolume'] - df['RealSellVolume']
            all_insider.append(df[['ticker', 'published_date', 'net_buy']])
    insider = pd.concat(all_insider, ignore_index=True)
    insider['published_date'] = pd.to_datetime(insider['published_date'])
    insider = insider[insider['published_date'].dt.year.isin(range(2015, 2023))]
    return insider

def load_order_data():
    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    return order

def load_returns():
    ret = pd.read_parquet(RETURNS, columns=['time', 'ticker', 'actual'])
    ret['time'] = pd.to_datetime(ret['time'])
    ret = ret[ret['time'].dt.year.isin(range(2015, 2023))]
    return ret

def wf_ic_simple(df, signal):
    df = df.dropna(subset=[signal, 'actual'])
    if len(df) > 50:
        ic, p = spearmanr(df[signal], df['actual'])
        return ic
    return np.nan

def main():
    order = load_order_data()
    ret = load_returns()
    insider = load_insider_data()
    
    order = order.rename(columns={'date': 'time'})
    
    merged = ret.merge(order[['time', 'ticker', 'c16']], on=['time', 'ticker'], how='inner')
    merged = merged.dropna(subset=['actual', 'c16'])
    
    # Lead: insider on T-1 predicts C16 on T
    insider['insider_date'] = insider['published_date'] + pd.Timedelta(days=1)
    insider = insider.rename(columns={'insider_date': 'time'})
    merged = merged.merge(insider[['ticker', 'time', 'net_buy']], on=['ticker', 'time'], how='left')
    merged['insider_lead'] = merged['net_buy'] > 0
    
    with_insider = merged[merged['insider_lead'] == True]
    without_insider = merged[merged['insider_lead'] == False]
    
    print(f"With prior insider: n={len(with_insider)}")
    print(f"Without prior insider: n={len(without_insider)}")
    
    w_ic = wf_ic_simple(with_insider, 'c16')
    wo_ic = wf_ic_simple(without_insider, 'c16')
    
    print(f"IC with prior insider: {w_ic:.4f}")
    print(f"IC without prior insider: {wo_ic:.4f}")
    
    if not np.isnan(w_ic) and not np.isnan(wo_ic):
        print(f"Boost: {((w_ic/wo_ic)-1)*100:+.1f}%")

if __name__ == '__main__':
    main()