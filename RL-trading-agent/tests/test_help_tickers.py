"""
Tests for helper tickers (market features) integration.
"""

import os
import json
import tempfile
import numpy as np
import pandas as pd

from vn_stock_rl.env import TradingEnv
from vn_stock_rl.evaluation.runner import evaluate_model


def _make_df(start: int, length: int, price: float) -> pd.DataFrame:
    times = np.arange(start, start + length)
    prices = np.full(length, price, dtype=float)
    return pd.DataFrame({
        "time": times,
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": np.ones(length, dtype=float),
    })


def test_help_tickers_alignment_and_shape():
    print("\n" + "="*80)
    print("TEST: Helper Tickers Alignment + Observation Shape")
    print("="*80)
    print("\n1. SYNTHETIC DATA")
    print("-----------------")
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Base stock: 0..119
        base_df = _make_df(0, 120, 100.0)
        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        
        # Helper tickers: 50..169 (overlap = 50..119 => 70 rows)
        helper1_df = _make_df(50, 120, 200.0)
        helper2_df = _make_df(50, 120, 300.0)
        helper1_df.to_parquet(os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet"), index=False)
        helper2_df.to_parquet(os.path.join(data_dir, "gia_lich_su_VN30_1D.parquet"), index=False)
        
        print(f"Base range:     0..119  (len={len(base_df)})")
        print(f"Helper range:   50..169 (len={len(helper1_df)})")
        print("Expected overlap: 50..119 -> 70 rows")
        
        print("\n2. EXPECTED BEHAVIOR")
        print("--------------------")
        print("Alignment: inner join on time")
        print("Expected aligned length: 70 rows")
        print("Expected obs size: lookback * 5 * (1 + num_helpers) + 3")
        
        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=10,
            help_tickers=["VNINDEX", "VN30"],
            market_data_dir=data_dir
        )
        
        expected_obs = 10 * 5 * (1 + 2) + 3
        
        print("\n3. ACTUAL RESULTS")
        print("-----------------")
        print(f"Aligned length: {len(env.df)}")
        print(f"Obs size:       {env.observation_space.shape[0]}")
        
        print("\n4. VALIDATION")
        print("-------------")
        assert len(env.df) == 70, f"Expected aligned length 70, got {len(env.df)}"
        print("✓ Aligned length matches expected intersection")
        assert env.observation_space.shape[0] == expected_obs, \
            f"Expected obs size {expected_obs}, got {env.observation_space.shape[0]}"
        print("✓ Observation size matches expected formula")


def test_help_tickers_dedup_in_evaluate():
    print("\n" + "="*80)
    print("TEST: Helper Tickers Dedup Gate (Single Stock)")
    print("="*80)
    print("\n1. SYNTHETIC DATA")
    print("-----------------")
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(data_dir, exist_ok=True)
        
        base_df = _make_df(0, 120, 100.0)
        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        
        print("Created only ACB parquet file")
        print("Help tickers passed: [ACB] (should be filtered out)")
        
        print("\n2. EXPECTED BEHAVIOR")
        print("--------------------")
        print("Dedup should remove ACB from help tickers")
        print("Evaluation should run without trying to load helper data")
        
        # If dedup fails, evaluation will try to load helper data and fail
        # because only ACB exists in this temp dir.
        evaluate_model(
            model_path=os.path.join(tmpdir, "dummy.zip"),
            stock="ACB",
            data_dir=data_dir,
            output_dir=out_dir,
            mode="test",
            forced_policy="flat",
            help_tickers=["ACB"],
            market_data_dir=data_dir
        )
        
        print("\n3. ACTUAL RESULTS")
        print("-----------------")
        print("Evaluation completed without missing helper data errors")
        
        print("\n4. VALIDATION")
        print("-------------")
        print("✓ Dedup gate worked (no helper loading attempted)")


def test_help_tickers_metadata_autoload():
    print("\n" + "="*80)
    print("TEST: Helper Tickers Metadata Auto-Load")
    print("="*80)
    print("\n1. SYNTHETIC DATA")
    print("-----------------")
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(data_dir, exist_ok=True)
        
        base_df = _make_df(0, 120, 100.0)
        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        
        # Keep full overlap with base series so this test isolates metadata auto-load behavior
        # and does not fail due lookback-dependent alignment truncation.
        helper_df = _make_df(0, 120, 200.0)
        helper_path = os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet")
        helper_df.to_parquet(helper_path, index=False)
        
        print("Created ACB and VNINDEX parquet files")
        
        # Write metadata beside dummy model
        model_path = os.path.join(tmpdir, "dummy.zip")
        meta_path = os.path.splitext(model_path)[0] + "_meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "model_name": "dummy",
                "help_tickers": ["VNINDEX"],
                "market_data_dir": data_dir
            }, f)
        
        print("Wrote metadata with help_tickers=[VNINDEX]")
        
        print("\n2. EXPECTED BEHAVIOR")
        print("--------------------")
        print("evaluate_model should auto-load help_tickers from metadata")
        print("Evaluation should succeed with aligned helper data")
        
        df_history, stats = evaluate_model(
            model_path=model_path,
            stock="ACB",
            data_dir=data_dir,
            output_dir=out_dir,
            mode="test",
            forced_policy="flat",
            help_tickers=None
        )
        
        print("\n3. ACTUAL RESULTS")
        print("-----------------")
        print(f"History rows: {len(df_history)}")
        
        print("\n4. VALIDATION")
        print("-------------")
        assert not df_history.empty, "Expected evaluation history to be non-empty"
        print("✓ Metadata auto-load produced a valid evaluation history")


def test_evaluate_model_metadata_autoloads_data_dir():
    print("\n" + "="*80)
    print("TEST: Data Dir Metadata Auto-Load")
    print("="*80)
    print("\n1. SYNTHETIC DATA")
    print("-----------------")
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "custom_data")
        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(data_dir, exist_ok=True)

        base_df = _make_df(0, 120, 100.0)
        stock = "ZZMETA"
        base_path = os.path.join(data_dir, f"gia_lich_su_{stock}_1D.parquet")
        base_df.to_parquet(base_path, index=False)

        model_path = os.path.join(tmpdir, "dummy_model.zip")
        meta_path = os.path.splitext(model_path)[0] + "_meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model_name": "dummy",
                    "data_dir": data_dir,
                },
                f,
            )

        print("Created custom parquet outside the default shared path")
        print("Wrote metadata with data_dir pointing at that custom directory")

        print("\n2. EXPECTED BEHAVIOR")
        print("--------------------")
        print("evaluate_model should load the stock parquet from metadata data_dir")

        df_history, stats = evaluate_model(
            model_path=model_path,
            stock=stock,
            output_dir=out_dir,
            mode="test",
            forced_policy="flat",
        )

        print("\n3. ACTUAL RESULTS")
        print("-----------------")
        print(f"History rows: {len(df_history)}")

        print("\n4. VALIDATION")
        print("-------------")
        assert not df_history.empty, "Expected evaluation history to be non-empty"
        assert stats["num_trades"] == 0, "Flat policy should still produce zero trades"
        print("✓ Metadata data_dir was honored")
