import json
import tempfile
from pathlib import Path

import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig
from research_pipelines.signal_labelling.auto_label.auto_label_heuristic import generate_auto_labels
from research_pipelines.supervised_label.core.rebuild_bar_labels import rebuild_bar_labels_dataframe
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
        chunk_length_min=10,
        chunk_length_max=20,
        default_chunk_length=20,
        min_bars_required=20,
        **overrides,
    )
    config.ensure_directories()
    return config


def _write_market_parquet(config: SupervisedLabelConfig, ticker: str, close_values) -> None:
    dates = pd.date_range("2020-01-01", periods=len(close_values), freq="D")
    frame = pd.DataFrame(
        {
            "time": dates,
            "open": close_values,
            "high": [value + 1.0 for value in close_values],
            "low": [value - 1.0 for value in close_values],
            "close": close_values,
            "volume": [1000.0 + idx for idx in range(len(close_values))],
        }
    )
    path = config.raw_data_dir / f"gia_lich_su_{ticker}_{config.timeframe}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def test_generate_auto_labels_creates_valid_range_records_and_bar_labels():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        aaa_close = [
            100.0,
            100.0,
            100.0,
            100.0,
            101.0,
            103.0,
            106.0,
            110.0,
            114.0,
            118.0,
            121.0,
            123.0,
            124.0,
            124.0,
            124.0,
            124.0,
            123.0,
            122.0,
            121.0,
            120.0,
            120.0,
            120.0,
            120.0,
            120.0,
            120.0,
        ]
        bbb_close = [50.0] * 25
        _write_market_parquet(config, "AAA", aaa_close)
        _write_market_parquet(config, "BBB", bbb_close)
        save_split_files({"train": ["AAA"], "val": ["BBB"], "test": []}, config=config)

        summary = generate_auto_labels(
            config=config,
            split_name="train",
            chunk_length=12,
            stride=12,
            horizon=4,
            min_forward_return=0.08,
            max_forward_drawdown=-0.03,
            min_range_bars=2,
        )

        assert summary.labeled_chunks >= 1
        assert summary.eligible_tickers == 1
        lines = [line for line in config.labels_jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == summary.labeled_chunks
        first_record = json.loads(lines[0])
        assert first_record["ticker"] == "AAA"
        assert first_record["selected_ranges"]
        rebuilt, invalid_records = rebuild_bar_labels_dataframe(config=config)
        assert not invalid_records
        assert set(rebuilt["ticker"].unique()) == {"AAA"}
        assert set(rebuilt["label"].unique()) == {0, 1}


def test_generate_auto_labels_skips_existing_chunk_ids_by_default():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        close_values = [
            100.0,
            100.0,
            100.0,
            101.0,
            103.0,
            106.0,
            109.0,
            112.0,
            114.0,
            115.0,
            116.0,
            116.0,
            116.0,
            116.0,
            116.0,
            116.0,
            115.0,
            115.0,
            115.0,
            115.0,
        ]
        _write_market_parquet(config, "AAA", close_values)
        save_split_files({"train": ["AAA"], "val": [], "test": []}, config=config)

        first_summary = generate_auto_labels(
            config=config,
            split_name="train",
            chunk_length=10,
            stride=10,
            horizon=3,
            min_forward_return=0.05,
            max_forward_drawdown=-0.02,
            min_range_bars=2,
        )
        second_summary = generate_auto_labels(
            config=config,
            split_name="train",
            chunk_length=10,
            stride=10,
            horizon=3,
            min_forward_return=0.05,
            max_forward_drawdown=-0.02,
            min_range_bars=2,
        )

        assert first_summary.labeled_chunks >= 1
        assert second_summary.labeled_chunks == 0
        assert second_summary.skipped_existing_chunks >= 1
