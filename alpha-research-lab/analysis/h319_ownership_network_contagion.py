"""
H319: ownership-network contagion audit.

Question:
    Do insider / holder links create a real cross-ticker spillover state, where
    a ticker with no own direct event or insider shock still benefits when a
    linked neighbor gets one?

Design:
    - build a static graph from pre-2023 insider / holder link evidence
    - use three graph variants:
      - shared ShareHolderCode
      - shared TransactionMan name
      - union of code + name + tiny issuer-family alias layer
    - evaluate only pure target rows with no own direct event-v2 or C5 shock
    - compare active neighbor-shock rows against the same-day eligible universe
      on both 1d (`actual`) and 5d forward relative return
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h310_event_v2_predictive_rescreen import _build_h310_state_panel
from analysis.h313_issuer_family_spillover_graph import _derive_ambiguous_family_aliases
from src.additive_selector_research import resolve_summary_artifact
from src.future_return_research import load_future_rel_5d
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


H309_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_issuer_lexicon_event_surface.json"
H310_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_event_v2_predictive_rescreen.json"
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
INSIDER_RAW_PATH = data_path("features/xs_insider_deals_raw.parquet")
INSIDER_FEATURE_PATH = data_path("features/xs_insider_quality_features.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

GRAPH_VARIANTS = (
    ("code", "Shared ShareHolderCode graph"),
    ("name", "Shared TransactionMan graph"),
    ("union", "Union graph: code + name + family aliases"),
)

STATE_SPECS = (
    ("nbr_event", "Neighbor has same-day event-v2 shock"),
    ("nbr_c5", "Neighbor has positive C5 shock"),
    ("nbr_any", "Neighbor has either same-day event-v2 or positive C5 shock"),
)

ENTITY_MIN_DEGREE = 2
ENTITY_MAX_DEGREE = 20
PASS_MIN_ACTIVE_DAYS = 120
PASS_MIN_ACTUAL_LIFT = 0.010
PASS_MIN_FWD5_LIFT = 0.001
MIXED_MIN_ACTIVE_DAYS = 120
MIXED_MIN_ACTUAL_LIFT = 0.0


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


def _load_listing_metadata() -> pd.DataFrame:
    listing_path = resolve_summary_artifact(H309_SUMMARY_PATH, "listing_metadata")
    listing = pd.read_parquet(listing_path).copy()
    listing["symbol"] = listing["symbol"].astype(str).str.upper()
    return listing


def _normalize_name(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.upper()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def _build_graph_edges(raw: pd.DataFrame, key_col: str, graph_kind: str) -> tuple[pd.DataFrame, dict[str, set[str]]]:
    degree = raw.groupby(key_col)["ticker"].nunique()
    valid = degree.loc[degree.between(ENTITY_MIN_DEGREE, ENTITY_MAX_DEGREE)].index
    scoped = raw.loc[raw[key_col].isin(valid) & raw[key_col].ne(""), ["ticker", key_col]].drop_duplicates().copy()

    edge_rows: list[dict[str, object]] = []
    neighbors: defaultdict[str, set[str]] = defaultdict(set)
    for entity_id, group in scoped.groupby(key_col, sort=True):
        tickers = sorted(set(group["ticker"].astype(str)))
        if len(tickers) < 2:
            continue
        for ticker in tickers:
            peers = [peer for peer in tickers if peer != ticker]
            neighbors[ticker].update(peers)
            for peer in peers:
                edge_rows.append(
                    {
                        "graph_kind": graph_kind,
                        "entity_id": str(entity_id),
                        "ticker": ticker,
                        "peer_ticker": peer,
                        "entity_degree": int(len(tickers)),
                    }
                )
    return pd.DataFrame(edge_rows), neighbors


def _build_family_neighbors(listing: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, set[str]]]:
    aliases = _derive_ambiguous_family_aliases(listing)
    edge_rows: list[dict[str, object]] = []
    neighbors: defaultdict[str, set[str]] = defaultdict(set)
    for row in aliases.itertuples(index=False):
        tickers = sorted(set(map(str, row.family_tickers)))
        if len(tickers) < 2:
            continue
        for ticker in tickers:
            peers = [peer for peer in tickers if peer != ticker]
            neighbors[ticker].update(peers)
            for peer in peers:
                edge_rows.append(
                    {
                        "graph_kind": "family",
                        "entity_id": str(row.family_alias),
                        "ticker": ticker,
                        "peer_ticker": peer,
                        "entity_degree": int(len(tickers)),
                    }
                )
    return pd.DataFrame(edge_rows), neighbors


def _union_neighbors(*neighbor_maps: dict[str, set[str]]) -> dict[str, set[str]]:
    union: defaultdict[str, set[str]] = defaultdict(set)
    for mapping in neighbor_maps:
        for ticker, peers in mapping.items():
            union[ticker].update(peers)
    return union


def _load_target_panel() -> pd.DataFrame:
    base = pd.read_parquet(S1_PATH, columns=["time", "ticker", "actual"]).copy()
    base["time"] = pd.to_datetime(base["time"], errors="coerce").dt.normalize()
    base = base.loc[base["time"].dt.year.between(2023, 2025)].copy()

    first_public_path = resolve_summary_artifact(H310_SUMMARY_PATH, "combined_first_public")
    state_panel, _ = _build_h310_state_panel(base[["time", "ticker"]].drop_duplicates(), first_public_path)

    c5 = pd.read_parquet(
        INSIDER_FEATURE_PATH,
        columns=["trading_day", "ticker", "xs_ins_relative_size_5d"],
    ).rename(columns={"trading_day": "time"})
    c5["time"] = pd.to_datetime(c5["time"], errors="coerce").dt.normalize()
    c5 = c5.loc[c5["time"].dt.year.between(2023, 2025)].copy()
    c5["c5_pos"] = pd.to_numeric(c5["xs_ins_relative_size_5d"], errors="coerce").fillna(0.0) > 0.0

    panel = (
        base.merge(
            state_panel[["time", "ticker", "event_today_novel20", "recent5_low_repeat20"]],
            on=["time", "ticker"],
            how="left",
            validate="one_to_one",
        )
        .merge(c5[["time", "ticker", "c5_pos"]], on=["time", "ticker"], how="left", validate="one_to_one")
        .merge(load_future_rel_5d(start_year=2023, end_year=2025), on=["time", "ticker"], how="left", validate="one_to_one")
        .sort_values(["time", "ticker"])
        .reset_index(drop=True)
    )
    for column in ("event_today_novel20", "recent5_low_repeat20", "c5_pos"):
        panel[column] = panel[column].fillna(False).astype(bool)
    panel["own_direct"] = panel[["event_today_novel20", "recent5_low_repeat20", "c5_pos"]].any(axis=1)
    return panel


def _build_neighbor_panel(
    panel: pd.DataFrame,
    graph_variant: str,
    neighbors: dict[str, set[str]],
) -> pd.DataFrame:
    by_day_event = {
        time: set(group.loc[group["event_today_novel20"], "ticker"].astype(str))
        for time, group in panel.groupby("time", sort=True)
    }
    by_day_c5 = {
        time: set(group.loc[group["c5_pos"], "ticker"].astype(str))
        for time, group in panel.groupby("time", sort=True)
    }

    rows: list[dict[str, object]] = []
    for day, group in panel.groupby("time", sort=True):
        event_tickers = by_day_event[day]
        c5_tickers = by_day_c5[day]
        for row in group.itertuples(index=False):
            nbr = neighbors.get(str(row.ticker), set())
            if not nbr or bool(row.own_direct):
                continue
            rows.append(
                {
                    "graph_variant": graph_variant,
                    "time": pd.Timestamp(day),
                    "ticker": str(row.ticker),
                    "actual": float(row.actual),
                    "fwd_rel_5d": _safe_float(row.fwd_rel_5d),
                    "degree": int(len(nbr)),
                    "nbr_event": bool(nbr & event_tickers),
                    "nbr_c5": bool(nbr & c5_tickers),
                    "nbr_any": bool((nbr & event_tickers) or (nbr & c5_tickers)),
                }
            )
    return pd.DataFrame(rows)


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
    return pd.DataFrame(rows)


def _phase_summary(frame: pd.DataFrame, state_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    daily = _daily_state_lift(scoped, state_col)
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "active_rows": int(scoped.loc[scoped[state_col].fillna(False).astype(bool)].shape[0]),
        "active_days": int(len(daily)),
        "avg_actual_lift": _safe_float(daily["actual_lift"].mean()) if not daily.empty else None,
        "avg_fwd5_lift": _safe_float(daily["fwd5_lift"].mean()) if not daily.empty else None,
        "avg_active_names_per_day": _safe_float(daily["active_rows"].mean()) if not daily.empty else None,
        "mean_degree": _safe_float(scoped["degree"].mean()) if not scoped.empty else None,
    }


def _evaluate(neighbor_panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for graph_variant, graph_note in GRAPH_VARIANTS:
        graph_frame = neighbor_panel.loc[neighbor_panel["graph_variant"].eq(graph_variant)].copy()
        for state_col, state_note in STATE_SPECS:
            row = {
                "graph_variant": graph_variant,
                "graph_note": graph_note,
                "state_name": state_col,
                "state_note": state_note,
            }
            for phase in ("dev", "validation", "confirmation"):
                summary = _phase_summary(graph_frame, state_col, phase)
                for key, value in summary.items():
                    row[f"{phase}_{key}"] = value

            rows.append(row)

    results = pd.DataFrame(rows)
    union_rows = results.loc[results["graph_variant"].eq("union")].copy()
    for idx, row in results.iterrows():
        if row["graph_variant"] == "union":
            validation_pass = bool(
                (row["validation_active_days"] or 0) >= PASS_MIN_ACTIVE_DAYS
                and (_safe_float(row["validation_avg_actual_lift"]) or 0.0) >= PASS_MIN_ACTUAL_LIFT
                and (_safe_float(row["validation_avg_fwd5_lift"]) or 0.0) >= PASS_MIN_FWD5_LIFT
            )
            confirmation_pass = bool(
                (row["confirmation_active_days"] or 0) >= PASS_MIN_ACTIVE_DAYS
                and (_safe_float(row["confirmation_avg_actual_lift"]) or 0.0) >= PASS_MIN_ACTUAL_LIFT
                and (_safe_float(row["confirmation_avg_fwd5_lift"]) or 0.0) >= PASS_MIN_FWD5_LIFT
            )
            mixed_condition = bool(
                not (validation_pass and confirmation_pass)
                and (row["validation_active_days"] or 0) >= MIXED_MIN_ACTIVE_DAYS
                and (row["confirmation_active_days"] or 0) >= MIXED_MIN_ACTIVE_DAYS
                and (_safe_float(row["validation_avg_actual_lift"]) or 0.0) > MIXED_MIN_ACTUAL_LIFT
                and (_safe_float(row["confirmation_avg_actual_lift"]) or 0.0) > MIXED_MIN_ACTUAL_LIFT
                and (_safe_float(row["validation_avg_fwd5_lift"]) or 0.0) >= 0.0
                and (_safe_float(row["confirmation_avg_fwd5_lift"]) or 0.0) >= 0.0
                and (
                    (_safe_float(row["validation_avg_actual_lift"]) or 0.0) >= 0.005
                    or (_safe_float(row["confirmation_avg_actual_lift"]) or 0.0) >= 0.005
                )
            )
            decision = "PASSED" if validation_pass and confirmation_pass else "MIXED" if mixed_condition else "FAILED"
        else:
            decision = "DIAGNOSTIC"
        results.loc[idx, "candidate_decision"] = decision

    if not union_rows.empty:
        pass
    return results


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    raw = pd.read_parquet(INSIDER_RAW_PATH).copy()
    raw["published_date"] = pd.to_datetime(raw["published_date"], errors="coerce").dt.normalize()
    raw = raw.loc[raw["published_date"].dt.year.between(2015, 2022)].copy()
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    raw["code_key"] = raw["ShareHolderCode"].fillna("").astype(str).str.upper().str.strip()
    raw["name_key"] = _normalize_name(raw["TransactionMan"])

    code_edges, code_neighbors = _build_graph_edges(raw, "code_key", "code")
    name_edges, name_neighbors = _build_graph_edges(raw, "name_key", "name")
    family_edges, family_neighbors = _build_family_neighbors(_load_listing_metadata())
    union_neighbors = _union_neighbors(code_neighbors, name_neighbors, family_neighbors)

    panel = _load_target_panel()
    code_panel = _build_neighbor_panel(panel, "code", code_neighbors)
    name_panel = _build_neighbor_panel(panel, "name", name_neighbors)
    union_panel = _build_neighbor_panel(panel, "union", union_neighbors)
    neighbor_panel = pd.concat([code_panel, name_panel, union_panel], ignore_index=True)

    results = _evaluate(neighbor_panel)
    union_results = results.loc[results["graph_variant"].eq("union")].copy()
    decision_rank = {"PASSED": 0, "MIXED": 1, "FAILED": 2}
    union_results["decision_rank"] = union_results["candidate_decision"].map(decision_rank).fillna(9)
    best_union = union_results.sort_values(
        ["decision_rank", "validation_avg_actual_lift", "confirmation_avg_actual_lift"],
        ascending=[True, False, False],
    ).iloc[0]

    if (union_results["candidate_decision"] == "PASSED").any():
        verdict = "PASSED"
        branch_decision = (
            "The ownership-network graph carries a real pure-spillover state. "
            "Advance to a sharper weighted or additive follow-up."
        )
    elif (union_results["candidate_decision"] == "MIXED").any():
        verdict = "MIXED"
        branch_decision = (
            "Ownership links create weak broad spillover, especially around neighbor C5 activity, "
            "but the effect is too small or unstable to promote. Keep it as offline evidence only."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The predeclared ownership graph does not produce a stable pure-spillover state on the "
            "current local stack. Park the branch unless a richer graph source becomes available."
        )

    edge_table = pd.concat([code_edges, name_edges, family_edges], ignore_index=True)
    edge_path = OUT_DIR / f"{ts}_h319_ownership_network_contagion_edges.parquet"
    panel_path = OUT_DIR / f"{ts}_h319_ownership_network_contagion_panel.parquet"
    results_path = OUT_DIR / f"{ts}_h319_ownership_network_contagion_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_research_branch_ownership_network_contagion_details.json"

    edge_table.to_parquet(edge_path, index=False)
    neighbor_panel.to_parquet(panel_path, index=False)
    results.to_parquet(results_path, index=False)

    graph_summary = {
        "code_tickers": int(len(code_neighbors)),
        "name_tickers": int(len(name_neighbors)),
        "family_tickers": int(len(family_neighbors)),
        "union_tickers": int(len(union_neighbors)),
        "code_edges_directed": int(len(code_edges)),
        "name_edges_directed": int(len(name_edges)),
        "family_edges_directed": int(len(family_edges)),
    }
    detail_payload = {
        "branch_decision": branch_decision,
        "graph_summary": graph_summary,
        "best_union": _json_safe(best_union.to_dict()),
        "results": _json_safe(results.to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(detail_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "best_union_state": best_union["state_name"],
        "best_union_decision": best_union["candidate_decision"],
        "best_union_validation_actual_lift": _safe_float(best_union["validation_avg_actual_lift"]),
        "best_union_validation_fwd5_lift": _safe_float(best_union["validation_avg_fwd5_lift"]),
        "best_union_confirmation_actual_lift": _safe_float(best_union["confirmation_avg_actual_lift"]),
        "best_union_confirmation_fwd5_lift": _safe_float(best_union["confirmation_avg_fwd5_lift"]),
        "union_graph_tickers": graph_summary["union_tickers"],
        "union_panel_rows": int(len(union_panel)),
    }
    artifacts = {
        "edge_table": edge_path,
        "neighbor_panel": panel_path,
        "results": results_path,
        "details": details_path,
    }
    metadata = {
        "question": "Do pre-2023 ownership links create pure cross-ticker spillover after excluding own direct event/insider shocks?",
        "protocol": {"dev": "2023", "validation": "2024", "confirmation": "2025"},
        "graph_degree_gate": {"min": ENTITY_MIN_DEGREE, "max": ENTITY_MAX_DEGREE},
        "note": "The union graph includes shared holder-code links, shared transaction-name links, and the tiny issuer-family alias layer.",
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_ownership_network_contagion",
        name="ownership_network_contagion",
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
