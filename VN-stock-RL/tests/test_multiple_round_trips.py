"""
TEST 7: Multiple Round Trips

WHAT IT TESTS:
- Sequential buy-sell cycles
- State resets between trades
- Cumulative returns over multiple trades

WHY IT MATTERS:
Real trading involves many trades. Each trade must properly
reset state for the next one. Bugs in state management
would compound over multiple trades.
"""

import numpy as np
from test_utils import (
    TestEnv, create_price_dataframe, run_episode,
    format_history, print_section, print_subsection
)


def test_multiple_round_trips():
    """Test multiple buy-sell cycles to ensure state resets correctly."""
    
    print_section("TEST 7: Multiple Round Trips")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    opens = [100, 105, 110, 108, 115, 120, 118, 125, 130, 128, 135, 140, 138, 145, 150]
    print(f"Price sequence: {opens}")
    print(f"  - Upward trending with oscillations")
    print(f"  - Each trade should be profitable")
    
    df = create_price_dataframe(opens)
    
    buy_fee = 0.001
    sell_fee = 0.001
    tax = 0.0005
    total_fee_per_trade = buy_fee + sell_fee + tax
    
    print(f"\nFee structure:")
    print(f"  - Buy fee: {buy_fee*100:.2f}%")
    print(f"  - Sell fee: {sell_fee*100:.2f}%")
    print(f"  - Capital gains tax: {tax*100:.2f}%")
    print(f"  - Total per round trip: {total_fee_per_trade*100:.2f}%")
    
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
    
    actions = [1, 1, 0, 1, 1, 0, 1, 1, 0, 0]
    print(f"Action sequence: {actions}")
    print("\nExpected pattern:")
    print("  Round trip 1: Buy → Hold → Sell")
    print("  Round trip 2: Buy → Hold → Sell")
    print("  Round trip 3: Buy → Hold → Sell")
    print("  Final: Flat")
    
    print("\nKey requirements:")
    print("  1. Each sell must return to flat position (pos=0)")
    print("  2. Each buy must start from flat position")
    print("  3. Cash after each sell becomes starting capital for next trade")
    print("  4. Returns compound over multiple trades")
    
    # ============================================================================
    # RUN TEST
    # ============================================================================
    print_subsection("3. ACTUAL RESULTS")
    
    history, df = run_episode(env, actions)
    
    print(f"\nRan {len(history)} steps")
    
    # Identify all trades
    trades = []
    current_buy = None
    
    for h in history:
        if h["pre_shares"] == 0.0 and h["post_shares"] > 0.0:
            current_buy = h
        elif h["pre_shares"] > 0.0 and h["post_shares"] == 0.0 and current_buy:
            trades.append({"buy": current_buy, "sell": h})
            current_buy = None
    
    print(f"\nIdentified {len(trades)} complete round trips:")
    for i, trade in enumerate(trades, 1):
        buy = trade["buy"]
        sell = trade["sell"]
        print(f"  Trade {i}: Buy at step {buy['step']} (${buy['open_exec']:.2f}) → "
              f"Sell at step {sell['step']} (${sell['open_exec']:.2f})")
    
    # ============================================================================
    # VALIDATION
    # ============================================================================
    print_subsection("4. VALIDATION")
    
    print("\n✓ Validating each round trip...")
    
    for i, trade in enumerate(trades, 1):
        buy = trade["buy"]
        sell = trade["sell"]
        
        # Check buy started from flat
        assert buy["pos_old"] == 0, (
            f"Trade {i}: Buy should start from flat position\n{format_history(history)}"
        )
        assert np.isclose(buy["pre_shares"], 0.0, atol=1e-10), (
            f"Trade {i}: Should have no shares before buy\n{format_history(history)}"
        )
        
        # Check sell returned to flat
        assert sell["pos_new"] == 0, (
            f"Trade {i}: Sell should return to flat position\n{format_history(history)}"
        )
        assert np.isclose(sell["post_shares"], 0.0, atol=1e-10), (
            f"Trade {i}: Should have no shares after sell\n{format_history(history)}"
        )
        
        # Calculate returns
        buy_price = buy["open_exec"]
        sell_price = sell["open_exec"]
        gross_return = (sell_price / buy_price - 1) * 100
        
        # Net return based on actual cash change
        cash_before = buy["pre_cash"]
        cash_after = sell["post_cash"]
        net_return = (cash_after / cash_before - 1) * 100
        
        print(f"\n  Trade {i}:")
        print(f"    Entry: ${buy_price:.2f} at step {buy['step']}")
        print(f"    Exit: ${sell_price:.2f} at step {sell['step']}")
        print(f"    Gross return: {gross_return:+.2f}%")
        print(f"    Net return: {net_return:+.2f}%")
        print(f"    Capital before: ${cash_before:.6f}")
        print(f"    Capital after: ${cash_after:.6f}")
        print(f"    ✓ State properly reset")
    
    # Check compounding
    print("\n✓ Validating return compounding...")
    
    if len(trades) >= 2:
        # Second trade should use proceeds from first trade
        trade1_final_cash = trades[0]["sell"]["post_cash"]
        trade2_initial_cash = trades[1]["buy"]["pre_cash"]
        
        assert np.isclose(trade1_final_cash, trade2_initial_cash, atol=1e-10), (
            f"Trade 2 should start with proceeds from trade 1\n"
            f"  Trade 1 final: ${trade1_final_cash:.6f}\n"
            f"  Trade 2 start: ${trade2_initial_cash:.6f}\n"
            f"{format_history(history)}"
        )
        
        print(f"  Trade 1 final cash: ${trade1_final_cash:.6f}")
        print(f"  Trade 2 start cash: ${trade2_initial_cash:.6f}")
        print(f"  ✓ Returns compound correctly")
    
    # ============================================================================
    # THEORY COMPARISON
    # ============================================================================
    print_subsection("5. COMPARISON TO THEORY")
    
    print("\nCumulative performance:")
    initial_capital = 1.0
    final_equity = history[-1]["equity_t1"]
    total_return = (final_equity / initial_capital - 1) * 100
    
    print(f"  Starting capital:    ${initial_capital:.6f}")
    print(f"  Final equity:        ${final_equity:.6f}")
    print(f"  Total return:        {total_return:+.2f}%")
    print(f"  Number of trades:    {len(trades)}")
    
    if len(trades) > 0:
        avg_return_per_trade = total_return / len(trades)
        print(f"  Avg return per trade: {avg_return_per_trade:+.2f}%")
    
    # Theoretical check: compounding
    print("\nCompounding verification:")
    compound_factor = 1.0
    for i, trade in enumerate(trades, 1):
        buy_price = trade["buy"]["open_exec"]
        sell_price = trade["sell"]["open_exec"]
        
        # Account for fees
        price_ratio = sell_price / buy_price
        trade_return = price_ratio * (1 - buy_fee) * (1 - sell_fee - tax)
        compound_factor *= trade_return
        
        print(f"  After trade {i}: ${compound_factor:.6f} (theory) vs ${trade['sell']['post_cash']:.6f} (actual)")
    
    expected_final = compound_factor
    actual_final = final_equity
    
    print(f"\n  Expected final (compound): ${expected_final:.6f}")
    print(f"  Actual final:              ${actual_final:.6f}")
    print(f"  Difference:                ${abs(expected_final - actual_final):.2e}")
    
    # Allow small tolerance for floating point
    assert np.isclose(expected_final, actual_final, rtol=1e-6), (
        f"Compounding mismatch\n{format_history(history)}"
    )
    print(f"  ✓ Compounding matches theory")
    
    print("\n" + "="*80)
    print("✅ TEST 7 PASSED - Multiple round trips work correctly!")
    print("="*80)
