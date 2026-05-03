#!/usr/bin/env python
"""S250: C16 × Volume Shock - C16 conditioned on volume spike in down markets."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

C16 = 'data/features/xs_order_pressure_daily.parquet'
LABEL = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

print('='*60)
print('TEST: S250 c16_vol_shock')
print('='*60)

c16 = pd.read_parquet(C16, columns=['time', 'ticker', 'order_volume_ratio_rank'])
c16['time'] = pd.to_datetime(c16['time'])
c16 = c16[c16['time'].dt.year.isin(range(2015, 2023))]

label = pd.read_parquet(LABEL, columns=['time', 'ticker', 'actual'])
label['time'] = pd.to_datetime(label['time'])
label = label[label['time'].dt.year.isin(range(2015, 2023))]

merged = c16.merge(label, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['order_volume_ratio_rank', 'actual'])

# Compute daily volume rank per ticker (as proxy for volume shock)
# We don't have volume directly, so use order_volume_ratio_rank as proxy
# But that's C16... Let's compute average actual as liquidity proxy

# Market state
daily = merged.groupby('time')['actual'].median().reset_index(name='market_return')
daily['market_direction'] = (daily['market_return'] < 0).astype(int)  # 0 = down, 1 = up
merged = merged.merge(daily[['time', 'market_direction']], on='time', how='left')

# Volume proxy: use number of stocks with extreme actual returns as "volume shock" proxy
# More stocks with |actual| > 2% = high volume day
daily['vol_shock'] = merged.groupby('time').apply(
    lambda x: (x['actual'].abs() > 0.02).mean()
)
daily['vol_shock_z'] = (daily['vol_shock'] - daily['vol_shock'].mean()) / daily['vol_shock'].std()
daily['vol_spike'] = (daily['vol_shock_z'] > 1).astype(int)  # > 1 std
merged = merged.merge(daily[['time', 'vol_spike', 'vol_shock_z']], on='time', how='left')

def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            # All
            ic_all, _ = spearmanr(y['order_volume_ratio_rank'], y['actual'])
            
            # Down + any C16
            down = y[y['market_direction'] == 0]
            ic_down = spearmanr(down['order_volume_ratio_rank'], down['actual'])[0] if len(down) > 30 else np.nan
            
            # Down + vol spike (high activity)
            down_vol = y[(y['market_direction'] == 0) & (y['vol_spike'] == 1)]
            ic_down_vol = spearmanr(down_vol['order_volume_ratio_rank'], down_vol['actual'])[0] if len(down_vol) > 30 else np.nan
            
            # Down + low vol (quiet day)
            down_quiet = y[(y['market_direction'] == 0) & (y['vol_spike'] == 0)]
            ic_down_quiet = spearmanr(down_quiet['order_volume_ratio_rank'], down_quiet['actual'])[0] if len(down_quiet) > 30 else np.nan
            
            # Up markets
            up = y[y['market_direction'] == 1]
            ic_up = spearmanr(up['order_volume_ratio_rank'], up['actual'])[0] if len(up) > 30 else np.nan
            
            results.append({
                'year': year, 'ic_all': ic_all, 'ic_down': ic_down, 
                'ic_down_vol': ic_down_vol, 'ic_down_quiet': ic_down_quiet, 'ic_up': ic_up, 'n': len(y)
            })
    return pd.DataFrame(results)

results = yearly_ic(merged)

print(f'\nResults:')
print(f'{"Year":<6} {"IC_all":>8} {"IC_dn":>8} {"IC_dn+vol":>10} {"IC_dn+quiet":>12} {"IC_up":>8} {"n":>10}')
print('-'*62)
for _, r in results.iterrows():
    print(f"{int(r['year']):<6} {r['ic_all']:+8.4f} {r['ic_down']:+8.4f} {r['ic_down_vol']:+10.4f} {r['ic_down_quiet']:+12.4f} {r['ic_up']:+8.4f} {int(r['n']):>10,}")

ic_all = results['ic_all'].mean()
ic_down = results['ic_down'].mean()
ic_down_vol = results['ic_down_vol'].mean()
ic_down_quiet = results['ic_down_quiet'].mean()
ic_up = results['ic_up'].mean()

print(f'\nAverages:')
print(f'  All markets:    IC = {ic_all:+.4f}')
print(f'  Down only:      IC = {ic_down:+.4f}')
print(f'  Down + vol:     IC = {ic_down_vol:+.4f}')
print(f'  Down + quiet:   IC = {ic_down_quiet:+.4f}')
print(f'  Up only:        IC = {ic_up:+.4f}')

baseline = 0.078
# Check best
if ic_down_vol > ic_down + 0.03:
    verdict = f'PASSED - vol spike amplifies ({ic_down_vol:+.4f})'
    tier = 2
elif ic_down > baseline + 0.02:
    verdict = f'PASSED - down strong ({ic_down:+.4f})'
    tier = 2
else:
    verdict = 'WEAK'

print(f'\nVerdict: {verdict}')
print(f'vs C16 baseline: {ic_down - baseline:+.4f}')

results.to_parquet('/home/manh/stocks-ecosystem/alpha-research-lab/analysis/artifacts/s250_c16_vol_shock.parquet', index=False)
print('\nSaved: artifacts/s250_c16_vol_shock.parquet')