"""
H297: activation-pressure interaction audit.

Question:
    Does next-cycle selector efficacy depend more on reserve scarcity,
    score-gap compression, and blocked-buy concentration than on simple
    breadth alone?
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")
LABELS_PATH = data_path("features/entry_alpha/entry_labels_cycle5.parquet")
META_PATH = data_path("features/activation_meta_daily.parquet")
STATE_PATH = data_path("features/activation_state_daily.parquet")

OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
PROTOCOL = ResearchProtocol(
    dev_start_year=2019,
    dev_end_year=2022,
    validation_start_year=2023,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

INTERACTION_COLUMNS = [
    "reserve_pressure_combo",
    "blocked_pressure_combo",
    "replacement_pressure_combo",
    "activation_pressure_combo",
]
BASELINE_COLUMNS = [
    "candidate_count",
    "buyable_breadth_all",
    "liq_open_breadth_all",
]
PASS_DEV_RHO = 0.12
PASS_VAL_RHO = 0.08
PASS_CONF_RHO = 0.05
PASS_Q_GAP = 0.01


def _pct_rank(series: pd.Series, *, ascending: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.rank(method="average", pct=True, ascending=ascending).astype(float)


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _safe_spearman(left: pd.Series, right: pd.Series) -> float | None:
    clean = (
        pd.concat([left.rename("left"), right.rename("right")], axis=1)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    if len(clean) < 20 or clean["left"].nunique() < 3 or clean["right"].nunique() < 3:
        return None
    stat = spearmanr(clean["left"], clean["right"]).statistic
    if not np.isfinite(stat):
        return None
    return float(np.asarray(stat).flat[0])


def _quintile_summary(frame: pd.DataFrame, state_col: str, target_col: str) -> pd.DataFrame:
    work = frame[[state_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if work.empty or work[state_col].nunique() < 5:
        return pd.DataFrame()
    work["quintile"] = pd.qcut(work[state_col].rank(method="first"), 5, labels=False) + 1
    return (
        work.groupby("quintile", sort=True)
        .agg(
            n=(target_col, "size"),
            state_mean=(state_col, "mean"),
            edge_mean=(target_col, "mean"),
        )
        .reset_index()
    )


def _phase_stats(frame: pd.DataFrame, *, state_col: str, target_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    scoped = scoped.dropna(subset=[state_col, target_col])
    qtab = _quintile_summary(scoped, state_col, target_col)
    q1 = q5 = q5_minus_q1 = None
    if not qtab.empty:
        q1 = _safe_float(qtab.loc[qtab["quintile"] == 1, "edge_mean"].iloc[0])
        q5 = _safe_float(qtab.loc[qtab["quintile"] == 5, "edge_mean"].iloc[0])
        if q1 is not None and q5 is not None:
            q5_minus_q1 = float(q5 - q1)
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "mean_target": _safe_float(scoped[target_col].mean()),
        "rho": _safe_spearman(scoped[state_col], scoped[target_col]),
        "q1_mean": q1,
        "q5_mean": q5,
        "q5_minus_q1": q5_minus_q1,
        "quintile_table": qtab.to_dict("records"),
    }


def _build_daily_panel() -> pd.DataFrame:
    panel = pd.read_parquet(
        PANEL_PATH,
        columns=[
            "time",
            "ticker",
            "selection_rank",
            "candidate_pool_rank",
            "candidate_pool_size",
            "selection_score",
            "selection_score_gap_to_next_candidate",
            "selection_score_gap_to_top_k_cutoff",
            "can_buy_next_open",
            "top_k",
            "actual",
        ],
    ).copy()
    labels = pd.read_parquet(
        LABELS_PATH,
        columns=["time", "ticker", "cycle_relative_return_vs_vnindex", "buy_now_label"],
    ).copy()
    meta = pd.read_parquet(META_PATH).copy()
    state = pd.read_parquet(STATE_PATH).copy()

    for frame in (panel, labels, meta, state):
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()

    panel = panel.loc[panel["time"].dt.year.between(2019, 2025)].copy()
    labels = labels.loc[labels["time"].dt.year.between(2019, 2025)].copy()
    meta = meta.loc[meta["time"].dt.year.between(2019, 2025)].copy()
    state = state.loc[state["time"].dt.year.between(2019, 2025)].copy()

    work = panel.merge(labels, on=["time", "ticker"], how="inner", validate="one_to_one")
    work["is_selected"] = work["selection_rank"] <= work["top_k"]
    work["can_buy_next_open"] = work["can_buy_next_open"].fillna(False).astype(bool)

    rows: list[dict[str, object]] = []
    for date, day in work.groupby("time", sort=True):
        selected = day.loc[day["is_selected"]].copy()
        if selected.empty:
            continue
        top_k = int(pd.to_numeric(day["top_k"], errors="coerce").dropna().iloc[0])
        cutoff_row = day.loc[day["selection_rank"] == top_k].head(1)
        cutoff_gap = _safe_float(cutoff_row["selection_score_gap_to_next_candidate"].iloc[0]) if not cutoff_row.empty else None
        cutoff_gap_to_cutoff = _safe_float(cutoff_row["selection_score_gap_to_top_k_cutoff"].iloc[0]) if not cutoff_row.empty else None
        selected_buyable = selected.loc[selected["can_buy_next_open"]].copy()
        pool_cycle = _safe_float(day["cycle_relative_return_vs_vnindex"].mean())
        selected_cycle = _safe_float(selected["cycle_relative_return_vs_vnindex"].mean())
        selected_buyable_cycle = _safe_float(selected_buyable["cycle_relative_return_vs_vnindex"].mean())
        pool_hit = _safe_float(day["buy_now_label"].mean())
        selected_hit = _safe_float(selected["buy_now_label"].mean())
        rows.append(
            {
                "time": pd.Timestamp(date),
                "candidate_pool_size": int(pd.to_numeric(day["candidate_pool_size"], errors="coerce").dropna().iloc[0]),
                "top_k": top_k,
                "candidate_slack": int(pd.to_numeric(day["candidate_pool_size"], errors="coerce").dropna().iloc[0]) - top_k,
                "cutoff_gap_to_next_candidate": cutoff_gap,
                "cutoff_gap_to_topk_cutoff": cutoff_gap_to_cutoff,
                "selected_buyable_count": int(selected_buyable.shape[0]),
                "selected_blocked_count": int(selected.shape[0] - selected_buyable.shape[0]),
                "pool_cycle_mean": pool_cycle,
                "selected_cycle_mean": selected_cycle,
                "selected_buyable_cycle_mean": selected_buyable_cycle,
                "selector_cycle_edge": None if pool_cycle is None or selected_cycle is None else float(selected_cycle - pool_cycle),
                "buyable_cycle_edge": None if pool_cycle is None or selected_buyable_cycle is None else float(selected_buyable_cycle - pool_cycle),
                "pool_hit_rate": pool_hit,
                "selected_hit_rate": selected_hit,
                "selector_hit_edge": None if pool_hit is None or selected_hit is None else float(selected_hit - pool_hit),
                "selected_actual_mean": _safe_float(selected["actual"].mean()),
                "pool_actual_mean": _safe_float(day["actual"].mean()),
            }
        )

    daily = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
    if daily.empty:
        raise ValueError("No daily selector-edge rows were built for H297")

    merged = daily.merge(meta, on="time", how="left", validate="one_to_one")
    state_only = state.drop(columns=[column for column in meta.columns if column != "time" and column in state.columns], errors="ignore")
    merged = merged.merge(state_only, on="time", how="left", validate="one_to_one")

    merged["buyable_shortfall"] = merged["top_k"] - pd.to_numeric(merged["full_top5_buyable_count"], errors="coerce")
    merged["reserve_buyable_slack"] = pd.to_numeric(merged["full_top10_buyable_count"], errors="coerce") - merged["top_k"]
    merged["blocked_buy_share"] = pd.to_numeric(merged["full_top5_blocked_buy_count"], errors="coerce") / merged["top_k"].replace(0, np.nan)
    merged["replacement_instability"] = 1.0 - pd.to_numeric(merged["full_top5_prev_overlap_ratio"], errors="coerce")
    merged["selector_disagreement_ratio"] = 1.0 - (
        pd.to_numeric(merged["selector_top5_overlap"], errors="coerce") / merged["top_k"].replace(0, np.nan)
    )
    merged["spread_compression"] = -pd.to_numeric(merged["full_top1_minus_top5_spread"], errors="coerce")

    reserve_terms = pd.concat(
        [
            _pct_rank(-merged["candidate_slack"]).rename("candidate_slack_rank"),
            _pct_rank(-merged["reserve_buyable_slack"]).rename("reserve_buyable_slack_rank"),
            _pct_rank(-merged["cutoff_gap_to_next_candidate"]).rename("cutoff_gap_rank"),
        ],
        axis=1,
    )
    blocked_terms = pd.concat(
        [
            _pct_rank(merged["buyable_shortfall"]).rename("buyable_shortfall_rank"),
            _pct_rank(merged["blocked_buy_share"]).rename("blocked_buy_share_rank"),
            _pct_rank(merged["full_recent_blocked_buy_ewm5"]).rename("recent_blocked_buy_rank"),
            _pct_rank(-merged["buyable_breadth_all"]).rename("inverse_buyable_breadth_rank"),
        ],
        axis=1,
    )
    replacement_terms = pd.concat(
        [
            _pct_rank(merged["replacement_instability"]).rename("replacement_instability_rank"),
            _pct_rank(merged["selector_disagreement_ratio"]).rename("selector_disagreement_rank"),
            _pct_rank(-merged["cutoff_gap_to_next_candidate"]).rename("compressed_cutoff_gap_rank"),
            _pct_rank(merged["spread_compression"]).rename("spread_compression_rank"),
        ],
        axis=1,
    )

    merged["reserve_pressure_combo"] = reserve_terms.mean(axis=1)
    merged["blocked_pressure_combo"] = blocked_terms.mean(axis=1)
    merged["replacement_pressure_combo"] = replacement_terms.mean(axis=1)
    merged["activation_pressure_combo"] = merged[
        ["reserve_pressure_combo", "blocked_pressure_combo", "replacement_pressure_combo"]
    ].mean(axis=1)
    return merged


def _state_result(frame: pd.DataFrame, *, state_col: str, state_group: str) -> dict[str, object]:
    phases = {
        phase: _phase_stats(frame, state_col=state_col, target_col="selector_cycle_edge", phase=phase)
        for phase in ("dev", "validation", "confirmation")
    }
    dev_rho = _safe_float(phases["dev"]["rho"]) or 0.0
    val_rho = _safe_float(phases["validation"]["rho"]) or 0.0
    conf_rho = _safe_float(phases["confirmation"]["rho"]) or 0.0
    expected_sign = np.sign(dev_rho) if dev_rho != 0 else 0.0
    same_sign = bool(
        expected_sign != 0
        and np.sign(val_rho) == expected_sign
        and np.sign(conf_rho) == expected_sign
    )
    pass_condition = bool(
        abs(dev_rho) >= PASS_DEV_RHO
        and abs(val_rho) >= PASS_VAL_RHO
        and abs(conf_rho) >= PASS_CONF_RHO
        and same_sign
        and abs(_safe_float(phases["validation"]["q5_minus_q1"]) or 0.0) >= PASS_Q_GAP
        and abs(_safe_float(phases["confirmation"]["q5_minus_q1"]) or 0.0) >= PASS_Q_GAP
    )
    mixed_condition = bool(
        not pass_condition
        and abs(dev_rho) >= 0.05
        and abs(val_rho) >= 0.03
        and same_sign
    )
    return {
        "state_name": state_col,
        "state_group": state_group,
        "candidate_decision": "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED",
        "dev_rho": phases["dev"]["rho"],
        "validation_rho": phases["validation"]["rho"],
        "confirmation_rho": phases["confirmation"]["rho"],
        "dev_q5_minus_q1": phases["dev"]["q5_minus_q1"],
        "validation_q5_minus_q1": phases["validation"]["q5_minus_q1"],
        "confirmation_q5_minus_q1": phases["confirmation"]["q5_minus_q1"],
        "dev_rows": phases["dev"]["rows"],
        "validation_rows": phases["validation"]["rows"],
        "confirmation_rows": phases["confirmation"]["rows"],
        "phase_details": phases,
    }


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    work["_decision_rank"] = work["candidate_decision"].map({"FAILED": 0, "MIXED": 1, "PASSED": 2}).fillna(-1)
    for column in ("validation_rho", "confirmation_rho", "dev_rho"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=["_decision_rank", "validation_rho", "confirmation_rho", "dev_rho", "state_name"],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def main() -> None:
    panel = _build_daily_panel()
    state_rows = [
        _state_result(panel, state_col=state_col, state_group="interaction")
        for state_col in INTERACTION_COLUMNS
    ] + [
        _state_result(panel, state_col=state_col, state_group="baseline")
        for state_col in BASELINE_COLUMNS
    ]
    results = _sort_results(pd.DataFrame(state_rows))
    if results.empty:
        raise ValueError("No state rows were evaluated for H297")

    interaction_results = results.loc[results["state_group"] == "interaction"].copy()
    baseline_results = results.loc[results["state_group"] == "baseline"].copy()
    best_interaction = interaction_results.iloc[0].to_dict()
    best_baseline = baseline_results.iloc[0].to_dict() if not baseline_results.empty else {}

    best_interaction_val = abs(_safe_float(best_interaction.get("validation_rho")) or 0.0)
    best_baseline_val = abs(_safe_float(best_baseline.get("validation_rho")) or 0.0)
    best_interaction_conf = abs(_safe_float(best_interaction.get("confirmation_rho")) or 0.0)
    pass_condition = bool(
        best_interaction.get("candidate_decision") == "PASSED"
        and best_interaction_val >= best_baseline_val + 0.02
    )
    mixed_condition = bool(
        not pass_condition
        and (
            best_interaction.get("candidate_decision") == "MIXED"
            or best_interaction_val > best_baseline_val
            or best_interaction_conf >= 0.03
        )
    )
    verdict = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
    branch_decision = {
        "PASSED": (
            "Activation pressure materially outperforms simple breadth. "
            "Advance only as a selector-state gate family, not as a reopened breadth branch."
        ),
        "MIXED": (
            "Reserve scarcity and blocked-buy pressure matter more than flat breadth, "
            "but the interaction is not yet strong or stable enough to promote."
        ),
        "FAILED": (
            "Close the activation-pressure interaction branch on the current contract. "
            "The date-level selector edge still is not explained meaningfully beyond the weak baseline states."
        ),
    }[verdict]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h297_activation_pressure_interactions_results.parquet"
    panel_path = OUT_DIR / f"{ts}_h297_activation_pressure_interactions_panel.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h297_activation_pressure_interactions_details.json"
    results.to_parquet(results_path, index=False)
    panel.to_parquet(panel_path, index=False)

    summary = {
        "verdict": verdict,
        "hypothesis": (
            "Selector efficacy should respond more to reserve scarcity, score-gap compression, "
            "and blocked-buy pressure than to flat breadth."
        ),
        "protocol": PROTOCOL.describe(),
        "target": "selector_cycle_edge",
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "selector_cycle_edge_mean": _safe_float(panel["selector_cycle_edge"].mean()),
        "selector_hit_edge_mean": _safe_float(panel["selector_hit_edge"].mean()),
        "best_interaction": best_interaction,
        "best_baseline": best_baseline,
        "tested_states": results[
            [
                "state_name",
                "state_group",
                "candidate_decision",
                "dev_rho",
                "validation_rho",
                "confirmation_rho",
                "validation_q5_minus_q1",
                "confirmation_q5_minus_q1",
            ]
        ].to_dict("records"),
        "branch_decision": branch_decision,
    }
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_activation_pressure_interactions",
        name="h297_activation_pressure_interactions",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "daily_panel": str(panel_path),
            "details": str(details_path),
        },
        metadata={
            "session": 128,
            "years": [2019, 2025],
            "target": "cycle_relative_return_vs_vnindex",
        },
    )

    print("H297 activation-pressure interactions")
    print(
        results[
            [
                "state_name",
                "state_group",
                "candidate_decision",
                "dev_rho",
                "validation_rho",
                "confirmation_rho",
                "validation_q5_minus_q1",
                "confirmation_q5_minus_q1",
            ]
        ].to_string(index=False)
    )
    print(f"\nVerdict: {verdict}")
    print(branch_decision)


if __name__ == "__main__":
    main()
