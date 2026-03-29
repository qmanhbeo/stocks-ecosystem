import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig
from research_pipelines.supervised_label.core.rebuild_bar_labels import rebuild_label_rows_for_record


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


def _write_market_parquet(config: SupervisedLabelConfig, ticker: str, days: int) -> pd.DataFrame:
    dates = pd.date_range("2021-04-01", periods=days, freq="D")
    values = np.arange(days, dtype=float)
    df = pd.DataFrame(
        {
            "time": dates,
            "open": 20.0 + values,
            "high": 21.0 + values,
            "low": 19.0 + values,
            "close": 20.5 + values,
            "volume": 500.0 + values,
        }
    )
    path = config.raw_data_dir / f"gia_lich_su_{ticker}_{config.timeframe}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def test_rebuild_bar_labels_maps_ranges_correctly():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        _write_market_parquet(config, "HPG", 20)

        record = {
            "label_id": "lbl_000001",
            "session_id": "session_2026-03-10_001",
            "ticker": "HPG",
            "ticker_split": "train",
            "timeframe": "1D",
            "chunk_id": "HPG_2021-04-03_2021-04-12_len10",
            "chunk_start": "2021-04-03",
            "chunk_end": "2021-04-12",
            "source_file": "data/stock/gia_lich_su_HPG_1D.parquet",
            "selected_ranges": [
                {"start_ts": "2021-04-04", "end_ts": "2021-04-05", "label": 1},
                {"start_ts": "2021-04-08", "end_ts": "2021-04-10", "label": 1},
            ],
            "default_label": 0,
            "confidence": "medium",
            "notes": "",
            "created_at": "2026-03-10T22:15:00Z",
        }
        rebuilt = rebuild_label_rows_for_record(record, config=config)
        label_map = dict(zip(rebuilt["date"], rebuilt["label"]))

        assert set(rebuilt["ticker_split"].tolist()) == {"train"}
        assert label_map["2021-04-03"] == 0
        assert label_map["2021-04-04"] == 1
        assert label_map["2021-04-05"] == 1
        assert label_map["2021-04-06"] == 0
        assert label_map["2021-04-08"] == 1
        assert label_map["2021-04-10"] == 1
        assert label_map["2021-04-12"] == 0


def test_rebuild_bar_labels_handles_overlapping_ranges():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        _write_market_parquet(config, "FPT", 15)

        record = {
            "label_id": "lbl_000002",
            "session_id": "session_2026-03-10_001",
            "ticker": "FPT",
            "timeframe": "1D",
            "chunk_id": "FPT_2021-04-02_2021-04-11_len10",
            "chunk_start": "2021-04-02",
            "chunk_end": "2021-04-11",
            "source_file": "data/stock/gia_lich_su_FPT_1D.parquet",
            "selected_ranges": [
                {"start_ts": "2021-04-04", "end_ts": "2021-04-07", "label": 1},
                {"start_ts": "2021-04-07", "end_ts": "2021-04-09", "label": 1},
            ],
            "default_label": 0,
            "confidence": "high",
            "notes": "",
            "created_at": "2026-03-10T22:15:00Z",
        }
        rebuilt = rebuild_label_rows_for_record(record, config=config)
        overlapping = rebuilt.loc[(rebuilt["date"] >= "2021-04-04") & (rebuilt["date"] <= "2021-04-09"), "label"]
        assert set(overlapping.tolist()) == {1}
        assert rebuilt.loc[rebuilt["date"] == "2021-04-03", "label"].iloc[0] == 0
