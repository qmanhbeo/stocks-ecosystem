import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig
from research_pipelines.supervised_label.core.chunk_sampler import ChunkSampler
from research_pipelines.supervised_label.split_utils import save_split_files


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
        min_bars_required=90,
        chunk_length_min=64,
        chunk_length_max=96,
    )
    config.ensure_directories()
    return config


def _write_market_parquet(config: SupervisedLabelConfig, ticker: str) -> None:
    dates = pd.date_range("2021-01-01", periods=120, freq="D")
    values = np.arange(len(dates), dtype=float)
    df = pd.DataFrame(
        {
            "time": dates,
            "open": 30.0 + values,
            "high": 31.0 + values,
            "low": 29.0 + values,
            "close": 30.5 + values,
            "volume": 1000.0 + values,
        }
    )
    path = config.raw_data_dir / f"gia_lich_su_{ticker}_{config.timeframe}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_labeling_sampler_never_draws_from_val_or_test_tickers():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = _build_config(root)
        for ticker in ("AAA", "BBB", "CCC"):
            _write_market_parquet(config, ticker)
        save_split_files({"train": ["AAA"], "val": ["BBB"], "test": ["CCC"]}, config=config)

        sampler = ChunkSampler(config=config, split_name="train", seed=99)
        sampled_tickers = {sampler.sample_chunk().ticker for _ in range(10)}

        assert sampled_tickers == {"AAA"}
