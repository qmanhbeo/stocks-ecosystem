"""
TEST 3: Price Execution Timing

WHAT IT TESTS:
- Actions made at end of day t execute at open of day t+1
- No lookahead bias (can't trade at current prices)
- Reward calculation uses correct prices

WHY IT MATTERS:
This is critical for preventing lookahead bias in backtesting.
If we could execute at current prices, we'd have unrealistic results.
"""

import numpy as np
from test_utils import (
    TestEnv, create_price_dataframe, run_episode,
    format_history, print_section, print_subsection
)


def test_execution_timing():
    """Test that actions execute at next open, not current."""
    
    print_section("TEST 3: Price Execution Timing")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    opens = [100, 110, 95, 105, 100, 120, 90, 100, 110, 115]
    print(f"Price sequence: {opens}")
    print(f"  - Large daily price changes make timing issues obvious")
    print(f"  - Example: Day 2 close=95, Day 3 open=105 (10.5% gap)")
    
    df = create_price_dataframe(opens)
    
    env = TestEnv(
        df=df,
        start_idx=2,
        end_idx=len(opens) - 2,
        mode="train",
        lookback_window=1,
        source_mode="return",
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,  # No fees to isolate timing effects
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    
    # ============================================================================
    # EXPECTED BEHAVIOR
    # ============================================================================
    print_subsection("2. EXPECTED BEHAVIOR")
    
    actions = [1, 1, 0]  # Buy, hold, sell
    print(f"Action sequence: {actions}")
    print("\nCritical timing rules:")
    print("  1. Agent observes data up to CLOSE of day t")
    print("  2. Agent makes decision at END of day t")
    print("  3. Decision executes at OPEN of day t+1")
    print("  4. Reward based on equity at OPEN of day t+1")
    
    print("\nExpected execution timeline:")
    print("  Step 0 (at idx=2):")
    print("    - Observe: close[2] = 95")
    print("    - Decide: action=1 (buy)")
    print("    - Execute: open[3] = 105 (next day)")
    print("    - Reward: based on equity change from 95 to 105")
    
    print("  Step 1 (at idx=3):")
    print("    - Observe: close[3] = 105")
    print("    - Decide: action=1 (hold)")
    print("    - Execute: open[4] = 100 (next day)")
    print("    - Reward: based on equity change from 105 to 100")
    
    print("  Step 2 (at idx=4):")
    print("    - Observe: close[4] = 100")
    print("    - Decide: action=0 (sell)")
    print("    - Execute: open[5] = 120 (next day)")
    print("    - Reward: based on equity change from 100 to 120")
    
    # ============================================================================
    # RUN TEST
    # ============================================================================
    print_subsection("3. ACTUAL RESULTS")
    
    history, df = run_episode(env, actions)
    
    print(f"\nRan {len(history)} steps:")
    for h in history:
        print(f"  Step {h['step']} (idx={h['pre_idx']}):")
        print(f"    Decision price (close): ${h['open_prev']:.2f}")
        print(f"    Execution price (open): ${h['open_exec']:.2f}")
        print(f"    Action: {h['action']}, Position: {h['pos_old']}→{h['pos_new']}")
        print(f"    Equity: ${h['equity_t']:.6f} → ${h['equity_t1']:.6f}")
        print(f"    Reward: {h['reward']*100:+.2f}%")
    
    # ============================================================================
    # VALIDATION
    # ============================================================================
    print_subsection("4. VALIDATION")
    
    print("\n✓ Checking execution timing...")
    
    for h in history:
        # Verify execution price is next day's open
        expected_exec_price = df.iloc[h["pre_idx"] + 1]["open"]
        assert np.isclose(h["open_exec"], expected_exec_price, atol=1e-10), (
            f"Step {h['step']}: Execution price mismatch\n"
            f"  Expected: ${expected_exec_price:.2f} (open[{h['pre_idx'] + 1}])\n"
            f"  Got: ${h['open_exec']:.2f}\n"
            f"{format_history(history)}"
        )
        
        # Verify decision price is current day's close (same as open in our data)
        expected_decision_price = df.iloc[h["pre_idx"]]["close"]
        assert np.isclose(h["open_prev"], expected_decision_price, atol=1e-10), (
            f"Step {h['step']}: Decision price mismatch\n"
            f"{format_history(history)}"
        )
        
        print(f"  Step {h['step']}: Executes at open[{h['pre_idx']+1}] = ${h['open_exec']:.2f} ✓")
    
    print("\n✓ Checking reward calculation uses correct prices...")
    
    for h in history:
        # Reward should be based on equity change from decision time to execution time
        # equity_t is based on open_prev (decision time)
        # equity_t1 is based on open_exec (execution time)
        expected_reward = (h["equity_t1"] / h["equity_t"]) - 1
        
        assert np.isclose(h["reward"], expected_reward, atol=1e-12), (
            f"Step {h['step']}: Reward calculation error\n"
            f"  Expected: {expected_reward:.8f}\n"
            f"  Got: {h['reward']:.8f}\n"
            f"{format_history(history)}"
        )
        
        print(f"  Step {h['step']}: Reward = (${h['equity_t1']:.6f} / ${h['equity_t']:.6f}) - 1 = {h['reward']*100:+.2f}% ✓")
    
    # ============================================================================
    # THEORY COMPARISON
    # ============================================================================
    print_subsection("5. COMPARISON TO THEORY")
    
    print("\nKey insight: Agent CANNOT execute at the price it observes")
    print("This prevents lookahead bias in backtesting")
    
    print("\nExample from Step 0:")
    step0 = history[0]
    print(f"  Agent sees close[2] = ${step0['open_prev']:.2f}")
    print(f"  But executes at open[3] = ${step0['open_exec']:.2f}")
    print(f"  Difference: {abs(step0['open_exec'] - step0['open_prev']):.2f}")
    print(f"  Cannot trade at observed price ✓")
    
    print("\nThis matches real-world trading:")
    print("  1. See data at market close")
    print("  2. Make decision overnight")
    print("  3. Execute at next market open")
    print("  4. Prices may gap overnight")
    
    print("\n" + "="*80)
    print("✅ TEST 3 PASSED - Execution timing is realistic!")
    print("="*80)
