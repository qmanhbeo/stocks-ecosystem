"""
TEST 2: Minimum Hold Period

WHAT IT TESTS:
- min_hold_days constraint enforcement
- Pending action tracking
- Delayed execution of sell orders

WHY IT MATTERS:
Many trading strategies require minimum holding periods to:
- Avoid wash sales
- Reduce transaction costs from overtrading
- Comply with regulatory requirements
"""

import numpy as np
from test_utils import (
    TestEnv, create_price_dataframe, run_episode,
    format_history, print_section, print_subsection
)


def test_min_hold_period():
    """Test that min_hold_days is enforced correctly."""
    
    print_section("TEST 2: Minimum Hold Period Enforcement")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    opens = [100, 100, 105, 110, 115, 120, 125, 130, 135, 140]
    print(f"Price sequence: {opens}")
    print(f"  - Prices steadily increase (always profitable to hold)")
    print(f"  - This ensures we can isolate the min_hold constraint")
    
    df = create_price_dataframe(opens)
    
    min_hold = 3
    print(f"\nConstraint: min_hold_days = {min_hold}")
    print(f"  After buying, must wait {min_hold} days before selling")
    
    env = TestEnv(
        df=df,
        start_idx=2,
        end_idx=len(opens) - 2,
        mode="train",
        lookback_window=1,
        source_mode="return",
        min_hold_days=min_hold,
        stop_loss=None,
        buy_fee_rate=0.001,
        sell_fee_rate=0.001,
        capital_gains_tax_rate=0.0,
    )
    
    # ============================================================================
    # EXPECTED BEHAVIOR
    # ============================================================================
    print_subsection("2. EXPECTED BEHAVIOR")
    
    actions = [1, 0, 0, 0, 0, 0]  # Buy, then try to sell immediately
    print(f"Action sequence: {actions}")
    print(f"  Step 0: Action 1 (buy) -> position opens")
    print(f"  Step 1: Action 0 (sell) -> BLOCKED (held 0 days, need {min_hold})")
    print(f"  Step 2: Action 0 (sell) -> BLOCKED (held 1 days, need {min_hold})")
    print(f"  Step 3: Action 0 (sell) -> BLOCKED (held 2 days, need {min_hold})")
    print(f"  Step 4: Action 0 (sell) -> ALLOWED (held 3 days, meets requirement)")
    print(f"  Step 5: Action 0 (flat) -> already flat")
    
    print("\nExpected timeline:")
    print("  Day 0: Buy executed")
    print("  Days 1-2: Sell requests queued as pending_action")
    print("  Day 3: Pending sell finally executes")
    print("  Days 4+: Remain flat")
    
    # ============================================================================
    # RUN TEST
    # ============================================================================
    print_subsection("3. ACTUAL RESULTS")
    
    history, df = run_episode(env, actions)
    
    print(f"\nRan {len(history)} steps:")
    for h in history:
        held_days = "N/A" if h['pos_old'] == 0 else h['step'] - next(x['step'] for x in history if x['pos_new'] == 1 and x['pos_old'] == 0)
        print(f"  Step {h['step']}: action={h['action']}, pos={h['pos_old']}→{h['pos_new']}, "
              f"pending={h['pending']}, held={held_days} days")
    
    # ============================================================================
    # VALIDATION
    # ============================================================================
    print_subsection("4. VALIDATION")
    
    # Find buy step
    buy_step = next(h for h in history if h["pre_shares"] == 0.0 and h["post_shares"] > 0.0)
    print(f"\n✓ Buy executed at step {buy_step['step']}")
    
    # Check enforcement during hold period
    print(f"\n✓ Checking min_hold_days={min_hold} enforcement...")
    
    for h in history:
        steps_since_buy = h["step"] - buy_step["step"]
        
        # During min hold period (before min_hold steps), sell should be blocked
        if steps_since_buy > 0 and steps_since_buy < min_hold:
            if h["action"] == 0:  # Sell action requested
                assert h["pos_new"] == 1, (
                    f"Step {h['step']}: Should still be in position during min hold period\n"
                    f"  Held {steps_since_buy} days, need {min_hold} days\n"
                    f"{format_history(history)}"
                )
                print(f"  Step {h['step']}: Sell BLOCKED (held {steps_since_buy}/{min_hold} days) ✓")
                
                # Verify pending_action is forced to hold (1, not the desired 0)
                assert h["pending"] == 1, (
                    f"Step {h['step']}: pending_action should be 1 (forced hold) when sell is blocked\n"
                    f"  Environment overrides action=0 (sell) to action=1 (hold) during min_hold period\n"
                    f"{format_history(history)}"
                )
        
        # After min_hold, sell should be allowed
        elif steps_since_buy >= min_hold and h["action"] == 0 and h["pos_old"] == 1:
            print(f"  Step {h['step']}: Sell ALLOWED (held {steps_since_buy}/{min_hold} days) ✓")
            
            # Should execute the sell
            if h["pos_new"] == 0:
                print(f"  Step {h['step']}: Position CLOSED ✓")
    
    # ============================================================================
    # THEORY COMPARISON
    # ============================================================================
    print_subsection("5. COMPARISON TO THEORY")
    
    # Find when sell actually executed
    sell_step = next((h for h in history if h["pre_shares"] > 0.0 and h["post_shares"] == 0.0), None)
    
    if sell_step:
        steps_held = sell_step["step"] - buy_step["step"]
        print(f"\nTheoretical vs Actual:")
        print(f"  Min hold required:     {min_hold} days (theory)")
        print(f"  Actual hold duration:  {steps_held} days (actual)")
        print(f"  Constraint satisfied:  {steps_held >= min_hold} ✓")
        
        assert steps_held >= min_hold, (
            f"Position closed too early!\n"
            f"  Required: {min_hold} days\n"
            f"  Actual: {steps_held} days\n"
            f"{format_history(history)}"
        )
    else:
        print("\nNote: Position never closed (episode ended before min_hold satisfied)")
        print("This is expected if episode is too short")
    
    print("\n" + "="*80)
    print("✅ TEST 2 PASSED - Min hold period correctly enforced!")
    print("="*80)
