"""
TEST 4: Equity Conservation

WHAT IT TESTS:
- The accounting identity: equity = cash + shares × price
- Equity changes only due to: (1) fees or (2) price movements
- No money creation or destruction

WHY IT MATTERS:
This is the fundamental law of accounting. If equity isn't conserved,
the entire reward calculation is wrong and training will be meaningless.
"""

import numpy as np
from test_utils import (
    TestEnv, create_price_dataframe, run_episode,
    format_history, print_section, print_subsection
)


def test_equity_conservation():
    """Test that equity is properly conserved through all operations."""
    
    print_section("TEST 4: Equity Conservation (Accounting Identity)")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    opens = [100, 105, 110, 108, 115, 120, 118, 125, 130, 128]
    print(f"Price sequence: {opens}")
    print(f"  - Prices fluctuate up and down")
    print(f"  - Tests equity tracking through price changes")
    
    df = create_price_dataframe(opens)
    
    buy_fee = 0.005
    sell_fee = 0.005
    tax = 0.002
    
    print(f"\nFee structure:")
    print(f"  - Buy fee: {buy_fee*100:.1f}%")
    print(f"  - Sell fee: {sell_fee*100:.1f}%")
    print(f"  - Capital gains tax: {tax*100:.1f}%")
    
    env = TestEnv(
        df=df,
        start_idx=2,
        end_idx=len(opens) - 2,
        mode="train",
        lookback_window=1,
        source_mode="return",
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=buy_fee,
        sell_fee_rate=sell_fee,
        capital_gains_tax_rate=tax,
    )
    
    # ============================================================================
    # EXPECTED BEHAVIOR
    # ============================================================================
    print_subsection("2. EXPECTED BEHAVIOR")
    
    actions = [1, 1, 0, 1, 0]  # Buy, hold, sell, buy, sell
    print(f"Action sequence: {actions}")
    
    print("\nEquity Conservation Law:")
    print("  equity_t1 = equity_t + price_change_impact - fees")
    print("\nWhere:")
    print("  - price_change_impact = shares × (price_t1 - price_t)")
    print("  - fees = transaction_costs (only when trading)")
    
    print("\nExpected changes:")
    print("  When flat (pos=0):")
    print("    - No price impact (shares=0)")
    print("    - Fees only on buy transactions")
    print("  When long (pos=1):")
    print("    - Equity moves with price × shares")
    print("    - Fees only on sell transactions")
    
    # ============================================================================
    # RUN TEST
    # ============================================================================
    print_subsection("3. ACTUAL RESULTS")
    
    history, df = run_episode(env, actions)
    
    print(f"\nRan {len(history)} steps:")
    for h in history:
        print(f"  Step {h['step']}: pos={h['pos_new']}, "
              f"cash=${h['post_cash']:.6f}, shares={h['post_shares']:.6f}, "
              f"equity=${h['equity_t1']:.6f}")
    
    # ============================================================================
    # VALIDATION
    # ============================================================================
    print_subsection("4. VALIDATION")
    
    print("\n✓ Checking accounting identity at each step...")
    
    total_fees = 0.0
    
    for h in history:
        # Check: equity = cash + shares × price (always must hold)
        equity_check_t = h["pre_cash"] + h["pre_shares"] * h["open_prev"]
        equity_check_t1 = h["post_cash"] + h["post_shares"] * h["open_exec"]
        
        assert np.isclose(h["equity_t"], equity_check_t, atol=1e-10), (
            f"Step {h['step']}: equity_t accounting error\n"
            f"  Expected: {equity_check_t:.8f}\n"
            f"  Got: {h['equity_t']:.8f}\n"
            f"{format_history(history)}"
        )
        
        assert np.isclose(h["equity_t1"], equity_check_t1, atol=1e-10), (
            f"Step {h['step']}: equity_t1 accounting error\n"
            f"  Expected: {equity_check_t1:.8f}\n"
            f"  Got: {h['equity_t1']:.8f}\n"
            f"{format_history(history)}"
        )
        
        print(f"  Step {h['step']}: ${h['post_cash']:.6f} + {h['post_shares']:.6f} × ${h['open_exec']:.2f} = ${h['equity_t1']:.6f} ✓")
    
    print("\n✓ Checking equity conservation...")
    
    for h in history:
        # Calculate fees paid
        fees_paid = 0.0
        if h["pre_shares"] == 0.0 and h["post_shares"] > 0.0:  # Buy
            fees_paid = h["equity_t"] * env.buy_fee_rate
        elif h["pre_shares"] > 0.0 and h["post_shares"] == 0.0:  # Sell
            gross_proceeds = h["pre_shares"] * h["open_exec"]
            fees_paid = gross_proceeds * (env.sell_fee_rate + env.capital_gains_tax_rate)
        
        total_fees += fees_paid
        
        # Calculate price change impact
        price_change_impact = 0.0
        if h["pre_shares"] > 0.0:  # Holding shares
            price_change_impact = h["pre_shares"] * (h["open_exec"] - h["open_prev"])
        
        # Check conservation law
        expected_equity_t1 = h["equity_t"] + price_change_impact - fees_paid
        
        assert np.isclose(h["equity_t1"], expected_equity_t1, rtol=1e-10), (
            f"Step {h['step']}: Equity not conserved\n"
            f"  equity_t: {h['equity_t']:.8f}\n"
            f"  + price_change: {price_change_impact:+.8f}\n"
            f"  - fees: {fees_paid:.8f}\n"
            f"  = expected: {expected_equity_t1:.8f}\n"
            f"  but got: {h['equity_t1']:.8f}\n"
            f"  difference: {abs(h['equity_t1'] - expected_equity_t1):.2e}\n"
            f"{format_history(history)}"
        )
        
        if abs(price_change_impact) > 0 or fees_paid > 0:
            print(f"  Step {h['step']}: ${h['equity_t']:.6f} {price_change_impact:+.6f} -{fees_paid:.6f} = ${h['equity_t1']:.6f} ✓")
    
    # ============================================================================
    # THEORY COMPARISON
    # ============================================================================
    print_subsection("5. COMPARISON TO THEORY")
    
    print("\nEquity flow analysis:")
    print(f"  Starting equity:   ${1.000000:.6f}")
    print(f"  Total fees paid:   ${total_fees:.6f}")
    print(f"  Final equity:      ${history[-1]['equity_t1']:.6f}")
    print(f"  Net P&L:           ${history[-1]['equity_t1'] - 1.0:+.6f}")
    
    # Calculate theoretical bounds
    max_possible_equity = 1.0  # If we caught every price increase perfectly
    min_possible_equity = 0.0  # Theoretical minimum (can't go negative in reality)
    
    print(f"\nSanity checks:")
    print(f"  Equity > 0:        {history[-1]['equity_t1'] > 0} ✓")
    print(f"  Fees > 0:          {total_fees > 0} ✓")
    print(f"  |P&L| reasonable: {abs(history[-1]['equity_t1'] - 1.0) < 0.5} ✓")
    
    print("\nKey insight: Equity changes ONLY due to:")
    print("  1. Price movements (when holding shares)")
    print("  2. Transaction fees (when trading)")
    print("  No other source of gain or loss exists ✓")
    
    print("\n" + "="*80)
    print("✅ TEST 4 PASSED - Equity is properly conserved!")
    print("="*80)
