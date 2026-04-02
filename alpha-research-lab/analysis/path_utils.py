from __future__ import annotations

import sys
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from src.repo_paths import DATA_ROOT, WORKSPACE_ROOT, data_path, workspace_path

__all__ = ["DATA_ROOT", "WORKSPACE_ROOT", "data_path", "workspace_path"]
