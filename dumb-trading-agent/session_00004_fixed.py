"""Session 00004 FIXED: C16 vs S1 comparison with tradability filter.

This session tests the SAME baseline to compare different strategies.
Key optimization: VNINDEX and price cache are cached.
"""

import pandas as pd
import numpy as np
import sys
sys.path.insert(0, "/home/manh/stocks-ecosystem/dumb-trading-agent")
import signals as s
import constraints as c
from backtest import (
    simulate_topk_constraint_compliant, 
    load_universe_prices,
    get_cached_vnindex,
)
from pathlib import Path

CACHE_DIR = Path("/home/manh/stocks-ecosystem/dumb-trading-agent/cache")
PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"


def load_or_build_price_cache(signal_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Load cached price data or build if missing."""
    import signals as slib
    import glob
    
    if PRICE_CACHE_FILE.exists():
        print("Loading cached price cache...")
        cache_df = pd.read_parquet(PRICE_CACHE_FILE)
        return {ticker: grp.set_index("time") for ticker, grp in cache_df.groupby("ticker")}
    
    print("Building price cache (one-time)...")
    tickers = set(signal_df["ticker"].unique())
    rows = []
    for ticker in tickers:
        try:
            df_stock = slib.load_stock_daily(ticker)
            df_stock["ticker"] = ticker
            rows.append(df_stock)
        except Exception:
            pass
    cache_df = pd.concat(rows, ignore_index=True)
    cache_df.to_parquet(PRICE_CACHE_FILE)
    print(f"Cached: {PRICE_CACHE_FILE}")
    return {ticker: grp.set_index("time") for ticker, grp in cache_df.groupby("ticker")}


def run_grid_search(
    signal_df: pd.DataFrame,
    signal_col: str,
    price_cache: dict,
    tradability_df: pd.DataFrame | None,
    param_grid: list[dict],
) -> pd.DataFrame:
    """Run grid search over parameter combinations."""
    results = []
    for params in param_grid:
        result = simulate_topk_constraint_compliant(
            signal_df, price_cache, signal_col,
            top_k=params.get("top_k", 5),
            rebalance_days=params.get("rebalance_days", 5),
            min_hold_days=params.get("min_hold_days", 3),
            tradability_df=tradability_df,
            min_volume=params.get("min_volume", 500_000),
        )
        results.append({**params, "return": result.total_return, "sharpe": result.sharpe, "trades": result.n_trades, "filtered": result.n_filtered})
        print(f"  {params} -> {result.total_return:.2%}")
    return pd.DataFrame(results)


if __name__ == "__main__":
    print("=== S00004 FIXED: Grid Search ===", flush=True)
    
    vn = get_cached_vnindex()
    print(f"VNINDEX: {vn.total_return:.2%}", flush=True)
    
    # Load data once
    print("Loading data...", flush=True)
    start, end = "2019-01-01", "2025-12-31"
    c16_df = s.load_order_pressure(start=start, end=end)
    tradability_df = c16_df[["time", "ticker", "can_buy_next_open"]].copy()
    df_s1 = s.load_rl_signal_matrix(start=start, end=end)
    price_cache = load_or_build_price_cache(df_s1)
    
    # Grid search: rebalance periods
    print("\n--- S1 Grid: rebalance_days ---", flush=True)
    for rebal in [5, 10, 20]:
        r = simulate_topk_constraint_compliant(
            df_s1, price_cache, "s1_proba", top_k=5, 
            rebalance_days=rebal, min_hold_days=3,
            tradability_df=tradability_df, min_volume=500_000,
        )
        print(f"rebal={rebal}d: ret={r.total_return:>7.2%}, trades={r.n_trades}, filt={r.n_filtered}", flush=True)
    
    # Grid search: top_k
    print("\n--- S1 Grid: top_k ---", flush=True)
    for k in [3, 5]:
        r = simulate_topk_constraint_compliant(
            df_s1, price_cache, "s1_proba", top_k=k, 
            rebalance_days=10, min_hold_days=3,
            tradability_df=tradability_df, min_volume=500_000,
        )
        print(f"top_k={k}: ret={r.total_return:>7.2%}, trades={r.n_trades}", flush=True)
    
    # C16
    print("\n--- C16 Top-5 ---", flush=True)
    c16_r = simulate_topk_constraint_compliant(
        c16_df, price_cache, "order_volume_ratio_rank", top_k=5,
        rebalance_days=5, min_hold_days=3,
        tradability_df=tradability_df, min_volume=500_000,
    )
    print(f"C16: ret={c16_r.total_return:>7.2%}, trades={c16_r.n_trades}", flush=True)
    
    print("\n=== DONE ===", flush=True)