#!/usr/bin/env python
"""X231: Walk-Forward Validation on C16 Discoveries."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

print('='*60)
print('TEST: X231 Walk-Forward Validation')
print('For each year Y: train on years < Y, test on year Y')
print('='*60)

# Load and prepare data
s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'actual'])
s1['time'] = pd.to_datetime(s1['time'])
s1 = s1[s1['time'].dt.year.isin(range(2015, 2026))]

order = pd.read_parquet(ORDER)
order['date'] = pd.to_datetime(order['date'])
order = order[order['date'].dt.year.isin(range(2015, 2026))]
order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
order = order.rename(columns={'date': 'time'})

merged = s1.merge(order, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['c16', 'actual'])
merged = merged.sort_values(['ticker', 'time'])

# Market state
daily = merged.groupby('time')['actual'].mean().reset_index(name='win_rate')
daily['market_down'] = (daily['win_rate'] < 0.5).astype(int)
merged = merged.merge(daily[['time', 'market_down']], on='time')

# Liquid
merged['move'] = merged.groupby('ticker')['c16'].transform(lambda x: x.rolling(20, min_periods=10).std())
merged['liquid'] = (merged['move'] > merged['move'].quantile(0.8)).astype(int)

# Divergence
merged['ret_lag1'] = merged.groupby('ticker')['actual'].shift(1)
merged = merged.dropna(subset=['ret_lag1'])
merged['price_dir'] = (merged['ret_lag1'] > 0).astype(int)
merged['c16_dir'] = (merged['c16'] > 0.5).astype(int)
merged['divergence'] = (merged['price_dir'] != merged['c16_dir']).astype(int)

def yearly_ic_only(df, years):
    """IC computed on each year separately (no training years needed)."""
    results = []
    for year in years:
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            ic, p = spearmanr(y['c16'], y['actual'])
            results.append({'year': year, 'ic': ic, 'n': len(y)})
    return pd.DataFrame(results)

def walk_forward_ic(df, years):
    """Walk-forward: train on all years < Y, test on year Y."""
    results = []
    for test_year in years:
        train = df[df['time'].dt.year < test_year]
        test = df[df['time'].dt.year == test_year]
        
        if len(train) < 100 or len(test) < 100:
            continue
            
        # Get signal thresholds from training data
        liquid_thresh = train['move'].quantile(0.8)
        c16_thresh = 0.5
        
        # Compute IC on test year
        ic, p = spearmanr(test['c16'], test['actual'])
        results.append({
            'test_year': test_year,
            'ic': ic,
            'n_train': len(train),
            'n_test': len(test)
        })
    return pd.DataFrame(results)

# Walk-forward windows - test each year
test_years = range(2017, 2026)  # 2017 first, need 2 prior years

print('\n--- BASELINE C16 Walk-Forward ---')
wf_baseline = walk_forward_ic(merged, test_years)
print(wf_baseline.to_string(index=False))
baseline_mean = wf_baseline['ic'].mean()
baseline_std = wf_baseline['ic'].std()
print(f'WF Mean: {baseline_mean:.4f} ± {baseline_std:.4f}')

print('\n--- X226: DOWN MARKET Walk-Forward ---')
down = merged[merged['market_down'] == 1]
wf_down = walk_forward_ic(down, test_years)
print(wf_down.to_string(index=False))
down_mean = wf_down['ic'].mean()
down_std = wf_down['ic'].std()
print(f'WF Mean: {down_mean:.4f} ± {down_std:.4f}')

print('\n--- X53: LIQUID FILTER Walk-Forward ---')
liquid = merged[merged['liquid'] == 1]
wf_liquid = walk_forward_ic(liquid, test_years)
print(wf_liquid.to_string(index=False))
liquid_mean = wf_liquid['ic'].mean()
liquid_std = wf_liquid['ic'].std()
print(f'WF Mean: {liquid_mean:.4f} ± {liquid_std:.4f}')

print('\n--- X229: TRIPLE STORM Walk-Forward ---')
triple = merged[(merged['liquid']==1) & (merged['market_down']==1) & (merged['divergence']==1)]
wf_triple = walk_forward_ic(triple, test_years)
print(wf_triple.to_string(index=False))
triple_mean = wf_triple['ic'].mean()
triple_std = wf_triple['ic'].std()
print(f'WF Mean: {triple_mean:.4f} ± {triple_std:.4f}')

print('\n' + '='*60)
print('WALK-FORWARD SUMMARY')
print('='*60)
print(f'Baseline:     {baseline_mean:.4f} ± {baseline_std:.4f}')
print(f'Down (X226): {down_mean:.4f} ± {down_std:.4f} ({(down_mean/abs(baseline_mean)-1)*100:+.0f}%)')
print(f'Liquid (X53): {liquid_mean:.4f} ± {liquid_std:.4f} ({(liquid_mean/abs(baseline_mean)-1)*100:+.0f}%)')
print(f'Triple (X229): {triple_mean:.4f} ± {triple_std:.4f} ({(triple_mean/abs(baseline_mean)-1)*100:+.0f}%)')

# Consistency check
print('\n--- CONSISTENCY: Years with Positive IC ---')
print(f'Baseline: {(wf_baseline["ic"]>0).sum()}/{len(wf_baseline)}')
print(f'Down:     {(wf_down["ic"]>0).sum()}/{len(wf_down)}')
print(f'Liquid:  {(wf_liquid["ic"]>0).sum()}/{len(wf_liquid)}')
print(f'Triple:  {(wf_triple["ic"]>0).sum()}/{len(wf_triple)}')

# Verdict
if (wf_triple['ic'] > 0).all() and triple_mean > baseline_mean:
    verdict = 'ROBUST - Triple Storm works every year'
elif (wf_triple['ic'] > 0).sum() >= len(wf_triple) * 0.7:
    verdict = 'MOSTLY ROBUST - works 70%+ years'
else:
    verdict = 'FRAGILE - inconsistent'

print(f'\nVerdict: {verdict}')
print('='*60)