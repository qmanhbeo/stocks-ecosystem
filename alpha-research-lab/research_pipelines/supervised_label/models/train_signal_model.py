"""Train the baseline supervised signal model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from research_pipelines.supervised_label.config import get_default_config
from research_pipelines.supervised_label.io_utils import make_relative_to_repo
from research_pipelines.supervised_label.variants import (
    LABEL_VARIANT_CHOICES,
    iter_label_variants,
    resolve_label_variant_paths,
)
from research_pipelines.supervised_label.core.label_storage import update_manifest

from .baselines import build_logistic_regression_pipeline, compute_metrics, label_distribution
from .dataset import SupervisedSignalDataset


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train the supervised_label baseline signal model.")
    parser.add_argument("--dataset-path", type=Path, default=None, help="Optional supervised dataset parquet path.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Optional export directory override.")
    parser.add_argument(
        "--split-strategy",
        choices=["dataset", "ticker"],
        default="dataset",
        help="How to split the exported supervised dataset for training/evaluation.",
    )
    parser.add_argument(
        "--label-variant",
        choices=LABEL_VARIANT_CHOICES,
        default="both",
        help="Which label variant to train. Defaults to both manual and auto.",
    )
    return parser


def main() -> None:
    try:
        import joblib
    except ImportError as exc:
        raise ImportError("joblib is required for model export. Install requirements.txt first.") from exc

    parser = build_arg_parser()
    args = parser.parse_args()

    config = get_default_config()
    if args.label_variant == "both" and (args.dataset_path or args.output_dir):
        parser.error("--dataset-path and --output-dir can only be used with a single --label-variant")

    for variant in iter_label_variants(args.label_variant):
        variant_paths = resolve_label_variant_paths(config, variant)
        variant_paths.ensure_directories()
        dataset_path = Path(args.dataset_path) if args.dataset_path else variant_paths.supervised_dataset_path
        if args.label_variant == "both" and not dataset_path.exists():
            print(f"[{variant}] skipped_missing_dataset={dataset_path}")
            continue
        dataset = SupervisedSignalDataset(dataset_path=dataset_path, config=config)
        train_split = dataset.get_split("train", split_strategy=args.split_strategy)
        val_split = dataset.get_split("val", split_strategy=args.split_strategy)

        model = build_logistic_regression_pipeline(random_state=config.random_seed)
        model.fit(train_split.X, train_split.y, classifier__sample_weight=train_split.sample_weights)

        train_prob = model.predict_proba(train_split.X)[:, 1]
        train_pred = (train_prob >= 0.5).astype(int)
        val_prob = model.predict_proba(val_split.X)[:, 1]
        val_pred = (val_prob >= 0.5).astype(int)

        metadata: Dict[str, object] = {
            "model_type": "logistic_regression",
            "label_variant": variant,
            "feature_columns": train_split.feature_columns,
            "split_strategy": args.split_strategy,
            "train_metrics": compute_metrics(train_split.y, train_pred, train_prob),
            "val_metrics": compute_metrics(val_split.y, val_pred, val_prob),
            "train_label_distribution": label_distribution(train_split.y),
            "val_label_distribution": label_distribution(val_split.y),
            "config": config.to_dict(),
        }

        output_dir = Path(args.output_dir) if args.output_dir else variant_paths.exports_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = output_dir / config.model_filename
        metadata_path = output_dir / config.model_metadata_filename
        metrics_csv_path = output_dir / "signal_model_metrics.csv"

        joblib.dump(model, model_path)
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        metrics_csv_path.write_text(
            "split,accuracy,precision,recall,f1,roc_auc\n"
            f"train,{metadata['train_metrics']['accuracy']},{metadata['train_metrics']['precision']},"
            f"{metadata['train_metrics']['recall']},{metadata['train_metrics']['f1']},{metadata['train_metrics']['roc_auc']}\n"
            f"val,{metadata['val_metrics']['accuracy']},{metadata['val_metrics']['precision']},"
            f"{metadata['val_metrics']['recall']},{metadata['val_metrics']['f1']},{metadata['val_metrics']['roc_auc']}\n",
            encoding="utf-8",
        )
        model_ref = make_relative_to_repo(model_path, config=config)
        update_manifest(
            config=config,
            latest_model_export=model_ref,
            **{f"latest_model_export_{variant}": model_ref},
        )

        print(f"[{variant}] model={model_path}")
        print(f"[{variant}] metadata={metadata_path}")
        print(f"[{variant}] metrics={metrics_csv_path}")


if __name__ == "__main__":
    main()
