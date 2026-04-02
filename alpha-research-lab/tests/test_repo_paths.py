from __future__ import annotations

from src.repo_paths import ARTIFACTS_ROOT, DATA_ROOT, LAB_ROOT, WORKSPACE_ROOT, artifact_path, data_path, lab_relative_path, resolve_data_path, workspace_path


def test_artifact_path_is_anchored_to_lab_root(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    assert artifact_path("run_summaries/latest_sample.json") == ARTIFACTS_ROOT / "run_summaries/latest_sample.json"
    assert artifact_path("portfolio_baselines") == LAB_ROOT / "artifacts/portfolio_baselines"


def test_lab_relative_path_relativizes_lab_absolute_paths() -> None:
    assert lab_relative_path(ARTIFACTS_ROOT / "portfolio_baselines/sample.parquet") == (
        "artifacts/portfolio_baselines/sample.parquet"
    )
    assert lab_relative_path("/tmp/external.parquet") == "/tmp/external.parquet"


def test_workspace_and_data_paths_are_anchored_to_workspace_root(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    assert workspace_path("docs/execution_reality.md") == WORKSPACE_ROOT / "docs/execution_reality.md"
    assert data_path("stock/gia_lich_su_FPT_1D.parquet") == DATA_ROOT / "stock/gia_lich_su_FPT_1D.parquet"
    assert data_path("data/features/xs_rl_signal_matrix.parquet") == DATA_ROOT / "features/xs_rl_signal_matrix.parquet"
    assert resolve_data_path("data/news/cafef/raw/2026-04-01.jsonl") == DATA_ROOT / "news/cafef/raw/2026-04-01.jsonl"
