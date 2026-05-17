#!/usr/bin/env python3
"""
Regression test: run_backtest signal wiring stays aligned with configured strategy types.

This catches drift where strategies.json introduces/retains a signal_type that
run_backtest.prepare_signal_df_from_config does not support.
"""

import sys

sys.path.insert(0, ".")

import run_backtest as rb
from strategies import loader as strategy_loader


TEST_START = "2024-01-01"
TEST_END = "2024-12-31"


def main() -> None:
    strategies = strategy_loader.load_strategies()
    by_signal_type = {}
    for name, cfg in strategies.items():
        by_signal_type.setdefault(cfg["signal_type"], (name, cfg))

    print("=" * 70)
    print("RUN_BACKTEST SIGNAL TYPE COVERAGE")
    print("=" * 70)

    for signal_type, (name, cfg) in sorted(by_signal_type.items()):
        print(f"Testing signal_type={signal_type} via strategy={name}")
        df = rb.prepare_signal_df_from_config(
            config=cfg,
            start_date=TEST_START,
            end_date=TEST_END,
            allow_2026=False,
        )
        assert len(df) > 0, f"{signal_type}: no rows returned"
        assert "time" in df.columns and "ticker" in df.columns, f"{signal_type}: missing base columns"
        assert cfg["signal_col"] in df.columns, (
            f"{signal_type}: expected signal column '{cfg['signal_col']}' not found in {list(df.columns)}"
        )
        print(f"  PASS rows={len(df)} cols={list(df.columns)}")

    print("=" * 70)
    print(f"PASS: {len(by_signal_type)} signal type(s) covered")
    print("=" * 70)


if __name__ == "__main__":
    main()
