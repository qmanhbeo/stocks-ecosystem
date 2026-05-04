import signals as s
import pandas as pd
from backtest import simulate_topk_constraint_compliant

trad = s.load_order_pressure(start='2019-01-01', end='2025-12-31')[['time','ticker','can_buy_next_open']]
pc = pd.read_parquet('cache/price_cache.parquet')
price_cache = {t: g.set_index('time') for t, g in pc.groupby('ticker')}

s1 = s.load_rl_signal_matrix(start='2019-01-01', end='2025-12-31')
c16 = s.load_order_pressure(start='2019-01-01', end='2025-12-31')
df = s1[['time','ticker','s1_proba']].merge(c16[['time','ticker','order_volume_ratio_rank']], on=['time','ticker'])

print('=== Blend weights (NO filters - quick) ===')
for w in [0.3, 0.5, 0.7, 0.8]:
    df_test = df.copy()
    df_test['blend'] = df_test['s1_proba'] * w + df_test['order_volume_ratio_rank'] * (1-w)
    r = simulate_topk_constraint_compliant(
        df_test, price_cache, 'blend', top_k=5, 
        rebalance_days=10, min_hold_days=3, 
        tradability_df=trad, min_volume=500_000,
        use_filters=False  # QUICK - no liquidity/tradability checks
    )
    print(f'{w:.0%}S1/{(1-w):.0%}C16: {r.total_return:>7.2%} ({r.n_trades}tr)')