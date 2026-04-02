import pandas as pd
from pathlib import Path
from path_utils import data_path

# VIX data coverage
vix = pd.read_parquet(data_path("fx-commodities/fx_commodities_vix_1D.parquet"))
vix['time'] = pd.to_datetime(vix['time'])
print('VIX last date:', vix['time'].max())
print('VIX 2026 rows:', len(vix[vix['time'].dt.year == 2026]))

# Stock 2026 coverage
stock_dir = data_path("stock")
stocks_2026 = []
for f in sorted(stock_dir.glob('gia_lich_su_*_1D.parquet')):
    ticker = f.name.replace('gia_lich_su_', '').replace('_1D.parquet', '')
    if ticker in ('VNINDEX', 'VN30'):
        continue
    df = pd.read_parquet(f, columns=['time'])
    df['time'] = pd.to_datetime(df['time'])
    if df['time'].dt.year.max() >= 2026:
        n = len(df[df['time'].dt.year == 2026])
        stocks_2026.append((ticker, n))

print(f'\nStocks with 2026 data: {len(stocks_2026)}')
if stocks_2026:
    total_rows = sum(r for _, r in stocks_2026)
    print(f'Total 2026 rows across all stocks: {total_rows}')
    print(f'Avg 2026 rows per stock: {total_rows/len(stocks_2026):.0f}')
    tickers = [t for t, _ in stocks_2026]
    print(f'Sample tickers: {tickers[:10]}')
