"""
H229: Historical order-book / queue feasibility audit.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary
from src.research_protocol import DEFAULT_PROTOCOL


OUT_DIR = Path("artifacts/portfolio_baselines")
PROBE_PATH = Path("analysis/probe_vnstock2_output.txt")


def main() -> None:
    protocol = DEFAULT_PROTOCOL
    tokens = ("orderbook", "order_book", "bid_ask", "queue", "market_depth", "depth_of_book")
    data_candidates = sorted(
        [
            str(path)
            for path in Path("data").rglob("*")
            if path.is_file()
            and any(token in str(path).lower() for token in tokens)
        ]
    )
    probe_has_schema = False
    if PROBE_PATH.exists():
        text = PROBE_PATH.read_text(encoding="utf-8", errors="ignore")
        probe_has_schema = all(token in text for token in ["bid_1_price", "ask_1_price", "match_price_ato", "match_price_atc"])
    feasible = bool(data_candidates)
    audit = {
        "local_order_book_files": data_candidates,
        "probe_schema_present": probe_has_schema,
        "feasible_now": feasible,
        "decision": "stop_exit_side_research_on_current_data_stack" if not feasible else "order_book_branch_can_open_later",
        "reason": "Local workspace has no historical queue/depth time series under data/; only a schema probe exists" if not feasible else "Historical queue/depth files exist locally",
    }
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = OUT_DIR / f"{ts}_h229_order_book_feasibility_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_order_book_feasibility_audit",
        name="h229_order_book_feasibility_audit",
        summary={"protocol": protocol.describe(), **audit},
        artifacts={"audit": str(audit_path)},
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
