from __future__ import annotations

from src.repo_paths import ARTIFACTS_ROOT, LAB_ROOT, artifact_path, lab_relative_path


def test_artifact_path_is_anchored_to_lab_root(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    assert artifact_path("run_summaries/latest_sample.json") == ARTIFACTS_ROOT / "run_summaries/latest_sample.json"
    assert artifact_path("portfolio_baselines") == LAB_ROOT / "artifacts/portfolio_baselines"


def test_lab_relative_path_relativizes_lab_absolute_paths() -> None:
    assert lab_relative_path(ARTIFACTS_ROOT / "portfolio_baselines/sample.parquet") == (
        "artifacts/portfolio_baselines/sample.parquet"
    )
    assert lab_relative_path("/tmp/external.parquet") == "/tmp/external.parquet"
