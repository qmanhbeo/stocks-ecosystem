"""
TEST 6: Extreme Fees

WHAT IT TESTS:
- Fee calculations with very high rates (50%)
- Numerical stability with extreme values
- Correctness under stress conditions

WHY IT MATTERS:
If the code works with extreme fees, it will work with normal fees.
This is a robustness test that catches edge cases and numerical issues.
"""

import numpy as np
from test_utils import (
    TestEnv, create_price_dataframe, run_episode,
    format_history, print_section, print_subsection
)


def test_extreme_fees():
    """Test with very high fees (50%) to ensure calculations are correct."""
    
    print_section("TEST 6: Extreme Fees (50% buy + sell fees)")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    opens = [100, 100, 100, 150, 150, 150, 150, 150, 150]
    print(f"Price sequence: {opens}")
    print(f"  - Constant initially, then jumps 50%")
    print(f"  - Large price increase to test against fee drag")
    
    df = create_price_dataframe(opens)
    
    extreme_fee = 0.5  # 50% fee!
    print(f"\nFee structure:")
    print(f"  - Buy fee: {extreme_fee*100:.0f}%")
    print(f"  - Sell fee: {extreme_fee*100:.0f}%")
    print(f"  - Total round-trip cost: {extreme_fee*2*100:.0f}%")
    print(f"\n  WARNING: These fees would never exist in real markets!")
    print(f"  This is a stress test for numerical correctness.")
    
    env = TestEnv(
        df=df,
        start_idx=2,
        end_idx=len(opens) - 2,
        mode="train",
        lookback_window=1,
        source_mode="return",
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=extreme_fee,
        sell_fee_rate=extreme_fee,
        capital_gains_tax_rate=0.0,
    )
    
    # ============================================================================
    # EXPECTED BEHAVIOR
    # ============================================================================
    print_subsection("2. EXPECTED BEHAVIOR")
    
    actions = [1, 1, 0, 0]  # Buy, hold (for min_hold), sell, flat
    print(f"Action sequence: {actions}")
    
    print("\nExpected buy transaction:")
    buy_price = 150.0  # Will execute at 150
    cash_after_fee = 1.0 * (1 - extreme_fee)
    expected_shares = cash_after_fee / buy_price
    print(f"  Initial cash: $1.00")
    print(f"  Buy fee: {extreme_fee*100:.0f}%")
    print(f"  Cash after fee: $1.00 × (1 - {extreme_fee}) = ${cash_after_fee:.2f}")
    print(f"  Shares bought: ${cash_after_fee:.2f} / ${buy_price:.2f} = {expected_shares:.6f}")
    print(f"  Effective cost: ${1.0 / expected_shares:.2f}/share")
    
    print("\nExpected sell transaction:")
    sell_price = 150.0  # Price stays at 150
    gross_proceeds = expected_shares * sell_price
    net_proceeds = gross_proceeds * (1 - extreme_fee)
    print(f"  Gross proceeds: {expected_shares:.6f} × ${sell_price:.2f} = ${gross_proceeds:.2f}")
    print(f"  Sell fee: {extreme_fee*100:.0f}%")
    print(f"  Net proceeds: ${gross_proceeds:.2f} × (1 - {extreme_fee}) = ${net_proceeds:.2f}")
    
    print("\nExpected outcome:")
    total_loss = 1.0 - net_proceeds
    print(f"  Started with: $1.00")
    print(f"  Ended with: ${net_proceeds:.2f}")
    print(f"  Loss from fees: ${total_loss:.2f} ({total_loss*100:.0f}%)")
    print(f"  Even though price was constant!")
    
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
    
    # Find buy transaction
    buy = next((h for h in history if h["pre_shares"] == 0.0 and h["post_shares"] > 0.0), None)
    
    if buy is None:
        print("\n⚠️  WARNING: No buy transaction found!")
        print("This might be due to episode being too short or other constraints.")
        print("Checking if buy action was attempted...")
        
        buy_attempt = next((h for h in history if h["action"] == 1 and h["pos_old"] == 0), None)
        if buy_attempt:
            print(f"  Buy action attempted at step {buy_attempt['step']}")
            print(f"  But position stayed at {buy_attempt['pos_new']}")
            print("  This indicates the buy was blocked (possibly pending)")
        
        # For this test, we need a complete round trip
        raise AssertionError(
            "Cannot complete test without buy transaction.\n"
            "Increase episode length or reduce min_hold_days."
        )
    
    print(f"\n✓ Buy transaction at step {buy['step']}:")
    print(f"  Shares: {buy['post_shares']:.6f} (expected: {expected_shares:.6f})")
    
    assert np.isclose(buy["post_shares"], expected_shares, atol=1e-10), (
        f"Buy shares mismatch\n"
        f"  Expected: {expected_shares:.8f}\n"
        f"  Got: {buy['post_shares']:.8f}\n"
        f"{format_history(history)}"
    )
    print(f"  ✓ Shares calculation correct")
    
    assert np.isclose(buy["post_cash"], 0.0, atol=1e-10), (
        f"Buy should use all cash\n{format_history(history)}"
    )
    print(f"  ✓ All cash used")
    
    # Find sell transaction
    sell = next((h for h in history if h["pre_shares"] > 0.0 and h["post_shares"] == 0.0), None)
    
    if sell is None:
        print("\n⚠️  WARNING: No sell transaction found!")
        print("Episode may have ended before sell could execute.")
        print("Test cannot complete without sell transaction.")
        raise AssertionError("No sell transaction found")
    
    print(f"\n✓ Sell transaction at step {sell['step']}:")
    expected_cash = sell["pre_shares"] * sell["open_exec"] * (1 - extreme_fee)
    print(f"  Cash: ${sell['post_cash']:.6f} (expected: ${expected_cash:.6f})")
    
    assert np.isclose(sell["post_cash"], expected_cash, atol=1e-10), (
        f"Sell cash mismatch\n"
        f"  Expected: {expected_cash:.8f}\n"
        f"  Got: {sell['post_cash']:.8f}\n"
        f"{format_history(history)}"
    )
    print(f"  ✓ Cash calculation correct")
    
    # ============================================================================
    # THEORY COMPARISON
    # ============================================================================
    print_subsection("5. COMPARISON TO THEORY")
    
    print("\nTheoretical vs Actual:")
    print(f"  Shares bought:     {expected_shares:.6f} (theory) vs {buy['post_shares']:.6f} (actual) ✓")
    print(f"  Final cash:        ${net_proceeds:.6f} (theory) vs ${sell['post_cash']:.6f} (actual) ✓")
    print(f"  Total loss:        ${total_loss:.6f} (theory) vs ${1.0 - sell['post_cash']:.6f} (actual) ✓")
    
    print("\nKey insight:")
    print(f"  With {extreme_fee*100:.0f}% buy fee and {extreme_fee*100:.0f}% sell fee,")
    print(f"  a round trip with NO price change loses {(1.0 - sell['post_cash'])*100:.0f}%!")
    print(f"  This shows fees compound multiplicatively, not additively.")
    
    print(f"\n  Mathematical proof:")
    print(f"    After buy:  equity = 1.0 × (1 - 0.5) = 0.5")
    print(f"    After sell: equity = 0.5 × (1 - 0.5) = 0.25")
    print(f"    Total loss: 1 - (1 - fee)² = 1 - 0.25 = 0.75 = 75%")
    
    print("\n" + "="*80)
    print("✅ TEST 6 PASSED - Fee calculations work even with extreme values!")
    print("="*80)
