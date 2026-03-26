import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig
from research_pipelines.supervised_label.core.chunk_sampler import ChunkSampler, build_chunk_id
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
        min_bars_required=100,
        chunk_length_min=64,
        chunk_length_max=128,
        **overrides,
    )
    config.ensure_directories()
    return config


def _write_market_parquet(config: SupervisedLabelConfig, ticker: str, days: int) -> pd.DataFrame:
    dates = pd.date_range("2021-01-01", periods=days, freq="D")
    base = np.arange(days, dtype=float)
    df = pd.DataFrame(
        {
            "time": dates,
            "open": 100.0 + base,
            "high": 101.0 + base,
            "low": 99.0 + base,
            "close": 100.5 + base,
            "volume": 1_000.0 + base,
        }
    )
    path = config.raw_data_dir / f"gia_lich_su_{ticker}_{config.timeframe}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def test_chunk_sampler_samples_only_valid_chunks_and_skips_short_histories():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        _write_market_parquet(config, "AAA", 150)
        _write_market_parquet(config, "BBB", 50)
        save_split_files({"train": ["AAA", "BBB"], "val": [], "test": []}, config=config)

        sampler = ChunkSampler(config=config, split_name="train", seed=42)
        sample = sampler.sample_chunk()

        assert sample.ticker == "AAA"
        assert config.chunk_length_min <= sample.chunk_length <= config.chunk_length_max
        assert len(sample.dataframe) == sample.chunk_length
        assert sample.chunk_id == build_chunk_id(sample.ticker, sample.chunk_start, sample.chunk_end, sample.chunk_length)


def test_chunk_sampler_chunk_id_is_stable_for_same_seed():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        _write_market_parquet(config, "AAA", 150)
        save_split_files({"train": ["AAA"], "val": [], "test": []}, config=config)

        sampler_a = ChunkSampler(config=config, split_name="train", seed=7)
        sampler_b = ChunkSampler(config=config, split_name="train", seed=7)

        sample_a = sampler_a.sample_chunk()
        sample_b = sampler_b.sample_chunk()

        assert sample_a.chunk_id == sample_b.chunk_id
        assert sample_a.chunk_start == sample_b.chunk_start
        assert sample_a.chunk_end == sample_b.chunk_end
