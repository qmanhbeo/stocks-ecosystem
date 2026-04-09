"""
H315: official disclosure timestamp source audit.

Question:
    Does the workspace already contain a usable official disclosure timestamp
    source that can replace or validate the CafeF-first-public event surface?
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from path_utils import data_path

from src.run_summary import write_run_summary


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = data_path("")
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

SEARCH_PATTERNS = (
    "*ssc*",
    "*disclosure*",
    "*cong_bo*",
    "*filing*",
    "*hose*announcement*",
    "*hnx*announcement*",
    "*official*",
)


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    hits: list[str] = []
    for pattern in SEARCH_PATTERNS:
        for path in DATA_ROOT.rglob(pattern):
            if path.is_file():
                hits.append(str(path))
    hits = sorted(set(hits))

    decision = "SKIP"
    branch_decision = "No local official disclosure timestamp history exists yet, so the official-source branch remains data-blocked."

    details = {
        "data_root": str(DATA_ROOT),
        "search_patterns": list(SEARCH_PATTERNS),
        "local_hits": hits[:200],
        "local_hit_count": int(len(hits)),
    }
    details_path = DETAILS_DIR / f"{ts}_h315_official_disclosure_timestamp_source_audit_details.json"
    details_path.write_text(json.dumps(details, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "skipped": True,
        "branch_decision": branch_decision,
        "local_hit_count": int(len(hits)),
        "blocker": "missing_local_official_disclosure_history",
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_official_disclosure_timestamp_source_audit",
        name="h315_official_disclosure_timestamp_source_audit",
        summary=summary,
        artifacts={"details": details_path},
        metadata={
            "session": 136,
            "branch_contract": "Only a locally available official disclosure timestamp history can advance this branch beyond a source audit.",
        },
    )


if __name__ == "__main__":
    main()
