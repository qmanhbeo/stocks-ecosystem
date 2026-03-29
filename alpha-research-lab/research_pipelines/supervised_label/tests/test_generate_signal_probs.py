from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

import research_pipelines.supervised_label.models.generate_signal_probs as generate_signal_probs


class _DummyModel:
    def predict_proba(self, X):
        probs = np.full(len(X), 0.8, dtype=float)
        return np.column_stack([1.0 - probs, probs])


def test_generate_signal_probs_removes_stale_prediction_files(tmp_path, monkeypatch):
    output_dir = tmp_path / "predictions"
    output_dir.mkdir(parents=True)

    stale_path = output_dir / "BBB_signal_predictions.parquet"
    pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "signal_prob_buyhold": [0.2],
            "signal_pred_label": [0],
            "signal_logit": [0.0],
            "smoothed_signal_prob": [0.2],
        }
    ).to_parquet(stale_path, index=False)

    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps({"feature_columns": ["feat1"]}), encoding="utf-8")
    variant_paths = SimpleNamespace(
        model_path=tmp_path / "model.joblib",
        metadata_path=metadata_path,
        predictions_dir=output_dir,
        ensure_directories=lambda: output_dir.mkdir(parents=True, exist_ok=True),
    )

    config = SimpleNamespace(
        repo_root=tmp_path,
        timeframe="1D",
        lookback_window=1,
        prediction_column="signal_prob_buyhold",
        prediction_label_column="signal_pred_label",
        smoothed_prediction_column="smoothed_signal_prob",
    )

    monkeypatch.setattr(generate_signal_probs, "get_default_config", lambda: config)
    monkeypatch.setattr(generate_signal_probs, "create_or_load_splits", lambda config, overwrite=False: {"train": ["AAA"], "val": [], "test": []})
    monkeypatch.setattr(generate_signal_probs, "iter_label_variants", lambda label_variant: ["manual"])
    monkeypatch.setattr(generate_signal_probs, "resolve_label_variant_paths", lambda config, variant: variant_paths)
    monkeypatch.setattr(
        generate_signal_probs,
        "load_ticker_dataframe",
        lambda ticker, config, timeframe: pd.DataFrame({"time": pd.date_range("2024-01-01", periods=2), "feat1": [1.0, 2.0]}),
    )
    monkeypatch.setattr(
        generate_signal_probs,
        "build_feature_frame",
        lambda raw_df, lookback_window: pd.DataFrame(
            {"date": ["2024-01-01", "2024-01-02"], "history_ready": [1, 1], "feat1": [1.0, 2.0]}
        ),
    )
    monkeypatch.setattr(generate_signal_probs, "update_manifest", lambda **kwargs: None)

    import joblib

    monkeypatch.setattr(joblib, "load", lambda path: _DummyModel())
    monkeypatch.setattr(
        "sys.argv",
        [
            "generate_signal_probs.py",
            "--label-variant",
            "manual",
            "--output-dir",
            str(output_dir),
            "--model-path",
            str(tmp_path / "model.joblib"),
            "--metadata-path",
            str(metadata_path),
        ],
    )

    generate_signal_probs.main()

    assert (output_dir / "AAA_signal_predictions.parquet").exists()
    assert not stale_path.exists()
