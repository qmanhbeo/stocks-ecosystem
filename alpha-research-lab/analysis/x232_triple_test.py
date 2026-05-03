#!/usr/bin/env python
"""X232: Triple Storm universal amplifier test."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

def build_triple_filters(merged):
    """Build Triple Storm conditions: liquid + down + divergence."""
    # Market state
    daily = merged.groupby('time')['actual'].mean().reset_index(name='win_rate')
    daily['market_down'] = (daily['win_rate'] < 0.5).astype(int)
    merged = merged.merge(daily[['time', 'market_down']], on='time')
    
    # Liquid
    merged['move'] = merged.groupby('ticker')['c16'].transform(
        lambda x: x.rolling(20, min_periods=10).std())
    merged['liquid'] = (merged['move'] > merged['move'].quantile(0.8)).astype(int)
    
    # Divergence
    merged['ret_lag1'] = merged.groupby('ticker')['actual'].shift(1)
    merged = merged.dropna(subset=['ret_lag1'])
    merged['price_dir'] = (merged['ret_lag1'] > 0).astype(int)
    merged['c16_dir'] = (merged['c16'] > 0.5).astype(int)
    merged['divergence'] = (merged['price_dir'] != merged['c16_dir']).astype(int)
    
    merged['triple'] = (merged['liquid']==1) & (merged['market_down']==1) & (merged['divergence']==1)
    merged['dual'] = (merged['liquid']==1) & (merged['market_down']==1)
    return merged

def walk_forward_ic(df, signal_col):
    """Compute IC per year, then average."""
    results = []
    for year in range(2015, 2023):
        test = df[df['time'].dt.year == year]
        if len(test) > 100:
            ic, p = spearmanr(test[signal_col], test['actual'])
            results.append({'year': year, 'ic': ic, 'n': len(test)})
    return pd.DataFrame(results)

def test_signal(signal_df, signal_col, signal_name):
    """Test signal with and without Triple conditions."""
    s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'actual'])
    s1['time'] = pd.to_datetime(s1['time'])
    s1 = s1[s1['time'].dt.year.isin(range(2015, 2023))]
    
    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    
    merged = s1.merge(order[['date', 'ticker', 'c16']], left_on=['time', 'ticker'], right_on=['date', 'ticker'], how='inner')
    merged = merged.merge(signal_df, on=['time', 'ticker'], how='inner')
    merged = merged.dropna(subset=['actual', signal_col])
    merged = merged.sort_values(['ticker', 'time'])
    
    merged = build_triple_filters(merged)
    
    # Baseline
    wf_base = walk_forward_ic(merged, signal_col)
    base_ic = wf_base['ic'].mean()
    base_n = wf_base['n'].sum()
    
    # With triple
    wf_triple = walk_forward_ic(merged[merged['triple']==1], signal_col)
    triple_ic = wf_triple['ic'].mean() if len(wf_triple) > 0 else np.nan
    triple_n = wf_triple['n'].sum() if len(wf_triple) > 0 else 0
    
    boost = (triple_ic / base_ic - 1) * 100 if base_ic > 0 and not np.isnan(triple_ic) else np.nan
    
    print(f'{signal_name}:')
    print(f'  Baseline: IC={base_ic:.4f}, n={base_n}')
    print(f'  +Triple: IC={triple_ic:.4f}, n={triple_n}')
    print(f'  Boost: {boost:.0f}%')
    
    return {
        'signal': signal_name,
        'base_ic': base_ic,
        'triple_ic': triple_ic,
        'boost': boost,
        'pass': boost > 20 if not np.isnan(boost) else False
    }

if __name__ == '__main__':
    import sys
    
    # Example: test volume zscore
    vol = pd.read_parquet('data/features/xs_volume_zscore_daily.parquet', 
                       columns=['time', 'ticker', 'xs_vol_zscore_1d'])
    vol['time'] = pd.to_datetime(vol['time'])
    vol = vol[vol['time'].dt.year.isin(range(2015, 2023))]
    
    result = test_signal(vol, 'xs_vol_zscore_1d', 'volume_zscore')
    print(f"\nVerdict: {'PASSED' if result['pass'] else 'FAILED'}")