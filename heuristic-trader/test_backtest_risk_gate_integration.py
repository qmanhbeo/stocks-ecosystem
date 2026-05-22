import pandas as pd

import backtest as bt


def _build_price_cache(dates, ticker: str) -> dict[str, pd.DataFrame]:
    px = pd.DataFrame(
        {
            "time": dates,
            "open": [100.0 + i for i in range(len(dates))],
            "close": [100.5 + i for i in range(len(dates))],
            "volume": [1_000_000 for _ in dates],
        }
    ).set_index("time")
    return {ticker: px}


def test_backtest_emits_gate_columns_and_killswitch_triggers() -> None:
    dates = pd.date_range("2025-01-01", periods=12, freq="D")
    signal_df = pd.DataFrame(
        {
            "time": dates,
            "ticker": ["AAA"] * len(dates),
            "sig": [0.9] * len(dates),
        }
    )
    cache = _build_price_cache(dates, "AAA")

    result = bt.simulate_topk_constraint_compliant(
        signal_df=signal_df,
        cache=cache,
        signal_col="sig",
        top_k=2,  # only one candidate available -> persistent underfill
        rebalance_days=1,
        min_hold_days=1,
        use_filters=False,
        collect_diagnostics=True,
        candidate_scan_multiplier=3,
        sizing_mode="fixed_initial",
        fallback_mode="none",
        gate_enabled=True,
        gate_profile="tail_first_v1",
        exposure_floor=0.10,
        exposure_ceiling=1.00,
        kill_switch_thresholds={"underfill_ratio": 0.40},
        cooldown_rebalances=2,
    )

    curve = result.curve
    for col in [
        "gate_state",
        "exposure_scale",
        "kill_switch_active",
        "gate_reason",
        "cooldown_remaining",
        "benchmark_state",
    ]:
        assert col in curve.columns

    assert (curve["kill_switch_active"] == True).any()
    assert (curve["exposure_scale"] <= 1.0).all()
    assert (curve["exposure_scale"] >= 0.10).all()

    gate_log = result.diagnostics.get("gate_log")
    assert gate_log is not None
    assert len(gate_log) > 0
