import numpy as np
import pandas as pd

from vn_stock_rl.data_tools.export_lab_signal_matrix import export_lab_signal_matrix
from vn_stock_rl.env import TradingEnv


def _make_price_df(length: int = 20) -> pd.DataFrame:
    times = pd.date_range("2024-01-01", periods=length, freq="D")
    prices = 100.0 + np.arange(length, dtype=np.float64)
    return pd.DataFrame(
        {
            "time": times,
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices + 0.5,
            "volume": 1000.0 + np.arange(length, dtype=np.float64),
        }
    )


def test_export_lab_signal_matrix_writes_per_ticker_files(tmp_path):
    matrix_path = tmp_path / "xs_rl_signal_matrix.parquet"
    output_dir = tmp_path / "rl_lab_matrix"
    matrix = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01"]),
            "ticker": ["ACB", "ACB", "FPT"],
            "actual": [1, 0, 1],
            "s1_proba": [0.8, 0.6, 0.3],
            "c12_gap_absorb_3": [0.1, 0.2, 0.7],
        }
    )
    matrix.to_parquet(matrix_path, index=False)

    manifest = export_lab_signal_matrix(matrix_path=matrix_path, output_dir=output_dir)

    assert manifest["signal_columns"] == ["s1_proba", "c12_gap_absorb_3"]
    assert manifest["files_written"] == 2
    exported = pd.read_parquet(output_dir / "ACB_signal_predictions.parquet")
    assert list(exported.columns) == ["date", "s1_proba", "c12_gap_absorb_3"]
    assert exported["date"].tolist() == ["2024-01-01", "2024-01-02"]


def test_trading_env_reads_custom_lab_signal_exports(tmp_path):
    data_path = tmp_path / "gia_lich_su_ACB_1D.parquet"
    matrix_path = tmp_path / "xs_rl_signal_matrix.parquet"
    output_dir = tmp_path / "rl_lab_matrix"

    price_df = _make_price_df()
    price_df.to_parquet(data_path, index=False)

    matrix = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-06"]),
            "ticker": ["ACB", "ACB", "ACB"],
            "actual": [1, 0, 1],
            "s1_proba": [0.9, 0.2, 0.8],
            "c12_gap_absorb_3": [0.4, -0.1, 0.3],
        }
    )
    matrix.to_parquet(matrix_path, index=False)
    export_lab_signal_matrix(matrix_path=matrix_path, output_dir=output_dir)

    signal_columns = ["s1_proba", "c12_gap_absorb_3"]
    env = TradingEnv(
        data_path=str(data_path),
        mode="train",
        lookback_window=3,
        train_episode_sampling_enabled=False,
        signal_feature_columns=signal_columns,
        signal_prediction_dir=str(output_dir),
    )

    expected = (
        price_df.assign(date=pd.to_datetime(price_df["time"]).dt.strftime("%Y-%m-%d"))
        .merge(
            pd.DataFrame(
                {
                    "date": ["2024-01-01", "2024-01-03", "2024-01-06"],
                    "s1_proba": [0.9, 0.2, 0.8],
                    "c12_gap_absorb_3": [0.4, -0.1, 0.3],
                }
            ),
            on="date",
            how="left",
        )
    )
    expected["s1_proba"] = expected["s1_proba"].fillna(0.0)
    expected["c12_gap_absorb_3"] = expected["c12_gap_absorb_3"].fillna(0.0)
    expected = expected[signal_columns].to_numpy(dtype=np.float64)

    np.testing.assert_allclose(env._signal, expected)
    env.close()


def test_export_lab_signal_matrix_removes_stale_subset_files(tmp_path):
    matrix_path = tmp_path / "xs_rl_signal_matrix.parquet"
    output_dir = tmp_path / "rl_lab_matrix"
    matrix = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "ticker": ["ACB", "FPT"],
            "actual": [1, 0],
            "s1_proba": [0.8, 0.4],
        }
    )
    matrix.to_parquet(matrix_path, index=False)

    export_lab_signal_matrix(matrix_path=matrix_path, output_dir=output_dir)
    manifest = export_lab_signal_matrix(
        matrix_path=matrix_path,
        output_dir=output_dir,
        tickers=["ACB"],
    )

    assert (output_dir / "ACB_signal_predictions.parquet").exists()
    assert not (output_dir / "FPT_signal_predictions.parquet").exists()
    assert manifest["stale_files_removed"] == ["FPT_signal_predictions.parquet"]
