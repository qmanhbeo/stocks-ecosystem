"""
H326: forward foreign-flow collector contract gate.

Question:
    If historical per-ticker foreign flow is unavailable, can the workspace
    safely start accumulating current-day VCI price_board foreign fields
    forward-only, with explicit metadata that the data is not backtestable yet?

Design:
    - validate the collector's schema normalization on a synthetic price_board
      fixture that mirrors vnstock's MultiIndex columns
    - inspect the canonical forward output root after a live or dry collector run
    - record pass / neutral state without running any alpha test
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_TOOLS = ROOT / "data_tools"
if str(DATA_TOOLS) not in sys.path:
    sys.path.insert(0, str(DATA_TOOLS))

from src.run_summary import write_run_summary  # noqa: E402
from collect_forward_foreign_flow import (  # noqa: E402
    CONTRACT_COLUMNS,
    DAILY_LATEST_PATH,
    LATEST_SNAPSHOT_PATH,
    MANIFEST_PATH,
    OUT_ROOT,
    REQUIRED_SOURCE_COLUMNS,
    normalize_price_board_frame,
)


DETAILS_DIR = ROOT / "artifacts" / "run_summaries"


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
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


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        try:
            return str(path.relative_to(ROOT.parent))
        except ValueError:
            return str(path)


def build_fixture() -> pd.DataFrame:
    columns = pd.MultiIndex.from_tuples(
        [
            ("listing", "symbol"),
            ("listing", "exchange"),
            ("listing", "trading_date"),
            ("listing", "sending_time"),
            ("bid_ask", "transaction_time"),
            ("match", "sending_time"),
            ("match", "current_room"),
            ("match", "total_room"),
            ("match", "foreign_buy_volume"),
            ("match", "foreign_sell_volume"),
            ("match", "foreign_buy_value"),
            ("match", "foreign_sell_value"),
            ("match", "accumulated_volume"),
            ("match", "accumulated_value"),
            ("match", "match_price"),
            ("match", "open_price"),
            ("match", "reference_price"),
            ("match", "ceiling_price"),
            ("match", "floor_price"),
        ]
    )
    rows = [
        [
            "FPT",
            "HSX",
            "2026-04-09",
            "20260409 07:45:01.000",
            "074500001",
            "20260409 07:45:02.000",
            250,
            1000,
            120,
            75,
            1200000,
            760000,
            5000,
            410000000,
            82000,
            81500,
            80000,
            85600,
            74400,
        ],
        [
            "VCB",
            "HSX",
            "2026-04-09",
            "20260409 07:45:01.000",
            "074500001",
            "20260409 07:45:02.000",
            500,
            2000,
            90,
            110,
            550000,
            670000,
            7000,
            390000000,
            59000,
            59200,
            58800,
            62900,
            54700,
        ],
    ]
    return pd.DataFrame(rows, columns=columns)


def validate_fixture_contract() -> dict[str, object]:
    frame = build_fixture()
    normalized = normalize_price_board_frame(frame, "2026-04-09T10:00:00Z")
    missing_contract = [column for column in CONTRACT_COLUMNS if column not in normalized.columns]
    missing_source = sorted(REQUIRED_SOURCE_COLUMNS - set("__".join(col) for col in frame.columns.to_flat_index()))
    fpt = normalized.loc[normalized["ticker"].eq("FPT")].iloc[0]
    vcb = normalized.loc[normalized["ticker"].eq("VCB")].iloc[0]
    checks = {
        "rows": int(len(normalized)),
        "missing_contract_columns": missing_contract,
        "missing_fixture_source_columns": missing_source,
        "fpt_net_volume": float(fpt["foreign_net_volume"]),
        "fpt_net_value": float(fpt["foreign_net_value"]),
        "fpt_room_used_ratio": float(fpt["foreign_room_used_ratio"]),
        "vcb_net_volume": float(vcb["foreign_net_volume"]),
        "vcb_net_value": float(vcb["foreign_net_value"]),
        "tickers": sorted(normalized["ticker"].tolist()),
    }
    checks["passed"] = (
        checks["rows"] == 2
        and not missing_contract
        and not missing_source
        and checks["fpt_net_volume"] == 45.0
        and checks["fpt_net_value"] == 440000.0
        and round(checks["fpt_room_used_ratio"], 6) == 0.75
        and checks["vcb_net_volume"] == -20.0
        and checks["vcb_net_value"] == -120000.0
    )
    return checks


def inspect_outputs() -> dict[str, object]:
    out: dict[str, object] = {
        "root": _relative(OUT_ROOT),
        "manifest_exists": MANIFEST_PATH.exists(),
        "latest_snapshot_exists": LATEST_SNAPSHOT_PATH.exists(),
        "daily_latest_exists": DAILY_LATEST_PATH.exists(),
    }
    if MANIFEST_PATH.exists():
        try:
            out["manifest"] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            out["manifest_error"] = f"{type(exc).__name__}: {exc}"
    if LATEST_SNAPSHOT_PATH.exists():
        try:
            latest = pd.read_parquet(LATEST_SNAPSHOT_PATH)
            out["latest_rows"] = int(len(latest))
            out["latest_tickers"] = int(latest["ticker"].nunique()) if "ticker" in latest.columns else None
            out["latest_trading_dates"] = (
                sorted(latest["trading_date"].dropna().astype(str).unique().tolist())
                if "trading_date" in latest.columns
                else []
            )
            out["latest_missing_contract_columns"] = [
                column for column in CONTRACT_COLUMNS if column not in latest.columns
            ]
            out["latest_required_non_null_counts"] = {
                column: int(latest[column].notna().sum())
                for column in [
                    "foreign_buy_volume",
                    "foreign_sell_volume",
                    "foreign_buy_value",
                    "foreign_sell_value",
                    "current_room",
                    "total_room",
                ]
                if column in latest.columns
            }
        except Exception as exc:
            out["latest_error"] = f"{type(exc).__name__}: {exc}"
    if DAILY_LATEST_PATH.exists():
        try:
            daily = pd.read_parquet(DAILY_LATEST_PATH, columns=["trading_date", "ticker", "collected_at_utc"])
            out["daily_latest_rows"] = int(len(daily))
            out["daily_latest_tickers"] = int(daily["ticker"].nunique())
            out["daily_latest_dates"] = sorted(daily["trading_date"].dropna().astype(str).unique().tolist())
        except Exception as exc:
            out["daily_latest_error"] = f"{type(exc).__name__}: {exc}"
    return out


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    fixture = validate_fixture_contract()
    outputs = inspect_outputs()
    live_capture_ready = bool(
        fixture.get("passed")
        and outputs.get("manifest_exists")
        and outputs.get("latest_snapshot_exists")
        and int(outputs.get("latest_rows") or 0) > 0
        and not outputs.get("latest_missing_contract_columns")
    )

    if live_capture_ready:
        verdict = "PASSED"
        branch_decision = (
            "The forward-only VCI price_board collector contract is implemented and has "
            "a valid current snapshot. Start running it daily, but do not run backtests "
            "until enough forward history accrues."
        )
    elif fixture.get("passed"):
        verdict = "NEUTRAL"
        branch_decision = (
            "The collector contract and schema normalization pass locally, but no valid "
            "live snapshot is present yet. Run the collector with network access to start "
            "the forward-only history."
        )
    else:
        verdict = "FAILED"
        branch_decision = "The collector contract failed its schema fixture; fix the collector before using it."

    details_path = DETAILS_DIR / f"{ts}_research_branch_forward_foreign_flow_collector_details.json"
    details = {
        "branch_decision": branch_decision,
        "fixture_contract": fixture,
        "outputs": outputs,
        "contract": {
            "root": _relative(OUT_ROOT),
            "snapshot": _relative(LATEST_SNAPSHOT_PATH),
            "daily_latest": _relative(DAILY_LATEST_PATH),
            "manifest": _relative(MANIFEST_PATH),
            "forward_only": True,
            "not_backtestable_yet": True,
        },
    }
    details_path.write_text(json.dumps(_json_safe(details), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "fixture_passed": bool(fixture.get("passed")),
        "live_capture_ready": live_capture_ready,
        "manifest_exists": bool(outputs.get("manifest_exists")),
        "latest_snapshot_exists": bool(outputs.get("latest_snapshot_exists")),
        "latest_rows": int(outputs.get("latest_rows") or 0),
        "latest_tickers": int(outputs.get("latest_tickers") or 0),
        "latest_trading_dates": outputs.get("latest_trading_dates") or [],
        "daily_latest_rows": int(outputs.get("daily_latest_rows") or 0),
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_forward_foreign_flow_collector",
        name="h326_forward_foreign_flow_collector",
        summary=summary,
        artifacts={"details": details_path},
        metadata={
            "question": "Can current-day board foreign fields be collected forward-only?",
            "source_gate": "No alpha test is run; this only validates the collector contract.",
            "not_backtestable_yet": True,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
