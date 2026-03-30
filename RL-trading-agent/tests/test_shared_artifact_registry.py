from __future__ import annotations

from pathlib import Path

from shared_recommendation.artifacts import (
    default_help_assets_dir as shared_help_dir,
    default_lab_signal_matrix_path as shared_lab_matrix_path,
    default_news_prediction_dir as shared_news_dir,
    default_signal_prediction_dir as shared_signal_dir,
    default_stock_data_dir as shared_stock_dir,
)
from vn_stock_rl import external_features


def test_rl_external_feature_defaults_delegate_to_shared_registry():
    assert external_features.shared_data_root() == Path("/home/manh/stocks/data")
    assert external_features.default_stock_data_dir() == shared_stock_dir()
    assert external_features.default_help_assets_dir() == shared_help_dir()
    assert external_features.default_news_prediction_dir() == shared_news_dir()
    assert external_features.default_signal_prediction_dir() == shared_signal_dir()
    assert external_features.default_lab_signal_matrix_path() == shared_lab_matrix_path()
