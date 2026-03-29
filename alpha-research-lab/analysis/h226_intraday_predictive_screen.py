"""
H226: Predictive screening placeholder for intraday structure.
Skips unless H225 coverage passes.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary
from src.research_protocol import DEFAULT_PROTOCOL

H225_SUMMARY_PATH = Path("artifacts/run_summaries/latest_portfolio_exit_intraday_structure_feasibility.json")


def main() -> None:
    protocol = DEFAULT_PROTOCOL
    payload = json.loads(H225_SUMMARY_PATH.read_text(encoding="utf-8")) if H225_SUMMARY_PATH.exists() else {"summary": {}}
    passed = bool(payload.get("summary", {}).get("coverage_gate_passed", False))
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if not passed:
        reason = "H225 coverage gate failed"
    else:
        reason = "Intraday predictive screening not implemented beyond the coverage gate because the local branch already closes on single-ticker intraday data"
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_intraday_predictive_screen",
        name="h226_intraday_predictive_screen",
        summary={"protocol": protocol.describe(), "skipped": True, "reason": reason},
        artifacts={},
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
