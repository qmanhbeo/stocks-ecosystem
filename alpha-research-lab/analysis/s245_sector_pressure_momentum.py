#!/usr/bin/env python
"""S245: Sector Pressure Momentum - sector-level C16 rate of change."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

C16 = 'data/features/xs_order_pressure_daily.parquet'
SECTOR = 'data/features/sector_classification.parquet'
LABEL = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

print('='*60)
print('TEST: S245 sector_pressure_momentum')
print('='*60)

c16 = pd.read_parquet(C16, columns=['time', 'ticker', 'order_volume_ratio_rank'])
c16['time'] = pd.to_datetime(c16['time'])
c16 = c16[c16['time'].dt.year.isin(range(2015, 2023))]

sector = pd.read_parquet(SECTOR, columns=['symbol', 'icb_name2'])
sector = sector.rename(columns={'symbol': 'ticker'})

label = pd.read_parquet(LABEL, columns=['time', 'ticker', 'actual'])
label['time'] = pd.to_datetime(label['time'])
label = label[label['time'].dt.year.isin(range(2015, 2023))]

merged = c16.merge(label, on=['time', 'ticker'], how='inner')
merged = merged.merge(sector, on='ticker', how='left')
merged = merged.dropna(subset=['order_volume_ratio_rank', 'actual', 'icb_name2'])

# Sector C16 momentum: sector average C16 change from yesterday
merged = merged.sort_values(['icb_name2', 'time'])
merged['sector_c16_lag1'] = merged.groupby('icb_name2')['order_volume_ratio_rank'].shift(1)
merged['sector_c16_change'] = merged['order_volume_ratio_rank'] - merged['sector_c16_lag1']
merged = merged.dropna(subset=['sector_c16_change'])

# Test: stock C16 conditioned on sector momentum
def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            # Full baseline
            ic_full, _ = spearmanr(y['order_volume_ratio_rank'], y['actual'])
            # Sector momentum > 0 (sector improving)
            pos = y[y['sector_c16_change'] > 0]
            ic_pos = spearmanr(pos['order_volume_ratio_rank'], pos['actual'])[0] if len(pos) > 30 else np.nan
            # Sector momentum < 0 (sector weakening)
            neg = y[y['sector_c16_change'] < 0]
            ic_neg = spearmanr(neg['order_volume_ratio_rank'], neg['actual'])[0] if len(neg) > 30 else np.nan
            results.append({'year': year, 'ic_full': ic_full, 'ic_pos_momentum': ic_pos, 'ic_neg_momentum': ic_neg, 'n': len(y)})
    return pd.DataFrame(results)

results = yearly_ic(merged)

print(f'\nResults:')
print(f'{"Year":<6} {"IC_all":>10} {"IC_sector+":>12} {"IC_sector-":>12} {"n":>10}')
print('-'*52)
for _, r in results.iterrows():
    print(f"{int(r['year']):<6} {r['ic_full']:+10.4f} {r['ic_pos_momentum']:+12.4f} {r['ic_neg_momentum']:+12.4f} {int(r['n']):>10,}")

ic_all = results['ic_full'].mean()
ic_pos = results['ic_pos_momentum'].mean()
ic_neg = results['ic_neg_momentum'].mean()

print(f'\nAverages:')
print(f'  All markets:      IC = {ic_all:+.4f}')
print(f'  Sector rising:    IC = {ic_pos:+.4f} (momentum > 0)')
print(f'  Sector falling:   IC = {ic_neg:+.4f} (momentum < 0)')
print(f'  Diff (pos-neg):   {ic_pos - ic_neg:+.4f}')

# Verdict
baseline = 0.078  # C16 baseline
if ic_pos > baseline + 0.03:
    verdict = 'PASSED - sector momentum boosts'
    tier = 2
elif ic_neg > baseline + 0.03:
    verdict = 'PASSED - sector momentum inverse boost'
    tier = 2
else:
    verdict = 'FAILED - sector momentum no help'
    tier = 4

print(f'\nVerdict: {verdict}')
print(f'Tier: {tier}')
print(f'vs C16 baseline: {ic_all - baseline:+.4f}')

results.to_parquet('alpha-research-lab/analysis/artifacts/s245_sector_momentum.parquet', index=False)
print('\nSaved: artifacts/s245_sector_momentum.parquet')