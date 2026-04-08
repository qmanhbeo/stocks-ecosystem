from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import run_summary
from src.repo_paths import DATA_ROOT, artifact_path


def test_write_run_summary_serializes_numpy_and_timestamp_types(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_summary, "RUN_SUMMARY_DIR", tmp_path / "artifacts" / "run_summaries")

    out = run_summary.write_run_summary(
        ts="20260330_000000",
        mode="sample",
        name="sample_name",
        summary={
            "vector": np.asarray([1, 2, 3]),
            "score": np.float64(0.25),
            "ts": pd.Timestamp("2026-03-30"),
            "missing": np.nan,
        },
        artifacts={
            "path": Path("data/foo.parquet"),
            "repo_path": artifact_path("portfolio_baselines/sample.parquet"),
        },
        metadata={"flags": np.asarray([True, False])},
    )

    payload = json.loads(Path(out).read_text(encoding="utf-8"))
    assert payload["summary"]["vector"] == [1, 2, 3]
    assert payload["summary"]["score"] == 0.25
    assert payload["summary"]["ts"] == "2026-03-30T00:00:00"
    assert payload["summary"]["missing"] is None
    assert payload["artifacts"]["path"] == "data/foo.parquet"
    assert payload["artifacts"]["repo_path"] == "artifacts/portfolio_baselines/sample.parquet"
    assert payload["metadata"]["flags"] == [True, False]


def test_write_run_summary_relativizes_workspace_data_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_summary, "RUN_SUMMARY_DIR", tmp_path / "artifacts" / "run_summaries")

    out = run_summary.write_run_summary(
        ts="20260330_000001",
        mode="sample",
        name="sample_name",
        summary={},
        artifacts={
            "matrix": DATA_ROOT / "features" / "xs_rl_signal_matrix.parquet",
        },
    )

    payload = json.loads(Path(out).read_text(encoding="utf-8"))
    assert payload["artifacts"]["matrix"] == "data/features/xs_rl_signal_matrix.parquet"
