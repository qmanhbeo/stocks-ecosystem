"""
TEST 9: Train/Val/Test Split Integrity

WHAT IT TESTS:
- Train/val/test splits have correct boundaries
- No overlap between splits (data leakage prevention)
- 1-day gap between splits is enforced
- Splits have reasonable sizes

WHY IT MATTERS:
Data leakage between splits causes overfitting and gives false confidence
in model performance. This test ensures clean separation.
"""

import numpy as np
import pandas as pd
from test_utils import (
    TestEnv, create_price_dataframe, print_section, print_subsection
)


def test_split_integrity():
    """Test that train/val/test splits are properly separated."""
    
    print_section("TEST 9: Train/Val/Test Split Integrity")
    
    # ============================================================================
    # TEST SETUP
    # ============================================================================
    print_subsection("1. SYNTHETIC DATA")
    
    # Create longer sequence to have meaningful splits
    total_days = 1000
    opens = [100.0 + i * 0.1 for i in range(total_days)]  # Slowly increasing
    print(f"Total data points: {total_days}")
    
    df = create_price_dataframe(opens)
    
    train_split = 0.7
    val_split = 0.15
    lookback = 10
    
    print(f"\nSplit configuration:")
    print(f"  Train split: {train_split*100:.0f}%")
    print(f"  Val split: {val_split*100:.0f}%")
    print(f"  Test split: {(1-train_split-val_split)*100:.0f}%")
    print(f"  Lookback window: {lookback}")
    
    # ============================================================================
    # EXPECTED BEHAVIOR
    # ============================================================================
    print_subsection("2. EXPECTED SPLIT BOUNDARIES")
    
    # Calculate expected boundaries (matching environment logic)
    valid_start_idx = lookback + 1  # Need history for observation
    train_end = int(total_days * train_split) - 1
    val_end = int(total_days * (train_split + val_split)) - 1
    
    print(f"\nExpected boundaries:")
    print(f"  Valid start: {valid_start_idx} (need lookback history)")
    print(f"  Train: [{valid_start_idx}, {train_end}]")
    print(f"  Gap: [{train_end + 1}]")
    print(f"  Val: [{train_end + 2}, {val_end}]")
    print(f"  Gap: [{val_end + 1}]")
    print(f"  Test: [{val_end + 2}, {total_days - 1}]")
    
    expected_train_size = train_end - valid_start_idx + 1
    expected_val_size = val_end - (train_end + 2) + 1
    expected_test_size = (total_days - 1) - (val_end + 2) + 1
    
    print(f"\nExpected sizes:")
    print(f"  Train: {expected_train_size} days")
    print(f"  Val: {expected_val_size} days")
    print(f"  Test: {expected_test_size} days")
    
    # ============================================================================
    # TEST TRAIN MODE
    # ============================================================================
    print_subsection("3. TESTING TRAIN MODE")
    
    # Create env in train mode
    env_train = TestEnv(
        df=df,
        start_idx=valid_start_idx,
        end_idx=train_end - 1,  # -1 because we need t+1
        mode="train",
        lookback_window=lookback,
        source_mode="return",
        min_hold_days=1,
    )
    
    obs, info = env_train.reset()
    
    print(f"\nTrain mode:")
    print(f"  Episode start: {env_train.episode_start_idx}")
    print(f"  Episode end: {env_train.episode_end_idx}")
    print(f"  Episode length: {env_train.episode_end_idx - env_train.episode_start_idx + 1}")
    
    # Verify train stays in train region
    assert env_train.episode_start_idx >= valid_start_idx, (
        f"Train start too early: {env_train.episode_start_idx} < {valid_start_idx}"
    )
    assert env_train.episode_end_idx <= train_end - 1, (
        f"Train end too late: {env_train.episode_end_idx} > {train_end - 1}"
    )
    print(f"  ✓ Train boundaries correct")
    
    # ============================================================================
    # TEST VAL MODE
    # ============================================================================
    print_subsection("4. TESTING VAL MODE")
    
    env_val = TestEnv(
        df=df,
        start_idx=train_end + 2,
        end_idx=val_end - 1,
        mode="val",
        lookback_window=lookback,
        source_mode="return",
        min_hold_days=1,
    )
    
    obs, info = env_val.reset()
    
    print(f"\nVal mode:")
    print(f"  Episode start: {env_val.episode_start_idx}")
    print(f"  Episode end: {env_val.episode_end_idx}")
    print(f"  Episode length: {env_val.episode_end_idx - env_val.episode_start_idx + 1}")
    
    # Verify val starts after train with gap
    assert env_val.episode_start_idx >= train_end + 2, (
        f"Val starts too early: {env_val.episode_start_idx} < {train_end + 2}\n"
        f"Missing gap between train and val!"
    )
    assert env_val.episode_end_idx <= val_end - 1, (
        f"Val end too late: {env_val.episode_end_idx} > {val_end - 1}"
    )
    print(f"  ✓ Val boundaries correct")
    print(f"  ✓ Gap between train and val: {env_val.episode_start_idx - train_end - 1} day(s)")
    
    # ============================================================================
    # TEST TEST MODE
    # ============================================================================
    print_subsection("5. TESTING TEST MODE")
    
    env_test = TestEnv(
        df=df,
        start_idx=val_end + 2,
        end_idx=total_days - 2,
        mode="test",
        lookback_window=lookback,
        source_mode="return",
        min_hold_days=1,
    )
    
    obs, info = env_test.reset()
    
    print(f"\nTest mode:")
    print(f"  Episode start: {env_test.episode_start_idx}")
    print(f"  Episode end: {env_test.episode_end_idx}")
    print(f"  Episode length: {env_test.episode_end_idx - env_test.episode_start_idx + 1}")
    
    # Verify test starts after val with gap
    assert env_test.episode_start_idx >= val_end + 2, (
        f"Test starts too early: {env_test.episode_start_idx} < {val_end + 2}\n"
        f"Missing gap between val and test!"
    )
    print(f"  ✓ Test boundaries correct")
    print(f"  ✓ Gap between val and test: {env_test.episode_start_idx - val_end - 1} day(s)")
    
    # ============================================================================
    # OVERLAP CHECK
    # ============================================================================
    print_subsection("6. CHECKING FOR OVERLAP")
    
    print("\n✓ Verifying no overlap in DECISION indices...")
    print("  (Lookback windows may overlap historical data, but decisions must not)")
    
    # Train decision range
    train_decision_start = env_train.episode_start_idx
    train_decision_end = env_train.episode_end_idx
    
    # Val decision range
    val_decision_start = env_val.episode_start_idx
    val_decision_end = env_val.episode_end_idx
    
    # Test decision range
    test_decision_start = env_test.episode_start_idx
    test_decision_end = env_test.episode_end_idx
    
    print(f"\n  Decision ranges (where agent makes choices):")
    print(f"    Train: [{train_decision_start}, {train_decision_end}]")
    print(f"    Val:   [{val_decision_start}, {val_decision_end}]")
    print(f"    Test:  [{test_decision_start}, {test_decision_end}]")
    
    # Check no overlap in decisions
    assert train_decision_end < val_decision_start, (
        f"Train and val decision ranges overlap!\n"
        f"  Train ends at: {train_decision_end}\n"
        f"  Val starts at: {val_decision_start}"
    )
    print(f"    ✓ Train and val decisions do not overlap")
    
    assert val_decision_end < test_decision_start, (
        f"Val and test decision ranges overlap!\n"
        f"  Val ends at: {val_decision_end}\n"
        f"  Test starts at: {test_decision_start}"
    )
    print(f"    ✓ Val and test decisions do not overlap")
    
    # Also show observation ranges (for information)
    train_obs_start = train_decision_start - lookback
    train_obs_end = train_decision_end + 1  # +1 for execution
    val_obs_start = val_decision_start - lookback
    val_obs_end = val_decision_end + 1
    test_obs_start = test_decision_start - lookback
    test_obs_end = test_decision_end + 1
    
    print(f"\n  Observation ranges (including lookback for context):")
    print(f"    Train: [{train_obs_start}, {train_obs_end}]")
    print(f"    Val:   [{val_obs_start}, {val_obs_end}]")
    print(f"    Test:  [{test_obs_start}, {test_obs_end}]")
    print(f"    Note: Lookback windows may overlap for context, but decisions don't ✓")
    
    # ============================================================================
    # SIZE SANITY CHECKS
    # ============================================================================
    print_subsection("7. SPLIT SIZE SANITY CHECKS")
    
    actual_train_size = env_train.episode_end_idx - env_train.episode_start_idx + 1
    actual_val_size = env_val.episode_end_idx - env_val.episode_start_idx + 1
    actual_test_size = env_test.episode_end_idx - env_test.episode_start_idx + 1
    
    print(f"\nActual split sizes:")
    print(f"  Train: {actual_train_size} days ({actual_train_size/total_days*100:.1f}%)")
    print(f"  Val:   {actual_val_size} days ({actual_val_size/total_days*100:.1f}%)")
    print(f"  Test:  {actual_test_size} days ({actual_test_size/total_days*100:.1f}%)")
    
    # Check splits are reasonable (train should be largest)
    assert actual_train_size > actual_val_size, (
        "Train split should be larger than val split"
    )
    assert actual_train_size > actual_test_size, (
        "Train split should be larger than test split"
    )
    print(f"  ✓ Train is largest split")
    
    # Check we're using most of the data
    total_used = actual_train_size + actual_val_size + actual_test_size
    usage_pct = total_used / total_days * 100
    print(f"\nTotal data usage: {total_used}/{total_days} ({usage_pct:.1f}%)")
    
    assert usage_pct > 90, (
        f"Only using {usage_pct:.1f}% of data - too much waste!"
    )
    print(f"  ✓ Using >90% of available data")
    
    # ============================================================================
    # COMPARISON TO THEORY
    # ============================================================================
    print_subsection("8. COMPARISON TO THEORY")
    
    print("\nKey insights:")
    print("  1. Splits have correct boundaries ✓")
    print("  2. 1-day gaps between splits enforced ✓")
    print("  3. No decision overlap/leakage ✓")
    print("  4. Train split is largest ✓")
    print("  5. Data usage is efficient (>90%) ✓")
    
    print("\nData flow verification:")
    print(f"  Train decisions: indices {train_decision_start} to {train_decision_end}")
    print(f"  Val decisions:   indices {val_decision_start} to {val_decision_end}")
    print(f"  Test decisions:  indices {test_decision_start} to {test_decision_end}")
    print(f"  Lookback windows may overlap historical data (for context)")
    print(f"  But decisions are made on completely separate data ✓")
    
    print("\n" + "="*80)
    print("✅ TEST 9 PASSED - Split integrity verified!")
    print("="*80)
