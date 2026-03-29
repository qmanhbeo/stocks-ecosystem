"""
TEST 11: Forced Policy Evaluation (Flat + Buy & Hold)

WHAT IT TESTS:
- forced policy flat: no trades, equity stays 1.0, zero rewards
- forced policy buy_hold: one buy, no sells, final equity matches buy & hold minus buy fee

WHY IT MATTERS:
Validates accounting and execution timing in the evaluation pipeline.
"""

import tempfile
from pathlib import Path

import numpy as np

from test_utils import create_price_dataframe, print_section, print_subsection
from vn_stock_rl.env import TradingEnv
from vn_stock_rl.evaluation.runner import evaluate_model


def _write_parquet(df, data_dir: Path, stock: str) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    data_path = data_dir / f"gia_lich_su_{stock}_1D.parquet"
    df.to_parquet(data_path)
    return data_path


def test_evaluate_forced_policies():
    """Test forced flat and buy-hold evaluation paths."""
    print_section("TEST 11: Forced Policy Evaluation (Flat + Buy & Hold)")
    
    print_subsection("1. SYNTHETIC DATA")
    opens = [100.0 + i for i in range(120)]  # Monotonic uptrend
    df = create_price_dataframe(opens)
    print(f"Data points: {len(opens)}")
    print(f"Price range: [{min(opens):.2f}, {max(opens):.2f}]")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        data_dir = tmp_path / "data"
        output_dir = tmp_path / "results"
        stock = "TEST"
        data_path = _write_parquet(df, data_dir, stock)
        
        # ======================================================================
        # FORCED FLAT
        # ======================================================================
        print_subsection("2. FORCED FLAT BASELINE")
        flat_output = output_dir / "flat"
        df_flat, stats_flat = evaluate_model(
            model_path="unused.zip",
            stock=stock,
            data_dir=str(data_dir),
            mode="test",
            output_dir=str(flat_output),
            deterministic=True,
            render=False,
            forced_policy="flat"
        )
        
        assert stats_flat["num_trades"] == 0, "Flat policy should have zero trades"
        assert np.all(df_flat["action"].values == 0), "Flat policy should always action=0"
        assert np.all(df_flat["position"].values == 0), "Flat policy should stay out of market"
        assert np.allclose(df_flat["reward"].values, 0.0, atol=1e-12), (
            "Flat policy should produce zero rewards"
        )
        assert np.allclose(df_flat["portfolio_value"].values, 1.0, atol=1e-12), (
            "Flat policy equity should remain at 1.0"
        )
        
        print("Flat baseline checks passed.")
        
        # ======================================================================
        # FORCED BUY & HOLD
        # ======================================================================
        print_subsection("3. FORCED BUY & HOLD BASELINE")
        buy_hold_output = output_dir / "buy_and_hold"
        df_hold, stats_hold = evaluate_model(
            model_path="unused.zip",
            stock=stock,
            data_dir=str(data_dir),
            mode="test",
            output_dir=str(buy_hold_output),
            deterministic=True,
            render=False,
            forced_policy="buy_hold"
        )
        
        assert stats_hold["num_trades"] == 1, "Buy & hold should execute exactly one buy trade"
        assert np.all(df_hold["action"].values == 1), "Buy & hold should always action=1"
        
        # Compute expected final equity from environment indices
        env = TradingEnv(data_path=str(data_path), mode="test", stop_loss=None)
        env.reset()
        buy_exec_price = df_hold.loc[df_hold["position"] == 1, "open"].iloc[0]
        open_final = env.df.iloc[env.episode_end_idx + 1]["open"]
        expected_final_equity = (1 - env.buy_fee_rate) * (open_final / buy_exec_price)
        actual_final_equity = df_hold["portfolio_value"].iloc[-1]

        assert np.isclose(actual_final_equity, expected_final_equity, atol=1e-10), (
            f"Final equity mismatch\n"
            f"  Expected: {expected_final_equity:.10f}\n"
            f"  Got:      {actual_final_equity:.10f}"
        )
        
        # Execution-aligned buy & hold should match forced buy & hold
        steps = df_hold["step"].values
        open_exec = env.df["open"].values[steps + 1]
        entry_exec_idx = env.episode_start_idx + 1
        entry_exec_price = env.df.iloc[entry_exec_idx]["open"]
        aligned_series = np.where(
            (steps + 1) < entry_exec_idx,
            1.0,
            (1 - env.buy_fee_rate) * (open_exec / entry_exec_price)
        )
        aligned_return = aligned_series[-1] - 1
        
        assert np.isclose(actual_final_equity - 1, aligned_return, atol=1e-12), (
            "Aligned buy & hold return should match forced buy & hold equity"
        )

        print("Buy & hold baseline checks passed.")
    
    print("\n" + "="*80)
    print("TEST 11 PASSED - Forced policy evaluation is correct!")
    print("="*80)
