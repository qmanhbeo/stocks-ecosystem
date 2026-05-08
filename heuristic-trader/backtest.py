"""
Constraint-compliant backtest engine.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import constraints as c

CACHE_DIR = Path("/home/manh/stocks-ecosystem/dumb-trading-agent/cache")
PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"
LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"
TRAD_CACHE_FILE = CACHE_DIR / "trad_lookup.joblib"


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


# === Pre-computed lookup helpers ===

def load_liquid_lookup() -> dict:
    """Load cached liquid date->tickers lookup."""
    import joblib
    if LIQUID_CACHE_FILE.exists():
        return joblib.load(LIQUID_CACHE_FILE)
    return {}


def load_trad_lookup() -> dict:
    """Load cached tradability (ticker,date)->can_buy lookup."""
    import joblib
    if TRAD_CACHE_FILE.exists():
        return joblib.load(TRAD_CACHE_FILE)
    return {}


def is_liquid(ticker: str, date, liquid_lookup: dict) -> bool:
    """Fast liquid check using pre-computed lookup.
    
    Returns True only if:
    - date IS in lookup AND ticker IS in the liquid set for that date
    """
    if date not in liquid_lookup:
        return False  # No data = NOT liquid
    return ticker in liquid_lookup.get(date, set())


def can_buy_fast(ticker: str, date, trad_lookup: dict) -> bool:
    """Fast tradability check using pre-computed lookup.
    
    Returns True only if:
    - (ticker, date) IS in lookup AND can_buy is True
    """
    if (ticker, date) not in trad_lookup:
        return False  # No data = NOT allowed
    return bool(trad_lookup.get((ticker, date), False))


# === Price lookups ===

def load_price_cache() -> dict[str, pd.DataFrame]:
    """Load cached price data."""
    if PRICE_CACHE_FILE.exists():
        pc = pd.read_parquet(PRICE_CACHE_FILE)
        return {t: g.set_index("time") for t, g in pc.groupby("ticker")}
    return {}


def get_price(cache: dict, ticker: str, date, price_type: str = "close") -> float | None:
    """Get price for ticker at date."""
    if ticker not in cache:
        return None
    try:
        return float(cache[ticker].loc[date, price_type])
    except KeyError:
        return None


# === Legacy filter functions (for when pre-computed not available) ===

def check_liquid(cache: dict, ticker: str, date, min_volume: int = 500_000) -> bool:
    """Check liquidity (legacy - compute on the fly)."""
    if ticker not in cache:
        return False
    try:
        df = cache[ticker]
        dates_sorted = sorted(df.index)
        idx = dates_sorted.index(date) if date in dates_sorted else len(dates_sorted) - 1
        start_idx = max(0, idx - 5)
        recent = df.iloc[start_idx:idx+1]
        if len(recent) < 3:
            return False
        avg_volume = recent['volume'].mean()
        if avg_volume < min_volume:
            return False
        if len(recent) >= 2:
            price_change = abs(recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]
            if price_change < 0.001:
                return False
        return True
    except:
        return False


def check_can_buy(tradability_df: pd.DataFrame | None, ticker: str, date) -> bool:
    """Check can_buy_next_open (legacy - compute on the fly)."""
    if tradability_df is None:
        return True
    try:
        row = tradability_df[(tradability_df['time'] == date) & (tradability_df['ticker'] == ticker)]
        if len(row) == 0:
            return False
        return bool(row['can_buy_next_open'].iloc[0])
    except:
        return True


# === Main backtest function ===

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
    use_filters: bool = True,
    liquid_lookup: dict | None = None,  # NEW: pre-computed
    trad_lookup: dict | None = None,     # NEW: pre-computed
) -> BacktestResult:
    """Constraint-compliant top-K by signal backtest."""

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

        # REBALANCE at every rebalance_days
        if i > 0 and i % rebalance_days == 0:
            prev_date = dates[i - 1]
            
            # SELL positions held >= min_hold_days
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

            # BUY new positions
            signal_day_df = signal_df[signal_df["time"] == prev_date]
            candidates = []
            for ticker in signal_day_df.nlargest(top_k * 3, signal_col)["ticker"]:
                # Check tradability
                if use_filters:
                    if trad_lookup is not None:
                        if not can_buy_fast(ticker, prev_date, trad_lookup):
                            n_filtered += 1
                            continue
                    elif tradability_df is not None:
                        if not check_can_buy(tradability_df, ticker, prev_date):
                            n_filtered += 1
                            continue
                
                # Check liquidity
                if use_filters:
                    if liquid_lookup is not None:
                        if not is_liquid(ticker, prev_date, liquid_lookup):
                            n_filtered += 1
                            continue
                    elif not check_liquid(cache, ticker, prev_date, min_volume):
                        n_filtered += 1
                        continue
                
                candidates.append(ticker)
                if len(candidates) >= top_k:
                    break
            
            # Execute buys
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

        # Calculate portfolio value
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
        ret / (len(curve) / 252) if len(curve) > 0 else 0,
        sharpe,
        max_dd,
        n_trades,
        curve,
        n_filtered=n_filtered,
    )


def get_cached_vnindex() -> BacktestResult:
    """Get VNINDEX baseline (cached)."""
    import signals as s
    
    VNINDEX_FILE = CACHE_DIR / "vnindex_baseline.parquet"
    if VNINDEX_FILE.exists():
        df = pd.read_parquet(VNINDEX_FILE)
    else:
        import constraints as cn
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
        df.to_parquet(VNINDEX_FILE)
    
    import numpy as np
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