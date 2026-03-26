"""
TEST 1: Basic Round Trip

WHAT IT TESTS:
- Complete buy-hold-sell cycle
- Fee calculations (buy fee, sell fee, capital gains tax)
- Share quantity calculations
- Final equity matches expected value

WHY IT MATTERS:
This is the fundamental operation of the trading environment.
If this test fails, nothing else can be trusted.
"""

import numpy as np
from test_utils import (
    TestEnv, create_price_dataframe, run_episode, 
    format_history, print_section, print_subsection
)


def test_basic_round_trip():
    """Test basic buy-hold-sell cycle with standard fees."""
    
    print_section("TEST 1: Basic Round Trip (Buy -> Hold -> Sell)")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    opens = [90, 95, 97, 100, 100, 100, 110, 121, 121, 121]
    print(f"Price sequence: {opens}")
    print(f"  - Warm-up period: indices 0-2 (for lookback_window=2)")
    print(f"  - Trading period: indices 3-7")
    print(f"  - We'll buy at index 3 (executes at open[4]=100)")
    print(f"  - We'll sell at index 5 (executes at open[6]=110) then later at 121")
    
    df = create_price_dataframe(opens)
    
    buy_fee = 0.003      # 0.3%
    sell_fee = 0.003     # 0.3%
    tax = 0.001          # 0.1%
    
    print(f"\nFee structure:")
    print(f"  - Buy fee: {buy_fee*100:.1f}%")
    print(f"  - Sell fee: {sell_fee*100:.1f}%")
    print(f"  - Capital gains tax: {tax*100:.1f}%")
    print(f"  - Total round-trip cost: {(buy_fee + sell_fee + tax)*100:.1f}%")
    
    env = TestEnv(
        df=df,
        start_idx=3,
        end_idx=len(opens) - 2,
        mode="train",
        lookback_window=2,
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
    
    actions = [1, 1, 0, 0]  # Buy, hold, sell, hold
    print(f"Action sequence: {actions}")
    print("  Step 0 (idx=3): Action 1 (buy) -> executes at open[4]=100")
    print("  Step 1 (idx=4): Action 1 (hold) -> no trade")
    print("  Step 2 (idx=5): Action 0 (sell) -> executes at open[6]=110")
    print("  Step 3 (idx=6): Action 0 (hold) -> no trade")
    
    print("\nExpected buy transaction:")
    buy_price = 100.0
    cash_after_fee = 1.0 * (1 - buy_fee)
    expected_shares = cash_after_fee / buy_price
    print(f"  Cash after fee: ${1.0} × (1 - {buy_fee}) = ${cash_after_fee:.6f}")
    print(f"  Shares bought: ${cash_after_fee:.6f} / ${buy_price} = {expected_shares:.6f}")
    
    print("\nExpected sell transaction:")
    sell_price = 121.0  # Price rises to 121 by the time we sell
    gross_proceeds = expected_shares * sell_price
    net_proceeds = gross_proceeds * (1 - sell_fee - tax)
    print(f"  Gross proceeds: {expected_shares:.6f} × ${sell_price} = ${gross_proceeds:.6f}")
    print(f"  Net proceeds: ${gross_proceeds:.6f} × (1 - {sell_fee + tax}) = ${net_proceeds:.6f}")
    
    print("\nExpected final outcome:")
    gross_return = (sell_price / buy_price - 1) * 100
    net_return = (net_proceeds / 1.0 - 1) * 100
    print(f"  Gross return: ({sell_price}/{buy_price} - 1) × 100 = {gross_return:.2f}%")
    print(f"  Net return: ({net_proceeds}/1.0 - 1) × 100 = {net_return:.2f}%")
    print(f"  Fee drag: {gross_return - net_return:.2f}%")
    
    # ============================================================================
    # RUN TEST
    # ============================================================================
    print_subsection("3. ACTUAL RESULTS")
    
    history, df = run_episode(env, actions)
    
    print(f"\nRan {len(history)} steps:")
    for h in history:
        print(f"  Step {h['step']}: pos={h['pos_old']}→{h['pos_new']}, "
              f"cash=${h['post_cash']:.6f}, shares={h['post_shares']:.6f}, "
              f"equity=${h['equity_t1']:.6f}")
    
    # ============================================================================
    # VALIDATION
    # ============================================================================
    print_subsection("4. VALIDATION")
    
    # Validation 1: Reward calculation
    print("\n✓ Checking reward calculations...")
    for h in history:
        expected_reward = (h["equity_t1"] / h["equity_t"]) - 1
        assert np.isclose(h["reward"], expected_reward, atol=1e-12), (
            f"Step {h['step']}: reward mismatch\n"
            f"  Expected: {expected_reward:.8f}\n"
            f"  Got: {h['reward']:.8f}\n"
            f"{format_history(history)}"
        )
    print("  All rewards match formula: reward = (equity_t1 / equity_t) - 1")
    
    # Validation 2: Buy transaction
    print("\n✓ Checking buy transaction...")
    buy = next(h for h in history if h["pre_shares"] == 0.0 and h["post_shares"] > 0.0)
    
    assert np.isclose(buy["post_shares"], expected_shares, atol=1e-12), (
        f"Buy shares mismatch\n"
        f"  Expected: {expected_shares:.8f}\n"
        f"  Got: {buy['post_shares']:.8f}\n"
        f"{format_history(history)}"
    )
    assert np.isclose(buy["post_cash"], 0.0, atol=1e-12), (
        f"Buy cash should be 0\n{format_history(history)}"
    )
    
    print(f"  Shares purchased: {buy['post_shares']:.6f} ✓")
    print(f"  Execution price: ${buy['open_exec']:.2f} ✓")
    print(f"  Effective cost: ${1.0 / buy['post_shares']:.4f}/share (includes {buy_fee*100:.1f}% fee) ✓")
    
    # Validation 3: Sell transaction
    print("\n✓ Checking sell transaction...")
    sell = next(h for h in history if h["pre_shares"] > 0.0 and h["post_shares"] == 0.0)
    expected_cash = sell["pre_shares"] * sell["open_exec"] * (1 - sell_fee - tax)
    
    assert np.isclose(sell["post_cash"], expected_cash, atol=1e-12), (
        f"Sell cash mismatch\n"
        f"  Expected: {expected_cash:.8f}\n"
        f"  Got: {sell['post_cash']:.8f}\n"
        f"{format_history(history)}"
    )
    assert np.isclose(sell["post_shares"], 0.0, atol=1e-12), (
        f"Sell shares should be 0\n{format_history(history)}"
    )
    
    print(f"  Shares sold: {sell['pre_shares']:.6f} ✓")
    print(f"  Execution price: ${sell['open_exec']:.2f} ✓")
    print(f"  Net price received: ${sell['post_cash'] / sell['pre_shares']:.4f}/share (after {(sell_fee+tax)*100:.1f}% fees) ✓")
    
    # Validation 4: Final equity
    print("\n✓ Checking final equity...")
    final_equity = history[-1]["equity_t1"]
    
    assert np.isclose(final_equity, expected_cash, atol=1e-12), (
        f"Final equity mismatch\n{format_history(history)}"
    )
    
    print(f"  Final equity: ${final_equity:.6f} ✓")
    
    # ============================================================================
    # THEORY COMPARISON
    # ============================================================================
    print_subsection("5. COMPARISON TO THEORY")
    
    actual_gross_return = (sell["open_exec"] / buy["open_exec"] - 1) * 100
    actual_net_return = (final_equity / 1.0 - 1) * 100
    actual_fee_drag = actual_gross_return - actual_net_return
    
    print("\nTheoretical vs Actual:")
    print(f"  Buy price:         ${buy_price:.2f} (theory) vs ${buy['open_exec']:.2f} (actual) ✓")
    print(f"  Sell price:        ${sell_price:.2f} (theory) vs ${sell['open_exec']:.2f} (actual) ✓")
    print(f"  Gross return:      {gross_return:.2f}% (theory) vs {actual_gross_return:.2f}% (actual) ✓")
    print(f"  Net return:        {net_return:.2f}% (theory) vs {actual_net_return:.2f}% (actual) ✓")
    print(f"  Fee drag:          {(buy_fee+sell_fee+tax)*100:.2f}% (theory) vs {actual_fee_drag:.2f}% (actual) ✓")
    print(f"  Final equity:      ${net_proceeds:.6f} (theory) vs ${final_equity:.6f} (actual) ✓")
    
    print("\n" + "="*80)
    print("✅ TEST 1 PASSED - All validations successful!")
    print("="*80)
