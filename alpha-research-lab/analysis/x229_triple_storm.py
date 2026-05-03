#!/usr/bin/env python
"""X229: Triple Storm - combine liquid + down market + divergence."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

print('='*60)
print('TEST: X229 triple_storm')
print('Hypothesis: liquid + down market + divergence = extreme')
print('='*60)

# Load data
s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'actual'])
s1['time'] = pd.to_datetime(s1['time'])
s1 = s1[s1['time'].dt.year.isin(range(2015, 2023))]

order = pd.read_parquet(ORDER)
order['date'] = pd.to_datetime(order['date'])
order = order[order['date'].dt.year.isin(range(2015, 2023))]
order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
order = order.rename(columns={'date': 'time'})

merged = s1.merge(order, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['c16', 'actual'])
merged = merged.sort_values(['ticker', 'time'])

# Market state: per-day win rate (mean actual). <0.5 = DOWN day
daily = merged.groupby('time')['actual'].mean().reset_index(name='win_rate')
daily['market_down'] = (daily['win_rate'] < 0.5).astype(int)  # 1=down day (win rate < 50%)
merged = merged.merge(daily[['time', 'market_down']], on='time')

# Liquid: 20-day rolling C16 std > 80th percentile
merged['move'] = merged.groupby('ticker')['c16'].transform(lambda x: x.rolling(20, min_periods=10).std())
merged['liquid'] = (merged['move'] > merged['move'].quantile(0.8)).astype(int)

# Divergence: lagged price direction vs C16 direction
merged['ret_lag1'] = merged.groupby('ticker')['actual'].shift(1)
merged = merged.dropna(subset=['ret_lag1'])
merged['price_dir'] = (merged['ret_lag1'] > 0).astype(int)  # 1=yesterday up
merged['c16_dir'] = (merged['c16'] > 0.5).astype(int)  # 1=high pressure
merged['divergence'] = (merged['price_dir'] != merged['c16_dir']).astype(int)

num_down_days = merged.groupby('time')['market_down'].first().sum()
print(f'\nTotal: {len(merged)}')
print(f'Down days: {num_down_days} ({num_down_days/len(daily)*100:.1f}% of {len(daily)} trading days)')
print(f'Liquid: {merged["liquid"].sum()} ({merged["liquid"].mean()*100:.1f}%)')
print(f'Divergence: {merged["divergence"].sum()} ({merged["divergence"].mean()*100:.1f}%)')

def yearly_ic(df, col='c16'):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            ic, p = spearmanr(y[col], y['actual'])
            results.append({'year': year, 'ic': ic, 'n': len(y)})
    return pd.DataFrame(results)

# Tests
print('\n--- RESULTS ---')
tests = [
    ('Baseline', merged),
    ('Liquid only', merged[merged['liquid'] == 1]),
    ('Down market only', merged[merged['market_down'] == 1]),
    ('Divergence only', merged[merged['divergence'] == 1]),
    ('Liquid + DOWN', merged[(merged['liquid']==1) & (merged['market_down']==1)]),
    ('Triple Storm', merged[(merged['liquid']==1) & (merged['market_down']==1) & (merged['divergence']==1)]),
]

results = []
for name, df in tests:
    if len(df) > 100:
        ic_df = yearly_ic(df)
        mean_ic = ic_df['ic'].mean()
        results.append((name, mean_ic, len(df)))
        print(f'{name}: IC={mean_ic:.4f} n={len(df)}')
    else:
        print(f'{name}: SKIP (n={len(df)})')
        results.append((name, 0, len(df)))

baseline_val = results[0][1]
print('\n--- COMPARISON vs Baseline ---')
for name, ic, n in results[1:]:
    if n > 100 and baseline_val > 0:
        pct = (ic / baseline_val - 1) * 100
        print(f'{name}: {pct:+.0f}% vs baseline')
    else:
        print(f'{name}: --')

# Verdict
best = max(results, key=lambda x: abs(x[1]) if x[2] > 100 else ('', 0, 0))
print(f'\nBest: {best[0]} at {best[1]:.4f}')

# Ladder
best_single = max([r for r in results if 'Liquid' in r[0] or 'Down' in r[0] or 'Divergence' in r[0]], 
                key=lambda x: abs(x[1]) if x[2] > 100 else ('', 0, 0))
if results[-1][1] > baseline_val * 1.1:
    verdict = 'PASSED - triple works'
elif results[-1][1] < baseline_val * 0.9:
    verdict = 'FAILED - stacking hurts'
else:
    verdict = f'NEUTRAL - use best single ({best_single[0]})'

print(f'Verdict: {verdict}')
print('='*60)