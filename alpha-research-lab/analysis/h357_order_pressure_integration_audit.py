"""
H357 - Order-Pressure Integration Audit.

Question:
- H356 showed CafeF posted order-volume pressure is a strong standalone signal.
  Does it remain useful after the frozen RL signal matrix and selector
  contract are accounted for?

Design:
- Exclude 2026.
- Build the exact H356 `order_volume_ratio_rank` feature from the raw CafeF
  order-statistics source.
- Test three integration views:
  1. redundancy against the existing matrix columns,
  2. residual IC after cross-sectional daily residualization versus the full
     library,
  3. label-level top-5 selector edge for full_library with and without the
     order-pressure column.

Decision ladder:
- PASSED:
  - order-pressure residual clears the strict 1d split,
  - max absolute candidate-library correlation is < 0.30,
  - and the equal-weight full-library-plus-order selector improves validation
    top-5 edge by at least 0.005 without hurting confirmation.
- MIXED:
  - residual signal survives and the selector is not materially harmed, but the
    selector improvement is too small for immediate publication.
- FAILED:
  - residual signal does not survive, redundancy is high, or selector
    integration damages validation / confirmation.
"""

from __future__ import annotations

from datetime import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns, signal_fill_value
from src.repo_paths import artifact_path, data_path
from src.research_protocol import DEFAULT_PROTOCOL, phase_mask
from src.run_summary import write_run_summary
from src.standalone_signal_utils import spearman_stat


MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
OUT_DIR = artifact_path("portfolio_baselines")

ORDER_FEATURE = "order_volume_ratio_rank"
RESIDUAL_FEATURE = "order_volume_ratio_full_library_residual_rank"
START_YEAR = 2015
END_YEAR = 2025
TOP_N = 5
MIN_YEAR_ROWS = 500
MIN_PHASE_ROWS = 500
MIN_REGRESSION_OBS = 50
PASS_IC = 0.01
PASS_PCT_YEARS = 0.60
PASS_MAX_CORR = 0.30
PASS_SELECTOR_VAL_DELTA = 0.005
CONFIRMATION_DAMAGE_FLOOR = -0.001


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _daily_rank(series: pd.Series, time_index: pd.Series) -> pd.Series:
    return (
        pd.to_numeric(series, errors="coerce")
        .groupby(time_index, sort=False)
        .rank(method="average", pct=True, ascending=True)
        .astype(float)
    )


def _load_order_pressure() -> pd.DataFrame:
    order = pd.read_parquet(
        ORDER_STATS_PATH,
        columns=["ticker", "date", "buy_order_volume", "sell_order_volume"],
    ).copy()
    order = order.rename(columns={"date": "time"})
    order["time"] = pd.to_datetime(order["time"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].astype(str).str.upper()
    order = order.loc[order["time"].dt.year.between(START_YEAR, END_YEAR)].dropna(subset=["time", "ticker"]).copy()

    buy = pd.to_numeric(order["buy_order_volume"], errors="coerce")
    sell = pd.to_numeric(order["sell_order_volume"], errors="coerce")
    denom = buy + sell
    order["order_volume_ratio"] = (buy - sell).div(denom.replace(0.0, np.nan))
    order[ORDER_FEATURE] = _daily_rank(order["order_volume_ratio"], order["time"])
    return order[["time", "ticker", ORDER_FEATURE]].dropna(subset=[ORDER_FEATURE])


def _load_panel() -> tuple[pd.DataFrame, list[str]]:
    matrix = pd.read_parquet(MATRIX_PATH).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    matrix = matrix.loc[matrix["time"].dt.year.between(START_YEAR, END_YEAR)].copy()
    full_library_columns = resolve_strategy_columns(matrix.columns.tolist(), "full_library")
    order = _load_order_pressure()
    panel = matrix.merge(order, on=["time", "ticker"], how="inner", validate="one_to_one")
    return panel, full_library_columns


def _filled_ranked_controls(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    for column in columns:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if column.endswith("_present"):
            out[column] = numeric.fillna(0.0).clip(lower=0.0, upper=1.0)
        else:
            out[column] = _daily_rank(numeric, frame["time"]).fillna(signal_fill_value(column))
    return out


def _residualize_order_pressure(frame: pd.DataFrame, controls: list[str]) -> pd.DataFrame:
    work = frame.copy()
    ranked_controls = _filled_ranked_controls(work, controls)
    work[controls] = ranked_controls[controls]

    residual_parts: list[pd.Series] = []
    for _, group in work.groupby("time", sort=False):
        clean = group[[ORDER_FEATURE, *controls]].replace([np.inf, -np.inf], np.nan).dropna()
        out = pd.Series(np.nan, index=group.index, dtype=float)
        if len(clean) >= MIN_REGRESSION_OBS:
            x = np.column_stack([np.ones(len(clean), dtype=float)] + [clean[column].to_numpy(dtype=float) for column in controls])
            y = clean[ORDER_FEATURE].to_numpy(dtype=float)
            beta = np.linalg.lstsq(x, y, rcond=None)[0]
            out.loc[clean.index] = y - x @ beta
        residual_parts.append(out)
    work[RESIDUAL_FEATURE] = pd.concat(residual_parts).sort_index()
    work[RESIDUAL_FEATURE] = _daily_rank(work[RESIDUAL_FEATURE], work["time"])
    return work


def _yearly_ic(frame: pd.DataFrame, feature: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby(frame["time"].dt.year, sort=True):
        clean = group[[feature, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_YEAR_ROWS or clean[feature].nunique() < 3 or clean["actual"].nunique() < 2:
            continue
        rho, p_value = spearmanr(clean[feature], clean["actual"])
        if np.isfinite(rho):
            rows.append(
                {
                    "year": int(year),
                    "n": int(len(clean)),
                    "ic": float(np.asarray(rho).flat[0]),
                    "p_value": float(np.asarray(p_value).flat[0]),
                }
            )
    return rows


def _phase_ic(frame: pd.DataFrame, feature: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=DEFAULT_PROTOCOL), [feature, "actual"]]
    clean = scoped.replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_PHASE_ROWS or clean[feature].nunique() < 3 or clean["actual"].nunique() < 2:
        return {"rows": int(len(clean)), "pooled_ic": None}
    rho = spearmanr(clean[feature], clean["actual"]).statistic
    return {"rows": int(len(clean)), "pooled_ic": float(np.asarray(rho).flat[0])}


def _ic_summary(frame: pd.DataFrame, feature: str) -> dict[str, object]:
    yearly = _yearly_ic(frame, feature)
    ics = [float(row["ic"]) for row in yearly]
    pos_years = int(sum(1 for ic in ics if ic > 0.0))
    avg_ic = float(np.mean(ics)) if ics else None
    pct_years = float(pos_years / len(ics)) if ics else None
    phases = {phase: _phase_ic(frame, feature, phase) for phase in ("dev", "validation", "confirmation")}
    strict = bool(
        (avg_ic or 0.0) > PASS_IC
        and (pct_years or 0.0) >= PASS_PCT_YEARS
        and (_safe_float(phases["dev"]["pooled_ic"]) or 0.0) > PASS_IC
        and (_safe_float(phases["validation"]["pooled_ic"]) or 0.0) > PASS_IC
        and (_safe_float(phases["confirmation"]["pooled_ic"]) or 0.0) > PASS_IC
    )
    return {
        "feature": feature,
        "avg_ic": avg_ic,
        "pos_years": pos_years,
        "years": int(len(yearly)),
        "pct_years_positive": pct_years,
        "phase_details": phases,
        "strict_split_pass": strict,
        "yearly": yearly,
    }


def _candidate_correlations(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in columns:
        corr = spearman_stat(frame[ORDER_FEATURE], frame[column])
        rows.append({"column": column, "corr_with_order_pressure": corr, "abs_corr": abs(corr) if np.isfinite(corr) else None})
    return pd.DataFrame(rows).sort_values("abs_corr", ascending=False, ignore_index=True)


def _daily_selector_edges(scored: pd.DataFrame, strategy: str) -> pd.DataFrame:
    score_col = f"score__{strategy}"
    rows: list[dict[str, object]] = []
    for date, day in scored.groupby("time", sort=True):
        clean = day[[score_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < TOP_N or clean[score_col].nunique() < 2:
            continue
        top = clean.nlargest(TOP_N, score_col)
        ranks = clean[score_col].rank(method="average", pct=True)
        q5 = clean.loc[ranks >= 0.8, "actual"].mean()
        q1 = clean.loc[ranks <= 0.2, "actual"].mean()
        rho = spearmanr(clean[score_col], clean["actual"]).statistic
        rows.append(
            {
                "time": pd.Timestamp(date),
                "strategy": strategy,
                "n": int(len(clean)),
                "daily_ic": float(np.asarray(rho).flat[0]),
                "baseline_hit": float(clean["actual"].mean()),
                "top5_hit": float(top["actual"].mean()),
                "top5_edge": float(top["actual"].mean() - clean["actual"].mean()),
                "q5_q1_spread": float(q5 - q1),
            }
        )
    return pd.DataFrame(rows)


def _selector_phase_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for strategy, strategy_daily in daily.groupby("strategy", sort=False):
        for phase in ("dev", "validation", "confirmation"):
            scoped = strategy_daily.loc[phase_mask(strategy_daily, phase, protocol=DEFAULT_PROTOCOL)].copy()
            yearly = scoped.assign(year=scoped["time"].dt.year).groupby("year")[["daily_ic", "top5_edge"]].mean()
            rows.append(
                {
                    "strategy": strategy,
                    "phase": phase,
                    "days": int(len(scoped)),
                    "avg_daily_ic": _safe_float(scoped["daily_ic"].mean()) if not scoped.empty else None,
                    "avg_top5_edge": _safe_float(scoped["top5_edge"].mean()) if not scoped.empty else None,
                    "avg_q5_q1_spread": _safe_float(scoped["q5_q1_spread"].mean()) if not scoped.empty else None,
                    "positive_ic_years": int((yearly["daily_ic"] > 0.0).sum()) if not yearly.empty else 0,
                    "positive_edge_years": int((yearly["top5_edge"] > 0.0).sum()) if not yearly.empty else 0,
                    "years": int(len(yearly)),
                }
            )
    return pd.DataFrame(rows)


def _selector_delta_table(summary: pd.DataFrame, baseline: str, candidate: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for phase in ("dev", "validation", "confirmation"):
        base = summary.loc[(summary["strategy"] == baseline) & (summary["phase"] == phase)].iloc[0]
        cand = summary.loc[(summary["strategy"] == candidate) & (summary["phase"] == phase)].iloc[0]
        out[phase] = {
            "baseline_top5_edge": _safe_float(base["avg_top5_edge"]),
            "candidate_top5_edge": _safe_float(cand["avg_top5_edge"]),
            "top5_edge_delta": (_safe_float(cand["avg_top5_edge"]) or 0.0) - (_safe_float(base["avg_top5_edge"]) or 0.0),
            "baseline_daily_ic": _safe_float(base["avg_daily_ic"]),
            "candidate_daily_ic": _safe_float(cand["avg_daily_ic"]),
            "daily_ic_delta": (_safe_float(cand["avg_daily_ic"]) or 0.0) - (_safe_float(base["avg_daily_ic"]) or 0.0),
        }
    return out


def main() -> None:
    print("H357 - Order-Pressure Integration Audit")
    print("=" * 78)

    panel, full_library_columns = _load_panel()
    if panel.empty:
        raise ValueError("No matrix/order-pressure integration panel rows were built")

    panel = _residualize_order_pressure(panel, full_library_columns)
    raw_ic = _ic_summary(panel, ORDER_FEATURE)
    residual_ic = _ic_summary(panel, RESIDUAL_FEATURE)
    corrs = _candidate_correlations(panel, full_library_columns)
    max_abs_corr = _safe_float(corrs["abs_corr"].max()) or 0.0
    max_corr_row = corrs.iloc[0].to_dict()

    strategies = {
        "full_library_baseline": list(full_library_columns),
        "full_library_plus_order_pressure": list(full_library_columns) + [ORDER_FEATURE],
        "order_pressure_only": [ORDER_FEATURE],
    }
    scored = compute_strategy_scores(panel, strategies)
    daily_edges = pd.concat([_daily_selector_edges(scored, strategy) for strategy in strategies], ignore_index=True)
    selector_summary = _selector_phase_summary(daily_edges)
    selector_delta = _selector_delta_table(
        selector_summary,
        baseline="full_library_baseline",
        candidate="full_library_plus_order_pressure",
    )

    validation_delta = _safe_float(selector_delta["validation"]["top5_edge_delta"]) or 0.0
    confirmation_delta = _safe_float(selector_delta["confirmation"]["top5_edge_delta"]) or 0.0
    residual_pass = bool(residual_ic["strict_split_pass"])
    low_redundancy = bool(max_abs_corr < PASS_MAX_CORR)
    selector_pass = bool(validation_delta >= PASS_SELECTOR_VAL_DELTA and confirmation_delta >= 0.0)
    selector_not_harmed = bool(validation_delta >= 0.0 and confirmation_delta >= CONFIRMATION_DAMAGE_FLOOR)

    if residual_pass and low_redundancy and selector_pass:
        verdict = "PASSED"
        branch_decision = (
            "Order pressure survives residualization and improves the frozen label-level selector. "
            "Advance to feature publication design plus a portfolio/tradability audit."
        )
    elif residual_pass and low_redundancy and selector_not_harmed:
        verdict = "MIXED"
        branch_decision = (
            "Order pressure survives as an independent RL-state candidate, but the equal-weight "
            "selector improvement is too small for direct selector publication."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Order pressure does not pass the integration gate strongly enough for publication "
            "under the current matrix / selector contract."
        )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selector_summary_path = OUT_DIR / f"{ts}_h357_order_pressure_integration_selector_summary.parquet"
    correlations_path = OUT_DIR / f"{ts}_h357_order_pressure_integration_correlations.parquet"
    daily_edges_path = OUT_DIR / f"{ts}_h357_order_pressure_integration_daily_edges.parquet"
    details_path = artifact_path("run_summaries") / f"{ts}_h357_order_pressure_integration_audit_details.json"

    selector_summary.to_parquet(selector_summary_path, index=False)
    corrs.to_parquet(correlations_path, index=False)
    daily_edges.to_parquet(daily_edges_path, index=False)

    summary = {
        "verdict": verdict,
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "protocol": DEFAULT_PROTOCOL.describe(),
        "order_feature": ORDER_FEATURE,
        "residual_feature": RESIDUAL_FEATURE,
        "full_library_column_count": int(len(full_library_columns)),
        "raw_order_pressure_ic": raw_ic,
        "residual_order_pressure_ic": residual_ic,
        "max_abs_candidate_corr": max_abs_corr,
        "max_corr_row": max_corr_row,
        "selector_delta": selector_delta,
        "selector_summary": selector_summary.to_dict("records"),
        "decision_flags": {
            "residual_pass": residual_pass,
            "low_redundancy": low_redundancy,
            "selector_pass": selector_pass,
            "selector_not_harmed": selector_not_harmed,
            "validation_top5_edge_delta": validation_delta,
            "confirmation_top5_edge_delta": confirmation_delta,
        },
        "branch_decision": branch_decision,
        "next_step": {
            "PASSED": "Design the published order-pressure feature artifact and run a portfolio/tradability audit before consumer docs change.",
            "MIXED": "Keep C16 as an RL-state candidate; defer publication until a portfolio/tradability audit or learned model needs it.",
            "FAILED": "Do not publish order pressure as a matrix feature under the current contract.",
        }[verdict],
    }
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_order_pressure_integration_audit",
        name="h357_order_pressure_integration_audit",
        summary=summary,
        artifacts={
            "selector_summary": selector_summary_path,
            "correlations": correlations_path,
            "daily_edges": daily_edges_path,
            "details": details_path,
            "matrix": MATRIX_PATH,
            "order_stats": ORDER_STATS_PATH,
        },
        metadata={
            "signal": "H357",
            "family": "order_pressure",
            "protocol": DEFAULT_PROTOCOL.describe(),
        },
    )

    print(
        f"Panel rows={len(panel):,}, dates={summary['panel_dates']}, tickers={summary['panel_tickers']}",
        flush=True,
    )
    print(
        f"Residual IC={_safe_float(residual_ic['avg_ic']) or 0.0:+.4f}, "
        f"strict={residual_pass}, max_corr={max_abs_corr:.4f}",
        flush=True,
    )
    print(
        f"Selector edge delta val={validation_delta:+.4f}, confirmation={confirmation_delta:+.4f}",
        flush=True,
    )
    print(f"VERDICT: {verdict}", flush=True)
    print(f"summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
