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
from vn_stock_rl.evaluation.metadata import _resolve_helper_inputs_from_meta


def test_rl_external_feature_defaults_delegate_to_shared_registry():
    assert external_features.shared_data_root() == external_features.WORKSPACE_ROOT / "data"
    assert external_features.default_stock_data_dir() == shared_stock_dir()
    assert external_features.default_help_assets_dir() == shared_help_dir()
    assert external_features.default_news_prediction_dir() == shared_news_dir()
    assert external_features.default_signal_prediction_dir() == shared_signal_dir()
    assert external_features.default_lab_signal_matrix_path() == shared_lab_matrix_path()


def test_rl_external_feature_fallback_paths_point_at_workspace_children():
    assert external_features.WORKSPACE_ROOT == external_features.REPO_ROOT.parent
    assert external_features.SHARED_RECOMMENDATION_ROOT == external_features.WORKSPACE_ROOT / "shared-recommendation"
    assert external_features.SHARED_RECOMMENDATION_ROOT.exists()


def test_eval_metadata_rehydrates_helper_paths_for_absolute_defaults():
    meta = {
        "data_dir": "/meta/data",
        "market_data_dir": "/meta/market",
        "help_assets_dir": "/meta/help",
    }

    data_dir, help_tickers, market_data_dir, help_assets, help_assets_dir = _resolve_helper_inputs_from_meta(
        meta=meta,
        data_dir=str(external_features.default_stock_data_dir()),
        help_tickers=None,
        market_data_dir=str(external_features.default_market_data_dir()),
        help_assets=None,
        help_assets_dir=str(external_features.default_help_assets_dir()),
    )

    assert data_dir == "/meta/data"
    assert help_tickers is None
    assert market_data_dir == "/meta/market"
    assert help_assets is None
    assert help_assets_dir == "/meta/help"
