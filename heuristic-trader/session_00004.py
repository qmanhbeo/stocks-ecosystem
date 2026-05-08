"""Session 00004: C16 vs S1 comparison - constraint-compliant.

Hypothesis: C16 (order pressure) should outperform S1 under proper constraints
because C16 has higher standalone IC and persistence.

Walk-forward validation: 2019-2025, testing per-year IC and returns.
"""

import pandas as pd
import numpy as np
import sys
sys.path.insert(0, "/home/manh/stocks-ecosystem/dumb-trading-agent")
import signals as s
import constraints as c
from backtest import simulate_topk_constraint_compliant, load_universe_prices


def compute_ic_per_year(signal_df: pd.DataFrame, signal_col: str, actual_col: str = "actual") -> pd.DataFrame:
    """Compute IC per year for a signal."""
    signal_df = signal_df.copy()
    signal_df["year"] = signal_df["time"].dt.year
    
    results = []
    for year in sorted(signal_df["year"].unique()):
        year_df = signal_df[signal_df["year"] == year].dropna(subset=[signal_col, actual_col])
        if len(year_df) > 10:
            ic = year_df[signal_col].corr(year_df[actual_col])
            results.append({"year": year, "ic": ic, "n": len(year_df)})
    
    return pd.DataFrame(results)


def run_wf_ic_test(signal_col: str, start: str = "2019-01-01", end: str = "2025-12-31") -> dict:
    """Walk-forward IC test per year."""
    df = s.load_rl_signal_matrix(start=start, end=end)
    if signal_col not in df.columns:
        print(f"Signal {signal_col} not in matrix, loading separate...")
        if signal_col == "order_volume_ratio_rank":
            df_op = s.load_order_pressure(start=start, end=end)
            df = df.merge(df_op[["time", "ticker", "order_volume_ratio_rank"]], 
                       on=["time", "ticker"], how="left")
        else:
            raise ValueError(f"Unknown signal: {signal_col}")
    
    df = df.dropna(subset=[signal_col, "actual"])
    ic_per_year = compute_ic_per_year(df, signal_col)
    
    return {
        "signal": signal_col,
        "avg_ic": ic_per_year["ic"].mean(),
        "positive_years": (ic_per_year["ic"] > 0).sum(),
        "total_years": len(ic_per_year),
        "ic_per_year": ic_per_year.to_dict(),
    }


def run_wf_backtest(signal_col: str, top_k: int = 5, rebalance_days: int = 5, 
                  min_hold_days: int = 3, start: str = "2019-01-01", 
                  end: str = "2025-12-31") -> dict:
    """Walk-forward backtest."""
    if signal_col == "order_volume_ratio_rank":
        df = s.load_order_pressure(start=start, end=end)
    else:
        df = s.load_rl_signal_matrix(start=start, end=end)
    
    cache = load_universe_prices(df)
    
    result = simulate_topk_constraint_compliant(
        df, cache, signal_col, top_k, rebalance_days, min_hold_days
    )
    
    return {
        "signal": signal_col,
        "return": result.total_return,
        "sharpe": result.sharpe,
        "max_dd": result.max_drawdown,
        "n_trades": result.n_trades,
    }


if __name__ == "__main__":
    print("=== Session 00004: C16 vs S1 Walk-Forward Test ===\n")
    
    # For fair comparison, need to merge both signals on same panel
    df_s1 = s.load_rl_signal_matrix(start="2019-01-01", end="2025-12-31")
    df_c16 = s.load_order_pressure(start="2019-01-01", end="2025-12-31")
    
    merged = df_s1.merge(
        df_c16[["time", "ticker", "order_volume_ratio_rank"]], 
        on=["time", "ticker"], how="inner"
    )
    merged = merged.dropna(subset=["s1_proba", "order_volume_ratio_rank", "actual"])
    print(f"Merged panel: {merged.shape}")
    
    # IC per year for both signals
    print("\n--- IC per year ---")
    for sig in ["s1_proba", "order_volume_ratio_rank"]:
        ic_per_year = compute_ic_per_year(merged, sig)
        print(f"\n{sig}:")
        print(ic_per_year.to_string(index=False))
        print(f"Avg IC: {ic_per_year['ic'].mean():.4f}, Positive years: {(ic_per_year['ic']>0).sum()}/{len(ic_per_year)}")
    
    # Constraint-compliant backtest comparison
    print("\n--- Constraint-Compliant Backtest (5-day rebalance, 3-day hold) ---")
    
    # VNINDEX baseline
    from backtest import simulate_vnindex_constraint_compliant
    vn = simulate_vnindex_constraint_compliant("2019-01-01", "2025-12-31")
    print(f"VNINDEX: return {vn.total_return:.2%}, sharpe {vn.sharpe:.2f}, trades {vn.n_trades}")
    
    # S1 backtest
    print("\nLoading prices for S1 test...")
    df = s.load_rl_signal_matrix(start="2019-01-01", end="2025-12-31")
    cache = load_universe_prices(df)
    s1_result = simulate_topk_constraint_compliant(df, cache, "s1_proba", 5, 5, 3)
    print(f"S1 Top-5: return {s1_result.total_return:.2%}, sharpe {s1_result.sharpe:.2f}, trades {s1_result.n_trades}")
    
    # C16 backtest
    print("\nLoading prices for C16 test...")
    df_c16 = s.load_order_pressure(start="2019-01-01", end="2025-12-31")
    cache_c16 = load_universe_prices(df_c16)
    c16_result = simulate_topk_constraint_compliant(df_c16, cache_c16, "order_volume_ratio_rank", 5, 5, 3)
    print(f"C16 Top-5: return {c16_result.total_return:.2%}, sharpe {c16_result.sharpe:.2f}, trades {c16_result.n_trades}")
    
    print("\n=== SUMMARY ===")
    print(f"VNINDEX: {vn.total_return:.2%}")
    print(f"S1 Top-5: {s1_result.total_return:.2%}")
    print(f"C16 Top-5: {c16_result.total_return:.2%}")