#!/usr/bin/env python
"""S244 dividend_signal_momentum test."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import glob

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
DIVIDEND = 'data/dividend_cache/*.parquet'

def load_dividend_dates():
    """Load dividend record dates."""
    files = glob.glob(DIVIDEND)
    all_events = []
    for f in files:
        df = pd.read_parquet(f)
        if 'record_date' in df.columns:
            all_events.append(df[['ticker', 'record_date']])
    events = pd.concat(all_events, ignore_index=True)
    events = events.dropna(subset=['record_date'])
    events['record_date'] = pd.to_datetime(events['record_date'])
    events = events[events['record_date'].dt.year.isin(range(2015, 2023))]
    events['has_dividend_30d'] = True
    return events[['ticker', 'record_date', 'has_dividend_30d']]

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

def main():
    df = load_data()
    div = load_dividend_dates()
    
    # For each row, check if ticker has dividend within 30 days
    div['window_start'] = div['record_date'] - pd.Timedelta(days=30)
    
    # Merge: for each (ticker, time), check if dividend in next 30 days
    df = df.merge(div, left_on=['ticker', 'time'], right_on=['ticker', 'record_date'], how='left')
    df['has_dividend_30d'] = df['has_dividend_30d'].fillna(False)
    
    # Test: within 30d of dividend vs no dividend
    with_div = df[df['has_dividend_30d'] == True]
    without_div = df[df['has_dividend_30d'] == False]
    
    print(f"With dividend (30d window): n={len(with_div)}")
    print(f"Without dividend: n={len(without_div)}")
    
    if len(with_div) > 100:
        ic, p = spearmanr(with_div['c16'], with_div['actual'])
        print(f"IC (with dividend): {ic:.4f}")
    else:
        print("Insufficient data for with-dividend test")
    
    if len(without_div) > 100:
        ic2, p2 = spearmanr(without_div['c16'], without_div['actual'])
        print(f"IC (without dividend): {ic2:.4f}")

if __name__ == '__main__':
    main()