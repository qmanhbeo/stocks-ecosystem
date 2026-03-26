"""
TEST 8: Episode Boundary Safety

WHAT IT TESTS:
- No lookahead bias (observations only use data up to current_step)
- Episode boundaries are correctly enforced
- Lookback window works at episode start
- Episode terminates cleanly

WHY IT MATTERS:
Lookahead bias is a silent killer - it makes your agent appear to work
great in backtesting but fail completely in real trading.
"""

import numpy as np
from test_utils import (
    TestEnv, create_price_dataframe, run_episode,
    format_history, print_section, print_subsection
)


def test_episode_boundaries():
    """Test that episode boundaries prevent lookahead bias."""
    
    print_section("TEST 8: Episode Boundary Safety")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    # Create data with distinctive values at each index for easy tracking
    opens = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150]
    print(f"Price sequence: {opens}")
    print(f"  - Each value is unique (10 * index)")
    print(f"  - Easy to detect if wrong index is accessed")
    
    df = create_price_dataframe(opens)
    
    lookback = 3
    start_idx = lookback + 1  # Need lookback history for observation
    end_idx = len(opens) - 2  # Need t+1 for execution
    
    print(f"\nEpisode configuration:")
    print(f"  Lookback window: {lookback}")
    print(f"  Start index: {start_idx}")
    print(f"  End index: {end_idx}")
    print(f"  Valid indices: {start_idx} to {end_idx}")
    
    env = TestEnv(
        df=df,
        start_idx=start_idx,
        end_idx=end_idx,
        mode="train",
        lookback_window=lookback,
        source_mode="raw",  # Use raw prices for easy verification
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    
    # ============================================================================
    # EXPECTED BEHAVIOR
    # ============================================================================
    print_subsection("2. EXPECTED BEHAVIOR")
    
    print("\nObservation rules:")
    print("  At step t (current_step=t):")
    print("  - Agent sees data from [t-lookback : t] (inclusive)")
    print("  - This includes close[t] for end-of-day decision")
    print("  - Agent CANNOT see t+1 (that's the future!)")
    print("  - Execution happens at open[t+1]")
    
    print("\nExample at start_idx=4:")
    print(f"  Observation includes indices: [1, 2, 3, 4]")
    print(f"  Prices in observation: {opens[1:5]}")
    print(f"  MUST NOT include: index 5 or higher")
    
    # ============================================================================
    # RUN TEST
    # ============================================================================
    print_subsection("3. ACTUAL RESULTS")
    
    # Run a few steps
    actions = [1, 1, 1, 0, 0]
    history, df = run_episode(env, actions)
    
    print(f"\nRan {len(history)} steps:")
    for h in history:
        print(f"  Step {h['step']}: current_step={h['pre_idx']}, "
              f"action={h['action']}, pos={h['pos_old']}→{h['pos_new']}")
    
    # ============================================================================
    # VALIDATION
    # ============================================================================
    print_subsection("4. VALIDATION")
    
    print("\n✓ Testing lookahead prevention...")
    
    # Reset to check observations manually
    obs, _ = env.reset()
    
    # Extract price features from observation (last 5*lookback features)
    n_features = lookback * 5  # OHLCV for each lookback day
    price_features = obs[:n_features]
    
    # Since source_mode='raw', features should be raw OHLCV values
    # For our data: open=high=low=close, so we can just check every 5th value
    observed_prices = price_features[::5][:lookback]  # Get open prices
    
    current_step = env.current_step
    expected_start = max(0, current_step - lookback + 1)
    expected_end = current_step + 1
    expected_prices = opens[expected_start:expected_end]
    
    print(f"  Current step: {current_step}")
    print(f"  Expected price range: indices {expected_start} to {current_step}")
    print(f"  Expected prices: {expected_prices}")
    print(f"  Observed prices: {observed_prices.tolist()}")
    
    # Verify we're not seeing future data
    max_allowed_idx = current_step
    max_observed_price = max(observed_prices)
    max_expected_price = opens[max_allowed_idx]
    
    assert max_observed_price <= max_expected_price, (
        f"LOOKAHEAD BIAS DETECTED!\n"
        f"  Current step: {current_step} (price={opens[current_step]})\n"
        f"  Max observed: {max_observed_price}\n"
        f"  Max allowed: {max_expected_price}\n"
        f"  Observation contains future data!"
    )
    print(f"  ✓ No future data in observation")
    
    print("\n✓ Testing episode termination...")
    
    # Continue stepping until termination
    terminated = False
    steps = 0
    max_steps = 20  # Safety limit
    
    while not terminated and steps < max_steps:
        obs, reward, terminated, truncated, info = env.step(1)
        steps += 1
        
        if terminated or truncated:
            print(f"  Episode terminated at step {env.current_step}")
            print(f"  Episode end_idx: {env.episode_end_idx}")
            print(f"  Final position: {env.position}")
            
            # Check we didn't go past episode_end_idx
            assert env.current_step <= env.episode_end_idx + 1, (
                f"Episode overran bounds!\n"
                f"  current_step: {env.current_step}\n"
                f"  episode_end_idx: {env.episode_end_idx}"
            )
            print(f"  ✓ Episode stayed within bounds")
            break
    
    assert terminated, "Episode should terminate within reasonable steps"
    print(f"  ✓ Episode terminated cleanly")
    
    # ============================================================================
    # BOUNDARY CHECKS
    # ============================================================================
    print_subsection("5. BOUNDARY CHECKS")
    
    print("\n✓ Checking lookback window at episode start...")
    
    # Reset and check first observation has enough history
    obs, _ = env.reset()
    
    assert env.current_step >= lookback, (
        f"Episode starts too early for lookback window!\n"
        f"  current_step: {env.current_step}\n"
        f"  lookback_window: {lookback}\n"
        f"  Need at least {lookback} rows before current_step"
    )
    print(f"  Episode start ({env.current_step}) >= lookback ({lookback}) ✓")
    
    print("\n✓ Checking execution price access...")
    
    # At each step, verify we can access open[t+1] for execution
    env.reset()
    for _ in range(min(3, end_idx - start_idx)):
        current = env.current_step
        
        # Verify we can access t+1
        assert current + 1 < len(df), (
            f"Cannot access execution price!\n"
            f"  current_step: {current}\n"
            f"  Need open[{current + 1}] but df only has {len(df)} rows"
        )
        
        execution_price = df.iloc[current + 1]["open"]
        print(f"  Step {current}: can access open[{current + 1}] = {execution_price} ✓")
        
        env.step(1)
    
    # ============================================================================
    # COMPARISON TO THEORY
    # ============================================================================
    print_subsection("6. COMPARISON TO THEORY")
    
    print("\nKey insights:")
    print("  1. Observations only contain data up to current_step ✓")
    print("  2. No lookahead bias (cannot see future prices) ✓")
    print("  3. Episode boundaries properly enforced ✓")
    print("  4. Lookback window has sufficient history ✓")
    print("  5. Execution prices (t+1) are accessible ✓")
    
    print("\n" + "="*80)
    print("✅ TEST 8 PASSED - Episode boundaries are safe!")
    print("="*80)
