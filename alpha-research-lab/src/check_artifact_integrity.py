from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.artifact_contract import validate_required_columns, validate_unique_keys  # noqa: E402
from src.repo_paths import data_path  # noqa: E402


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: Path
    required_columns: tuple[str, ...]
    key_columns: tuple[str, ...] = ()
    manifest_path: Path | None = None
    monotonic_time: bool = False


FEATURE_DIR = data_path("features")
RL_PARTS_DIR = FEATURE_DIR / "_rl_signal_matrix_parts"

ARTIFACTS: dict[str, ArtifactSpec] = {
    "rl_matrix": ArtifactSpec(
        name="rl_matrix",
        path=FEATURE_DIR / "xs_rl_signal_matrix.parquet",
        required_columns=(
            "time",
            "ticker",
            "s1_proba",
            "actual",
            "c4_oc_asym_5d",
            "c5_ins_relative_size_5d",
            "c5_signal_present",
            "c6_contrarian_intra_5d",
            "c7_ceiling_count_5d",
            "c8_vol_zscore_5d",
            "c9_reversal_1d",
            "c10_illiq_level_rank",
            "c11_ret_60d_lag_rank",
            "c12_gap_absorb_3",
            "c13_compress_blowoff_2",
            "c14_clv_volconf_resid_rank",
        ),
        key_columns=("time", "ticker"),
        monotonic_time=True,
    ),
    "activation_state": ArtifactSpec(
        name="activation_state",
        path=FEATURE_DIR / "activation_state_daily.parquet",
        required_columns=(
            "time",
            "full_top5_mean_clv",
            "s1_top5_mean_clv",
            "full_top5_prev_overlap_ratio",
            "s1_top5_prev_overlap_ratio",
            "full_top1_prev_same",
            "s1_top1_prev_same",
        ),
        key_columns=("time",),
        manifest_path=FEATURE_DIR / "activation_state_daily_manifest.json",
        monotonic_time=True,
    ),
    "activation_meta": ArtifactSpec(
        name="activation_meta",
        path=FEATURE_DIR / "activation_meta_daily.parquet",
        required_columns=(
            "time",
            "full_future_cycle_relative_return",
            "s1_future_cycle_relative_return",
            "full_recent_cycle_relative_return_ewm3",
            "s1_recent_cycle_relative_return_ewm3",
            "full_selector_drawdown",
            "s1_selector_drawdown",
            "delta_liq_open_breadth_all_1d",
            "selector_confidence_combo",
            "selector_entry_quality_combo",
        ),
        key_columns=("time",),
        manifest_path=FEATURE_DIR / "activation_meta_daily_manifest.json",
        monotonic_time=True,
    ),
    "c10": ArtifactSpec(
        name="c10",
        path=RL_PARTS_DIR / "c10_illiq.parquet",
        required_columns=("time", "ticker", "c10_illiq_level_rank"),
        key_columns=("time", "ticker"),
        manifest_path=RL_PARTS_DIR / "c10_illiq_manifest.json",
        monotonic_time=True,
    ),
    "c11": ArtifactSpec(
        name="c11",
        path=RL_PARTS_DIR / "c11_3m_continuation.parquet",
        required_columns=("time", "ticker", "c11_ret_60d_lag_rank"),
        key_columns=("time", "ticker"),
        manifest_path=RL_PARTS_DIR / "c11_3m_continuation_manifest.json",
        monotonic_time=True,
    ),
    "c12": ArtifactSpec(
        name="c12",
        path=RL_PARTS_DIR / "c12_gap_absorption.parquet",
        required_columns=("time", "ticker", "c12_gap_absorb_3"),
        key_columns=("time", "ticker"),
        manifest_path=RL_PARTS_DIR / "c12_gap_absorption_manifest.json",
        monotonic_time=True,
    ),
    "c13": ArtifactSpec(
        name="c13",
        path=RL_PARTS_DIR / "c13_compress_blowoff.parquet",
        required_columns=("time", "ticker", "c13_compress_blowoff_2"),
        key_columns=("time", "ticker"),
        manifest_path=RL_PARTS_DIR / "c13_compress_blowoff_manifest.json",
        monotonic_time=True,
    ),
    "c14": ArtifactSpec(
        name="c14",
        path=RL_PARTS_DIR / "c14_clv_resid.parquet",
        required_columns=("time", "ticker", "c14_clv_volconf_resid_rank"),
        key_columns=("time", "ticker"),
        manifest_path=RL_PARTS_DIR / "c14_clv_resid_manifest.json",
        monotonic_time=True,
    ),
}


def _read_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Manifest is not readable JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest must be a JSON object: {path}")
    return payload


def check_artifact(spec: ArtifactSpec, *, require_manifest: bool = False) -> dict[str, object]:
    if not spec.path.exists():
        raise FileNotFoundError(f"Artifact missing: {spec.path}")
    columns = tuple(dict.fromkeys([*spec.required_columns, *spec.key_columns]))
    try:
        frame = pd.read_parquet(spec.path, columns=list(columns))
    except Exception as exc:
        raise ValueError(f"Artifact is not readable parquet: {spec.path}") from exc

    validate_required_columns(frame, spec.required_columns, spec.name)
    if "time" in frame.columns:
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
        if frame["time"].isna().any():
            raise ValueError(f"{spec.name} has invalid time values")
        if spec.monotonic_time and not frame["time"].is_monotonic_increasing:
            raise ValueError(f"{spec.name} time column is not monotonic increasing")
    if spec.key_columns:
        validate_unique_keys(frame, spec.key_columns, spec.name)

    manifest_summary = None
    if spec.manifest_path is not None:
        if require_manifest or spec.manifest_path.exists():
            manifest = _read_manifest(spec.manifest_path)
            manifest_summary = {
                "path": str(spec.manifest_path),
                "build_timestamp": manifest.get("build_timestamp"),
                "row_count": manifest.get("row_count"),
                "column_count": manifest.get("column_count"),
            }

    return {
        "artifact": spec.name,
        "path": str(spec.path),
        "rows": int(len(frame)),
        "columns_checked": list(columns),
        "time_min": frame["time"].min().date().isoformat() if "time" in frame.columns and len(frame) else None,
        "time_max": frame["time"].max().date().isoformat() if "time" in frame.columns and len(frame) else None,
        "manifest": manifest_summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate important alpha-lab artifacts.")
    parser.add_argument("--artifact", choices=sorted(ARTIFACTS), help="Single artifact key to validate.")
    parser.add_argument("--all", action="store_true", help="Validate all configured artifacts.")
    parser.add_argument("--require-manifest", action="store_true", help="Fail if configured manifest is absent.")
    parser.add_argument("--summary", action="store_true", help="Print JSON summaries for passing artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.all and not args.artifact:
        raise SystemExit("Choose --artifact <name> or --all")
    names = sorted(ARTIFACTS) if args.all else [str(args.artifact)]
    summaries = []
    for name in names:
        summary = check_artifact(ARTIFACTS[name], require_manifest=args.require_manifest)
        summaries.append(summary)
        print(f"OK {name}: rows={summary['rows']:,} {summary['time_min']} -> {summary['time_max']}")
    if args.summary:
        print(json.dumps(summaries, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
