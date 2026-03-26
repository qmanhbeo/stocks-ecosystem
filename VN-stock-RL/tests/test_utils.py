"""
Shared Utilities for Bookkeeping Tests

This module contains common functionality used across all test files.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple

from vn_stock_rl.env import BaseTradingEnv


class TestEnv(BaseTradingEnv):
    """
    Test environment with controlled data and episode range.
    
    This allows us to:
    - Use synthetic price data with known properties
    - Control the exact episode boundaries
    - Test specific scenarios in isolation
    """
    
    def __init__(self, df: pd.DataFrame, start_idx: int, end_idx: int, **kwargs):
        self._df_source = df.reset_index(drop=True)
        self._start_idx = start_idx
        self._end_idx = end_idx
        kwargs.setdefault("drawdown_penalty_enabled", False)
        super().__init__(**kwargs)

    def _setup_data(self):
        self.df = self._df_source
        cache = self._compute_cache_from_df(self.df)
        self._set_active_cache(cache)

    def _get_current_dataframe(self) -> pd.DataFrame:
        return self.df

    def _reset_episode_range(self):
        self.episode_start_idx = self._start_idx
        self.episode_end_idx = self._end_idx


TestEnv.__test__ = False


def create_price_dataframe(opens: List[float]) -> pd.DataFrame:
    """
    Create a simple dataframe with constant OHLC prices.
    
    Args:
        opens: List of open prices (used for all OHLC values)
        
    Returns:
        DataFrame with time, open, high, low, close, volume columns
    """
    return pd.DataFrame({
        "time": np.arange(len(opens)),
        "open": opens,
        "high": opens,
        "low": opens,
        "close": opens,
        "volume": np.ones(len(opens)),
    })


def run_episode(env: TestEnv, actions: List[int]) -> Tuple[List[Dict], pd.DataFrame]:
    """
    Run an episode and collect detailed step-by-step history.
    
    Args:
        env: Test environment
        actions: List of actions to take (0=sell/flat, 1=buy/long)
        
    Returns:
        history: List of dictionaries containing all state variables for each step
        df: The price dataframe
    """
    env.reset()
    df = env._get_current_dataframe()
    history = []
    
    for action in actions:
        # Capture pre-step state
        pre_idx = env.current_step
        open_prev = df.iloc[pre_idx]["open"]
        open_exec = df.iloc[pre_idx + 1]["open"]
        pre_cash, pre_shares = env.cash, env.shares
        pos_old = env.position
        pending = env.pending_action
        
        # Take action
        _, reward, terminated, truncated, _ = env.step(action)
        
        # Capture post-step state
        post_cash, post_shares = env.cash, env.shares
        pos_new = env.position
        equity_t = pre_cash + pre_shares * open_prev
        equity_t1 = post_cash + post_shares * open_exec
        
        history.append({
            "step": len(history),
            "pre_idx": pre_idx,
            "open_prev": open_prev,
            "open_exec": open_exec,
            "pos_old": pos_old,
            "pos_new": pos_new,
            "action": action,
            "pending": pending,
            "pre_cash": pre_cash,
            "pre_shares": pre_shares,
            "post_cash": post_cash,
            "post_shares": post_shares,
            "equity_t": equity_t,
            "equity_t1": equity_t1,
            "reward": reward,
        })
        
        if terminated or truncated:
            break
    
    return history, df


def format_history(history: List[Dict]) -> str:
    """
    Format history for debugging output.
    
    Creates a table showing all state variables for each step.
    """
    header = (
        "step pre_idx open_prev open_exec pos_old pos_new action pending "
        "pre_cash pre_shares post_cash post_shares equity_t equity_t1 reward"
    )
    lines = [header]
    for row in history:
        lines.append(
            f"{row['step']:>4} {row['pre_idx']:>7} {row['open_prev']:>9.4f} {row['open_exec']:>9.4f} "
            f"{row['pos_old']:>7} {row['pos_new']:>7} {row['action']:>6} {row['pending']:>7} "
            f"{row['pre_cash']:>8.6f} {row['pre_shares']:>9.6f} "
            f"{row['post_cash']:>9.6f} {row['post_shares']:>10.6f} "
            f"{row['equity_t']:>9.6f} {row['equity_t1']:>10.6f} {row['reward']:>8.6f}"
        )
    return "\n".join(lines)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(title)
    print("="*80)


def print_subsection(title: str):
    """Print a formatted subsection header."""
    print(f"\n{title}")
    print("-" * len(title))
