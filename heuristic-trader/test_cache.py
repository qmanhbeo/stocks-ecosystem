import signals as s
import pandas as pd
import joblib
from backtest import simulate_topk_constraint_compliant
from pathlib import Path

CACHE_DIR = Path("/home/manh/stocks-ecosystem/dumb-trading-agent/cache")
LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"

# Load cached
liquid_lookup = joblib.load(LIQUID_CACHE_FILE)
print(f"Loaded liquid cache: {len(liquid_lookup)} dates")

trad = s.load_order_pressure(start='2019-01-01', end='2025-12-31')[['time','ticker','can_buy_next_open']]
pc = pd.read_parquet('cache/price_cache.parquet')
price_cache = {t: g.set_index("time") for t, g in pc.groupby("ticker")}

s1 = s.load_rl_signal_matrix(start='2019-01-01', end='2025-12-31')
c16 = s.load_order_pressure(start='2019-01-01', end='2025-12-31')
df = s1[['time','ticker','s1_proba']].merge(c16[['time','ticker','order_volume_ratio_rank']], on=['time','ticker'])
df['blend'] = df['s1_proba'] * 0.7 + df['order_volume_ratio_rank'] * 0.3

# Quick test (ablation - no filters)
r = simulate_topk_constraint_compliant(df, price_cache, 'blend', top_k=5, rebalance_days=10, min_hold_days=3, tradability_df=None, use_filters=False)
print(f"70/30 no filter: {r.total_return:.2%} ({r.n_trades}tr)")
print(f"Expected with filters: ~82%")