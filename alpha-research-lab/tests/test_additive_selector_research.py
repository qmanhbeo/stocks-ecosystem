from __future__ import annotations

from pathlib import Path

import pandas as pd

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
    run_summaries = tmp_path / "artifacts" / "run_summaries"
    run_summaries.mkdir(parents=True)
    summary_path = run_summaries / "latest_sample.json"
    summary_path.write_text('{"artifacts":{"results":"artifacts/portfolio_baselines/sample_results.parquet"}}\n', encoding="utf-8")
    resolved = resolve_summary_artifact(summary_path, "results")
    assert resolved == (tmp_path / "artifacts" / "portfolio_baselines" / "sample_results.parquet").resolve()


def test_summary_payload_helpers_detect_skip(tmp_path: Path) -> None:
    run_summaries = tmp_path / "artifacts" / "run_summaries"
    run_summaries.mkdir(parents=True)
    summary_path = run_summaries / "latest_sample.json"
    summary_path.write_text('{"summary":{"skipped":true,"reason":"x"},"artifacts":{}}\n', encoding="utf-8")
    payload = load_summary_payload(summary_path)
    assert payload["summary"]["reason"] == "x"
    assert summary_is_skipped(summary_path) is True
