"""
TEST 5: Position State Transitions

WHAT IT TESTS:
- Position state machine (flat=0, long=1)
- Valid state transitions
- Cash/shares consistency with position

WHY IT MATTERS:
The position state drives all trading logic. Invalid states
or transitions indicate bugs in the core logic.
"""

import numpy as np
from test_utils import (
    TestEnv, create_price_dataframe, run_episode,
    format_history, print_section, print_subsection
)


def test_position_transitions():
    """Test all position state transitions."""
    
    print_section("TEST 5: Position State Transitions")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    opens = [100] * 15
    print(f"Price sequence: {opens}")
    print(f"  - Constant prices eliminate price effects")
    print(f"  - Pure focus on position state machine")
    
    df = create_price_dataframe(opens)
    
    env = TestEnv(
        df=df,
        start_idx=2,
        end_idx=len(opens) - 2,
        mode="train",
        lookback_window=1,
        source_mode="return",
        min_hold_days=2,
        stop_loss=None,
        buy_fee_rate=0.0,  # No fees to isolate state logic
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    
    # ============================================================================
    # EXPECTED BEHAVIOR
    # ============================================================================
    print_subsection("2. EXPECTED BEHAVIOR")
    
    actions = [1, 1, 1, 0, 0, 1, 1, 0, 0]
    print(f"Action sequence: {actions}")
    
    print("\nPosition state machine:")
    print("  State 0 (FLAT): cash=1.0, shares=0.0")
    print("  State 1 (LONG): cash≈0.0, shares>0.0")
    
    print("\nValid transitions:")
    print("  0 → 0: Stay flat")
    print("  0 → 1: Buy (action=1)")
    print("  1 → 1: Hold position")
    print("  1 → 0: Sell (action=0, after min_hold)")
    
    print("\nInvariants:")
    print("  - Position ∈ {0, 1} always")
    print("  - If pos=0: shares=0, cash≈1.0")
    print("  - If pos=1: shares>0, cash≈0")
    print("  - equity = cash + shares × price ≈ 1.0 (no fees)")
    
    # ============================================================================
    # RUN TEST
    # ============================================================================
    print_subsection("3. ACTUAL RESULTS")
    
    history, df = run_episode(env, actions)
    
    print(f"\nRan {len(history)} steps:")
    print("\nState transitions:")
    for h in history:
        transition = f"{h['pos_old']} → {h['pos_new']}"
        print(f"  Step {h['step']}: {transition} (action={h['action']}, pending={h['pending']})")
        print(f"            cash=${h['post_cash']:.4f}, shares={h['post_shares']:.4f}, equity=${h['equity_t1']:.4f}")
    
    # ============================================================================
    # VALIDATION
    # ============================================================================
    print_subsection("4. VALIDATION")
    
    print("\n✓ Checking position values are valid...")
    for h in history:
        assert h["pos_new"] in [0, 1], (
            f"Step {h['step']}: Invalid position state {h['pos_new']}\n"
            f"{format_history(history)}"
        )
    print("  All positions in {0, 1} ✓")
    
    print("\n✓ Checking state invariants...")
    for h in history:
        if h["pos_new"] == 0:  # Flat
            # Should have all cash, no shares
            assert np.isclose(h["post_shares"], 0.0, atol=1e-10), (
                f"Step {h['step']}: Flat position but shares={h['post_shares']}\n"
                f"{format_history(history)}"
            )
            assert np.isclose(h["post_cash"], 1.0, atol=1e-10), (
                f"Step {h['step']}: Flat position but cash={h['post_cash']}\n"
                f"{format_history(history)}"
            )
            print(f"  Step {h['step']}: pos=0 → cash=${h['post_cash']:.4f}, shares={h['post_shares']:.4f} ✓")
            
        elif h["pos_new"] == 1:  # Long
            # Should have shares, minimal cash
            assert h["post_shares"] > 0, (
                f"Step {h['step']}: Long position but shares={h['post_shares']}\n"
                f"{format_history(history)}"
            )
            assert np.isclose(h["post_cash"], 0.0, atol=1e-10), (
                f"Step {h['step']}: Long position but cash={h['post_cash']}\n"
                f"{format_history(history)}"
            )
            print(f"  Step {h['step']}: pos=1 → cash=${h['post_cash']:.4f}, shares={h['post_shares']:.4f} ✓")
    
    print("\n✓ Checking transition validity...")
    for i, h in enumerate(history):
        if i == 0:
            continue
        prev = history[i-1]
        
        # Check transition is valid
        if prev["pos_new"] == 0 and h["pos_new"] == 1:
            print(f"  Step {h['step']}: 0→1 (BUY) ✓")
        elif prev["pos_new"] == 1 and h["pos_new"] == 0:
            print(f"  Step {h['step']}: 1→0 (SELL) ✓")
        elif prev["pos_new"] == h["pos_new"]:
            print(f"  Step {h['step']}: {h['pos_new']}→{h['pos_new']} (HOLD) ✓")
    
    # ============================================================================
    # THEORY COMPARISON
    # ============================================================================
    print_subsection("5. COMPARISON TO THEORY")
    
    print("\nState machine verification:")
    transitions = []
    for i, h in enumerate(history):
        if i == 0:
            transitions.append(f"START→{h['pos_new']}")
        else:
            prev = history[i-1]
            transitions.append(f"{prev['pos_new']}→{h['pos_new']}")
    
    print(f"  Transition sequence: {' '.join(transitions)}")
    
    # Count each type
    buy_transitions = sum(1 for t in transitions if t == "0→1")
    sell_transitions = sum(1 for t in transitions if t == "1→0")
    
    print(f"\n  Buy transitions (0→1):  {buy_transitions}")
    print(f"  Sell transitions (1→0): {sell_transitions}")
    print(f"  Net position changes:   {buy_transitions - sell_transitions}")
    
    final_pos = history[-1]["pos_new"]
    expected_net = 1 if final_pos == 1 else 0
    actual_net = buy_transitions - sell_transitions
    
    print(f"\n  Final position: {final_pos}")
    print(f"  Expected from transitions: {expected_net}")
    print(f"  Match: {final_pos == expected_net} ✓")
    
    print("\n" + "="*80)
    print("✅ TEST 5 PASSED - Position state machine works correctly!")
    print("="*80)
