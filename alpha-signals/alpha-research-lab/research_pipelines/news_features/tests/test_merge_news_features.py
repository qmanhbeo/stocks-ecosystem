import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig
from research_pipelines.news_features.core.merge_news_features import merge_news_features


def _build_config(root) -> NewsFeaturesConfig:
    package_root = root / "sub_pipelines" / "news_features"
    artifacts_dir = package_root / "artifacts"
    config = NewsFeaturesConfig(
        repo_root=root,
        package_root=package_root,
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        normalized_dir=artifacts_dir / "normalized",
        tagged_dir=artifacts_dir / "tagged",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()
    return config


def test_merge_news_features_aligns_on_date_and_fills_missing(tmp_path):
    config = _build_config(tmp_path)
    base_df = pd.DataFrame({"time": pd.date_range("2026-03-10", periods=3, freq="D"), "close": [1.0, 2.0, 3.0]})
    features = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA"],
            "date": ["2026-03-10", "2026-03-12"],
            "news_article_count_1d": [2.0, 1.0],
            "news_embed_00": [0.25, 0.75],
        }
    )
    features.to_parquet(config.per_ticker_feature_path("AAA"), index=False)

    merged = merge_news_features(base_df, "AAA", include_columns=["news_article_count_1d", "news_embed_00"], config=config)
    assert merged["news_article_count_1d"].tolist() == [2.0, 0.0, 1.0]
    assert merged["news_embed_00"].tolist() == [0.25, 0.0, 0.75]


def test_merge_news_features_rejects_duplicate_dates(tmp_path):
    config = _build_config(tmp_path)
    base_df = pd.DataFrame({"date": ["2026-03-10", "2026-03-11"]})
    features = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA"],
            "date": ["2026-03-10", "2026-03-10"],
            "news_article_count_1d": [1.0, 2.0],
        }
    )
    features.to_parquet(config.per_ticker_feature_path("AAA"), index=False)

    try:
        merge_news_features(base_df, "AAA", include_columns=["news_article_count_1d"], config=config)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected duplicate feature dates to raise an error")
