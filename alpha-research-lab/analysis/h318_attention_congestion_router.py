"""
H318: attention-congestion router proxy audit.

Question:
    Do the surviving H310 event-v2 states react differently when market-wide
    attention is congested, or is the idea still blocked by missing / flat
    market-attention data?

Design:
    1. Audit the published xs_llm_news_market_daily surface on 2023-2025.
    2. If it is effectively flat, fall back to raw CafeF attention proxies:
       - raw article load
       - mapped event breadth
       - high-distraction days = high raw load + low mapped-share
    3. Evaluate the primary H310 same-day state and one secondary recent-window
       state on 1d and 5d lift, comparing high-congestion days with the
       complementary not-high days.

The contract is intentionally narrow:
    - frozen 2023 / 2024 / 2025 split
    - no 2026+ read
    - no live promotion claim
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h310_event_v2_predictive_rescreen import _build_h310_state_panel
from src.additive_selector_research import resolve_summary_artifact
from src.future_return_research import load_future_rel_5d
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


H310_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_event_v2_predictive_rescreen.json"
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
LLM_MARKET_PATH = data_path("features/xs_llm_news_market_daily.parquet")
RAW_NEWS_DIR = data_path("news/cafef/raw")
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
OUT_DIR = ROOT / "artifacts" / "timing_data"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

STATE_SPECS = (
    ("event_today_novel20", "primary_same_day"),
    ("recent5_low_repeat20", "secondary_recent_window"),
)

PROXY_SPECS = (
    ("high_raw_load", "Top-tercile raw CafeF article count", "load"),
    ("high_event_breadth", "Top-tercile mapped event breadth", "breadth"),
    ("high_distraction", "Top-tercile raw load plus bottom-tercile mapped share", "distraction"),
)

MARKET_AUDIT_COLUMNS = (
    "daily_market_tone",
    "market_tone_momentum",
    "uncertainty_index",
    "avg_surprise",
    "event_diversity",
    "frac_new_information",
    "frac_expectation_misses",
    "frac_market_scope",
)

MIN_ACTIVE_DAYS = 12
PASS_MIN_DAYS = 18
PASS_MIN_LAG_DELTA = 0.005
PASS_MIN_FWD5_DELTA = 0.003
MIXED_MIN_LAG_DELTA = 0.0


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


def _load_base_panel() -> pd.DataFrame:
    panel = pd.read_parquet(S1_PATH, columns=["time", "ticker", "actual"]).copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel = panel.loc[panel["time"].dt.year.between(2023, 2025)].copy()

    first_public_path = resolve_summary_artifact(H310_SUMMARY_PATH, "combined_first_public")
    state_panel, _ = _build_h310_state_panel(panel[["time", "ticker"]].drop_duplicates(), first_public_path)
    panel = panel.merge(
        state_panel[["time", "ticker", "event_today_novel20", "recent5_low_repeat20"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    panel = panel.merge(
        load_future_rel_5d(start_year=2023, end_year=2025),
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    for column, _note in STATE_SPECS:
        panel[column] = panel[column].fillna(False).astype(bool)
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _audit_market_daily_surface() -> dict[str, object]:
    if not LLM_MARKET_PATH.exists():
        return {
            "exists": False,
            "rows": 0,
            "dates": 0,
            "all_columns_flat": True,
            "column_unique_counts": {},
        }

    market = pd.read_parquet(LLM_MARKET_PATH).copy()
    market["time"] = pd.to_datetime(market["time"], errors="coerce").dt.normalize()
    market = market.loc[market["time"].dt.year.between(2023, 2025)].copy()
    unique_counts = {
        column: int(pd.Series(market[column]).nunique(dropna=False))
        for column in MARKET_AUDIT_COLUMNS
        if column in market.columns
    }
    all_flat = bool(unique_counts) and all(count <= 1 for count in unique_counts.values())
    return {
        "exists": True,
        "rows": int(len(market)),
        "dates": int(market["time"].nunique()) if not market.empty else 0,
        "all_columns_flat": all_flat,
        "column_unique_counts": unique_counts,
    }


def _build_attention_proxy_panel() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted(RAW_NEWS_DIR.glob("202[3-5]-*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            raw_articles = sum(1 for _ in handle)
        rows.append({"time": pd.Timestamp(path.stem), "raw_articles": raw_articles})
    raw = pd.DataFrame(rows)

    first_public_path = resolve_summary_artifact(H310_SUMMARY_PATH, "combined_first_public")
    first_public = pd.read_parquet(
        first_public_path,
        columns=["time", "ticker", "event_family", "article_count_1d"],
    ).copy()
    first_public["time"] = pd.to_datetime(first_public["time"], errors="coerce").dt.normalize()
    first_public = first_public.loc[first_public["time"].dt.year.between(2023, 2025)].copy()

    mapped = (
        first_public.groupby("time", as_index=False)
        .agg(
            mapped_event_rows=("ticker", "size"),
            mapped_event_tickers=("ticker", "nunique"),
            mapped_event_families=("event_family", "nunique"),
            mapped_event_articles=("article_count_1d", "sum"),
        )
    )

    panel = raw.merge(mapped, on="time", how="left")
    for column in ("mapped_event_rows", "mapped_event_tickers", "mapped_event_families", "mapped_event_articles"):
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0.0)
    panel["mapped_share"] = panel["mapped_event_rows"].div(panel["raw_articles"].clip(lower=1.0))
    panel["year"] = panel["time"].dt.year

    dev = panel.loc[panel["year"].eq(2023)].copy()
    raw_high = float(dev["raw_articles"].quantile(2 / 3))
    breadth_high = float(dev["mapped_event_tickers"].quantile(2 / 3))
    mapped_share_low = float(dev["mapped_share"].quantile(1 / 3))

    panel["high_raw_load"] = panel["raw_articles"] >= raw_high
    panel["high_event_breadth"] = panel["mapped_event_tickers"] >= breadth_high
    panel["high_distraction"] = (panel["raw_articles"] >= raw_high) & (panel["mapped_share"] <= mapped_share_low)

    panel["raw_high_threshold"] = raw_high
    panel["breadth_high_threshold"] = breadth_high
    panel["mapped_share_low_threshold"] = mapped_share_low
    return panel.sort_values("time").reset_index(drop=True)


def _daily_state_lift(frame: pd.DataFrame, state_col: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for time, group in frame.groupby("time", sort=True):
        active = group.loc[group[state_col].fillna(False).astype(bool)].copy()
        if active.empty:
            continue
        actual_mean = _safe_float(group["actual"].mean())
        active_actual_mean = _safe_float(active["actual"].mean())
        fwd5_mean = _safe_float(group["fwd_rel_5d"].mean())
        active_fwd5_mean = _safe_float(active["fwd_rel_5d"].mean())
        rows.append(
            {
                "time": pd.Timestamp(time),
                "active_rows": int(len(active)),
                "actual_lift": None if actual_mean is None or active_actual_mean is None else float(active_actual_mean - actual_mean),
                "fwd5_lift": None if fwd5_mean is None or active_fwd5_mean is None else float(active_fwd5_mean - fwd5_mean),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["lag_gap"] = pd.to_numeric(out["fwd5_lift"], errors="coerce") - pd.to_numeric(out["actual_lift"], errors="coerce")
    return out


def _phase_proxy_summary(frame: pd.DataFrame, state_col: str, proxy_col: str, phase: str, is_high: bool) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    scoped = scoped.loc[scoped[proxy_col].fillna(False).astype(bool).eq(bool(is_high))].copy()
    daily = _daily_state_lift(scoped, state_col)
    return {
        "proxy_days": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "active_rows": int(scoped.loc[scoped[state_col].fillna(False).astype(bool)].shape[0]),
        "active_days": int(len(daily)),
        "avg_actual_lift": _safe_float(daily["actual_lift"].mean()) if not daily.empty else None,
        "avg_fwd5_lift": _safe_float(daily["fwd5_lift"].mean()) if not daily.empty else None,
        "avg_lag_gap": _safe_float(daily["lag_gap"].mean()) if not daily.empty else None,
    }


def _evaluate(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for state_col, state_note in STATE_SPECS:
        for proxy_col, proxy_note, proxy_type in PROXY_SPECS:
            row = {
                "state_name": state_col,
                "state_note": state_note,
                "proxy_name": proxy_col,
                "proxy_note": proxy_note,
                "proxy_type": proxy_type,
            }
            for phase in ("dev", "validation", "confirmation"):
                high = _phase_proxy_summary(frame, state_col, proxy_col, phase, True)
                control = _phase_proxy_summary(frame, state_col, proxy_col, phase, False)
                for prefix, summary in (("high", high), ("control", control)):
                    for key, value in summary.items():
                        row[f"{phase}_{prefix}_{key}"] = value

                lag_gap_delta = (_safe_float(high["avg_lag_gap"]) or 0.0) - (_safe_float(control["avg_lag_gap"]) or 0.0)
                fwd5_delta = (_safe_float(high["avg_fwd5_lift"]) or 0.0) - (_safe_float(control["avg_fwd5_lift"]) or 0.0)
                actual_delta = (_safe_float(high["avg_actual_lift"]) or 0.0) - (_safe_float(control["avg_actual_lift"]) or 0.0)
                row[f"{phase}_lag_gap_delta"] = lag_gap_delta
                row[f"{phase}_fwd5_lift_delta"] = fwd5_delta
                row[f"{phase}_actual_lift_delta"] = actual_delta

            validation_pass = bool(
                (row["validation_high_active_days"] or 0) >= PASS_MIN_DAYS
                and row["validation_lag_gap_delta"] >= PASS_MIN_LAG_DELTA
                and row["validation_fwd5_lift_delta"] >= PASS_MIN_FWD5_DELTA
            )
            confirmation_pass = bool(
                (row["confirmation_high_active_days"] or 0) >= PASS_MIN_DAYS
                and row["confirmation_lag_gap_delta"] >= PASS_MIN_LAG_DELTA
                and row["confirmation_fwd5_lift_delta"] >= PASS_MIN_FWD5_DELTA
            )
            mixed_condition = bool(
                (row["validation_high_active_days"] or 0) >= MIN_ACTIVE_DAYS
                and (row["confirmation_high_active_days"] or 0) >= MIN_ACTIVE_DAYS
                and row["validation_lag_gap_delta"] >= MIXED_MIN_LAG_DELTA
                and row["confirmation_lag_gap_delta"] >= MIXED_MIN_LAG_DELTA
                and (
                    row["validation_fwd5_lift_delta"] > 0.0
                    or row["confirmation_fwd5_lift_delta"] > 0.0
                )
            )

            if validation_pass and confirmation_pass:
                decision = "PASSED"
            elif mixed_condition:
                decision = "MIXED"
            else:
                decision = "FAILED"
            row["candidate_decision"] = decision
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    market_audit = _audit_market_daily_surface()
    attention_proxy = _build_attention_proxy_panel()
    base_panel = _load_base_panel().merge(
        attention_proxy[
            [
                "time",
                "raw_articles",
                "mapped_event_rows",
                "mapped_event_tickers",
                "mapped_share",
                "high_raw_load",
                "high_event_breadth",
                "high_distraction",
            ]
        ],
        on="time",
        how="left",
        validate="many_to_one",
    )
    results = _evaluate(base_panel)

    details_path = DETAILS_DIR / f"{ts}_research_branch_attention_congestion_router_details.json"
    proxy_panel_path = OUT_DIR / f"{ts}_h318_attention_congestion_router_daily_proxies.parquet"
    result_table_path = OUT_DIR / f"{ts}_h318_attention_congestion_router_results.parquet"

    attention_proxy.to_parquet(proxy_panel_path, index=False)
    results.to_parquet(result_table_path, index=False)

    best_primary = (
        results.loc[results["state_name"].eq("event_today_novel20")]
        .sort_values(
            ["candidate_decision", "validation_lag_gap_delta", "confirmation_lag_gap_delta"],
            ascending=[True, False, False],
        )
        .iloc[0]
    )
    best_secondary = (
        results.loc[results["state_name"].eq("recent5_low_repeat20")]
        .sort_values(
            ["candidate_decision", "validation_lag_gap_delta", "confirmation_lag_gap_delta"],
            ascending=[True, False, False],
        )
        .iloc[0]
    )

    primary_pass = bool(best_primary["candidate_decision"] == "PASSED")
    any_mixed = bool((results["candidate_decision"] == "MIXED").any())
    if primary_pass:
        verdict = "PASSED"
        branch_decision = (
            "Attention congestion looks real enough to keep as a routed offline branch. "
            "Advance to a sharper additive or external-attention follow-up."
        )
    elif any_mixed:
        verdict = "MIXED"
        branch_decision = (
            "Raw archive attention proxies show only unstable local separation. "
            "Keep the idea as offline evidence only and wait for richer market-attention data "
            "before reopening a broader router."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The published market-attention surface is flat on 2023-2025 and the raw proxy fallback "
            "does not produce a stable slow-diffusion pattern. Park attention congestion on the "
            "current local data stack."
        )

    detail_payload = {
        "market_daily_audit": market_audit,
        "proxy_thresholds": {
            "raw_high_threshold": _safe_float(attention_proxy["raw_high_threshold"].iloc[0]) if not attention_proxy.empty else None,
            "breadth_high_threshold": _safe_float(attention_proxy["breadth_high_threshold"].iloc[0]) if not attention_proxy.empty else None,
            "mapped_share_low_threshold": _safe_float(attention_proxy["mapped_share_low_threshold"].iloc[0]) if not attention_proxy.empty else None,
        },
        "best_primary": _json_safe(best_primary.to_dict()),
        "best_secondary": _json_safe(best_secondary.to_dict()),
        "results": _json_safe(results.to_dict(orient="records")),
        "branch_decision": branch_decision,
    }
    details_path.write_text(json.dumps(detail_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "market_daily_surface_flat_2023_2025": bool(market_audit["all_columns_flat"]),
        "market_daily_rows": market_audit["rows"],
        "best_primary_proxy": best_primary["proxy_name"],
        "best_primary_decision": best_primary["candidate_decision"],
        "best_primary_validation_lag_gap_delta": _safe_float(best_primary["validation_lag_gap_delta"]),
        "best_primary_confirmation_lag_gap_delta": _safe_float(best_primary["confirmation_lag_gap_delta"]),
        "best_primary_validation_fwd5_lift_delta": _safe_float(best_primary["validation_fwd5_lift_delta"]),
        "best_primary_confirmation_fwd5_lift_delta": _safe_float(best_primary["confirmation_fwd5_lift_delta"]),
        "best_secondary_proxy": best_secondary["proxy_name"],
        "best_secondary_decision": best_secondary["candidate_decision"],
        "proxy_days_2023_2025": int(attention_proxy["time"].nunique()) if not attention_proxy.empty else 0,
    }
    artifacts = {
        "daily_proxy_panel": proxy_panel_path,
        "result_table": result_table_path,
        "details": details_path,
    }
    metadata = {
        "question": "Do market-wide attention-congestion states change the H310 event-v2 response?",
        "protocol": {
            "dev": "2023",
            "validation": "2024",
            "confirmation": "2025",
        },
        "state_specs": [name for name, _note in STATE_SPECS],
        "proxy_specs": [name for name, _note, _kind in PROXY_SPECS],
        "note": "The intended xs_llm_news_market_daily representation was audited first; raw archive proxies were used because the published surface is flat on 2023-2025.",
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_attention_congestion_router",
        name="attention_congestion_router",
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
