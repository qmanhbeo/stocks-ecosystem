import signals as s
import pandas as pd
import joblib
from backtest import simulate_topk_constraint_compliant, load_liquid_lookup, load_trad_lookup
from pathlib import Path

CACHE_DIR = Path("/home/manh/stocks-ecosystem/dumb-trading-agent/cache")

# Load pre-computed
liquid_lookup = load_liquid_lookup()
trad_lookup = load_trad_lookup()
print(f"Liquid: {len(liquid_lookup)} dates")
print(f"Trad: {len(trad_lookup)} entries")

# Load price cache
pc = pd.read_parquet('cache/price_cache.parquet')
price_cache = {t: g.set_index("time") for t, g in pc.groupby("ticker")}

# Load signals
s1 = s.load_rl_signal_matrix(start='2019-01-01', end='2025-12-31')
c16 = s.load_order_pressure(start='2019-01-01', end='2025-12-31')
df = s1[['time','ticker','s1_proba']].merge(c16[['time','ticker','order_volume_ratio_rank']], on=['time','ticker'])
df['blend'] = df['s1_proba'] * 0.7 + df['order_volume_ratio_rank'] * 0.3

# Run with pre-computed
import time
start = time.time()
r = simulate_topk_constraint_compliant(df, price_cache, 'blend', top_k=5, rebalance_days=10, min_hold_days=3, use_filters=True, liquid_lookup=liquid_lookup, trad_lookup=trad_lookup)
elapsed = time.time() - start

print(f"70/30 with pre-computed: {r.total_return:.2%} ({r.n_trades}tr, {elapsed:.1f}s)")