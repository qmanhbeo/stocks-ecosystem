from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = REPO_ROOT.parent
SHARED_RECOMMENDATION_ROOT = WORKSPACE_ROOT / "shared-recommendation"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SHARED_RECOMMENDATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_RECOMMENDATION_ROOT))

import pytest

from vn_stock_rl.config import DEFAULT_CONFIG, reset_runtime_defaults

TEST_TEMP_ROOT = REPO_ROOT / "tests" / ".tmp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(TEST_TEMP_ROOT)
os.environ["TEMP"] = str(TEST_TEMP_ROOT)
os.environ["TMP"] = str(TEST_TEMP_ROOT)
tempfile.tempdir = str(TEST_TEMP_ROOT)


class RepoTemporaryDirectory:
    """Repo-local replacement for tempfile.TemporaryDirectory during tests."""

    def __init__(self, suffix: str | None = None, prefix: str | None = None, dir: str | None = None, **_kwargs):
        base_dir = Path(dir) if dir is not None else TEST_TEMP_ROOT
        name = f"{prefix or 'tmp'}{uuid.uuid4().hex}{suffix or ''}"
        self._path = base_dir / name
        self._path.mkdir(parents=True, exist_ok=False)
        self.name = str(self._path)
        self._closed = False

    def __enter__(self) -> str:
        return self.name

    def cleanup(self) -> None:
        if self._closed:
            return
        shutil.rmtree(self.name, ignore_errors=True)
        self._closed = True

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.cleanup()
        return False


tempfile.TemporaryDirectory = RepoTemporaryDirectory


@pytest.fixture
def tmp_path():
    path = TEST_TEMP_ROOT / f"pytest-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _apply_test_default_config() -> None:
    DEFAULT_CONFIG["train_split"] = 0.7
    DEFAULT_CONFIG["val_split"] = 0.15
    DEFAULT_CONFIG["lookback_window"] = 90
    DEFAULT_CONFIG["start_episode_position"] = 0.0

    DEFAULT_CONFIG["train_episode_sampling"] = {
        "enabled": False,
        "mode": "fraction",
        "min_fraction": 0.2,
        "max_fraction": 0.6,
    }

    DEFAULT_CONFIG["reward_shaping"] = {
        "drawdown_penalty": {
            "enabled": False,
            "lambda": 0.05,
            "train_only": True,
        },
        "benchmark_relative": {
            "enabled": False,
            "benchmark": "self_buy_hold",
            "weight": 1.0,
        },
    }

    DEFAULT_CONFIG["input_features"] = {
        "source_mode": "return",
        "ohlcv": ["open", "high", "low", "close", "volume"],
        "ma_windows": [],
        "helpers_ma_windows": [],
        "returns_windows": [],
        "helpers_returns_windows": [],
        "calendar": [],
        "engineered_features": {
            "enabled": [],
            "window_policy": {
                "mode": "explicit",
                "explicit_windows": [5, 10, 20],
                "logspace_min": 5,
                "logspace_max": 20,
                "logspace_count": 3,
            },
            "horizons": {"medium_index": 1, "long_index": 2},
            "relative_strength": {
                "market_proxy_preference": ["VNINDEX", "VN30"],
                "include_long_horizon": True,
            },
        },
    }


@pytest.fixture(autouse=True)
def isolate_runtime_defaults():
    reset_runtime_defaults()
    _apply_test_default_config()
    yield
    reset_runtime_defaults()
    _apply_test_default_config()
