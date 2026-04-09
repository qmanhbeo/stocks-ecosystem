"""
H304: execution spillover substitutes audit.

Question:
    When the raw top-ranked name is blocked or falls into the same thin bucket
    that broke H296, does the tradable edge spill into the nearest eligible
    same-family or same-sector substitute, or does it simply disappear?
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

from src.entry_alpha_research import assign_entry_thesis_family
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


CANDIDATE_PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")
LABELS_PATH = data_path("features/entry_alpha/entry_labels_cycle5.parquet")
SECTOR_PATH = data_path("features/sector_classification.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

PROTOCOL = ResearchProtocol(
    dev_start_year=2019,
    dev_end_year=2022,
    validation_start_year=2023,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

HOSE_UNIVERSE_SIZE = 394
H296_MID_TOP_K = 200
THIN_ADV20_RANK_MAX = 1.0 - (H296_MID_TOP_K / HOSE_UNIVERSE_SIZE)
SUBSTITUTE_RANK_MIN = 2
SUBSTITUTE_RANK_MAX = 10
PASS_MIN_VALIDATION_DATES = 80
PASS_MIN_CONFIRMATION_DATES = 40
PASS_VALIDATION_EDGE = 0.003
PASS_CONFIRMATION_EDGE = 0.001
PASS_VALIDATION_HIT = 0.52
PASS_CONFIRMATION_HIT = 0.50

STATE_SPECS = (
    ("blocked_top1", "Top1 blocked", lambda row: bool(not row["top1_buyable"])),
    ("thin_top1_h296", "Top1 in H296-thin bucket", lambda row: bool(row["top1_thin_h296"])),
    (
        "blocked_or_thin_top1",
        "Top1 blocked or H296-thin",
        lambda row: bool((not row["top1_buyable"]) or row["top1_thin_h296"]),
    ),
)

RELATION_SPECS = (
    ("same_family", "Same thesis family"),
    ("same_sector", "Same sector"),
    ("same_family_or_sector", "Same family or sector"),
)


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
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


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def load_panel() -> pd.DataFrame:
    candidate_cols = [
        "time",
        "ticker",
        "candidate_pool_rank",
        "selection_score",
        "can_buy_next_open",
        "xs_adv20_rank",
    ]
    panel = pd.read_parquet(CANDIDATE_PANEL_PATH, columns=candidate_cols).copy()
    labels = pd.read_parquet(
        LABELS_PATH,
        columns=["time", "ticker", "cycle_relative_return_vs_vnindex"],
    ).copy()
    sectors = pd.read_parquet(SECTOR_PATH)[["symbol", "icb_name2"]].rename(
        columns={"symbol": "ticker", "icb_name2": "sector_label"}
    )

    panel["time"] = pd.to_datetime(panel["time"], errors="coerce")
    labels["time"] = pd.to_datetime(labels["time"], errors="coerce")
    panel = panel.loc[panel["time"].dt.year.between(2019, 2025)].copy()
    labels = labels.loc[labels["time"].dt.year.between(2019, 2025)].copy()

    panel = assign_entry_thesis_family(panel)
    panel = panel.merge(sectors, on="ticker", how="left", validate="many_to_one")
    panel = panel.merge(labels, on=["time", "ticker"], how="left", validate="one_to_one")
    panel["can_buy_next_open"] = panel["can_buy_next_open"].fillna(False).astype(bool)
    panel["candidate_pool_rank"] = pd.to_numeric(panel["candidate_pool_rank"], errors="coerce")
    panel["xs_adv20_rank"] = pd.to_numeric(panel["xs_adv20_rank"], errors="coerce")
    panel["cycle_relative_return_vs_vnindex"] = pd.to_numeric(
        panel["cycle_relative_return_vs_vnindex"], errors="coerce"
    )
    return panel


def _build_state_table(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for time, group in panel.groupby("time", sort=True):
        top1 = group.loc[group["candidate_pool_rank"] == 1].copy()
        if top1.empty:
            continue
        row = top1.iloc[0]
        rows.append(
            {
                "time": pd.Timestamp(time),
                "top1_ticker": str(row["ticker"]),
                "top1_buyable": bool(row["can_buy_next_open"]),
                "top1_thin_h296": bool((_safe_float(row["xs_adv20_rank"]) or np.inf) < THIN_ADV20_RANK_MAX),
                "top1_family": row.get("entry_thesis_family"),
                "top1_sector": row.get("sector_label"),
            }
        )
    return pd.DataFrame(rows)


def _relation_mask(substitutes: pd.DataFrame, state_row: pd.Series, relation_name: str) -> pd.Series:
    if relation_name == "same_family":
        return substitutes["entry_thesis_family"].astype(object) == state_row.get("top1_family")
    if relation_name == "same_sector":
        return substitutes["sector_label"].astype(object) == state_row.get("top1_sector")
    if relation_name == "same_family_or_sector":
        return (
            (substitutes["entry_thesis_family"].astype(object) == state_row.get("top1_family"))
            | (substitutes["sector_label"].astype(object) == state_row.get("top1_sector"))
        )
    raise ValueError(f"Unknown relation {relation_name!r}")


def _build_date_level_substitute_rows(panel: pd.DataFrame, state_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    by_time = {pd.Timestamp(time): frame.sort_values("candidate_pool_rank").copy() for time, frame in panel.groupby("time", sort=True)}

    for _, state_row in state_table.iterrows():
        date = pd.Timestamp(state_row["time"])
        date_panel = by_time.get(date)
        if date_panel is None or date_panel.empty:
            continue
        substitutes = date_panel.loc[
            (date_panel["candidate_pool_rank"] >= SUBSTITUTE_RANK_MIN)
            & (date_panel["candidate_pool_rank"] <= SUBSTITUTE_RANK_MAX)
            & date_panel["can_buy_next_open"]
        ].copy()
        if substitutes.empty:
            continue

        for state_name, state_label, state_fn in STATE_SPECS:
            if not bool(state_fn(state_row)):
                continue
            for relation_name, relation_label in RELATION_SPECS:
                in_group = substitutes.loc[_relation_mask(substitutes, state_row, relation_name)].copy()
                out_group = substitutes.loc[~_relation_mask(substitutes, state_row, relation_name)].copy()
                if in_group.empty or out_group.empty:
                    continue
                in_group = in_group.sort_values("candidate_pool_rank")
                out_group = out_group.sort_values("candidate_pool_rank")
                chosen = in_group.iloc[0]
                other_top = out_group.iloc[0]
                other_mean = pd.to_numeric(out_group["cycle_relative_return_vs_vnindex"], errors="coerce").mean()
                chosen_ret = _safe_float(chosen.get("cycle_relative_return_vs_vnindex"))
                other_top_ret = _safe_float(other_top.get("cycle_relative_return_vs_vnindex"))
                if chosen_ret is None or other_top_ret is None or pd.isna(other_mean):
                    continue
                rows.append(
                    {
                        "time": date,
                        "state_name": state_name,
                        "state_label": state_label,
                        "relation_name": relation_name,
                        "relation_label": relation_label,
                        "top1_ticker": state_row["top1_ticker"],
                        "top1_family": state_row.get("top1_family"),
                        "top1_sector": state_row.get("top1_sector"),
                        "chosen_ticker": str(chosen["ticker"]),
                        "chosen_rank": int(chosen["candidate_pool_rank"]),
                        "chosen_cycle_rel": float(chosen_ret),
                        "other_top_ticker": str(other_top["ticker"]),
                        "other_top_rank": int(other_top["candidate_pool_rank"]),
                        "other_top_cycle_rel": float(other_top_ret),
                        "other_mean_cycle_rel": float(other_mean),
                        "edge_vs_other_top": float(chosen_ret - other_top_ret),
                        "edge_vs_other_mean": float(chosen_ret - float(other_mean)),
                        "eligible_substitute_count": int(len(substitutes)),
                        "same_group_count": int(len(in_group)),
                        "other_group_count": int(len(out_group)),
                    }
                )
    return pd.DataFrame(rows)


def _phase_summary(frame: pd.DataFrame, *, edge_column: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    edge = pd.to_numeric(scoped[edge_column], errors="coerce").dropna()
    return {
        "mean_edge": float(edge.mean()) if not edge.empty else None,
        "hit_rate": float((edge > 0.0).mean()) if not edge.empty else None,
        "dates": int(len(edge)),
        "avg_same_group_count": float(pd.to_numeric(scoped["same_group_count"], errors="coerce").mean()) if not scoped.empty else None,
        "avg_other_group_count": float(pd.to_numeric(scoped["other_group_count"], errors="coerce").mean()) if not scoped.empty else None,
        "avg_chosen_rank": float(pd.to_numeric(scoped["chosen_rank"], errors="coerce").mean()) if not scoped.empty else None,
        "avg_other_top_rank": float(pd.to_numeric(scoped["other_top_rank"], errors="coerce").mean()) if not scoped.empty else None,
    }


def _decision_row(frame: pd.DataFrame, *, state_name: str, state_label: str, relation_name: str, relation_label: str) -> dict[str, object]:
    scoped = frame.loc[
        (frame["state_name"] == state_name)
        & (frame["relation_name"] == relation_name)
    ].copy()
    row = {
        "state_name": state_name,
        "state_label": state_label,
        "relation_name": relation_name,
        "relation_label": relation_label,
        "total_dates": int(len(scoped)),
    }
    for phase in ("dev", "validation", "confirmation"):
        top_summary = _phase_summary(scoped, edge_column="edge_vs_other_top", phase=phase)
        mean_summary = _phase_summary(scoped, edge_column="edge_vs_other_mean", phase=phase)
        for key, value in top_summary.items():
            row[f"{phase}_top_{key}"] = value
        for key, value in mean_summary.items():
            row[f"{phase}_mean_{key}"] = value
    return row


def _pass_condition(row: pd.Series) -> bool:
    return bool(
        (_safe_float(row.get("validation_top_mean_edge")) or -np.inf) >= PASS_VALIDATION_EDGE
        and (_safe_float(row.get("confirmation_top_mean_edge")) or -np.inf) >= PASS_CONFIRMATION_EDGE
        and (_safe_float(row.get("validation_top_hit_rate")) or -np.inf) >= PASS_VALIDATION_HIT
        and (_safe_float(row.get("confirmation_top_hit_rate")) or -np.inf) >= PASS_CONFIRMATION_HIT
        and int(pd.to_numeric(row.get("validation_top_dates"), errors="coerce") or 0) >= PASS_MIN_VALIDATION_DATES
        and int(pd.to_numeric(row.get("confirmation_top_dates"), errors="coerce") or 0) >= PASS_MIN_CONFIRMATION_DATES
    )


def _mixed_condition(row: pd.Series) -> bool:
    return bool(
        (_safe_float(row.get("validation_mean_mean_edge")) or -np.inf) > 0.0
        or (_safe_float(row.get("validation_top_mean_edge")) or -np.inf) > 0.0
        or (_safe_float(row.get("confirmation_top_mean_edge")) or -np.inf) > 0.0
    )


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    for column in (
        "validation_top_mean_edge",
        "confirmation_top_mean_edge",
        "validation_mean_mean_edge",
        "confirmation_mean_mean_edge",
        "validation_top_hit_rate",
        "confirmation_top_hit_rate",
    ):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work["_decision_rank"] = work.apply(lambda row: 2 if _pass_condition(row) else 1 if _mixed_condition(row) else 0, axis=1)
    return work.sort_values(
        by=[
            "_decision_rank",
            "validation_top_mean_edge",
            "confirmation_top_mean_edge",
            "validation_mean_mean_edge",
            "total_dates",
            "state_name",
            "relation_name",
        ],
        ascending=[False, False, False, False, False, True, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def main() -> None:
    panel = load_panel()
    state_table = _build_state_table(panel)
    date_level = _build_date_level_substitute_rows(panel, state_table)
    if date_level.empty:
        raise ValueError("No substitute rows available for H304")

    results = pd.DataFrame(
        [
            _decision_row(date_level, state_name=state_name, state_label=state_label, relation_name=relation_name, relation_label=relation_label)
            for state_name, state_label, _ in STATE_SPECS
            for relation_name, relation_label in RELATION_SPECS
        ]
    )
    results = _sort_results(results)

    pass_rows = results.loc[results.apply(_pass_condition, axis=1)].copy()
    mixed_rows = results.loc[results.apply(_mixed_condition, axis=1)].copy()
    decision = "PASSED" if not pass_rows.empty else "MIXED" if not mixed_rows.empty else "FAILED"
    best_candidate = results.iloc[0].to_dict() if not results.empty else {}

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_stem = f"{ts}_h304_execution_spillover_substitutes"
    results_path = OUT_DIR / f"{artifact_stem}_results.parquet"
    date_level_path = OUT_DIR / f"{artifact_stem}_date_level.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{artifact_stem}_details.json"

    results.to_parquet(results_path, index=False)
    date_level.to_parquet(date_level_path, index=False)

    summary = {
        "decision": decision,
        "protocol": PROTOCOL.describe(),
        "thin_adv20_rank_max": THIN_ADV20_RANK_MAX,
        "substitute_rank_window": [SUBSTITUTE_RANK_MIN, SUBSTITUTE_RANK_MAX],
        "state_date_counts": {
            state_name: int(state_table.apply(lambda row: state_fn(row), axis=1).sum())
            for state_name, _, state_fn in STATE_SPECS
        },
        "best_candidate": best_candidate,
        "pass_candidate_count": int(len(pass_rows)),
        "mixed_candidate_count": int(len(mixed_rows)),
        "branch_decision": {
            "PASSED": "Nearest eligible substitutes preserve the edge on stressed execution dates strongly enough to justify a narrower substitute-aware follow-through.",
            "MIXED": "There is only weak local substitute evidence on stressed execution dates, not enough to reopen execution routing as a branch yet.",
            "FAILED": "The nearest eligible same-family or same-sector substitutes do not preserve edge on stressed execution dates; the raw execution mismatch appears to destroy the alpha rather than reroute it cleanly.",
        }[decision],
    }
    details_payload = {
        "summary": summary,
        "results": results.to_dict(orient="records"),
        "pass_rows": pass_rows.to_dict(orient="records"),
        "mixed_rows": mixed_rows.to_dict(orient="records"),
        "thresholds": {
            "pass_validation_edge": PASS_VALIDATION_EDGE,
            "pass_confirmation_edge": PASS_CONFIRMATION_EDGE,
            "pass_validation_hit": PASS_VALIDATION_HIT,
            "pass_confirmation_hit": PASS_CONFIRMATION_HIT,
            "pass_min_validation_dates": PASS_MIN_VALIDATION_DATES,
            "pass_min_confirmation_dates": PASS_MIN_CONFIRMATION_DATES,
        },
    }
    details_path.write_text(json.dumps(_json_safe(details_payload), indent=2) + "\n", encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_execution_spillover_substitutes",
        name="h304_execution_spillover_substitutes",
        summary=summary,
        artifacts={
            "results": results_path,
            "date_level": date_level_path,
            "details": details_path,
        },
        metadata={
            "session": 130,
            "protocol": PROTOCOL.describe(),
            "branch_contract": "H304 is a narrow substitute-beneficiary audit on the frozen 2019-2025 candidate panel only; no live-branch change.",
        },
    )

    print("H304 execution spillover substitutes audit")
    print(json.dumps(_json_safe(summary), indent=2))


if __name__ == "__main__":
    main()
