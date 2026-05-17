#!/usr/bin/env python3
"""
Smoke tests for heuristic-trader Phase 1 safety/audit layer.

Run: python test_smoke.py
"""

import inspect
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd


def test_lockbox_blocks_2026():
    """A. Lockbox blocks 2026 by default."""
    print("\n[A] Testing lockbox blocks 2026 by default...")

    # Import signals module
    import signals as s

    # Test: load_rl_signal_matrix with end in 2026 should raise
    try:
        s.load_rl_signal_matrix(end="2026-03-31")
        print("  FAIL: Should have raised ValueError for 2026 date")
        return False
    except ValueError as e:
        if "2026" in str(e):
            print("  PASS: Lockbox correctly blocks 2026 end date")
            return True
        print(f"  FAIL: Wrong error message: {e}")
        return False


def test_artifact_production():
    """B. Valid run produces artifacts."""
    print("\n[B] Testing artifact production...")

    os.chdir(Path(__file__).parent)

    with tempfile.TemporaryDirectory() as tmpdir:
        import run_backtest as rb

        output_dir = Path(tmpdir) / "smoke_test"

        metrics = rb.run_strategy_for_test(
            strategy_name="s1_top3_rebal10",
            start_date="2025-01-01",
            end_date="2025-03-31",
            output_dir=output_dir,
            allow_2026=False,
        )

        required = ["config.json", "metrics.json", "daily_equity.parquet"]
        missing = [f for f in required if not (output_dir / f).exists()]

        if missing:
            print(f"  FAIL: Missing artifacts: {missing}")
            return False

        import json
        with open(output_dir / "metrics.json") as f:
            saved_metrics = json.load(f)

        print(f"  PASS: All artifacts created (return: {saved_metrics.get('total_return')})")
        return True


def test_artifact_respects_end_date():
    """C. Artifact respects end-date."""
    print("\n[C] Testing artifact respects end-date...")

    os.chdir(Path(__file__).parent)

    with tempfile.TemporaryDirectory() as tmpdir:
        import run_backtest as rb
        import json

        output_dir = Path(tmpdir) / "smoke_test"

        test_end = "2025-03-31"
        metrics = rb.run_strategy_for_test(
            strategy_name="s1_top3_rebal10",
            start_date="2025-01-01",
            end_date=test_end,
            output_dir=output_dir,
            allow_2026=False,
        )

        curve_path = output_dir / "daily_equity.parquet"
        if not curve_path.exists():
            print("  FAIL: No equity curve generated")
            return False

        curve = pd.read_parquet(curve_path)
        max_date = pd.to_datetime(curve["date"]).max()
        requested_end = pd.to_datetime(test_end)

        if max_date <= requested_end:
            print(f"  PASS: Max date {max_date.date()} <= requested {test_end}")
            return True
        else:
            print(f"  FAIL: Max date {max_date.date()} > requested {test_end}")
            return False


def test_loader_has_lockbox_filter():
    """D. Loader functions contain lockbox filtering."""
    print("\n[D] Testing loader functions contain lockbox filtering...")

    import signals as s

    loaders = [
        "load_rl_signal_matrix",
        "load_order_pressure",
        "load_order_pressure_raw",
        "load_order_pressure_delta",
        "load_order_pressure_c17_active_boost",
        "load_low_breadth_regime",
        "load_activation_state",
        "load_activation_meta",
        "load_insider_features",
        "load_event_surface",
        "load_stock_daily",
    ]

    failed = []
    for name in loaders:
        func = getattr(s, name, None)
        if func is None:
            failed.append(f"{name} (not found)")
            continue
        src = inspect.getsource(func)
        if "_apply_lockbox_filter" not in src:
            failed.append(name)

    if failed:
        print(f"  FAIL: Missing lockbox in: {failed}")
        return False

    print(f"  PASS: All {len(loaders)} loaders have lockbox filter")
    return True


def main():
    """Run all smoke tests and report results."""
    print("=" * 60)
    print("heuristic-trader Smoke Tests - Phase 1.5")
    print("=" * 60)

    results = {}

    # Run tests
    results["A_lockbox_2026"] = test_lockbox_blocks_2026()
    results["B_artifact_production"] = test_artifact_production()
    results["C_artifact_end_date"] = test_artifact_respects_end_date()
    results["D_loader_lockbox"] = test_loader_has_lockbox_filter()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n✅ ALL SMOKE TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
