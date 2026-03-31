import json
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.repo_paths import artifact_path, lab_relative_path


RUN_SUMMARY_DIR = artifact_path("run_summaries")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return slug.strip("._") or "run"


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return lab_relative_path(value)
    if isinstance(value, str):
        return lab_relative_path(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def write_run_summary(*, ts: str, mode: str, name: str,
                      summary: dict, artifacts: Optional[dict] = None,
                      metadata: Optional[dict] = None) -> str:
    """
    Persist a compact machine-readable summary for a single run.

    A permanent per-run JSON file is written under the lab repo's
    artifacts/run_summaries/,
    and a convenience latest_<mode>.json pointer is refreshed for quick lookup.
    """
    RUN_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "ts": ts,
        "mode": mode,
        "name": name,
        "summary": _json_safe(summary or {}),
        "artifacts": _json_safe(artifacts or {}),
        "metadata": _json_safe(metadata or {}),
    }

    out_path = RUN_SUMMARY_DIR / f"{ts}_{_slugify(name)}_{mode}.json"
    latest_path = RUN_SUMMARY_DIR / f"latest_{mode}.json"

    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    out_path.write_text(body, encoding="utf-8")
    latest_path.write_text(body, encoding="utf-8")
    return str(out_path)
