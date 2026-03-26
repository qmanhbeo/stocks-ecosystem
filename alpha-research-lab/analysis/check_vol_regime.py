import pandas as pd, numpy as np

df = pd.read_parquet('data/stock/gia_lich_su_VNINDEX_1D.parquet')
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time')
df['ret'] = df['close'].pct_change()
df['vol20'] = df['ret'].rolling(20).std() * np.sqrt(252)
df['vol_pct'] = df['vol20'].expanding(min_periods=252).rank(pct=True)
df['high_vol'] = (df['vol_pct'] > 0.70).astype(int)
df['year'] = df['time'].dt.year

summary = df[df['year'].between(2019,2025)].groupby('year').agg(
    n_days=('time','count'),
    high_vol_days=('high_vol','sum'),
    avg_ann_vol=('vol20','mean')
)
summary['pct_high'] = (summary['high_vol_days'] / summary['n_days'] * 100).round(1)
summary['avg_ann_vol'] = (summary['avg_ann_vol'] * 100).round(1)
print(summary.to_string())
