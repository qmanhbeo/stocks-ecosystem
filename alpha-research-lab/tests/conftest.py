from __future__ import annotations

import sys
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = LAB_ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
SHARED_RECOMMENDATION_ROOT = WORKSPACE_ROOT / "shared-recommendation"

for path in (LAB_ROOT, SHARED_MARKET_RULES_ROOT, SHARED_RECOMMENDATION_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
