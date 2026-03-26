from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vn_stock_rl.evaluation.metadata import _to_json_safe

def _extract_trades(
    df_history: pd.DataFrame,
    buy_fee_rate: float = 0.0,
    sell_fee_rate: float = 0.0,
    capital_gains_tax_rate: float = 0.0,
) -> pd.DataFrame:
    trades = []
    if len(df_history) < 2:
        return pd.DataFrame(trades)

    fee_multiplier = (
        (1.0 - float(buy_fee_rate))
        * (1.0 - float(sell_fee_rate) - float(capital_gains_tax_rate))
    )
    positions = df_history['position'].to_numpy()
    steps = df_history['step'].to_numpy()
    open_prices = df_history['open'].to_numpy()
    dates = df_history['date'].to_numpy()

    entry_step = None
    entry_price = None
    entry_date = None

    for i in range(1, positions.shape[0]):
        prev_pos = positions[i - 1]
        curr_pos = positions[i]

        # Detect entry (position changes from 0 to 1)
        if curr_pos == 1 and prev_pos == 0:
            entry_step = steps[i]
            entry_price = open_prices[i]
            entry_date = dates[i]
            continue

        # Detect exit (position changes from 1 to 0)
        if curr_pos == 0 and prev_pos == 1 and entry_step is not None:
            exit_step = steps[i]
            exit_price = open_prices[i]
            exit_date = dates[i]

            gross_multiplier = float(exit_price) / float(entry_price)
            net_return = (fee_multiplier * gross_multiplier) - 1.0
            hold_days = exit_step - entry_step

            trades.append({
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_step': entry_step,
                'exit_step': exit_step,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'hold_days': hold_days,
                'return': net_return,
                'profit': 'Win' if net_return > 0 else 'Loss'
            })

            entry_step = None

    return pd.DataFrame(trades)

def _persist_eval_outputs(
    output_dir: str,
    metrics_only: bool,
    df_history: pd.DataFrame,
    stats: Dict[str, Any],
    model_type: str,
    stock: str,
    mode: str,
    aligned_buy_hold_series: Optional[np.ndarray],
    metrics: Dict[str, Any],
):
    if not metrics_only:
        results_file = os.path.join(output_dir, "evaluation_history.csv")
        df_history.to_csv(results_file, index=False)
        print(f"\nResults saved to: {results_file}")
        print("\nGenerating visualizations...")
        create_plots(df_history, stats, output_dir, model_type, stock, mode, buy_hold_series=aligned_buy_hold_series)

    metrics_path = os.path.join(output_dir, "metrics_summary.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(metrics), f, indent=2)
    if not metrics_only:
        pd.DataFrame([metrics]).to_csv(os.path.join(output_dir, "metrics_summary.csv"), index=False)

def create_plots(df_history, stats, output_dir, model_type, stock, mode, buy_hold_series=None):
    """Create visualization plots."""
    
    fig, axes = plt.subplots(4, 1, figsize=(15, 12))
    mode_label = {
        "train": "Training",
        "val": "Validation",
        "test": "Test",
    }.get(mode, str(mode).title())
    fig.suptitle(
        f'RL Trading Agent Evaluation ({model_type}) - {stock} - {mode_label} set',
        fontsize=16,
        fontweight='bold'
    )
    
    # Plot 1: Price and positions
    ax1 = axes[0]
    ax1.plot(df_history['step'], df_history['close'], label='Close Price', color='black', alpha=0.7)
    
    # Highlight long positions
    long_mask = df_history['position'] == 1
    ax1.fill_between(df_history['step'], df_history['close'].min(), df_history['close'].max(),
                      where=long_mask, alpha=0.2, color='green', label='Long Position')
    
    ax1.set_xlabel('Step')
    ax1.set_ylabel('Price')
    ax1.set_title('Price Chart with Positions')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Cumulative returns (now both using geometric/multiplicative returns)
    ax2 = axes[1]
    # Convert portfolio value to return percentage
    rl_return = (df_history['portfolio_value'] - 1) * 100
    ax2.plot(df_history['step'], rl_return, label='RL Agent', color='blue', linewidth=2)
    
    # Buy and hold comparison (geometric)
    if buy_hold_series is None:
        buy_hold = ((df_history['close'] / df_history['close'].iloc[0]) - 1) * 100
        buy_hold_label = 'Buy & Hold'
    else:
        buy_hold = (buy_hold_series - 1) * 100
        buy_hold_label = 'Buy & Hold (Aligned)'
    ax2.plot(df_history['step'], buy_hold, label=buy_hold_label, color='orange', linewidth=2, linestyle='--')
    
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_xlabel('Step')
    ax2.set_ylabel('Cumulative Return (%)')
    ax2.set_title('Cumulative Returns Comparison (Geometric)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Daily returns (raw execution returns; not reward-shaped)
    ax3 = axes[2]
    if 'raw_return' in df_history.columns:
        daily_series = df_history['raw_return']
        daily_title = 'Daily Returns (Raw)'
        daily_ylabel = 'Return'
    else:
        # Backward compatibility for old history files
        daily_series = df_history['reward']
        daily_title = 'Daily Rewards'
        daily_ylabel = 'Reward'
    colors = ['green' if r > 0 else 'red' for r in daily_series]
    ax3.bar(df_history['step'], daily_series, color=colors, alpha=0.6)
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax3.set_xlabel('Step')
    ax3.set_ylabel(daily_ylabel)
    ax3.set_title(daily_title)
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Position and hold count
    ax4 = axes[3]
    ax4_twin = ax4.twinx()
    
    ax4.plot(df_history['step'], df_history['position'], label='Position', color='blue', linewidth=2)
    ax4_twin.plot(df_history['step'], df_history['hold_count'], label='Hold Count', color='red', linewidth=1, alpha=0.7)
    
    ax4.set_xlabel('Step')
    ax4.set_ylabel('Position', color='blue')
    ax4_twin.set_ylabel('Hold Count', color='red')
    ax4.set_title('Position and Hold Count Over Time')
    ax4.tick_params(axis='y', labelcolor='blue')
    ax4_twin.tick_params(axis='y', labelcolor='red')
    ax4.grid(True, alpha=0.3)
    
    # Add legends
    lines1, labels1 = ax4.get_legend_handles_labels()
    lines2, labels2 = ax4_twin.get_legend_handles_labels()
    ax4.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    
    # Save figure
    plot_file = os.path.join(output_dir, "evaluation_plots.png")
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    print(f"Plots saved to: {plot_file}")
    
    plt.close()

def analyze_trades(
    df_history,
    output_dir,
    buy_fee_rate: float = 0.0,
    sell_fee_rate: float = 0.0,
    capital_gains_tax_rate: float = 0.0,
):
    """Analyze individual trades in detail."""
    
    print("\n" + "="*60)
    print("Trade Analysis")
    print("="*60)

    df_trades = _extract_trades(
        df_history,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        capital_gains_tax_rate=capital_gains_tax_rate,
    )
    if not df_trades.empty:
        
        print(f"\nTotal Trades: {len(df_trades)}")
        print(f"Winning Trades: {(df_trades['return'] > 0).sum()}")
        print(f"Losing Trades: {(df_trades['return'] <= 0).sum()}")
        print(f"\nAverage Hold Days: {df_trades['hold_days'].mean():.1f}")
        print(f"Average Win: {df_trades[df_trades['return'] > 0]['return'].mean():.4f}")
        print(f"Average Loss: {df_trades[df_trades['return'] <= 0]['return'].mean():.4f}")
        
        # Save trades
        trades_file = os.path.join(output_dir, "trades_detail.csv")
        df_trades.to_csv(trades_file, index=False)
        print(f"\nTrade details saved to: {trades_file}")
        
        # Show first 10 trades
        print("\nFirst 10 Trades:")
        print("-"*60)
        print(df_trades.head(10).to_string(index=False))
    else:
        print("No completed trades found.")
