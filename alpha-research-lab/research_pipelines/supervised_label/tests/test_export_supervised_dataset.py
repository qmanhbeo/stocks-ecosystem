import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig
from research_pipelines.supervised_label.core.export_supervised_dataset import export_supervised_dataset_dataframe
from research_pipelines.supervised_label.split_utils import save_split_files


def _build_config(root: Path, **overrides) -> SupervisedLabelConfig:
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
        lookback_window=20,
        **overrides,
    )
    config.ensure_directories()
    return config


def _write_market_parquet(config: SupervisedLabelConfig, ticker: str, days: int) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=days, freq="D")
    values = np.arange(days, dtype=float)
    df = pd.DataFrame(
        {
            "time": dates,
            "open": 100.0 + values,
            "high": 101.0 + values,
            "low": 99.0 + values,
            "close": 100.5 + values,
            "volume": 1000.0 + values,
        }
    )
    path = config.raw_data_dir / f"gia_lich_su_{ticker}_{config.timeframe}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def _write_bar_labels(config: SupervisedLabelConfig, ticker: str, dates, labels) -> None:
    rows = pd.DataFrame(
        {
            "ticker": ticker,
            "date": [pd.Timestamp(value).strftime("%Y-%m-%d") for value in dates],
            "chunk_id": [f"{ticker}_chunk_001"] * len(dates),
            "label": labels,
            "confidence": ["medium"] * len(dates),
            "confidence_weight": [0.75] * len(dates),
            "session_id": ["session_2026-03-10_001"] * len(dates),
        }
    )
    rows.to_parquet(config.datasets_dir / config.bar_labels_filename, index=False)


def test_export_supervised_dataset_has_required_columns_and_aligned_targets():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        raw_df = _write_market_parquet(config, "AAA", 90)
        labeled_dates = raw_df.iloc[40:45]["time"].tolist()
        _write_bar_labels(config, "AAA", labeled_dates, [0, 1, 1, 0, 1])
        save_split_files({"train": ["AAA"], "val": [], "test": []}, config=config)

        exported = export_supervised_dataset_dataframe(config=config)
        assert {"ticker", "date", "chunk_id", "label", "confidence", "confidence_weight", "ret_1"} <= set(exported.columns)
        assert exported["label"].tolist() == [0, 1, 1, 0, 1]
        assert exported["ticker_split"].tolist() == ["train"] * 5
        target_date = pd.Timestamp(labeled_dates[1]).strftime("%Y-%m-%d")
        idx = raw_df.index[raw_df["time"] == pd.Timestamp(target_date)][0]
        expected_ret_1 = (raw_df.iloc[idx]["close"] / raw_df.iloc[idx - 1]["close"]) - 1.0
        actual_ret_1 = exported.loc[exported["date"] == target_date, "ret_1"].iloc[0]
        assert abs(actual_ret_1 - expected_ret_1) < 1e-12


def test_export_supervised_dataset_does_not_leak_future_bars():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        raw_df = _write_market_parquet(config, "AAA", 90)
        labeled_dates = raw_df.iloc[50:53]["time"].tolist()
        _write_bar_labels(config, "AAA", labeled_dates, [1, 0, 1])
        save_split_files({"train": ["AAA"], "val": [], "test": []}, config=config)

        exported_before = export_supervised_dataset_dataframe(config=config)
        target_date = pd.Timestamp(labeled_dates[0]).strftime("%Y-%m-%d")
        before_row = exported_before.loc[exported_before["date"] == target_date].iloc[0]

        mutated = raw_df.copy()
        target_idx = mutated.index[mutated["time"] == pd.Timestamp(target_date)][0]
        mutated.loc[target_idx + 1 :, ["open", "high", "low", "close", "volume"]] = 9_999.0
        mutated.to_parquet(config.raw_data_dir / "gia_lich_su_AAA_1D.parquet", index=False)

        exported_after = export_supervised_dataset_dataframe(config=config)
        after_row = exported_after.loc[exported_after["date"] == target_date].iloc[0]

        for feature_name in ("ret_1", "ret_3", "momentum_3", "sma_ratio_3", "volatility_3"):
            assert abs(before_row[feature_name] - after_row[feature_name]) < 1e-12
