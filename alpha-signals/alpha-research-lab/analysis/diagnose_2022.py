"""
Diagnose the 2022 failure: which months, what model predictions, what FPT did.
Helps understand why the X9 ensemble is wrong in 2022 regardless of VNINDEX trend state.
"""
import pandas as pd
import numpy as np

xs  = pd.read_csv('data/features/xs_fpt_proba.csv', parse_dates=['time'])
ss  = pd.read_csv('data/features/ss_fpt_proba_e32.csv', parse_dates=['time'])
vix_df = pd.read_parquet('data/fx-commodities/fx_commodities_vix_1D.parquet')[['time','close']].rename(columns={'close':'vix'})
vix_df['time'] = pd.to_datetime(vix_df['time'])
vni_df = pd.read_parquet('data/stock/gia_lich_su_VNINDEX_1D.parquet')[['time','close']].rename(columns={'close':'vni'})
vni_df['time'] = pd.to_datetime(vni_df['time'])

m = xs.merge(ss[['time','ss_proba']], on='time')
m['ens_proba'] = (m['xs_proba'] + m['ss_proba']) / 2
m['ens_pred']  = (m['ens_proba'] > 0.5).astype(int)
m['xs_pred']   = (m['xs_proba'] > 0.5).astype(int)
m['ss_pred']   = (m['ss_proba'] > 0.5).astype(int)
m['agree']     = (m['xs_pred'] == m['ss_pred']).astype(int)
m['conf']      = (abs(m['ens_proba'] - 0.5) >= 0.05).astype(int)
m['correct']   = (m['ens_pred'] == m['actual']).astype(int)

vix_idx = vix_df.sort_values('time').set_index('time')
vni_s   = vni_df.sort_values('time').copy()
vni_s['ret20'] = vni_s['vni'] / vni_s['vni'].shift(20) - 1
vni_s['ret60'] = vni_s['vni'] / vni_s['vni'].shift(60) - 1
vni_idx = vni_s.set_index('time')

m['vix']   = vix_idx['vix'].reindex(m['time'].values, method='ffill').values
m['vn20']  = vni_idx['ret20'].reindex(m['time'].values, method='ffill').values
m['vn60']  = vni_idx['ret60'].reindex(m['time'].values, method='ffill').values
m['month'] = m['time'].dt.month

y22 = m[m['year'] == 2022].copy()

print("=== 2022 Full Year — All Predicted Days ===")
print(f"Total days: {len(y22)}, naive rate: {y22['actual'].mean():.1%}")
print()

print("=== 2022 X8-E32 Confident Trades (vix>=18, agree, conf) by Month ===")
x8 = y22[(y22['conf']==1) & (y22['agree']==1) & (y22['vix']>=18)]
for mo, g in x8.groupby('month'):
    acc   = g['correct'].mean()
    naive = g['actual'].mean()
    vn60m = g['vn60'].mean()
    pred1_pct = g['ens_pred'].mean()
    print(f"  {mo:02d}/{2022}  n={len(g):3d}  acc={acc:.0%}  naive={naive:.0%}  "
          f"edge={acc-naive:+.0%}  pred_up%={pred1_pct:.0%}  vn60={vn60m:+.1%}")

print()
print("=== X9: With VNINDEX 60d >= -5% filter ===")
x9 = y22[(y22['conf']==1) & (y22['agree']==1) & (y22['vix']>=18) & (y22['vn60']>=-0.05)]
for mo, g in x9.groupby('month'):
    acc   = g['correct'].mean()
    naive = g['actual'].mean()
    print(f"  {mo:02d}/{2022}  n={len(g):3d}  acc={acc:.0%}  naive={naive:.0%}  edge={acc-naive:+.0%}")

print()
print("=== What direction does the ensemble predict in 2022? ===")
print(f"X8 trades — predict UP: {x8['ens_pred'].sum()} ({x8['ens_pred'].mean():.0%}), "
      f"predict DOWN: {(1-x8['ens_pred']).sum()} ({(1-x8['ens_pred']).mean():.0%})")
print(f"Actual UP rate in X8 days: {x8['actual'].mean():.0%}")
print()
print("=== Per-direction accuracy ===")
up_calls   = x8[x8['ens_pred']==1]
down_calls = x8[x8['ens_pred']==0]
if len(up_calls) > 0:
    print(f"  Predicted UP  (n={len(up_calls)}): actual_up={up_calls['actual'].mean():.0%}  "
          f"acc={up_calls['correct'].mean():.0%}")
if len(down_calls) > 0:
    print(f"  Predicted DOWN (n={len(down_calls)}): actual_up={down_calls['actual'].mean():.0%}  "
          f"acc={down_calls['correct'].mean():.0%}")

print()
print("=== 2022 context: what VNINDEX was doing each month ===")
for mo, g in y22.groupby('month'):
    vn20 = g['vn20'].mean()
    vn60 = g['vn60'].mean()
    print(f"  {mo:02d}/2022  vn20_avg={vn20:+.1%}  vn60_avg={vn60:+.1%}  "
          f"n_x8_conf={len(g[(g['conf']==1)&(g['agree']==1)&(g['vix']>=18)])}")
