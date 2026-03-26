"""
TEST 12: Stop-Loss Override

WHAT IT TESTS:
- Stop-loss forces an exit even when min_hold_days is not satisfied
- Stop-loss overrides the min-hold constraint (as implemented)

WHY IT MATTERS:
Risk controls should be able to cut losses regardless of holding period.
"""

import numpy as np
import pandas as pd

from test_utils import (
    TestEnv, print_section, print_subsection
)


def test_stop_loss_overrides_min_hold():
    """Verify stop-loss triggers an early exit even if min_hold_days is unmet."""
    print_section("TEST 12: Stop-Loss Override (Min Hold vs Stop-Loss)")
    
    # =======================================================================
    # SYNTHETIC DATA
    # =======================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    opens = [100.0] * 8
    closes = [100.0, 100.0, 100.0, 100.0, 90.0, 90.0, 90.0, 90.0]  # Drop at index 4
    highs = [max(o, c) for o, c in zip(opens, closes)]
    lows = [min(o, c) for o, c in zip(opens, closes)]
    
    df = pd.DataFrame({
        "time": np.arange(len(opens)),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.ones(len(opens)),
    })
    
    print(f"Open prices:  {opens}")
    print(f"Close prices: {closes}")
    print("  - Entry executes at open[4] = 100")
    print("  - Close[4] = 90 triggers stop-loss (-10%)")
    
    # =======================================================================
    # ENV SETUP
    # =======================================================================
    print_subsection("2. ENV SETUP")
    
    env = TestEnv(
        df=df,
        start_idx=2,
        end_idx=len(opens) - 2,
        mode="train",
        lookback_window=1,
        source_mode="return",
        min_hold_days=3,
        stop_loss=0.05,  # 5% stop-loss
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    
    print("Constraints:")
    print(f"  min_hold_days = {env.min_hold_days}")
    print(f"  stop_loss = {env.stop_loss * 100:.1f}%")
    
    # =======================================================================
    # RUN STEPS
    # =======================================================================
    print_subsection("3. RUNNING STEPS")
    
    env.reset()
    
    # Step 0: schedule buy (executes at open[4])
    env.step(1)
    print(f"Step 0: position={env.position}, pending={env.pending_action}")
    assert env.position == 0, "Buy should not execute immediately (pending action model)"
    
    # Step 1: buy executes at open[4], stop-loss should trigger for close[4]
    env.step(1)
    print(f"Step 1: position={env.position}, hold={env.hold_count}, pending={env.pending_action}")
    assert env.position == 1, "Position should be long after buy execution"
    assert env.hold_count == 1, "Hold count should be 1 right after entry"
    assert env.hold_count < env.min_hold_days, "Hold count should be below min_hold_days"
    assert env.pending_action == 0, "Stop-loss should schedule an exit"
    
    # Step 2: stop-loss exit executes
    env.step(1)
    print(f"Step 2: position={env.position}, hold={env.hold_count}, pending={env.pending_action}")
    assert env.position == 0, "Stop-loss should force exit despite min_hold_days"
    
    print("\nStop-loss override confirmed.")
    print("\n" + "="*80)
    print("✅ TEST 12 PASSED - Stop-loss overrides min-hold constraint!")
    print("="*80)
