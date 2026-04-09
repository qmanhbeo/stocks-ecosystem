"""
H324: historical foreign-flow source gate.

Question:
    Is there any real historical per-ticker foreign buy/sell or foreign-room
    table available locally that can support the next acquisition branch?

Design:
    - inventory local candidate paths under the canonical root data warehouse
    - distinguish real per-ticker foreign-flow tables from the known VNM ETF
      proxy and ticker-name collisions such as the stock VNM file
    - if a real table exists, record its schema/coverage for a follow-up pilot
    - if not, save a source-blocked summary instead of re-testing H110
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary  # noqa: E402


DATA_ROOT = data_path("")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
FOREIGN_PROXY_PATH = data_path("features/xs_foreign_demand_daily.parquet")
VNM_ETF_PATH = data_path("fx-commodities/fx_commodities_vnm_etf_1D.parquet")

PATH_KEYWORDS = re.compile(
    r"foreign|foreigner|room|ownership|nuoc|ngoai|n[uư][oơ]c|flow|vnm_etf|xs_foreign",
    re.IGNORECASE,
)
REAL_FLOW_COLUMNS = {
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_buy_value",
    "foreign_sell_value",
    "foreign_net_buy_value",
    "foreign_net_value",
    "foreign_room",
    "foreign_volume",
    "current_holding_ratio",
    "foreign_ownership",
}
PROXY_COLUMNS = {
    "xs_foreign_affinity_120d",
    "xs_foreign_affinity_20d",
    "xs_vnm_premium_1d",
    "xs_fa_rank",
    "xs_fa_signal",
}


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _classify_path(path: Path, columns: set[str]) -> str:
    path_text = str(path.relative_to(DATA_ROOT)).lower()
    lower_cols = {column.lower() for column in columns}
    if path == FOREIGN_PROXY_PATH or PROXY_COLUMNS & lower_cols:
        return "proxy_vnm_etf_affinity"
    if path == VNM_ETF_PATH or "vnm_etf" in path_text:
        return "proxy_vnm_etf_price"
    if "/vnm" in path_text or "gia_lich_su_vnm" in path_text or path.name.startswith("VNM"):
        return "ticker_name_collision_vnm"
    if {"time", "ticker"} <= lower_cols and REAL_FLOW_COLUMNS & lower_cols:
        return "real_candidate"
    if REAL_FLOW_COLUMNS & lower_cols:
        return "schema_fragment_current_or_unmapped"
    return "name_only_not_foreign_flow"


def _scan_candidates() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted(DATA_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(DATA_ROOT)
        if not PATH_KEYWORDS.search(str(rel)):
            continue
        row: dict[str, object] = {
            "path": str(rel),
            "suffix": path.suffix,
            "size_bytes": int(path.stat().st_size),
            "classification": "unread",
            "rows": None,
            "columns": None,
            "time_min": None,
            "time_max": None,
            "ticker_count": None,
            "has_time": False,
            "has_ticker": False,
            "real_flow_column_hits": None,
            "proxy_column_hits": None,
        }
        columns: set[str] = set()
        frame: pd.DataFrame | None = None
        if path.suffix == ".parquet":
            try:
                frame = pd.read_parquet(path)
                columns = {str(column) for column in frame.columns}
                row["rows"] = int(len(frame))
                row["columns"] = sorted(columns)
                row["has_time"] = "time" in columns
                row["has_ticker"] = "ticker" in columns
                if "time" in columns and len(frame) > 0:
                    t = pd.to_datetime(frame["time"], errors="coerce")
                    row["time_min"] = _json_safe(t.min())
                    row["time_max"] = _json_safe(t.max())
                if "ticker" in columns and len(frame) > 0:
                    row["ticker_count"] = int(frame["ticker"].astype(str).nunique())
            except Exception as exc:  # pragma: no cover - inventory should keep going
                row["read_error"] = f"{type(exc).__name__}: {exc}"
        elif path.suffix == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                columns = set(payload.keys()) if isinstance(payload, dict) else set()
                row["columns"] = sorted(columns)
            except Exception as exc:  # pragma: no cover
                row["read_error"] = f"{type(exc).__name__}: {exc}"
        lower_cols = {column.lower() for column in columns}
        row["real_flow_column_hits"] = sorted(REAL_FLOW_COLUMNS & lower_cols)
        row["proxy_column_hits"] = sorted(PROXY_COLUMNS & lower_cols)
        row["classification"] = _classify_path(path, columns)
        rows.append(row)
    return pd.DataFrame(rows)


def _proxy_snapshot() -> dict[str, object]:
    out: dict[str, object] = {}
    if FOREIGN_PROXY_PATH.exists():
        proxy = pd.read_parquet(FOREIGN_PROXY_PATH)
        proxy["time"] = pd.to_datetime(proxy["time"], errors="coerce")
        out["xs_foreign_demand_daily"] = {
            "exists": True,
            "rows": int(len(proxy)),
            "tickers": int(proxy["ticker"].astype(str).nunique()) if "ticker" in proxy.columns else None,
            "time_min": _json_safe(proxy["time"].min()),
            "time_max": _json_safe(proxy["time"].max()),
            "columns": list(proxy.columns),
            "classification": "archive-only VNM ETF affinity proxy, not real foreign buy/sell",
        }
    else:
        out["xs_foreign_demand_daily"] = {"exists": False}
    if VNM_ETF_PATH.exists():
        vnm = pd.read_parquet(VNM_ETF_PATH)
        vnm["time"] = pd.to_datetime(vnm["time"], errors="coerce")
        out["vnm_etf_price"] = {
            "exists": True,
            "rows": int(len(vnm)),
            "time_min": _json_safe(vnm["time"].min()),
            "time_max": _json_safe(vnm["time"].max()),
            "columns": list(vnm.columns),
            "classification": "date-level ETF proxy, not per-ticker foreign flow",
        }
    else:
        out["vnm_etf_price"] = {"exists": False}
    return out


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    inventory = _scan_candidates()
    proxy_snapshot = _proxy_snapshot()
    real_candidates = inventory.loc[inventory["classification"].eq("real_candidate")].copy()
    schema_fragments = inventory.loc[inventory["classification"].eq("schema_fragment_current_or_unmapped")].copy()

    if not real_candidates.empty:
        verdict = "NEUTRAL"
        branch_decision = (
            "A possible historical foreign-flow table exists locally. Validate ticker/date integrity "
            "and run the pilot IC audit before building a feature surface."
        )
    else:
        verdict = "SKIP"
        branch_decision = (
            "No real historical per-ticker foreign buy/sell or foreign-room table exists in the local "
            "canonical data warehouse. Only the known failed VNM ETF proxy surfaces are present, "
            "so the branch remains source-blocked."
        )

    inventory_path = OUT_DIR / f"{ts}_h324_historical_foreign_flow_source_inventory.parquet"
    details_path = DETAILS_DIR / f"{ts}_research_branch_historical_foreign_flow_source_details.json"
    inventory.to_parquet(inventory_path, index=False)

    details = {
        "branch_decision": branch_decision,
        "proxy_snapshot": proxy_snapshot,
        "classification_counts": inventory["classification"].value_counts().to_dict() if not inventory.empty else {},
        "real_candidates": _json_safe(real_candidates.to_dict(orient="records")),
        "schema_fragments": _json_safe(schema_fragments.to_dict(orient="records")),
        "candidate_inventory": _json_safe(inventory.to_dict(orient="records")),
        "external_probe_note": (
            "Session command `python analysis/probe_vnstock.py` was run with network permission. "
            "Installed vnstock 3.5.0 exposed no `quote.history_foreign_ownership`; `price_board` remains current-day only."
        ),
    }
    details_path.write_text(json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "candidate_paths": int(len(inventory)),
        "real_candidate_paths": int(len(real_candidates)),
        "schema_fragment_paths": int(len(schema_fragments)),
        "classification_counts": {str(k): int(v) for k, v in inventory["classification"].value_counts().to_dict().items()}
        if not inventory.empty
        else {},
        "proxy_snapshot": proxy_snapshot,
    }
    artifacts = {
        "inventory": inventory_path,
        "details": details_path,
    }
    metadata = {
        "question": "Is a real historical per-ticker foreign buy/sell or foreign-room table available locally?",
        "source_gate": "No alpha test is run unless a real table with time+ticker+foreign-flow columns exists.",
        "excluded_surfaces": {
            "xs_foreign_demand_daily.parquet": "H110 VNM ETF proxy, archive-only and already failed",
            "fx_commodities_vnm_etf_1D.parquet": "date-level ETF price proxy, not per-ticker foreign flow",
        },
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_historical_foreign_flow_source",
        name="h324_historical_foreign_flow_source",
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
