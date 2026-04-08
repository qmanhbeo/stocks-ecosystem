from __future__ import annotations

from pathlib import Path

import pandas as pd
import src.additive_selector_research as additive_selector_research

from src.additive_selector_research import (
    additive_candidate_deltas,
    additive_candidate_passes,
    blend_state_scoped_scores,
    load_summary_payload,
    resolve_summary_artifact,
    summary_is_skipped,
)


def test_blend_state_scoped_scores_only_changes_state_rows() -> None:
    base = pd.Series([0.2, 0.4, 0.6])
    atom = pd.Series([0.8, 0.2, 0.0])
    state = pd.Series([False, True, False])
    blended = blend_state_scoped_scores(base, atom, state, atom_weight=0.20)
    assert [round(value, 6) for value in blended.tolist()] == [0.2, 0.36, 0.6]


def test_additive_candidate_passes_uses_validation_and_confirmation_thresholds() -> None:
    baseline = pd.Series(
        {
            "validation_relative_total_return": 0.10,
            "validation_information_ratio_annualized": 0.50,
            "confirmation_relative_total_return": 0.06,
            "confirmation_information_ratio_annualized": 0.40,
        }
    )
    winner = pd.Series(
        {
            "validation_relative_total_return": 0.17,
            "validation_information_ratio_annualized": 0.51,
            "confirmation_relative_total_return": 0.03,
            "confirmation_information_ratio_annualized": 0.37,
        }
    )
    loser = pd.Series(
        {
            "validation_relative_total_return": 0.12,
            "validation_information_ratio_annualized": 0.52,
            "confirmation_relative_total_return": -0.02,
            "confirmation_information_ratio_annualized": 0.31,
        }
    )
    assert additive_candidate_passes(winner, baseline)
    assert not additive_candidate_passes(loser, baseline)
    deltas = additive_candidate_deltas(winner, baseline)
    assert round(deltas["validation_relative_delta"], 4) == 0.07


def test_resolve_summary_artifact_resolves_relative_to_artifacts_root(tmp_path: Path) -> None:
    lab_root = tmp_path / "workspace" / "alpha-research-lab"
    run_summaries = lab_root / "artifacts" / "run_summaries"
    run_summaries.mkdir(parents=True)
    summary_path = run_summaries / "latest_sample.json"
    summary_path.write_text('{"artifacts":{"results":"artifacts/portfolio_baselines/sample_results.parquet"}}\n', encoding="utf-8")
    resolved = resolve_summary_artifact(summary_path, "results")
    assert resolved == (lab_root / "artifacts" / "portfolio_baselines" / "sample_results.parquet").resolve()


def test_resolve_summary_artifact_resolves_workspace_data_relative_to_workspace_root(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    lab_root = workspace_root / "alpha-research-lab"
    run_summaries = lab_root / "artifacts" / "run_summaries"
    run_summaries.mkdir(parents=True)
    summary_path = run_summaries / "latest_sample.json"
    summary_path.write_text('{"artifacts":{"scores":"data/features/entry_alpha/entry_scores_daily.parquet"}}\n', encoding="utf-8")

    resolved = resolve_summary_artifact(summary_path, "scores")

    assert resolved == (workspace_root / "data" / "features" / "entry_alpha" / "entry_scores_daily.parquet").resolve()


def test_resolve_summary_artifact_rebases_legacy_workspace_absolute_paths(tmp_path: Path, monkeypatch) -> None:
    workspace_root = tmp_path / "workspace"
    lab_root = workspace_root / "alpha-research-lab"
    target_path = workspace_root / "data" / "features" / "entry_alpha" / "entry_scores_daily.parquet"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"time": pd.to_datetime(["2026-03-27"]), "ticker": ["AAA"]}).to_parquet(target_path, index=False)

    monkeypatch.setattr(additive_selector_research, "WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(additive_selector_research, "LAB_ROOT", lab_root)

    run_summaries = lab_root / "artifacts" / "run_summaries"
    run_summaries.mkdir(parents=True)
    summary_path = run_summaries / "latest_sample.json"
    summary_path.write_text(
        '{"artifacts":{"scores":"/home/manh/stocks/data/features/entry_alpha/entry_scores_daily.parquet"}}\n',
        encoding="utf-8",
    )

    resolved = resolve_summary_artifact(summary_path, "scores")

    assert resolved == target_path.resolve()


def test_summary_payload_helpers_detect_skip(tmp_path: Path) -> None:
    run_summaries = tmp_path / "artifacts" / "run_summaries"
    run_summaries.mkdir(parents=True)
    summary_path = run_summaries / "latest_sample.json"
    summary_path.write_text('{"summary":{"skipped":true,"reason":"x"},"artifacts":{}}\n', encoding="utf-8")
    payload = load_summary_payload(summary_path)
    assert payload["summary"]["reason"] == "x"
    assert summary_is_skipped(summary_path) is True
