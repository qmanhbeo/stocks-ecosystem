"""Evaluate a trained supervised signal model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from research_pipelines.supervised_label.config import get_default_config
from research_pipelines.supervised_label.variants import (
    LABEL_VARIANT_CHOICES,
    iter_label_variants,
    resolve_label_variant_paths,
)

from .baselines import compute_metrics, label_distribution
from .dataset import SupervisedSignalDataset


def _save_optional_plots(output_dir: Path, split_name: str, y_true, y_pred, y_prob) -> None:
    try:
        import matplotlib
        from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix
    except Exception:
        return

    try:
        matplotlib.use("Agg")
    except Exception:
        return

    try:
        import matplotlib.pyplot as plt
    except Exception:
        return

    matrix = confusion_matrix(y_true, y_pred)
    figure, axis = plt.subplots(figsize=(4, 4))
    ConfusionMatrixDisplay(matrix).plot(ax=axis, colorbar=False)
    figure.tight_layout()
    figure.savefig(output_dir / f"confusion_matrix_{split_name}.png")
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(6, 4))
    axis.hist(y_prob, bins=20)
    axis.set_title(f"Probability histogram ({split_name})")
    axis.set_xlabel("signal_prob_buyhold")
    axis.set_ylabel("count")
    figure.tight_layout()
    figure.savefig(output_dir / f"probability_histogram_{split_name}.png")
    plt.close(figure)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate the supervised_label baseline signal model.")
    parser.add_argument("--dataset-path", type=Path, default=None, help="Optional supervised dataset parquet path.")
    parser.add_argument("--model-path", type=Path, default=None, help="Optional model path override.")
    parser.add_argument("--metadata-path", type=Path, default=None, help="Optional metadata path override.")
    parser.add_argument("--split", choices=["train", "val", "test"], default="val", help="Split to evaluate.")
    parser.add_argument(
        "--label-variant",
        choices=LABEL_VARIANT_CHOICES,
        default="both",
        help="Which label variant to evaluate. Defaults to both manual and auto.",
    )
    return parser


def main() -> None:
    try:
        import joblib
    except ImportError as exc:
        raise ImportError("joblib is required for model loading. Install requirements.txt first.") from exc

    parser = build_arg_parser()
    args = parser.parse_args()
    config = get_default_config()
    if args.label_variant == "both" and (args.dataset_path or args.model_path or args.metadata_path):
        parser.error(
            "--dataset-path, --model-path, and --metadata-path can only be used with a single --label-variant"
        )

    for variant in iter_label_variants(args.label_variant):
        variant_paths = resolve_label_variant_paths(config, variant)
        variant_paths.ensure_directories()

        model_path = Path(args.model_path) if args.model_path else variant_paths.model_path
        metadata_path = Path(args.metadata_path) if args.metadata_path else variant_paths.metadata_path
        dataset_path = Path(args.dataset_path) if args.dataset_path else variant_paths.supervised_dataset_path
        if args.label_variant == "both" and (
            not dataset_path.exists() or not model_path.exists() or not metadata_path.exists()
        ):
            print(
                f"[{variant}] skipped_missing_evaluation_inputs "
                f"dataset={dataset_path} model={model_path} metadata={metadata_path}"
            )
            continue
        model = joblib.load(model_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        dataset = SupervisedSignalDataset(dataset_path=dataset_path, config=config)
        split_data = dataset.get_split(
            args.split,
            split_strategy=str(metadata.get("split_strategy", "dataset")),
            feature_columns=list(metadata.get("feature_columns", [])),
            fallback_to_dataset=True,
        )

        y_prob = model.predict_proba(split_data.X)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        metrics = compute_metrics(split_data.y, y_pred, y_prob)
        result = {
            "label_variant": variant,
            "split": args.split,
            "metrics": metrics,
            "label_distribution": label_distribution(split_data.y),
        }

        output_dir = variant_paths.exports_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"signal_model_evaluation_{args.split}.json"
        csv_path = output_dir / f"signal_model_evaluation_{args.split}.csv"
        json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        pd.DataFrame([{"label_variant": variant, "split": args.split, **metrics}]).to_csv(csv_path, index=False)
        _save_optional_plots(output_dir, args.split, split_data.y, y_pred, y_prob)

        print(f"[{variant}] evaluation_json={json_path}")
        print(f"[{variant}] evaluation_csv={csv_path}")


if __name__ == "__main__":
    main()
