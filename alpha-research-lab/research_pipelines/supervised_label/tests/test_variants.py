from pathlib import Path
import tempfile

from research_pipelines.supervised_label.config import SupervisedLabelConfig
from research_pipelines.supervised_label.variants import iter_label_variants, resolve_label_variant_paths


def _build_config(root: Path) -> SupervisedLabelConfig:
    package_root = root / "sub_pipelines" / "supervised_label"
    return SupervisedLabelConfig(
        repo_root=root,
        package_root=package_root,
        labels_root=root / "data" / "labels" / "supervised",
        signal_features_root=root / "data" / "features" / "signals",
        raw_data_dir=root / "data" / "stock",
        artifacts_dir=root / "data" / "labels" / "supervised",
        configs_dir=package_root / "configs",
        splits_dir=root / "data" / "labels" / "supervised" / "splits",
        sessions_dir=root / "artifacts" / "labeling_sessions",
        labels_dir=root / "data" / "labels" / "supervised" / "ranges",
        exports_dir=root / "artifacts" / "signal_models",
        datasets_dir=root / "data" / "features" / "signals" / "datasets",
        predictions_dir=root / "data" / "features" / "signals" / "predictions",
        labels_jsonl_path=root / "data" / "labels" / "supervised" / "ranges" / "range_labels.jsonl",
        manifest_path=root / "data" / "labels" / "supervised" / "manifest.json",
    )


def test_iter_label_variants_expands_both():
    assert tuple(iter_label_variants("both")) == ("manual", "auto")
    assert tuple(iter_label_variants("manual")) == ("manual",)


def test_resolve_label_variant_paths_separates_outputs():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = _build_config(Path(temp_dir))

        manual = resolve_label_variant_paths(config, "manual")
        auto = resolve_label_variant_paths(config, "auto")

        assert manual.labels_jsonl_path.name == "range_labels.jsonl"
        assert auto.labels_jsonl_path.name == "heuristic_range_labels.jsonl"
        assert manual.datasets_dir == config.datasets_dir / "manual"
        assert auto.datasets_dir == config.datasets_dir / "auto"
        assert manual.exports_dir == config.exports_dir / "manual"
        assert auto.exports_dir == config.exports_dir / "auto"
        assert manual.predictions_dir == config.predictions_dir / "manual"
        assert auto.predictions_dir == config.predictions_dir / "auto"
