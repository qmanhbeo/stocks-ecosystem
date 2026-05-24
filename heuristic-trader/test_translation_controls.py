from __future__ import annotations

import pandas as pd

import backtest as bt


def _build_price_cache(dates: pd.DatetimeIndex, tickers: list[str]) -> dict[str, pd.DataFrame]:
    cache: dict[str, pd.DataFrame] = {}
    for t in tickers:
        px = pd.DataFrame(
            {
                "time": dates,
                "open": [100.0 for _ in dates],
                "close": [100.0 for _ in dates],
                "volume": [2_000_000 for _ in dates],
            }
        ).set_index("time")
        cache[t] = px
    return cache


def _build_signal_df(rows: list[tuple[pd.Timestamp, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["time", "ticker", "sig"]).sort_values(["time", "ticker"]).reset_index(drop=True)


def test_replace_threshold_blocks_low_edge_replacements() -> None:
    dates = pd.date_range("2025-01-01", periods=5, freq="D")
    signal_rows = []
    per_day = [
        {"AAA": 1.00, "BBB": 0.99},
        {"AAA": 1.00, "BBB": 1.001},
        {"AAA": 1.00, "BBB": 1.001},
        {"AAA": 1.00, "BBB": 1.001},
        {"AAA": 1.00, "BBB": 1.001},
    ]
    for dt, score_map in zip(dates, per_day):
        for ticker, score in score_map.items():
            signal_rows.append((dt, ticker, score))

    result = bt.simulate_topk_constraint_compliant(
        signal_df=_build_signal_df(signal_rows),
        cache=_build_price_cache(dates, ["AAA", "BBB"]),
        signal_col="sig",
        top_k=1,
        rebalance_days=1,
        min_hold_days=1,
        use_filters=False,
        collect_diagnostics=True,
        replace_threshold_bps=50.0,
    )
    trades = result.diagnostics["trade_log"]
    if len(trades) > 0:
        sell_rows = trades[trades["action"] == "SELL"]
        assert len(sell_rows) == 0


def test_max_new_positions_cap_applies_per_rebalance() -> None:
    dates = pd.date_range("2025-01-01", periods=5, freq="D")
    signal_rows = []
    per_day = [
        {"AAA": 1.00, "BBB": 0.99, "CCC": 0.80, "DDD": 0.79},
        {"AAA": 0.70, "BBB": 0.69, "CCC": 1.00, "DDD": 0.99},
        {"AAA": 0.70, "BBB": 0.69, "CCC": 1.00, "DDD": 0.99},
        {"AAA": 0.70, "BBB": 0.69, "CCC": 1.00, "DDD": 0.99},
        {"AAA": 0.70, "BBB": 0.69, "CCC": 1.00, "DDD": 0.99},
    ]
    for dt, score_map in zip(dates, per_day):
        for ticker, score in score_map.items():
            signal_rows.append((dt, ticker, score))

    result = bt.simulate_topk_constraint_compliant(
        signal_df=_build_signal_df(signal_rows),
        cache=_build_price_cache(dates, ["AAA", "BBB", "CCC", "DDD"]),
        signal_col="sig",
        top_k=2,
        rebalance_days=1,
        min_hold_days=1,
        use_filters=False,
        collect_diagnostics=True,
        max_new_positions_per_rebalance=1,
    )
    fallback_log = result.diagnostics["fallback_log"]
    assert (fallback_log["new_positions_selected"] <= 1).all()


def test_regime_translation_overrides_scan_and_cadence() -> None:
    dates = pd.date_range("2025-01-01", periods=7, freq="D")
    signal_rows = []
    for dt in dates:
        signal_rows.extend(
            [
                (dt, "AAA", 1.0),
                (dt, "BBB", 0.9),
                (dt, "CCC", 0.8),
            ]
        )
    result = bt.simulate_topk_constraint_compliant(
        signal_df=_build_signal_df(signal_rows),
        cache=_build_price_cache(dates, ["AAA", "BBB", "CCC"]),
        signal_col="sig",
        top_k=1,
        rebalance_days=1,
        min_hold_days=1,
        use_filters=False,
        collect_diagnostics=True,
        regime_translation={
            "disabled": {
                "rebalance_interval_days": 2,
                "candidate_scan_multiplier": 7,
            }
        },
    )
    filtered = result.diagnostics["filtered_breakdown"]
    assert len(filtered) == 3
    assert (filtered["n_candidates"] == 7).all()


def test_conviction_rank_gap_weights_are_non_uniform() -> None:
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    signal_rows = []
    per_day = [
        {"AAA": 2.0, "BBB": 1.0, "CCC": 0.5},
        {"AAA": 2.0, "BBB": 1.0, "CCC": 0.5},
        {"AAA": 2.0, "BBB": 1.0, "CCC": 0.5},
        {"AAA": 2.0, "BBB": 1.0, "CCC": 0.5},
    ]
    for dt, score_map in zip(dates, per_day):
        for ticker, score in score_map.items():
            signal_rows.append((dt, ticker, score))

    result = bt.simulate_topk_constraint_compliant(
        signal_df=_build_signal_df(signal_rows),
        cache=_build_price_cache(dates, ["AAA", "BBB", "CCC"]),
        signal_col="sig",
        top_k=2,
        rebalance_days=1,
        min_hold_days=1,
        use_filters=False,
        collect_diagnostics=True,
        buy_fee=0.0,
        sell_fee=0.0,
        conviction_mode="rank_gap",
        conviction_strength=2.0,
        conviction_cap=2.0,
    )
    buys = result.diagnostics["trade_log"]
    buys = buys[buys["action"] == "BUY"]
    assert "conviction_weight" in buys.columns
    first_rebal = buys[buys["date"] == dates[1]]
    assert len(first_rebal) == 2
    assert float(first_rebal["conviction_weight"].max()) > float(first_rebal["conviction_weight"].min())


def test_underfill_recovery_state_is_logged() -> None:
    dates = pd.date_range("2025-01-01", periods=6, freq="D")
    signal_rows = []
    for dt in dates:
        signal_rows.extend(
            [
                (dt, "AAA", 1.0),
                (dt, "BBB", 0.5),
            ]
        )
    cache = _build_price_cache(dates, ["AAA", "BBB"])
    liquid_lookup = {dt: {"AAA", "BBB"} for dt in dates}
    trad_lookup = {(ticker, dt): (ticker == "AAA") for dt in dates for ticker in ["AAA", "BBB"]}
    result = bt.simulate_topk_constraint_compliant(
        signal_df=_build_signal_df(signal_rows),
        cache=cache,
        signal_col="sig",
        top_k=2,
        rebalance_days=1,
        min_hold_days=1,
        use_filters=True,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        collect_diagnostics=True,
        underfill_recovery_days=2,
    )
    curve = result.curve
    assert "recovery_backlog_slots" in curve.columns
    assert int(curve["recovery_backlog_slots"].max()) >= 1
