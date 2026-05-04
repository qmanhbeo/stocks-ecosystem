from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


BRANCH_NAME = "h381_silent_order_pressure"
MODE = "research_branch_silent_order_pressure"
OUT_DIR = artifact_path("order_pressure")

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
NEWS_PATH = data_path("features/news/datasets/news_daily_features.parquet")

MIN_YEAR_ROWS = 500
MIN_TRAIN_YEARS = 2


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    peer: str | None = None
    baseline: str = "c16_all"


STATE_SPECS = [
    StateSpec("c16_all", "All C16 rows", None, "c16_all"),
    StateSpec("silent_1d", "C16 rows with phobert_article_count_1d == 0", "active_1d", "c16_all"),
    StateSpec("active_1d", "C16 rows with phobert_article_count_1d > 0", "silent_1d", "c16_all"),
    StateSpec("silent_5d", "C16 rows with phobert_article_count_5d == 0", "active_5d", "c16_all"),
    StateSpec("active_5d", "C16 rows with phobert_article_count_5d > 0", "silent_5d", "c16_all"),
    StateSpec("c16_down_market", "All C16 rows on down-market days", None, "c16_down_market"),
    StateSpec(
        "silent_1d_down_market",
        "No 1d PhoBERT news on down-market days",
        "active_1d_down_market",
        "c16_down_market",
    ),
    StateSpec(
        "active_1d_down_market",
        "Active 1d PhoBERT news on down-market days",
        "silent_1d_down_market",
        "c16_down_market",
    ),
    StateSpec(
        "silent_5d_down_market",
        "No 5d PhoBERT news on down-market days",
        "active_5d_down_market",
        "c16_down_market",
    ),
    StateSpec(
        "active_5d_down_market",
        "Active 5d PhoBERT news on down-market days",
        "silent_5d_down_market",
        "c16_down_market",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H381: test whether C16 order pressure is stronger before public "
            "PhoBERT news narrative appears. Fixed no-news states, TRUE "
            "walk-forward yearly folds, no 2026 rows."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--news-path", type=str, default=str(NEWS_PATH))
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-year-rows", type=int, default=MIN_YEAR_ROWS)
    return parser.parse_args()


def _safe_ic(frame: pd.DataFrame, score_col: str, target_col: str, min_rows: int) -> dict[str, object]:
    clean = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < int(min_rows) or clean[score_col].nunique() < 3 or clean[target_col].nunique() < 2:
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    rho, p_value = spearmanr(clean[score_col], clean[target_col])
    rho_value = float(np.asarray(rho).flat[0])
    p_value_float = float(np.asarray(p_value).flat[0])
    if not np.isfinite(rho_value):
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    return {"rows": int(len(clean)), "ic": rho_value, "p_value": p_value_float}


def _load_panel(args: argparse.Namespace) -> pd.DataFrame:
    s1 = pd.read_parquet(args.s1_path, columns=["time", "ticker", "actual"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()

    c16 = pd.read_parquet(
        args.c16_path,
        columns=[
            "time",
            "ticker",
            "order_volume_ratio_rank",
            "order_pressure_available",
            "can_buy_next_open",
        ],
    ).copy()
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()

    news = pd.read_parquet(
        args.news_path,
        columns=["date", "ticker", "phobert_article_count_1d", "phobert_article_count_5d"],
    ).copy()
    news = news.rename(columns={"date": "time"})
    news["time"] = pd.to_datetime(news["time"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()

    panel = s1.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.loc[
        panel["time"].dt.year.between(int(args.start_year), int(args.end_year))
    ].copy()
    panel = panel.loc[panel["order_pressure_available"].fillna(False).astype(bool)].copy()
    panel["phobert_article_count_1d"] = pd.to_numeric(
        panel["phobert_article_count_1d"], errors="coerce"
    ).fillna(0.0)
    panel["phobert_article_count_5d"] = pd.to_numeric(
        panel["phobert_article_count_5d"], errors="coerce"
    ).fillna(0.0)
    panel["order_volume_ratio_rank"] = pd.to_numeric(
        panel["order_volume_ratio_rank"], errors="coerce"
    )
    panel["actual"] = pd.to_numeric(panel["actual"], errors="coerce")
    market = panel.groupby("time", as_index=False)["actual"].mean().rename(columns={"actual": "market_actual_mean"})
    market["market_down"] = market["market_actual_mean"] <= 0.5
    panel = panel.merge(market[["time", "market_down"]], on="time", how="left", validate="many_to_one")
    panel["year"] = panel["time"].dt.year.astype(int)
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    base = pd.Series(True, index=panel.index)
    silent_1d = panel["phobert_article_count_1d"].fillna(0.0) <= 0.0
    active_1d = panel["phobert_article_count_1d"].fillna(0.0) > 0.0
    silent_5d = panel["phobert_article_count_5d"].fillna(0.0) <= 0.0
    active_5d = panel["phobert_article_count_5d"].fillna(0.0) > 0.0
    down = panel["market_down"].fillna(False).astype(bool)
    masks = {
        "c16_all": base,
        "silent_1d": silent_1d,
        "active_1d": active_1d,
        "silent_5d": silent_5d,
        "active_5d": active_5d,
        "c16_down_market": down,
        "silent_1d_down_market": silent_1d & down,
        "active_1d_down_market": active_1d & down,
        "silent_5d_down_market": silent_5d & down,
        "active_5d_down_market": active_5d & down,
    }
    if state not in masks:
        raise ValueError(f"Unknown state {state!r}")
    return masks[state]


def _fold_rows(panel: pd.DataFrame, *, min_train_years: int, min_year_rows: int) -> pd.DataFrame:
    years = sorted(int(year) for year in panel["year"].unique())
    rows: list[dict[str, object]] = []
    for test_year in years:
        train_years = [year for year in years if year < int(test_year)]
        if len(train_years) < int(min_train_years):
            continue
        test = panel.loc[panel["year"] == int(test_year)].copy()
        train = panel.loc[panel["year"].isin(train_years)].copy()
        if train.empty or test.empty:
            continue
        for spec in STATE_SPECS:
            train_state = train.loc[_state_mask(train, spec.name)].copy()
            test_state = test.loc[_state_mask(test, spec.name)].copy()
            train_ic = _safe_ic(train_state, "order_volume_ratio_rank", "actual", int(min_year_rows))
            test_ic = _safe_ic(test_state, "order_volume_ratio_rank", "actual", int(min_year_rows))
            rows.append(
                {
                    "test_year": int(test_year),
                    "train_start_year": int(min(train_years)),
                    "train_end_year": int(max(train_years)),
                    "state": spec.name,
                    "label": spec.label,
                    "peer": spec.peer,
                    "baseline": spec.baseline,
                    "train_rows": int(train_ic["rows"]),
                    "train_ic": train_ic["ic"],
                    "train_p_value": train_ic["p_value"],
                    "test_rows": int(test_ic["rows"]),
                    "test_ic": test_ic["ic"],
                    "test_p_value": test_ic["p_value"],
                }
            )
    return pd.DataFrame(rows)


def _summarize_states(folds: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        state_rows = folds.loc[folds["state"] == spec.name].copy()
        valid = state_rows.dropna(subset=["test_ic"]).copy()
        if valid.empty:
            mean_ic = None
            pos_years = 0
            confirmation_2025 = None
        else:
            mean_ic = float(valid["test_ic"].mean())
            pos_years = int((valid["test_ic"] > 0.0).sum())
            conf = valid.loc[valid["test_year"] == 2025, "test_ic"]
            confirmation_2025 = float(conf.iloc[0]) if not conf.empty else None
        rows.append(
            {
                "state": spec.name,
                "label": spec.label,
                "peer": spec.peer,
                "baseline": spec.baseline,
                "wf_mean_ic": mean_ic,
                "wf_years": int(len(valid)),
                "wf_pos_years": pos_years,
                "wf_pct_pos_years": float(pos_years / len(valid)) if len(valid) else None,
                "confirmation_2025_ic": confirmation_2025,
                "mean_test_rows": float(valid["test_rows"].mean()) if not valid.empty else 0.0,
            }
        )
    summary = pd.DataFrame(rows)
    mean_by_state = summary.set_index("state")["wf_mean_ic"].to_dict()
    conf_by_state = summary.set_index("state")["confirmation_2025_ic"].to_dict()
    summary["lift_vs_baseline_mean_ic"] = [
        (row["wf_mean_ic"] - mean_by_state.get(row["baseline"]))
        if row["wf_mean_ic"] is not None and mean_by_state.get(row["baseline"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    summary["lift_vs_peer_mean_ic"] = [
        (row["wf_mean_ic"] - mean_by_state.get(row["peer"]))
        if row["peer"] and row["wf_mean_ic"] is not None and mean_by_state.get(row["peer"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    summary["lift_vs_baseline_2025_ic"] = [
        (row["confirmation_2025_ic"] - conf_by_state.get(row["baseline"]))
        if row["confirmation_2025_ic"] is not None and conf_by_state.get(row["baseline"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    return summary.sort_values(
        by=["wf_mean_ic", "lift_vs_baseline_mean_ic", "mean_test_rows"],
        ascending=[False, False, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, state: str) -> dict[str, object]:
    row = summary.loc[summary["state"] == state]
    if row.empty:
        return {}
    return row.iloc[0].to_dict()


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _verdict(summary: pd.DataFrame) -> tuple[str, str, str]:
    primary = _state_record(summary, "silent_5d")
    fallback = _state_record(summary, "silent_1d")
    down = _state_record(summary, "silent_5d_down_market")
    primary_pass = bool(
        (_safe_float(primary.get("wf_mean_ic")) or 0.0) > 0.0
        and (_safe_float(primary.get("lift_vs_baseline_mean_ic")) or 0.0) > 0.005
        and (_safe_float(primary.get("lift_vs_peer_mean_ic")) or 0.0) > 0.0
        and (_safe_float(primary.get("wf_pct_pos_years")) or 0.0) >= 0.60
        and (_safe_float(primary.get("confirmation_2025_ic")) or 0.0) > 0.0
    )
    fallback_pass = bool(
        (_safe_float(fallback.get("wf_mean_ic")) or 0.0) > 0.0
        and (_safe_float(fallback.get("lift_vs_baseline_mean_ic")) or 0.0) > 0.005
        and (_safe_float(fallback.get("wf_pct_pos_years")) or 0.0) >= 0.60
        and (_safe_float(fallback.get("confirmation_2025_ic")) or 0.0) > 0.0
    )
    down_pass = bool(
        (_safe_float(down.get("wf_mean_ic")) or 0.0) > 0.0
        and (_safe_float(down.get("lift_vs_baseline_mean_ic")) or 0.0) > 0.005
        and (_safe_float(down.get("lift_vs_peer_mean_ic")) or 0.0) > 0.0
        and (_safe_float(down.get("confirmation_2025_ic")) or 0.0) > 0.0
    )
    if primary_pass:
        return (
            "PASSED",
            "offline_evidence",
            "No-5d-news C16 beat all-C16 and active-news C16 under the fixed WF gate.",
        )
    if fallback_pass or down_pass:
        return (
            "MIXED",
            "park_or_narrow",
            "A no-news variant worked, but the primary no-5d-news gate did not fully clear.",
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "No fixed no-news C16 state beat the direct C16 baseline cleanly enough.",
    )


def main() -> None:
    args = parse_args()
    if int(args.end_year) >= 2026:
        raise ValueError("H381 must not train or test on 2026+; set --end-year <= 2025")

    panel = _load_panel(args)
    if panel.empty:
        raise ValueError("No rows after building H381 panel")
    folds = _fold_rows(
        panel,
        min_train_years=int(args.min_train_years),
        min_year_rows=int(args.min_year_rows),
    )
    if folds.empty:
        raise ValueError("No walk-forward fold rows produced")
    state_summary = _summarize_states(folds)
    verdict, durable_status, branch_decision = _verdict(state_summary)

    primary = _state_record(state_summary, "silent_5d")
    one_day = _state_record(state_summary, "silent_1d")
    down = _state_record(state_summary, "silent_5d_down_market")
    c16_all = _state_record(state_summary, "c16_all")
    active_5d = _state_record(state_summary, "active_5d")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    summary = {
        "branch": "silent_order_pressure",
        "experiment_id": "H381",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "target": "actual",
            "score": "order_volume_ratio_rank",
            "primary_state": "silent_5d",
            "direct_variation_benchmark": "c16_all",
            "peer_benchmark": "active_5d",
            "down_market_control": "silent_5d_down_market vs c16_down_market and active_5d_down_market",
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "news_1d_active_share": float((panel["phobert_article_count_1d"] > 0.0).mean()),
        "news_5d_active_share": float((panel["phobert_article_count_5d"] > 0.0).mean()),
        "c16_all": c16_all,
        "silent_5d": primary,
        "active_5d": active_5d,
        "silent_1d": one_day,
        "silent_5d_down_market": down,
        "pass_rule": (
            "PASS if silent_5d WF mean IC is positive, beats all-C16 by >0.005, "
            "beats active_5d, has >=60% positive WF years, and 2025 IC is positive. "
            "MIXED if silent_1d or silent_5d_down_market clears the analogous partial gate. "
            "Otherwise FAILED."
        ),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode=MODE,
        name=BRANCH_NAME,
        summary=summary,
        artifacts={
            "folds": folds_path,
            "states": states_path,
            "s1": Path(args.s1_path),
            "c16": Path(args.c16_path),
            "news": Path(args.news_path),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
        },
    )

    print("H381 silent order pressure")
    print(f"saved_summary={summary_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(
        f"verdict={verdict} | c16_all_ic={_safe_float(c16_all.get('wf_mean_ic')) or 0.0:+.4f} | "
        f"silent_5d_ic={_safe_float(primary.get('wf_mean_ic')) or 0.0:+.4f} | "
        f"active_5d_ic={_safe_float(active_5d.get('wf_mean_ic')) or 0.0:+.4f} | "
        f"silent_5d_lift={_safe_float(primary.get('lift_vs_baseline_mean_ic')) or 0.0:+.4f}"
    )
    print(
        state_summary[
            [
                "state",
                "wf_mean_ic",
                "wf_years",
                "wf_pos_years",
                "confirmation_2025_ic",
                "lift_vs_baseline_mean_ic",
                "lift_vs_peer_mean_ic",
                "mean_test_rows",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
