import numpy as np
import pandas as pd

from vn_stock_rl.external_features import default_signal_prediction_dir
from vn_stock_rl.env import TradingEnv
from vn_stock_rl.evaluation.metadata import _merge_env_overrides


def _make_price_df(length: int = 12) -> pd.DataFrame:
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


def test_trading_env_merges_news_features_into_base_dataframe(tmp_path):
    data_path = tmp_path / "gia_lich_su_ACB_1D.parquet"
    news_dir = tmp_path / "news_predictions"
    news_dir.mkdir()

    price_df = _make_price_df()
    price_df.to_parquet(data_path, index=False)

    news_columns = ["news_article_count_1d", "news_sentiment_keyword_score_mean"]
    news_df = pd.DataFrame(
        {
            "ticker": ["ACB", "ACB", "ACB"],
            "date": ["2024-01-01", "2024-01-03", "2024-01-06"],
            "news_article_count_1d": [2.0, 5.0, 1.0],
            "news_sentiment_keyword_score_mean": [0.5, -1.0, 3.0],
        }
    )
    news_df.to_parquet(news_dir / "ACB_news_features.parquet", index=False)

    env = TradingEnv(
        data_path=str(data_path),
        mode="train",
        lookback_window=3,
        train_episode_sampling_enabled=False,
        news_feature_columns=news_columns,
        news_prediction_dir=str(news_dir),
    )

    expected = (
        price_df.assign(date=pd.to_datetime(price_df["time"]).dt.strftime("%Y-%m-%d"))
        .merge(news_df[["date", *news_columns]], on="date", how="left")
        .fillna(0.0)[news_columns]
        .to_numpy(dtype=np.float64)
    )

    assert env.news_feature_names == news_columns
    assert env.input_features["news_features"]["columns"] == news_columns
    assert env.input_features["news_features"]["prediction_dir"] == str(news_dir)
    np.testing.assert_allclose(env._news, expected)

    obs, _ = env.reset()
    assert obs.shape == env.observation_space.shape

    env.close()


def test_trading_env_merges_signal_features_into_base_dataframe(tmp_path):
    data_path = tmp_path / "gia_lich_su_ACB_1D.parquet"
    signal_dir = tmp_path / "signal_predictions"
    signal_dir.mkdir()

    price_df = _make_price_df()
    price_df.to_parquet(data_path, index=False)

    signal_columns = ["signal_prob_buyhold", "smoothed_signal_prob"]
    signal_df = pd.DataFrame(
        {
            "ticker": ["ACB", "ACB", "ACB"],
            "date": ["2024-01-01", "2024-01-03", "2024-01-06"],
            "signal_prob_buyhold": [0.9, 0.2, 0.8],
            "smoothed_signal_prob": [0.8, 0.4, 0.6],
        }
    )
    signal_df.to_parquet(signal_dir / "ACB_signal_predictions.parquet", index=False)

    env = TradingEnv(
        data_path=str(data_path),
        mode="train",
        lookback_window=3,
        train_episode_sampling_enabled=False,
        signal_feature_columns=signal_columns,
        signal_prediction_dir=str(signal_dir),
    )

    expected = (
        price_df.assign(date=pd.to_datetime(price_df["time"]).dt.strftime("%Y-%m-%d"))
        .merge(signal_df[["date", *signal_columns]], on="date", how="left")
    )
    expected["signal_prob_buyhold"] = expected["signal_prob_buyhold"].fillna(0.5)
    expected["smoothed_signal_prob"] = expected["smoothed_signal_prob"].fillna(0.5)
    expected = expected[signal_columns].to_numpy(dtype=np.float64)

    assert env.signal_feature_names == signal_columns
    assert env.input_features["signal_features"]["columns"] == signal_columns
    assert env.input_features["signal_features"]["prediction_dir"] == str(signal_dir)
    np.testing.assert_allclose(env._signal, expected)

    obs, _ = env.reset()
    assert obs.shape == env.observation_space.shape

    env.close()


def test_merge_env_overrides_reads_and_overrides_news_feature_metadata():
    meta = {
        "environment_config": {
            "input_features": {
                "news_features": {
                    "columns": ["news_article_count_1d", "news_article_count_3d"],
                    "prediction_dir": "C:/tmp/news_predictions",
                }
            }
        }
    }

    env_kwargs = _merge_env_overrides(
        meta=meta,
        explicit_env_overrides={
            "news_feature_columns": ["news_sentiment_keyword_score_mean"],
            "news_prediction_dir": "D:/custom_news",
        },
        forced_policy=None,
    )

    assert env_kwargs["news_feature_columns"] == ["news_sentiment_keyword_score_mean"]
    assert env_kwargs["news_prediction_dir"] == "D:/custom_news"


def test_merge_env_overrides_reads_and_overrides_signal_feature_metadata():
    meta = {
        "environment_config": {
            "input_features": {
                "signal_features": {
                    "columns": ["signal_prob_buyhold", "smoothed_signal_prob"],
                    "prediction_dir": "C:/tmp/signal_predictions",
                }
            }
        }
    }

    env_kwargs = _merge_env_overrides(
        meta=meta,
        explicit_env_overrides={
            "signal_feature_columns": ["signal_prob_buyhold"],
            "signal_prediction_dir": "D:/custom_signal",
        },
        forced_policy=None,
    )

    assert env_kwargs["signal_feature_columns"] == ["signal_prob_buyhold"]
    assert env_kwargs["signal_prediction_dir"] == "D:/custom_signal"


def test_signal_feature_config_defaults_to_auto_prediction_branch():
    columns, prediction_dir = TradingEnv._resolve_signal_feature_config(["signal_prob_buyhold"], None)

    assert columns == ["signal_prob_buyhold"]
    assert prediction_dir == str(default_signal_prediction_dir())
