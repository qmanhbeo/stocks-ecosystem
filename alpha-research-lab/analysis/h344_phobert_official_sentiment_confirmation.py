"""
H344 - PhoBERT Official-Sentiment Confirmation Audit.

Question:
- Does the fixed H343 winner, `h343_sentiment_x_official`, survive the lab's
  dev / validation / confirmation split strongly enough to be treated as more
  than offline evidence?

Design:
- Do not re-search features.
- Read the saved H343 summary artifact.
- Use only the fixed H343 best feature's yearly ICs.
- Apply the locked historical split:
  - dev: 2016-2022, because the PhoBERT news surface begins in 2016
  - validation: 2023-2024
  - confirmation: 2025
- Do not use 2026.

Decision ladder:
- PASS:
  - dev pooled yearly avg IC > 0.01
  - validation pooled yearly avg IC > 0.01
  - confirmation IC > 0.01
- MIXED:
  - dev and validation pass, but confirmation is positive below 0.01
- FAIL:
  - confirmation is non-positive, or dev/validation fail.
"""

from __future__ import annotations

from datetime import datetime
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary


H343_SUMMARY_PATH = REPO_ROOT / "artifacts/run_summaries/latest_research_branch_phobert_semantic_condition_audit.json"
FIXED_FEATURE = "h343_sentiment_x_official"


def _phase_summary(yearly: list[dict[str, object]], years: set[int]) -> dict[str, object]:
    rows = [row for row in yearly if int(row["year"]) in years]
    ics = [float(row["ic"]) for row in rows]
    return {
        "years": sorted(int(row["year"]) for row in rows),
        "rows": int(sum(int(row["n"]) for row in rows)),
        "avg_ic": float(np.mean(ics)) if ics else None,
        "pos_years": int(sum(1 for ic in ics if ic > 0.0)),
        "year_count": int(len(ics)),
        "yearly": rows,
    }


def main() -> None:
    print("H344 - PhoBERT Official-Sentiment Confirmation Audit")
    print("=" * 78)

    h343 = json.loads(H343_SUMMARY_PATH.read_text(encoding="utf-8"))
    best = h343["summary"]["best_feature"]
    if str(best["feature_name"]) != FIXED_FEATURE:
        raise RuntimeError(f"Expected fixed H343 feature {FIXED_FEATURE}, found {best['feature_name']}")

    yearly = best["yearly"]
    phases = {
        "dev": _phase_summary(yearly, set(range(2016, 2023))),
        "validation": _phase_summary(yearly, {2023, 2024}),
        "confirmation": _phase_summary(yearly, {2025}),
    }

    dev_ic = float(phases["dev"]["avg_ic"] or 0.0)
    validation_ic = float(phases["validation"]["avg_ic"] or 0.0)
    confirmation_ic = float(phases["confirmation"]["avg_ic"] or 0.0)

    if dev_ic > 0.01 and validation_ic > 0.01 and confirmation_ic > 0.01:
        verdict = "PASSED"
    elif dev_ic > 0.01 and validation_ic > 0.01 and confirmation_ic > 0.0:
        verdict = "MIXED"
    else:
        verdict = "FAILED"

    summary = {
        "verdict": verdict,
        "fixed_feature": FIXED_FEATURE,
        "source_h343_summary": str(H343_SUMMARY_PATH),
        "source_h343_verdict": h343["summary"].get("verdict"),
        "source_h343_best_feature": {k: v for k, v in best.items() if k != "yearly"},
        "protocol": {
            "dev_years": [2016, 2022],
            "validation_years": [2023, 2024],
            "confirmation_year": 2025,
            "forward_start_year": 2026,
        },
        "phase_details": phases,
        "branch_decision": (
            "The H343 official-conditioned PhoBERT sentiment feature is useful offline evidence, "
            "but it is not a standalone promoted signal because 2025 confirmation is non-positive."
        ),
        "next_step": (
            "Keep the official-conditioned sentiment transform for the later combined local-news audit; "
            "do not promote it alone or tune more BERT-only sentiment variants."
        ),
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = write_run_summary(
        ts=ts,
        mode="research_branch_phobert_official_sentiment_confirmation",
        name="h344_phobert_official_sentiment_confirmation",
        summary=summary,
        artifacts={"source_h343_summary": str(H343_SUMMARY_PATH)},
        metadata={"signal": "H344", "family": "news_sentiment"},
    )

    print(
        f"Fixed feature: {FIXED_FEATURE} | dev={dev_ic:.4f} | "
        f"validation={validation_ic:.4f} | confirmation={confirmation_ic:.4f}",
        flush=True,
    )
    print(f"VERDICT: {verdict}", flush=True)
    print(f"summary: {path}", flush=True)


if __name__ == "__main__":
    main()
