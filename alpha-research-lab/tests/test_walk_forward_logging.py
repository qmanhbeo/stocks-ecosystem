from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import ensemble_wf
import walk_forward


class _DummyModel:
    def fit(self, X, y, **_kwargs):
        self._n_rows = len(X)
        return self

    def predict(self, X):
        return np.ones(len(X), dtype=float) * 0.01

    def predict_proba(self, X):
        proba = np.full(len(X), 0.6, dtype=float)
        return np.column_stack([1.0 - proba, proba])


def _make_year_split_df() -> pd.DataFrame:
    frames = []
    for year, count in ((2018, 190), (2019, 10), (2020, 25)):
        dates = pd.date_range(f"{year}-01-01", periods=count, freq="D")
        idx = np.arange(count, dtype=float)
        frames.append(
            pd.DataFrame(
                {
                    "time": dates,
                    "feature": idx,
                    "future_return_5d": np.where((idx % 2) == 0, 0.01, -0.01),
                    "future_rel_dir_5d": (idx % 2 == 0).astype(int),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _write_config(path: Path, target_col: str) -> Path:
    config = {
        "experiment_name": "skip_logging_regression",
        "data": {"target_col": target_col},
        "model": {"type": "linear_regression", "params": {}},
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_walk_forward_prints_skip_diagnostics(monkeypatch, tmp_path: Path, capsys) -> None:
    df = _make_year_split_df()
    config_path = _write_config(tmp_path / "walk_forward_config.json", "future_return_5d")

    monkeypatch.setattr(walk_forward, "load_data", lambda *_args, **_kwargs: df.copy())
    monkeypatch.setattr(walk_forward, "generate_features", lambda in_df, _config: in_df.copy())
    monkeypatch.setattr(walk_forward, "get_feature_columns", lambda *_args, **_kwargs: ["feature"])
    monkeypatch.setattr(walk_forward, "get_model", lambda _config: _DummyModel())
    monkeypatch.setattr(
        walk_forward,
        "evaluate_model",
        lambda _y_true, _preds: {
            "edge_over_naive": 0.1,
            "dir_pvalue_vs_naive": 0.04,
            "direction_accuracy": 0.6,
            "naive_dir_acc": 0.5,
            "mae": 0.01,
        },
    )
    monkeypatch.setattr(walk_forward, "write_run_summary", lambda **_kwargs: str(tmp_path / "summary.json"))
    monkeypatch.chdir(tmp_path)

    walk_forward.run_walk_forward(str(config_path), min_train_years=1)

    captured = capsys.readouterr().out
    assert "[SKIP] 2019: train=190, test=10" in captured


def test_ensemble_single_stock_prints_skip_diagnostics(monkeypatch, tmp_path: Path, capsys) -> None:
    df = _make_year_split_df()
    config_path = _write_config(tmp_path / "ensemble_config.json", "future_rel_dir_5d")
    out_csv = tmp_path / "single_stock_proba.csv"

    monkeypatch.setattr(ensemble_wf, "load_data", lambda *_args, **_kwargs: df.copy())
    monkeypatch.setattr(ensemble_wf, "generate_features", lambda in_df, _config: in_df.copy())
    monkeypatch.setattr(ensemble_wf, "get_feature_columns", lambda *_args, **_kwargs: ["feature"])
    monkeypatch.setattr(ensemble_wf, "get_model", lambda _config: _DummyModel())

    proba_df = ensemble_wf.save_single_stock_proba(
        str(config_path),
        str(out_csv),
        min_train_years=1,
    )

    captured = capsys.readouterr().out
    assert "[SKIP] 2019: train=190, test=10" in captured
    assert not proba_df.empty
    assert out_csv.exists()
