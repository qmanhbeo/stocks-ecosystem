#!/usr/bin/env python
"""Detailed consecutive down days test - FIXED v2."""
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

def wf_ic_simple(df, signal):
    df = df.dropna(subset=[signal, 'actual'])
    if len(df) > 50:
        ic, p = spearmanr(df[signal], df['actual'])
        return ic
    return np.nan

def main():
    df = load_data()
    
    # Market return per day
    market_daily = df.groupby('time')['actual'].mean().reset_index()
    market_daily = market_daily.rename(columns={'actual': 'market_return'})
    market_daily['market_down'] = market_daily['market_return'] < 0
    
    # Shift by date
    market_daily = market_daily.sort_values('time')
    market_daily['prev_market_down'] = market_daily['market_down'].shift(1)
    market_daily['prev_2d_down'] = (market_daily['prev_market_down'].shift(1) == True) & (market_daily['prev_market_down'] == True)
    
    # Merge back
    df = df.merge(market_daily[['time', 'market_down', 'prev_market_down', 'prev_2d_down']], on='time')
    
    # Base: all C16
    all_ic = wf_ic_simple(df, 'c16')
    print(f"Baseline (all): IC={all_ic:.4f}")
    
    # Single day down
    down_df = df[df['market_down'] == True]
    down_ic = wf_ic_simple(down_df, 'c16')
    print(f"Single down day: IC={down_ic if not np.isnan(down_ic) else 'N/A'}, n={len(down_df)}")
    
    # Streak 2d
    streak_df = df[df['prev_2d_down'] == True]
    streak_ic = wf_ic_simple(streak_df, 'c16')
    print(f"Consecutive 2d down: IC={streak_ic if not np.isnan(streak_ic) else 'N/A'}, n={len(streak_df)}")
    
    # Streak 3d
    market_daily['prev_3d_down'] = (market_daily['prev_2d_down'].shift(1) == True) & (market_daily['prev_2d_down'] == True)
    df = df.merge(market_daily[['time', 'prev_3d_down']], on='time')
    streak3_df = df[df['prev_3d_down'] == True]
    streak3_ic = wf_ic_simple(streak3_df, 'c16')
    print(f"Consecutive 3d down: IC={streak3_ic if not np.isnan(streak3_ic) else 'N/A'}, n={len(streak3_df)}")

if __name__ == '__main__':
    main()