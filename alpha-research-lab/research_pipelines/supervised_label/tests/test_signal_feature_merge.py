import tempfile
from pathlib import Path

import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig
from research_pipelines.supervised_label.core.merge_signal_features import merge_signal_features


def _build_config(root: Path) -> SupervisedLabelConfig:
    package_root = root / "sub_pipelines" / "supervised_label"
    artifacts_dir = package_root / "artifacts"
    config = SupervisedLabelConfig(
        repo_root=root,
        package_root=package_root,
        raw_data_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        splits_dir=artifacts_dir / "splits",
        sessions_dir=artifacts_dir / "sessions",
        labels_dir=artifacts_dir / "labels",
        exports_dir=artifacts_dir / "exports",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        labels_jsonl_path=artifacts_dir / "labels" / "range_labels.jsonl",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()
    return config


def test_signal_feature_merge_aligns_on_date_and_fills_missing():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        base_df = pd.DataFrame({"time": pd.date_range("2021-01-01", periods=3, freq="D"), "close": [1.0, 2.0, 3.0]})
        predictions = pd.DataFrame(
            {
                "ticker": ["AAA", "AAA"],
                "date": ["2021-01-01", "2021-01-03"],
                "signal_prob_buyhold": [0.9, 0.1],
                "signal_pred_label": [1, 0],
            }
        )
        predictions.to_parquet(config.predictions_dir / "AAA_signal_predictions.parquet", index=False)

        merged = merge_signal_features(base_df, "AAA", config=config)
        assert merged["signal_prob_buyhold"].tolist() == [0.9, 0.5, 0.1]
        assert merged["signal_pred_label"].tolist() == [1, 0, 0]


def test_signal_feature_merge_rejects_duplicate_prediction_dates():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        base_df = pd.DataFrame({"time": pd.date_range("2021-01-01", periods=2, freq="D"), "close": [1.0, 2.0]})
        predictions = pd.DataFrame(
            {
                "ticker": ["AAA", "AAA"],
                "date": ["2021-01-01", "2021-01-01"],
                "signal_prob_buyhold": [0.9, 0.1],
                "signal_pred_label": [1, 0],
            }
        )
        predictions.to_parquet(config.predictions_dir / "AAA_signal_predictions.parquet", index=False)

        try:
            merge_signal_features(base_df, "AAA", config=config)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected duplicate prediction dates to raise an error")
