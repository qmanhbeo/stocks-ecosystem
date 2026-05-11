"""
Quick test: verify 2024 fold result matches walk_forward baseline.
"""

import signals as s
import backtest as bt
import pandas as pd
import constraints as cn


# Load signal for 2024 only
signal_df = s.load_rl_signal_matrix(start="2024-01-01", end="2024-12-31", allow_2026=False)

c16_df = s.load_order_pressure(start="2024-01-01", end="2024-12-31")
c16_df = c16_df[["time", "ticker", "order_volume_ratio_rank"]].copy()
c16_df["time"] = pd.to_datetime(c16_df["time"], errors="coerce").dt.normalize()
signal_df["time"] = pd.to_datetime(signal_df["time"], errors="coerce").dt.normalize()
signal_df = signal_df.merge(c16_df, on=["time", "ticker"], how="left")

if "blend" in signal_df.columns:
    signal_df.drop(columns=["blend"], inplace=True)

signal_df["blend"] = signal_df["s1_proba"] * 0.7 + signal_df["order_volume_ratio_rank"] * 0.3

# Run with default params (no explicit params)
cache = bt.load_price_cache()
liquid_lookup = bt.load_liquid_lookup()
trad_lookup = bt.load_trad_lookup()

result = bt.simulate_topk_constraint_compliant(
    signal_df,
    cache,
    signal_col="blend",
    top_k=5,
    rebalance_days=10,
    min_hold_days=3,
    initial_capital=1_000_000_000.0,
    liquid_lookup=liquid_lookup,
    trad_lookup=trad_lookup,
    collect_diagnostics=False,
)

print(f"total_return: {result.total_return}")
print(f"annualized_return: {result.annualized_return}")
print(f"sharpe: {result.sharpe}")
print(f"max_drawdown: {result.max_drawdown}")
print(f"n_trades: {result.n_trades}")
print(f"n_filtered: {result.n_filtered}")
print(f"final_value: {result.curve['portfolio_value'].iloc[-1]}")

# Compare to walk_forward fold_2024
# fold_2024: total_return=0.186784, annualized_return=0.188279, sharpe=1.166732, max_drawdown=-0.118993, n_trades=52, n_filtered=287, final_value=1186784292.07