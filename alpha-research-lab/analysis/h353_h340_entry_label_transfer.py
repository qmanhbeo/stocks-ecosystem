"""
H353: H340 entry-label transfer audit.

Question:
    Does the H340 same-day buy-volume pressure rewrite of bullish C5 transfer
    to the entry-alpha candidate-book contract?

Design:
    - reuse the fixed H340 dev buy-volume support threshold
    - join existing entry-alpha candidate, label, and score artifacts
    - join existing CafeF order-statistics rows
    - evaluate active C5/order-pressure states against the entry prior
    - use 2019-2022 dev, 2023-2024 validation, 2025 confirmation, 2026 excluded
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

from src.research_protocol import ResearchProtocol, phase_mask  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


H340_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_c5_order_pressure_split.json"
CANDIDATE_PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")
ENTRY_LABELS_PATH = data_path("features/entry_alpha/entry_labels_cycle5.parquet")
ENTRY_SCORES_PATH = data_path("features/entry_alpha/entry_scores_daily.parquet")
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2019,
    dev_end_year=2022,
    validation_start_year=2023,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

STATE_SPECS = (
    ("c5_positive", "Raw positive C5 state inside the entry candidate book", "control"),
    ("h340_buy_vol_gate", "H340 positive C5 with same-day buy-volume imbalance > 0", "candidate"),
    ("h340_buy_vol_strong", "H340 positive C5 with buy-volume imbalance >= dev support median", "candidate"),
    ("h340_rejected_positive_c5", "Positive C5 row rejected by same-day buy-volume imbalance", "diagnostic"),
)

METRIC_SPECS = (
    ("buy_now_label", "label"),
    ("cycle_return_net", "net"),
    ("cycle_relative_return_vs_vnindex", "rel_vnindex"),
)

MATCH_BUCKETS = 5
MIN_ACTIVE_ROWS = 50
MIN_ACTIVE_DATES = 30


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


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _daily_rank(series: pd.Series, time_index: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=True,
    )


def _load_h340_threshold() -> float:
    payload = json.loads(H340_SUMMARY_PATH.read_text(encoding="utf-8"))
    threshold = payload["summary"].get("dev_volume_support_threshold")
    if threshold is None:
        threshold = payload["artifacts"].get("dev_volume_support_threshold")
    numeric = pd.to_numeric(threshold, errors="coerce")
    if pd.isna(numeric) or float(numeric) <= 0.0:
        raise ValueError(f"Invalid H340 dev volume support threshold: {threshold!r}")
    return float(numeric)


def _load_entry_panel() -> pd.DataFrame:
    candidate_cols = [
        "time",
        "ticker",
        "selection_score",
        "selection_rank",
        "candidate_pool_rank",
        "candidate_pool_size",
        "can_buy_next_open",
        "activation_state",
        "activation_scale",
        "actual",
        "c5_ins_relative_size_5d",
    ]
    label_cols = [
        "time",
        "ticker",
        "cycle_return_net",
        "cycle_relative_return_vs_vnindex",
        "cycle_relative_return_vs_cash",
        "buy_now_label",
    ]
    score_cols = [
        "time",
        "ticker",
        "research_phase",
        "entry_prob__implementation_context",
        "entry_prob__price_state",
        "entry_prob__blend",
    ]
    candidates = pd.read_parquet(CANDIDATE_PANEL_PATH, columns=candidate_cols).copy()
    labels = pd.read_parquet(ENTRY_LABELS_PATH, columns=label_cols).copy()
    scores = pd.read_parquet(ENTRY_SCORES_PATH, columns=score_cols).copy()

    for frame in (candidates, labels, scores):
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
        frame.dropna(subset=["time", "ticker"], inplace=True)
        frame = frame

    candidates = candidates.loc[candidates["time"].dt.year.between(2019, 2025)].copy()
    labels = labels.loc[labels["time"].dt.year.between(2019, 2025)].copy()
    scores = scores.loc[scores["time"].dt.year.between(2019, 2025)].copy()

    panel = candidates.merge(labels, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(scores, on=["time", "ticker"], how="left", validate="one_to_one")

    numeric_cols = [
        "selection_score",
        "selection_rank",
        "candidate_pool_rank",
        "candidate_pool_size",
        "activation_scale",
        "actual",
        "c5_ins_relative_size_5d",
        "cycle_return_net",
        "cycle_relative_return_vs_vnindex",
        "cycle_relative_return_vs_cash",
        "buy_now_label",
        "entry_prob__implementation_context",
        "entry_prob__price_state",
        "entry_prob__blend",
    ]
    for col in numeric_cols:
        panel[col] = pd.to_numeric(panel[col], errors="coerce")
    panel["entry_prior_score"] = panel["entry_prob__blend"].combine_first(panel["selection_score"])
    panel["entry_prior_rank"] = _daily_rank(panel["entry_prior_score"], panel["time"])
    bucket = np.ceil(pd.to_numeric(panel["entry_prior_rank"], errors="coerce") * MATCH_BUCKETS)
    panel["entry_prior_bucket"] = bucket.clip(lower=1, upper=MATCH_BUCKETS).astype("Int64")
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _load_order_stats() -> pd.DataFrame:
    order = pd.read_parquet(
        ORDER_STATS_PATH,
        columns=["ticker", "date", "buy_order_volume", "sell_order_volume"],
    ).rename(columns={"date": "time"})
    order["time"] = pd.to_datetime(order["time"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].astype(str).str.upper()
    order = order.loc[order["time"].dt.year.between(2019, 2025)].copy()
    buy = pd.to_numeric(order["buy_order_volume"], errors="coerce").fillna(0.0)
    sell = pd.to_numeric(order["sell_order_volume"], errors="coerce").fillna(0.0)
    denom = buy + sell
    order["order_volume_ratio"] = np.where(denom > 0.0, (buy - sell) / denom, 0.0)
    return order[["time", "ticker", "order_volume_ratio"]]


def _build_panel() -> tuple[pd.DataFrame, float]:
    threshold = _load_h340_threshold()
    panel = _load_entry_panel()
    order = _load_order_stats()
    panel = panel.merge(order, on=["time", "ticker"], how="left", validate="one_to_one")
    panel["order_volume_ratio"] = pd.to_numeric(panel["order_volume_ratio"], errors="coerce").fillna(0.0)
    c5 = pd.to_numeric(panel["c5_ins_relative_size_5d"], errors="coerce").fillna(0.0)
    pressure = pd.to_numeric(panel["order_volume_ratio"], errors="coerce").fillna(0.0)
    panel["c5_positive"] = c5 > 0.0
    panel["h340_buy_vol_gate"] = panel["c5_positive"] & (pressure > 0.0)
    panel["h340_buy_vol_strong"] = panel["c5_positive"] & (pressure >= threshold)
    panel["h340_rejected_positive_c5"] = panel["c5_positive"] & (pressure <= 0.0)
    panel["h340_scaled_c5_score"] = np.where(
        c5 > 0.0,
        c5 * np.clip(pressure / threshold, 0.0, 1.0),
        c5,
    )
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True), threshold


def _daily_lift(frame: pd.DataFrame, state_col: str, metric_col: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for time, group in frame.groupby("time", sort=True):
        state = group[state_col].fillna(False).astype(bool)
        active_metric = pd.to_numeric(group.loc[state, metric_col], errors="coerce").dropna()
        all_metric = pd.to_numeric(group[metric_col], errors="coerce").dropna()
        if active_metric.empty or all_metric.empty:
            continue
        rows.append(
            {
                "time": pd.Timestamp(time),
                "active_count": int(active_metric.shape[0]),
                "lift": float(active_metric.mean() - all_metric.mean()),
            }
        )
    daily = pd.DataFrame(rows)
    return {
        "daily_count": int(len(daily)),
        "daily_lift": _safe_float(daily["lift"].mean()) if not daily.empty else None,
        "daily_lift_hit_rate": _safe_float((daily["lift"] > 0.0).mean()) if not daily.empty else None,
        "avg_active_names_per_active_day": _safe_float(daily["active_count"].mean()) if not daily.empty else None,
    }


def _entry_prior_matched_lift(frame: pd.DataFrame, state_col: str, metric_col: str) -> dict[str, object]:
    metric = pd.to_numeric(frame[metric_col], errors="coerce")
    work = frame.loc[metric.notna() & frame["entry_prior_bucket"].notna()].copy()
    if work.empty:
        return {"matched_rows": 0, "matched_lift": None, "matched_lift_hit_rate": None}

    work["_metric"] = pd.to_numeric(work[metric_col], errors="coerce")
    work["_state"] = work[state_col].fillna(False).astype(bool)
    refs = (
        work.loc[~work["_state"]]
        .groupby(["time", "entry_prior_bucket"], as_index=False)["_metric"]
        .mean()
        .rename(columns={"_metric": "_matched_mean"})
    )
    active = work.loc[work["_state"], ["time", "ticker", "entry_prior_bucket", "_metric"]].copy()
    matched = active.merge(refs, on=["time", "entry_prior_bucket"], how="left", validate="many_to_one")
    matched = matched.dropna(subset=["_matched_mean", "_metric"]).copy()
    if matched.empty:
        return {"matched_rows": 0, "matched_lift": None, "matched_lift_hit_rate": None}
    matched["_lift"] = matched["_metric"] - matched["_matched_mean"]
    return {
        "matched_rows": int(len(matched)),
        "matched_lift": _safe_float(matched["_lift"].mean()),
        "matched_lift_hit_rate": _safe_float((matched["_lift"] > 0.0).mean()),
    }


def _daily_state_ic(frame: pd.DataFrame, state_col: str, metric_col: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for time, group in frame.groupby("time", sort=True):
        clean = group[[state_col, metric_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < 8 or clean[state_col].nunique() < 2 or clean[metric_col].nunique() < 2:
            continue
        ic = clean[state_col].astype(float).corr(pd.to_numeric(clean[metric_col], errors="coerce"), method="spearman")
        if not np.isfinite(ic):
            continue
        rows.append({"time": pd.Timestamp(time), "ic": float(ic)})
    daily = pd.DataFrame(rows)
    return {
        "daily_ic_count": int(len(daily)),
        "daily_ic_mean": _safe_float(daily["ic"].mean()) if not daily.empty else None,
        "daily_ic_hit_rate": _safe_float((daily["ic"] > 0.0).mean()) if not daily.empty else None,
    }


def _phase_state_summary(panel: pd.DataFrame, state_col: str, phase: str) -> dict[str, object]:
    scoped = panel.loc[phase_mask(panel, phase, protocol=PROTOCOL)].copy()
    state = scoped[state_col].fillna(False).astype(bool)
    active = scoped.loc[state].copy()
    summary: dict[str, object] = {
        "phase": phase,
        "state": state_col,
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "active_rows": int(len(active)),
        "active_dates": int(active["time"].nunique()) if not active.empty else 0,
        "coverage": float(state.mean()) if not scoped.empty else 0.0,
        "active_entry_prior_rank_mean": _safe_float(active["entry_prior_rank"].mean()) if not active.empty else None,
        "all_entry_prior_rank_mean": _safe_float(scoped["entry_prior_rank"].mean()) if not scoped.empty else None,
        "active_order_volume_ratio_mean": _safe_float(active["order_volume_ratio"].mean()) if not active.empty else None,
    }
    for metric_col, metric_slug in METRIC_SPECS:
        active_metric = pd.to_numeric(active[metric_col], errors="coerce").dropna() if not active.empty else pd.Series(dtype=float)
        all_metric = pd.to_numeric(scoped[metric_col], errors="coerce").dropna() if not scoped.empty else pd.Series(dtype=float)
        summary[f"active_{metric_slug}_mean"] = _safe_float(active_metric.mean()) if not active_metric.empty else None
        summary[f"all_{metric_slug}_mean"] = _safe_float(all_metric.mean()) if not all_metric.empty else None
        summary[f"raw_{metric_slug}_lift"] = (
            None if active_metric.empty or all_metric.empty else float(active_metric.mean() - all_metric.mean())
        )
        daily = _daily_lift(scoped, state_col, metric_col)
        matched = _entry_prior_matched_lift(scoped, state_col, metric_col)
        daily_ic = _daily_state_ic(scoped, state_col, metric_col)
        summary[f"daily_{metric_slug}_lift"] = daily["daily_lift"]
        summary[f"daily_{metric_slug}_lift_days"] = daily["daily_count"]
        summary[f"daily_{metric_slug}_lift_hit_rate"] = daily["daily_lift_hit_rate"]
        summary[f"matched_{metric_slug}_lift"] = matched["matched_lift"]
        summary[f"matched_{metric_slug}_rows"] = matched["matched_rows"]
        summary[f"matched_{metric_slug}_lift_hit_rate"] = matched["matched_lift_hit_rate"]
        summary[f"daily_{metric_slug}_ic_mean"] = daily_ic["daily_ic_mean"]
        summary[f"daily_{metric_slug}_ic_days"] = daily_ic["daily_ic_count"]
        summary[f"daily_{metric_slug}_ic_hit_rate"] = daily_ic["daily_ic_hit_rate"]
    return summary


def _make_results(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for state_col, note, kind in STATE_SPECS:
        for phase in ("dev", "validation", "confirmation"):
            row = _phase_state_summary(panel, state_col, phase)
            row["state_note"] = note
            row["state_kind"] = kind
            rows.append(row)
    return pd.DataFrame(rows)


def _row(results: pd.DataFrame, state: str, phase: str) -> pd.Series:
    match = results.loc[(results["state"] == state) & (results["phase"] == phase)]
    if match.empty:
        raise ValueError(f"Missing result for {state} / {phase}")
    return match.iloc[0]


def _positive(row: pd.Series, key: str) -> bool:
    value = pd.to_numeric(row.get(key), errors="coerce")
    return bool(pd.notna(value) and float(value) > 0.0)


def _state_positive_bundle(row: pd.Series) -> bool:
    return (
        _positive(row, "daily_label_lift")
        and _positive(row, "matched_label_lift")
        and _positive(row, "matched_net_lift")
        and _positive(row, "matched_rel_vnindex_lift")
    )


def _beats_control(candidate: pd.Series, control: pd.Series) -> bool:
    cand_net = pd.to_numeric(candidate.get("matched_net_lift"), errors="coerce")
    ctrl_net = pd.to_numeric(control.get("matched_net_lift"), errors="coerce")
    cand_rel = pd.to_numeric(candidate.get("matched_rel_vnindex_lift"), errors="coerce")
    ctrl_rel = pd.to_numeric(control.get("matched_rel_vnindex_lift"), errors="coerce")
    if pd.isna(cand_net) or pd.isna(ctrl_net) or pd.isna(cand_rel) or pd.isna(ctrl_rel):
        return False
    return bool(float(cand_net) >= float(ctrl_net) and float(cand_rel) >= float(ctrl_rel))


def _candidate_decision(results: pd.DataFrame, state: str) -> dict[str, object]:
    val = _row(results, state, "validation")
    conf = _row(results, state, "confirmation")
    raw_val = _row(results, "c5_positive", "validation")
    raw_conf = _row(results, "c5_positive", "confirmation")
    enough = (
        int(val["active_rows"]) >= MIN_ACTIVE_ROWS
        and int(val["active_dates"]) >= MIN_ACTIVE_DATES
        and int(conf["active_rows"]) >= MIN_ACTIVE_ROWS
        and int(conf["active_dates"]) >= MIN_ACTIVE_DATES
    )
    if not enough:
        return {"state": state, "decision": "SKIPPED", "reason": "insufficient_active_rows_or_dates"}

    val_positive = _state_positive_bundle(val)
    conf_positive = _state_positive_bundle(conf)
    val_beats = _beats_control(val, raw_val)
    conf_beats = _beats_control(conf, raw_conf)
    if val_positive and conf_positive and val_beats and conf_beats:
        return {
            "state": state,
            "decision": "PASSED",
            "reason": "positive_entry_lifts_both_phases_and_beats_raw_c5",
        }
    if val_positive and conf_positive:
        return {
            "state": state,
            "decision": "MIXED",
            "reason": "positive_both_phases_but_raw_c5_control_not_cleared",
        }
    if val_positive or conf_positive:
        return {"state": state, "decision": "MIXED", "reason": "one_phase_positive_only"}
    return {"state": state, "decision": "FAILED", "reason": "entry_lifts_not_positive_in_validation_and_confirmation"}


def _decide(results: pd.DataFrame) -> dict[str, object]:
    decisions = [
        _candidate_decision(results, "h340_buy_vol_gate"),
        _candidate_decision(results, "h340_buy_vol_strong"),
    ]
    decision_rank = {"PASSED": 0, "MIXED": 1, "FAILED": 2, "SKIPPED": 3}
    scored = []
    for item in decisions:
        val = _row(results, item["state"], "validation")
        conf = _row(results, item["state"], "confirmation")
        score = (
            (_safe_float(val.get("matched_rel_vnindex_lift")) or 0.0)
            + (_safe_float(conf.get("matched_rel_vnindex_lift")) or 0.0)
            + (_safe_float(val.get("matched_net_lift")) or 0.0)
            + (_safe_float(conf.get("matched_net_lift")) or 0.0)
        )
        scored.append({**item, "score": score})
    best = sorted(scored, key=lambda x: (decision_rank.get(x["decision"], 9), -x["score"]))[0]
    if any(item["decision"] == "PASSED" for item in scored):
        verdict = "PASSED"
        branch_decision = (
            "H340 transfers to the entry-alpha candidate contract. Advance to a narrow entry-prior integration audit."
        )
    elif any(item["decision"] == "MIXED" for item in scored):
        verdict = "MIXED"
        branch_decision = (
            "H340 shows partial entry-candidate evidence, but does not cleanly improve validation and confirmation "
            "entry labels/returns over raw C5."
        )
    elif all(item["decision"] == "SKIPPED" for item in scored):
        verdict = "SKIPPED"
        branch_decision = "H340 states are too sparse in the entry-alpha candidate book for a valid test."
    else:
        verdict = "FAILED"
        branch_decision = (
            "H340 remains a strong daily-state C5 rewrite, but it does not transfer to the entry-alpha candidate-book "
            "label contract after matching against the existing entry prior."
        )

    val = _row(results, best["state"], "validation")
    conf = _row(results, best["state"], "confirmation")
    return {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "candidate_decisions": scored,
        "best_state": best["state"],
        "best_state_decision": best["decision"],
        "best_state_reason": best["reason"],
        "validation_active_rows": int(val["active_rows"]),
        "validation_active_dates": int(val["active_dates"]),
        "validation_matched_label_lift": _safe_float(val["matched_label_lift"]),
        "validation_matched_net_lift": _safe_float(val["matched_net_lift"]),
        "validation_matched_rel_vnindex_lift": _safe_float(val["matched_rel_vnindex_lift"]),
        "confirmation_active_rows": int(conf["active_rows"]),
        "confirmation_active_dates": int(conf["active_dates"]),
        "confirmation_matched_label_lift": _safe_float(conf["matched_label_lift"]),
        "confirmation_matched_net_lift": _safe_float(conf["matched_net_lift"]),
        "confirmation_matched_rel_vnindex_lift": _safe_float(conf["matched_rel_vnindex_lift"]),
    }


def _print_results(results: pd.DataFrame, decision: dict[str, object]) -> None:
    table = results.loc[
        results["state"].isin(["c5_positive", "h340_buy_vol_gate", "h340_buy_vol_strong"]),
        [
            "state",
            "phase",
            "active_rows",
            "active_dates",
            "matched_label_lift",
            "matched_net_lift",
            "matched_rel_vnindex_lift",
            "active_entry_prior_rank_mean",
            "active_order_volume_ratio_mean",
        ],
    ].copy()
    print("\nH353: H340 ENTRY-LABEL TRANSFER AUDIT")
    print(table.to_string(index=False))
    print(f"\nverdict={decision['verdict']} | best_state={decision['best_state']} | reason={decision['best_state_reason']}")


def main() -> None:
    panel, threshold = _build_panel()
    if (panel["time"].dt.year >= 2026).any():
        raise ValueError("H353 predictive panel unexpectedly includes 2026+ rows")

    results = _make_results(panel)
    decision = _decide(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    panel_out = OUT_DIR / f"{ts}_h353_h340_entry_label_transfer_panel.parquet"
    results_out = OUT_DIR / f"{ts}_h353_h340_entry_label_transfer_results.parquet"
    details_out = DETAILS_DIR / f"{ts}_h353_h340_entry_label_transfer_details.json"

    panel.to_parquet(panel_out, index=False)
    results.to_parquet(results_out, index=False)

    summary = {
        **decision,
        "protocol": PROTOCOL.describe(),
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "h340_dev_volume_support_threshold": threshold,
    }
    details = {
        "summary": summary,
        "state_specs": [
            {"state": state, "note": note, "kind": kind}
            for state, note, kind in STATE_SPECS
        ],
        "metric_specs": [
            {"metric": metric, "slug": slug}
            for metric, slug in METRIC_SPECS
        ],
        "decision_rules": {
            "minimum_active_rows_per_validation_phase": MIN_ACTIVE_ROWS,
            "minimum_active_dates_per_validation_phase": MIN_ACTIVE_DATES,
            "pass": (
                "validation and confirmation daily/matched label plus matched net and relative-return lifts are positive, "
                "and matched net/relative lifts beat raw positive C5 in both phases"
            ),
            "mixed": "one or both phases positive without clearing raw positive C5",
            "failed": "sufficient coverage but no positive validation/confirmation entry lift",
            "skipped": "insufficient validation or confirmation active rows/dates",
        },
    }
    details_out.write_text(json.dumps(_json_safe(details), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_h340_entry_label_transfer",
        name="h353_h340_entry_label_transfer",
        summary=summary,
        artifacts={
            "panel": str(panel_out),
            "results": str(results_out),
            "details": str(details_out),
        },
        metadata={
            "h340_summary": str(H340_SUMMARY_PATH),
            "candidate_panel": str(CANDIDATE_PANEL_PATH),
            "entry_labels": str(ENTRY_LABELS_PATH),
            "entry_scores": str(ENTRY_SCORES_PATH),
            "order_stats": str(ORDER_STATS_PATH),
        },
    )

    _print_results(results, decision)
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
