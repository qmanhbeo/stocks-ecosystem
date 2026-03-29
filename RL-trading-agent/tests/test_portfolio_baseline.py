from __future__ import annotations

import numpy as np
import pandas as pd

from vn_stock_rl.evaluation.portfolio_baseline import (
    compute_strategy_scores,
    run_portfolio_baseline,
)


def _make_price_df(length: int, base_price: float, volume_level: float) -> pd.DataFrame:
    times = pd.date_range("2020-01-01", periods=length, freq="D")
    close = base_price + np.linspace(0.0, 20.0, length, dtype=np.float64)
    open_ = close * 0.998
    return pd.DataFrame(
        {
            "time": times,
            "open": open_,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(length, volume_level, dtype=np.float64),
        }
    )


def _make_signal_df(length: int, offset: float) -> pd.DataFrame:
    times = pd.date_range("2020-01-01", periods=length, freq="D")
    return pd.DataFrame(
        {
            "date": times.strftime("%Y-%m-%d"),
            "s1_proba": np.linspace(0.1 + offset, 0.9 + offset, length, dtype=np.float64),
            "c5_signal_present": np.where(np.arange(length) % 2 == 0, 1.0, 0.0),
        }
    )


def _write_ticker_bundle(tmp_path, ticker: str, price_df: pd.DataFrame, signal_df: pd.DataFrame) -> None:
    price_df.to_parquet(tmp_path / f"gia_lich_su_{ticker}_1D.parquet", index=False)
    signal_dir = tmp_path / "signals"
    signal_dir.mkdir(parents=True, exist_ok=True)
    signal_df.to_parquet(signal_dir / f"{ticker}_signal_predictions.parquet", index=False)


def test_compute_strategy_scores_ranks_non_presence_and_keeps_presence():
    signal_slice = np.array(
        [
            [0.1, 1.0],
            [0.3, 0.0],
            [0.2, 1.0],
        ],
        dtype=np.float64,
    )

    scores = compute_strategy_scores(
        signal_slice,
        ["s1_proba", "c5_signal_present"],
        ["s1_proba", "c5_signal_present"],
    )

    # s1 ranks = [1/3, 1.0, 2/3], presence stays raw [1, 0, 1]
    expected = np.array([(1 / 3 + 1.0) / 2, (1.0 + 0.0) / 2, (2 / 3 + 1.0) / 2], dtype=np.float64)
    np.testing.assert_allclose(scores, expected)


def test_run_portfolio_baseline_builds_same_universe_summary(tmp_path):
    length = 400
    _write_ticker_bundle(
        tmp_path,
        "ACB",
        _make_price_df(length, 100.0, 2_000_000.0),
        _make_signal_df(length, 0.00),
    )
    _write_ticker_bundle(
        tmp_path,
        "FPT",
        _make_price_df(length, 90.0, 1_500_000.0),
        _make_signal_df(length, 0.05),
    )
    _write_ticker_bundle(
        tmp_path,
        "HPG",
        _make_price_df(length, 80.0, 200_000.0),
        _make_signal_df(length, 0.10),
    )

    summary, daily_frames = run_portfolio_baseline(
        mode="test",
        data_dir=str(tmp_path),
        signal_prediction_dir=str(tmp_path / "signals"),
        signal_columns=["s1_proba", "c5_signal_present"],
        strategies=["s1_only", "full_library"],
        start_date=None,
        end_date=None,
        portfolio_universe_size=2,
        portfolio_top_k=1,
        portfolio_universe_tickers=None,
    )

    assert summary["portfolio_universe_size"] == 2
    assert summary["universe_tickers"] == ["ACB", "FPT"]
    assert set(summary["strategies"]) == {"s1_only", "full_library"}
    assert summary["strategies"]["full_library"]["signal_columns"] == ["s1_proba", "c5_signal_present"]
    assert len(daily_frames["s1_only"]) > 0
    assert len(daily_frames["full_library"]) > 0
