from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


VALIDATION_REL_DELTA_MIN = 0.05
VALIDATION_IR_DELTA_MIN = 0.05
CONFIRMATION_REL_DELTA_FLOOR = -0.05
CONFIRMATION_IR_DELTA_FLOOR = -0.05


def load_summary_payload(summary_path: Path) -> dict[str, object]:
    return json.loads(Path(summary_path).read_text(encoding="utf-8"))


def summary_is_skipped(summary_path: Path) -> bool:
    payload = load_summary_payload(summary_path)
    return bool(payload.get("summary", {}).get("skipped"))


def resolve_summary_artifact(summary_path: Path, key: str) -> Path:
    payload = load_summary_payload(summary_path)
    artifact = payload.get("artifacts", {}).get(str(key))
    if not artifact:
        raise ValueError(f"Summary {summary_path} does not contain artifact key {key!r}")
    artifact_path = Path(str(artifact))
    if artifact_path.is_absolute():
        return artifact_path
    summary_root = Path(summary_path).resolve().parents[2]
    return (summary_root / artifact_path).resolve()


def blend_state_scoped_scores(
    baseline_score: pd.Series | np.ndarray,
    atom_score: pd.Series | np.ndarray,
    state_mask: pd.Series | np.ndarray,
    *,
    atom_weight: float,
) -> pd.Series:
    base = pd.Series(pd.to_numeric(baseline_score, errors="coerce"), dtype=float)
    atom = pd.Series(pd.to_numeric(atom_score, errors="coerce"), dtype=float)
    state = pd.Series(state_mask).fillna(False).astype(bool)
    if len(base) != len(atom) or len(base) != len(state):
        raise ValueError("baseline_score, atom_score, and state_mask must have the same length")
    atom_weight = float(atom_weight)
    if atom_weight < 0.0 or atom_weight > 1.0:
        raise ValueError("atom_weight must lie in [0, 1]")
    out = base.copy()
    out.loc[state] = ((1.0 - atom_weight) * base.loc[state] + atom_weight * atom.loc[state]).clip(0.0, 1.0)
    return out.astype(float)


def additive_candidate_deltas(candidate_row: pd.Series, baseline_row: pd.Series) -> dict[str, float]:
    val_rel = float(pd.to_numeric(candidate_row.get("validation_relative_total_return"), errors="coerce"))
    val_ir = float(pd.to_numeric(candidate_row.get("validation_information_ratio_annualized"), errors="coerce"))
    conf_rel = float(pd.to_numeric(candidate_row.get("confirmation_relative_total_return"), errors="coerce"))
    conf_ir = float(pd.to_numeric(candidate_row.get("confirmation_information_ratio_annualized"), errors="coerce"))
    base_val_rel = float(pd.to_numeric(baseline_row.get("validation_relative_total_return"), errors="coerce"))
    base_val_ir = float(pd.to_numeric(baseline_row.get("validation_information_ratio_annualized"), errors="coerce"))
    base_conf_rel = float(pd.to_numeric(baseline_row.get("confirmation_relative_total_return"), errors="coerce"))
    base_conf_ir = float(pd.to_numeric(baseline_row.get("confirmation_information_ratio_annualized"), errors="coerce"))
    return {
        "validation_relative_delta": val_rel - base_val_rel,
        "validation_ir_delta": val_ir - base_val_ir,
        "confirmation_relative_delta": conf_rel - base_conf_rel,
        "confirmation_ir_delta": conf_ir - base_conf_ir,
    }


def additive_candidate_passes(
    candidate_row: pd.Series,
    baseline_row: pd.Series,
    *,
    validation_rel_delta_min: float = VALIDATION_REL_DELTA_MIN,
    validation_ir_delta_min: float = VALIDATION_IR_DELTA_MIN,
    confirmation_rel_delta_floor: float = CONFIRMATION_REL_DELTA_FLOOR,
    confirmation_ir_delta_floor: float = CONFIRMATION_IR_DELTA_FLOOR,
) -> bool:
    deltas = additive_candidate_deltas(candidate_row, baseline_row)
    passes_validation = (
        deltas["validation_relative_delta"] >= float(validation_rel_delta_min)
        or deltas["validation_ir_delta"] >= float(validation_ir_delta_min)
    )
    survives_confirmation = (
        deltas["confirmation_relative_delta"] >= float(confirmation_rel_delta_floor)
        and deltas["confirmation_ir_delta"] >= float(confirmation_ir_delta_floor)
    )
    return bool(passes_validation and survives_confirmation)
