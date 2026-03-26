import pandas as pd
probas = pd.read_parquet('data/features/xs_barrier_all_probas_hose_full.parquet')
probas['time'] = pd.to_datetime(probas['time'])
years = sorted(probas['time'].dt.year.unique())
print('Years in probas:', years)
yr2026 = probas[probas['time'].dt.year == 2026]
print('2026 rows:', len(yr2026))
if len(yr2026) > 0:
    print('2026 date range:', yr2026['time'].min(), '->', yr2026['time'].max())
    print('2026 tickers:', yr2026['ticker'].nunique())
