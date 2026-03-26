import json
import re
from pathlib import Path
from typing import Optional


RUN_SUMMARY_DIR = Path("artifacts/run_summaries")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return slug.strip("._") or "run"


def write_run_summary(*, ts: str, mode: str, name: str,
                      summary: dict, artifacts: Optional[dict] = None,
                      metadata: Optional[dict] = None) -> str:
    """
    Persist a compact machine-readable summary for a single run.

    A permanent per-run JSON file is written under artifacts/run_summaries/,
    and a convenience latest_<mode>.json pointer is refreshed for quick lookup.
    """
    RUN_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "ts": ts,
        "mode": mode,
        "name": name,
        "summary": summary or {},
        "artifacts": artifacts or {},
        "metadata": metadata or {},
    }

    out_path = RUN_SUMMARY_DIR / f"{ts}_{_slugify(name)}_{mode}.json"
    latest_path = RUN_SUMMARY_DIR / f"latest_{mode}.json"

    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    out_path.write_text(body, encoding="utf-8")
    latest_path.write_text(body, encoding="utf-8")
    return str(out_path)
