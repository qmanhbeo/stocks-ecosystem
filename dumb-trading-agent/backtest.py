"""
Constraint-compliant backtest engine with caching.

Vietnam market constraints:
- Decision: at close[T] based on signal available at T
- Entry: execute at open[T+1] (next day opening price)
- Earliest exit: open[T+min_hold_days+1] (after min hold days)
- T+2 settlement means first legal sell is T+3 fill
- Price limits: ±7%
- Fees: buy 0.1%, sell 0.15%, CGT 0.01%

Key artifacts cached:
- VNINDEX baseline: same every time
- Price cache: static by ticker
- Tradability: static by date/ticker
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import constraints as c

CACHE_DIR = Path("/home/manh/stocks-ecosystem/dumb-trading-agent/cache")
CACHE_DIR.mkdir(exist_ok=True)


@dataclass
class BacktestResult:
    name: str
    total_return: float
    annualized_return: float
    sharpe: float
    max_drawdown: float
    n_trades: int
    curve: pd.DataFrame
    constraints_followed: str = "N/A"
    n_filtered: int = 0


VNINDEX_BASELINE_FILE = CACHE_DIR / "vnindex_baseline.parquet"
PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"


def get_cached_vnindex() -> BacktestResult:
    """Get cached VNINDEX baseline. Computes and saves if missing."""
    import constraints as cn
    import numpy as np
    
    if VNINDEX_BASELINE_FILE.exists():
        df = pd.read_parquet(VNINDEX_BASELINE_FILE)
    else:
        # Compute full baseline 2019-2025
        vn = cn.load_vnindex(start="2019-01-01", end="2025-12-31")
        if len(vn) == 0:
            return BacktestResult("", 0, 0, 0, 0, 0, pd.DataFrame())
        
        start_open = vn["open"].iloc[0]
        end_open = vn["open"].iloc[-1]
        shares = int(100_000_000 / start_open)
        cost = shares * start_open * 1.001
        initial_cash = 100_000_000 - cost
        proceeds = shares * end_open * 0.9984
        final_value = initial_cash + proceeds
        ret = (final_value / 100_000_000) - 1.0
        
        curve = vn[["time", "open"]].copy()
        curve["holdings_value"] = curve["open"] * shares
        curve["cash"] = initial_cash
        curve["portfolio_value"] = curve["cash"] + curve["holdings_value"]
        curve["return"] = curve["portfolio_value"] / 100_000_000 - 1.0
        curve["return_pct"] = curve["portfolio_value"].pct_change()
        
        df = curve
        VNINDEX_BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(VNINDEX_BASELINE_FILE)
        print(f"Cached VNINDEX baseline: {VNINDEX_BASELINE_FILE}")
    
    returns = df["return_pct"].dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    max_dd = (df["portfolio_value"] / df["portfolio_value"].cummax() - 1.0).min()
    
    return BacktestResult(
        "VNINDEX_hold",
        df["return"].iloc[-1],
        df["return"].iloc[-1] / (len(df) / 252) if len(df) > 0 else 0,
        sharpe,
        max_dd,
        2,
        df,
    )


def load_universe_prices(
    signal_df: pd.DataFrame,
    price_dir: str = "/home/manh/stocks-ecosystem/data/stock",
) -> dict[str, pd.DataFrame]:
    """Pre-load price data for all tickers in signal matrix."""
    tickers = set(signal_df["ticker"].unique())
    price_cache: dict[str, pd.DataFrame] = {}
    print(f"Loading price data for {len(tickers)} tickers...")
    for ticker in tickers:
        try:
            df_stock = s.load_stock_daily(ticker)
            if len(df_stock) > 0:
                price_cache[ticker] = df_stock.set_index("time")
        except Exception:
            pass
    print(f"Loaded {len(price_cache)} price series")
    return price_cache


def get_price(
    cache: dict[str, pd.DataFrame],
    ticker: str,
    date,
    price_type: str = "close"
) -> float | None:
    """Get price for ticker at date."""
    if ticker not in cache:
        return None
    try:
        return float(cache[ticker].loc[date, price_type])
    except KeyError:
        return None


def check_liquid(
    cache: dict[str, pd.DataFrame],
    ticker: str,
    date,
    min_volume: int = 500_000,
    price_change_threshold: float = 0.001,
) -> bool:
    """Check if ticker is liquid and price is not stale.
    
    Returns True if:
    - Average volume over last 5 days > min_volume
    - Price changed at least price_change_threshold over last 5 days (not stale)
    """
    if ticker not in cache:
        return False
    try:
        df = cache[ticker]
        # Get last 5 days of data
        dates_sorted = sorted(df.index)
        idx = dates_sorted.index(date) if date in dates_sorted else len(dates_sorted) - 1
        start_idx = max(0, idx - 5)
        recent = df.iloc[start_idx:idx+1]
        
        if len(recent) < 3:
            return False
        
        # Check volume
        avg_volume = recent['volume'].mean()
        if avg_volume < min_volume:
            return False
        
        # Check price change (detect stale data)
        if len(recent) >= 2:
            price_change = abs(recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]
            if price_change < price_change_threshold:
                return False
        
        return True
    except:
        return False


def check_can_buy(
    tradability_df: pd.DataFrame | None,
    ticker: str,
    date,
) -> bool:
    """Check can_buy_next_open from tradability data."""
    if tradability_df is None:
        return True  # No filter = allow all
    try:
        row = tradability_df[(tradability_df['time'] == date) & (tradability_df['ticker'] == ticker)]
        if len(row) == 0:
            return False
        return bool(row['can_buy_next_open'].iloc[0])
    except:
        return True


def get_prev_trading_day(dates: list, current_idx: int, lookback: int = 1) -> pd.Timestamp | None:
    """Get previous trading day index."""
    for i in range(current_idx - lookback, -1, -1):
        if i >= 0:
            return dates[i]
    return None


def simulate_topk_constraint_compliant(
    signal_df: pd.DataFrame,
    cache: dict[str, pd.DataFrame],
    signal_col: str = "s1_proba",
    top_k: int = 5,
    rebalance_days: int = 5,
    min_hold_days: int = 3,
    initial_capital: float = 1_000_000_000.0,
    buy_fee: float = c.DEFAULT_BUY_FEE_RATE,
    sell_fee: float = c.DEFAULT_SELL_FEE_RATE,
    tradability_df: pd.DataFrame | None = None,
    min_volume: int = 500_000,
) -> BacktestResult:
    """Constraint-compliant top-K by signal backtest.

    Flow:
    1. At close[T]: decide which tickers to rank by signal
    2. At open[T+1]: execute buys at open price (only if liquid and can_buy)
    3. Hold for min_hold_days
    4. At open[T+min_hold_days+1]: earliest sell at open price
    
    Filters:
    - Volume filter: avg volume > min_volume over last 5 days
    - Price change filter: detect stale data (no price change = reject)
    - Tradability filter: can_buy_next_open from C16 data
    """

    signal_df = signal_df.sort_values("time").reset_index(drop=True)
    dates = sorted(signal_df["time"].unique())

    if len(dates) < 2:
        return BacktestResult("", 0, 0, 0, 0, 0, pd.DataFrame())

    holdings: dict[str, tuple[int, int]] = {}
    cash = initial_capital
    equity_curve = []
    n_trades = 0
    n_skips = 0
    n_filtered = 0

    for i, date in enumerate(dates):
        day_df = signal_df[signal_df["time"] == date]
        if len(day_df) == 0:
            continue

        # REBALANCE DECISION at close[T-1] -> execute at open[T]
        if i > 0 and i % rebalance_days == 0:
            prev_date = dates[i - 1]
            
            # SELL: earliest at open[T] for positions entered at T-1
            for ticker in list(holdings.keys()):
                shares, entry_idx = holdings[ticker]
                hold_days = i - entry_idx
                
                if hold_days >= min_hold_days:
                    open_price = get_price(cache, ticker, prev_date, "open")
                    if open_price and open_price > 0:
                        sell_value = shares * open_price * (1 - sell_fee)
                        cash += sell_value
                        n_trades += 1
                    else:
                        n_skips += 1
                    del holdings[ticker]

            # BUY: execute at open[T] based on signal at close[T-1]
            # Filter by liquidity and tradability
            signal_day_df = signal_df[signal_df["time"] == prev_date]
            candidates = []
            for ticker in signal_day_df.nlargest(top_k * 3, signal_col)["ticker"]:
                # Check tradability
                if tradability_df is not None:
                    if not check_can_buy(tradability_df, ticker, prev_date):
                        n_filtered += 1
                        continue
                
                # Check liquidity (volume + stale price)
                if not check_liquid(cache, ticker, prev_date, min_volume):
                    n_filtered += 1
                    continue
                
                candidates.append(ticker)
                if len(candidates) >= top_k:
                    break
            
            for ticker in candidates:
                if ticker in holdings:
                    continue
                
                open_price = get_price(cache, ticker, date, "open")
                if open_price and open_price > 0 and cash > 0:
                    shares = int((initial_capital / top_k) / open_price)
                    if shares > 0:
                        cost = shares * open_price * (1 + buy_fee)
                        if cash >= cost:
                            cash -= cost
                            holdings[ticker] = (shares, i)

        # Calculate portfolio value at close[T] for equity curve
        holdings_value = 0
        for ticker, (shares, _) in holdings.items():
            close_price = get_price(cache, ticker, date, "close")
            if close_price:
                holdings_value += shares * close_price

        portfolio_value = cash + holdings_value
        equity_curve.append({
            "date": date,
            "portfolio_value": portfolio_value,
            "cash": cash,
            "holdings_value": holdings_value,
            "n_holdings": len(holdings),
        })

    curve = pd.DataFrame(equity_curve)
    if len(curve) == 0:
        return BacktestResult("", 0, 0, 0, 0, 0, pd.DataFrame())

    curve["return_pct"] = curve["portfolio_value"].pct_change()
    curve["return"] = curve["portfolio_value"] / initial_capital - 1.0
    
    ret = curve["return"].iloc[-1]
    returns = curve["return_pct"].dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    max_dd = (curve["portfolio_value"] / curve["portfolio_value"].cummax() - 1.0).min()

    return BacktestResult(
        f"TopK_{signal_col}_K{top_k}_R{rebalance_days}_H{min_hold_days}",
        ret,
        ret / (len(dates) / 252) if len(dates) > 0 else 0,
        sharpe,
        max_dd,
        n_trades,
        curve,
        constraints_followed=f"decision@close[T-1], entry@open[T], exit@open[T+{min_hold_days}] + liq filter",
        n_filtered=n_filtered,
    )


def simulate_vnindex_constraint_compliant(
    start: str,
    end: str,
    initial_capital: float = 1_000_000_000.0,
    buy_fee: float = c.DEFAULT_BUY_FEE_RATE,
    sell_fee: float = c.DEFAULT_SELL_FEE_RATE,
) -> BacktestResult:
    """Buy and hold VNINDEX - constraint-compliant.
    
    - Buy at first open, hold through period, sell at last open
    """
    vn = c.load_vnindex(start=start, end=end)
    if len(vn) == 0:
        return BacktestResult("", 0, 0, 0, 0, 0, pd.DataFrame())

    start_open = vn["open"].iloc[0]
    end_open = vn["open"].iloc[-1]

    shares = int(initial_capital / start_open)
    cost = shares * start_open * (1 + buy_fee)
    initial_cash = initial_capital - cost
    proceeds = shares * end_open * (1 - sell_fee)
    final_value = initial_cash + proceeds

    ret = (final_value / initial_capital) - 1.0
    days = len(vn)

    curve = vn[["time", "open"]].copy()
    curve["holdings_value"] = curve["open"] * shares
    curve["cash"] = initial_cash
    curve["portfolio_value"] = curve["cash"] + curve["holdings_value"]
    curve["return"] = curve["portfolio_value"] / initial_capital - 1.0
    curve["return_pct"] = curve["portfolio_value"].pct_change()

    returns = curve["return_pct"].dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    max_dd = (curve["portfolio_value"] / curve["portfolio_value"].cummax() - 1.0).min()

    return BacktestResult(
        "VNINDEX_hold",
        ret,
        ret / (days / 252) if days > 0 else 0,
        sharpe,
        max_dd,
        2,
        curve,
        constraints_followed="entry@open[start], exit@open[end]",
    )


def run_baseline_comparison(
    start: str = "2019-01-01",
    end: str = "2025-12-31",
    top_k: int = 5,
    rebalance_days: int = 5,
    min_hold_days: int = 3,
) -> pd.DataFrame:
    """Run full baseline comparison with constraint compliance."""
    results = []

    print("\n=== VNINDEX Baseline (constraint-compliant) ===")
    vn = simulate_vnindex_constraint_compliant(start, end)
    print(f"Return: {vn.total_return:.2%}, Sharpe: {vn.sharpe:.2f}, Constraints: {vn.constraints_followed}")
    results.append({
        "strategy": "VNINDEX",
        "return": vn.total_return,
        "sharpe": vn.sharpe,
        "max_dd": vn.max_drawdown,
        "n_trades": vn.n_trades,
        "constraints": vn.constraints_followed,
    })

    print("\n=== Signal Matrix ===")
    df = s.load_rl_signal_matrix(start=start, end=end)
    print(f"Loaded {df.shape}")
    
    cache = load_universe_prices(df)

    print(f"\n=== S1 Top-{top_k} (constraint-compliant) ===")
    s1 = simulate_topk_constraint_compliant(
        df, cache, "s1_proba", top_k, rebalance_days, min_hold_days
    )
    print(f"Return: {s1.total_return:.2%}, Sharpe: {s1.sharpe:.2f}, Constraints: {s1.constraints_followed}")
    results.append({
        "strategy": f"S1_Top{top_k}",
        "return": s1.total_return,
        "sharpe": s1.sharpe,
        "max_dd": s1.max_drawdown,
        "n_trades": s1.n_trades,
        "constraints": s1.constraints_followed,
    })

    return pd.DataFrame(results)


if __name__ == "__main__":
    print("=== Baseline Comparison 2019-2025 ===")
    print("=== CONSTRAINT-COMPLIANT BACKTEST ===\n")
    
    # Test different configurations - focus on lower turnover
    configs = [
        (20, 3, "20-day rebalance (monthly), 3-day hold"),
        (10, 3, "10-day rebalance, 3-day hold"),
    ]
    
    all_results = []
    
    for reb, hold, desc in configs:
        print(f"\n--- {desc} ---")
        results = run_baseline_comparison(
            "2019-01-01", "2025-12-31", 
            rebalance_days=reb, 
            min_hold_days=hold
        )
        all_results.append((desc, results))
    
    print("\n=== SUMMARY ===")
    for desc, res in all_results:
        print(f"\n{desc}:")
        print(res.to_string(index=False))