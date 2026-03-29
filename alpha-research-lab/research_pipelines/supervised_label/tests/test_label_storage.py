import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig
from research_pipelines.supervised_label.core.label_storage import append_label_record, build_label_record, create_session_record
from research_pipelines.supervised_label.core.validation import LabelValidationError
from research_pipelines.supervised_label.schemas import ChunkSample


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
        min_bars_required=64,
    )
    config.ensure_directories()
    return config


def _write_market_parquet(config: SupervisedLabelConfig, ticker: str, days: int) -> pd.DataFrame:
    dates = pd.date_range("2021-01-01", periods=days, freq="D")
    values = np.arange(days, dtype=float)
    df = pd.DataFrame(
        {
            "time": dates,
            "open": 50.0 + values,
            "high": 51.0 + values,
            "low": 49.0 + values,
            "close": 50.5 + values,
            "volume": 1000.0 + values,
        }
    )
    path = config.raw_data_dir / f"gia_lich_su_{ticker}_{config.timeframe}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def test_label_storage_writes_jsonl_and_supports_multiple_ranges():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        raw_df = _write_market_parquet(config, "HPG", 120)
        chunk_df = raw_df.iloc[10:81].copy().reset_index(drop=True)
        session = create_session_record(config=config)
        chunk = ChunkSample(
            ticker="HPG",
            chunk_id="HPG_2021-01-11_2021-03-22_len71",
            chunk_start="2021-01-11",
            chunk_end="2021-03-22",
            source_file=str((config.raw_data_dir / "gia_lich_su_HPG_1D.parquet").relative_to(config.repo_root)),
            chunk_length=len(chunk_df),
            dataframe=chunk_df,
        )

        record = build_label_record(
            chunk_sample=chunk,
            session_id=session.session_id,
            selected_ranges=[
                {"start_ts": "2021-01-20", "end_ts": "2021-01-25", "label": 1},
                {"start_ts": "2021-02-10", "end_ts": "2021-02-14", "label": 1},
            ],
            confidence="medium",
            notes="trend continuation",
            ticker_split="train",
            config=config,
        )
        saved = append_label_record(record, config=config)

        assert saved["ticker"] == "HPG"
        assert saved["ticker_split"] == "train"
        assert len(saved["selected_ranges"]) == 2
        assert (config.sessions_dir / f"{session.session_id}.json").exists()
        lines = [line for line in config.labels_jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 1
        persisted = json.loads(lines[0])
        assert persisted["label_id"].startswith("lbl_")
        assert persisted["notes"] == "trend continuation"

        second_record = build_label_record(
            chunk_sample=chunk,
            session_id=session.session_id,
            selected_ranges=[{"start_ts": "2021-02-20", "end_ts": "2021-02-24", "label": 1}],
            confidence="high",
            notes="second pass",
            config=config,
        )
        append_label_record(second_record, config=config)
        lines = [line for line in config.labels_jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 2


def test_label_storage_rejects_malformed_record():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        raw_df = _write_market_parquet(config, "FPT", 100)
        chunk_df = raw_df.iloc[5:70].copy().reset_index(drop=True)
        session = create_session_record(config=config)
        chunk = ChunkSample(
            ticker="FPT",
            chunk_id="FPT_2021-01-06_2021-03-11_len65",
            chunk_start="2021-01-06",
            chunk_end="2021-03-11",
            source_file=str((config.raw_data_dir / "gia_lich_su_FPT_1D.parquet").relative_to(config.repo_root)),
            chunk_length=len(chunk_df),
            dataframe=chunk_df,
        )
        record = build_label_record(
            chunk_sample=chunk,
            session_id=session.session_id,
            selected_ranges=[{"start_ts": "2021-01-20", "end_ts": "2021-01-25", "label": 1}],
            config=config,
        ).to_dict()
        record["selected_ranges"] = []

        try:
            append_label_record(record, config=config)
        except LabelValidationError:
            pass
        else:
            raise AssertionError("Expected malformed label record to be rejected")


def test_label_storage_rejects_multiple_ranges_when_disabled():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        config.allow_multiple_ranges = False
        raw_df = _write_market_parquet(config, "VCB", 100)
        chunk_df = raw_df.iloc[5:70].copy().reset_index(drop=True)
        session = create_session_record(config=config)
        chunk = ChunkSample(
            ticker="VCB",
            chunk_id="VCB_2021-01-06_2021-03-11_len65",
            chunk_start="2021-01-06",
            chunk_end="2021-03-11",
            source_file=str((config.raw_data_dir / "gia_lich_su_VCB_1D.parquet").relative_to(config.repo_root)),
            chunk_length=len(chunk_df),
            dataframe=chunk_df,
        )
        record = build_label_record(
            chunk_sample=chunk,
            session_id=session.session_id,
            selected_ranges=[
                {"start_ts": "2021-01-20", "end_ts": "2021-01-25", "label": 1},
                {"start_ts": "2021-02-01", "end_ts": "2021-02-05", "label": 1},
            ],
            ticker_split="train",
            config=config,
        )

        try:
            append_label_record(record, config=config)
        except LabelValidationError:
            pass
        else:
            raise AssertionError("Expected multiple selected ranges to be rejected when disabled")


def test_create_session_record_rejects_duplicate_explicit_session_id():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)

        create_session_record(config=config, session_id="session_fixed")

        try:
            create_session_record(config=config, session_id="session_fixed")
        except FileExistsError:
            pass
        else:
            raise AssertionError("Expected duplicate explicit session_id to be rejected")
