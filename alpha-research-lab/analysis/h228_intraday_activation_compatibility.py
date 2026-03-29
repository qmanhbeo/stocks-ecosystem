"""
H228: Intraday sticky-activation compatibility placeholder.
Skips unless H227 produces a promoted exit winner.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary
from src.research_protocol import DEFAULT_PROTOCOL


def main() -> None:
    protocol = DEFAULT_PROTOCOL
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_intraday_activation_compatibility",
        name="h228_intraday_activation_compatibility",
        summary={"protocol": protocol.describe(), "skipped": True, "reason": "H227 produced no promoted intraday exit winner"},
        artifacts={},
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
