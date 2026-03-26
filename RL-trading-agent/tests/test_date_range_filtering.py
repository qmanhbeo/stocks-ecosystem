import pandas as pd

from vn_stock_rl.env import MultiStockEnv, TradingEnv
from vn_stock_rl.evaluation.metadata import _merge_env_overrides


def _make_dt_df(start: str, periods: int, price_offset: float = 0.0) -> pd.DataFrame:
    times = pd.date_range(start, periods=periods, freq="D")
    prices = price_offset + 100.0 + pd.Series(range(periods), dtype=float)
    return pd.DataFrame(
        {
            "time": times,
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "volume": 1000.0 + pd.Series(range(periods), dtype=float),
        }
    )


def test_trading_env_filters_sample_dates_before_split(tmp_path):
    data_path = tmp_path / "gia_lich_su_ACB_1D.parquet"
    df = _make_dt_df("2020-01-01", periods=180)
    df.to_parquet(data_path, index=False)

    start_date = "2020-02-15"
    end_date = "2020-05-31"
    expected_df = df.loc[
        (df["time"] >= pd.Timestamp(start_date)) & (df["time"] <= pd.Timestamp(end_date))
    ].reset_index(drop=True)

    env = TradingEnv(
        data_path=str(data_path),
        mode="train",
        lookback_window=10,
        train_episode_sampling_enabled=False,
        start_date=start_date,
        end_date=end_date,
    )

    splits = env._compute_splits(len(expected_df), env.lookback_window, env.train_split, env.val_split)

    assert len(env.df) == len(expected_df)
    assert env.df["time"].min() == expected_df["time"].min()
    assert env.df["time"].max() == expected_df["time"].max()
    assert env.train_start_date == expected_df.iloc[splits["train_start_idx"]]["time"]
    assert env.train_end_date == expected_df.iloc[splits["train_end_idx"]]["time"]
    assert env.val_start_date == expected_df.iloc[splits["val_start_idx"]]["time"]
    assert env.val_end_date == expected_df.iloc[splits["val_end_idx"]]["time"]
    assert env.test_start_date == expected_df.iloc[splits["test_start_idx"]]["time"]
    assert env.test_end_date == expected_df.iloc[splits["test_end_idx"]]["time"]
    assert env.input_features["sample_start_date"] == start_date
    assert env.input_features["sample_end_date"] == end_date

    env.close()


def test_multi_stock_env_filters_each_stock_before_split(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    acb_df = _make_dt_df("2020-01-01", periods=200, price_offset=0.0)
    fpt_df = _make_dt_df("2020-01-01", periods=200, price_offset=50.0)
    acb_df.to_parquet(data_dir / "gia_lich_su_ACB_1D.parquet", index=False)
    fpt_df.to_parquet(data_dir / "gia_lich_su_FPT_1D.parquet", index=False)

    start_date = "2020-03-01"
    end_date = "2020-06-30"

    env = MultiStockEnv(
        data_dir=str(data_dir),
        mode="train",
        stocks=["ACB", "FPT"],
        lookback_window=12,
        train_episode_sampling_enabled=False,
        start_date=start_date,
        end_date=end_date,
    )

    assert sorted(env.stock_names) == ["ACB", "FPT"]
    for stock_record in env.stock_data:
        stock_df = stock_record["df"]
        expected_df = (
            acb_df if stock_record["name"] == "ACB" else fpt_df
        ).loc[
            lambda frame: (frame["time"] >= pd.Timestamp(start_date)) & (frame["time"] <= pd.Timestamp(end_date))
        ].reset_index(drop=True)
        splits = env._compute_splits(len(expected_df), env.lookback_window, env.train_split, env.val_split)

        assert len(stock_df) == len(expected_df)
        assert stock_df["time"].min() == expected_df["time"].min()
        assert stock_df["time"].max() == expected_df["time"].max()
        assert stock_record["train_start"] == splits["train_start_idx"]
        assert stock_record["train_end"] == splits["train_end_idx"]
        assert stock_record["val_start"] == splits["val_start_idx"]
        assert stock_record["val_end"] == splits["val_end_idx"]
        assert stock_record["test_start"] == splits["test_start_idx"]
        assert stock_record["test_end"] == splits["test_end_idx"]

    env.close()


def test_merge_env_overrides_reads_sample_date_bounds_from_metadata():
    meta = {
        "environment_config": {
            "input_features": {
                "sample_start_date": "2016-01-01",
                "sample_end_date": "2026-02-24",
            }
        }
    }

    env_kwargs = _merge_env_overrides(
        meta=meta,
        explicit_env_overrides={"start_date": None, "end_date": None},
        forced_policy=None,
    )

    assert env_kwargs["start_date"] == "2016-01-01"
    assert env_kwargs["end_date"] == "2026-02-24"
