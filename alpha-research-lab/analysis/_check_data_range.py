import pandas as pd
from pathlib import Path
from path_utils import data_path

fpt = pd.read_parquet(data_path("stock/gia_lich_su_FPT_1D.parquet"))
fpt['time'] = pd.to_datetime(fpt['time'])
print('FPT OHLC last date:', fpt['time'].max())
print('FPT OHLC rows in 2026:', len(fpt[fpt['time'].dt.year == 2026]))

vni = pd.read_parquet(data_path("stock/gia_lich_su_VNINDEX_1D.parquet"))
vni['time'] = pd.to_datetime(vni['time'])
print('VNINDEX last date:', vni['time'].max())

# Count how many stock files have 2026 data
stock_dir = data_path("stock")
n_with_2026 = 0
for f in sorted(stock_dir.glob('gia_lich_su_*_1D.parquet')):
    df = pd.read_parquet(f, columns=['time'])
    df['time'] = pd.to_datetime(df['time'])
    if df['time'].dt.year.max() >= 2026:
        n_with_2026 += 1
print(f'Stock files with 2026 data: {n_with_2026}')
