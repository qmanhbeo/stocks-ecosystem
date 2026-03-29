"""Generate per-bar signal probabilities for RL feature merges."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research_pipelines.supervised_label.config import get_default_config
from research_pipelines.supervised_label.io_utils import load_ticker_dataframe, make_relative_to_repo
from research_pipelines.supervised_label.split_utils import create_or_load_splits
from research_pipelines.supervised_label.variants import (
    LABEL_VARIANT_CHOICES,
    iter_label_variants,
    resolve_label_variant_paths,
)

from research_pipelines.supervised_label.core.feature_builder import build_feature_frame
from research_pipelines.supervised_label.core.label_storage import update_manifest


def _prediction_output_filename(ticker: str) -> str:
    return f"{str(ticker).upper()}_signal_predictions.parquet"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate per-bar signal probabilities from a trained model.")
    parser.add_argument("--model-path", type=Path, default=None, help="Optional model path override.")
    parser.add_argument("--metadata-path", type=Path, default=None, help="Optional metadata path override.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Optional prediction directory override.")
    parser.add_argument(
        "--label-variant",
        choices=LABEL_VARIANT_CHOICES,
        default="both",
        help="Which label variant to generate. Defaults to both manual and auto.",
    )
    return parser


def _safe_logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-6, 1.0 - 1e-6)
    return np.log(clipped / (1.0 - clipped))


def main() -> None:
    try:
        import joblib
    except ImportError as exc:
        raise ImportError("joblib is required for prediction generation. Install requirements.txt first.") from exc

    parser = build_arg_parser()
    args = parser.parse_args()
    config = get_default_config()
    if args.label_variant == "both" and (args.model_path or args.metadata_path or args.output_dir):
        parser.error(
            "--model-path, --metadata-path, and --output-dir can only be used with a single --label-variant"
        )

    split_map = create_or_load_splits(config=config, overwrite=False)
    tickers = sorted({ticker for values in split_map.values() for ticker in values})

    for variant in iter_label_variants(args.label_variant):
        variant_paths = resolve_label_variant_paths(config, variant)
        variant_paths.ensure_directories()
        model_path = Path(args.model_path) if args.model_path else variant_paths.model_path
        metadata_path = Path(args.metadata_path) if args.metadata_path else variant_paths.metadata_path
        output_dir = Path(args.output_dir) if args.output_dir else variant_paths.predictions_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        existing_prediction_files = {
            path.name: path
            for path in output_dir.glob("*_signal_predictions.parquet")
            if path.is_file()
        }
        if args.label_variant == "both" and (not model_path.exists() or not metadata_path.exists()):
            print(f"[{variant}] skipped_missing_model_inputs model={model_path} metadata={metadata_path}")
            continue

        model = joblib.load(model_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        feature_columns = list(metadata.get("feature_columns", []))
        written_filenames: set[str] = set()

        for ticker in tickers:
            raw_df = load_ticker_dataframe(ticker=ticker, config=config, timeframe=config.timeframe)
            feature_frame = build_feature_frame(raw_df, lookback_window=config.lookback_window)
            usable = feature_frame.loc[feature_frame["history_ready"] == 1].copy()
            usable = usable.dropna(subset=feature_columns).reset_index(drop=True)
            if usable.empty:
                continue
            probabilities = model.predict_proba(usable[feature_columns].astype(float))[:, 1]
            predictions = pd.DataFrame(
                {
                    "ticker": ticker,
                    "date": usable["date"],
                    config.prediction_column: probabilities,
                    config.prediction_label_column: (probabilities >= 0.5).astype(int),
                    "signal_logit": _safe_logit(probabilities),
                    config.smoothed_prediction_column: pd.Series(probabilities).rolling(5, min_periods=1).mean().values,
                }
            )
            if predictions["date"].duplicated().any():
                raise ValueError(f"Duplicate prediction dates generated for {ticker}")
            filename = _prediction_output_filename(ticker)
            written_filenames.add(filename)
            predictions.to_parquet(output_dir / filename, index=False)

        for filename, path in sorted(existing_prediction_files.items()):
            if filename in written_filenames:
                continue
            path.unlink()

        output_ref = make_relative_to_repo(output_dir, config=config)
        update_manifest(
            config=config,
            latest_prediction_export=output_ref,
            **{f"latest_prediction_export_{variant}": output_ref},
        )
        print(f"[{variant}] prediction_dir={output_dir}")


if __name__ == "__main__":
    main()
