from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


BRANCH_NAME = "h388_fresh_selection_pulse"
MODE = "research_branch_fresh_selection_pulse"
OUT_DIR = artifact_path("entry_alpha")

MIN_TRAIN_YEARS = 2
MIN_YEAR_ROWS = 20
FRESH_DORMANCY_DAYS = 20
STALE_REPEAT_MAX_DAYS = 19
PASS_MIN_LIFT = 0.002

LABEL_COLUMNS = [
    "cycle_return_net",
    "cycle_relative_return_vs_vnindex",
    "buy_now_label",
]


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    family: str


STATE_SPECS = [
    StateSpec("top5_all", "Buyable top-5 candidate rows", "top5"),
    StateSpec("top5_incumbent", "Top-5 rows that were also top-5 on the previous trading day", "top5"),
    StateSpec("top5_stale_repeat", "Top-5 rows returning after 2-19 trading days", "top5"),
    StateSpec("top5_fresh20", "Top-5 rows returning after at least 20 trading days out", "top5"),
    StateSpec("top5_first_ever", "Top-5 rows with no prior top-5 appearance in panel history", "top5"),
    StateSpec("top10_all", "Buyable top-10 candidate rows", "top10"),
    StateSpec("top10_incumbent", "Top-10 rows that were also top-10 on the previous trading day", "top10"),
    StateSpec("top10_stale_repeat", "Top-10 rows returning after 2-19 trading days", "top10"),
    StateSpec("top10_fresh20", "Top-10 rows returning after at least 20 trading days out", "top10"),
    StateSpec("top10_first_ever", "Top-10 rows with no prior top-10 appearance in panel history", "top10"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H388: fresh selection pulse audit. Computes prior top-5/top-10 "
            "candidate-set appearances and tests whether reappearances after "
            "dormancy beat incumbent and short-repeat candidate rows."
        )
    )
    parser.add_argument(
        "--candidate-panel",
        type=str,
        default=str(data_path("features/entry_alpha/candidate_panel_daily.parquet")),
    )
    parser.add_argument(
        "--labels",
        type=str,
        default=str(data_path("features/entry_alpha/entry_labels_cycle5.parquet")),
    )
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-year-rows", type=int, default=MIN_YEAR_ROWS)
    parser.add_argument("--fresh-dormancy-days", type=int, default=FRESH_DORMANCY_DAYS)
    parser.add_argument("--stale-repeat-max-days", type=int, default=STALE_REPEAT_MAX_DAYS)
    parser.add_argument("--pass-min-lift", type=float, default=PASS_MIN_LIFT)
    return parser.parse_args()


def _safe_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).astype(float)


def _load_panel(
    candidate_panel_path: Path,
    labels_path: Path,
    *,
    start_year: int,
    end_year: int,
    fresh_dormancy_days: int,
    stale_repeat_max_days: int,
) -> pd.DataFrame:
    if int(end_year) >= 2026:
        raise ValueError("H388 must not train or test on 2026+; set --end-year <= 2025")

    candidate = pd.read_parquet(candidate_panel_path).copy()
    labels = pd.read_parquet(labels_path).copy()
    required_candidate = ["time", "ticker", "candidate_pool_rank", "can_buy_next_open"]
    missing_candidate = [column for column in required_candidate if column not in candidate.columns]
    if missing_candidate:
        raise ValueError(f"Candidate panel missing required columns: {missing_candidate}")
    missing_labels = [column for column in LABEL_COLUMNS if column not in labels.columns]
    if missing_labels:
        raise ValueError(f"Labels file missing required columns: {missing_labels}")

    for frame in [candidate, labels]:
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
        frame["ticker"] = frame["ticker"].astype(str).str.upper()

    panel = candidate.merge(
        labels[["time", "ticker", *LABEL_COLUMNS]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    panel["candidate_pool_rank"] = _safe_float(panel["candidate_pool_rank"])
    panel["cycle_return_net"] = _safe_float(panel["cycle_return_net"])
    panel["cycle_relative_return_vs_vnindex"] = _safe_float(panel["cycle_relative_return_vs_vnindex"])
    panel["buy_now_label"] = _safe_float(panel["buy_now_label"])
    panel["can_buy_next_open"] = panel["can_buy_next_open"].fillna(False).astype(bool)
    panel = panel.dropna(
        subset=[
            "time",
            "ticker",
            "candidate_pool_rank",
            "cycle_return_net",
            "cycle_relative_return_vs_vnindex",
        ]
    ).copy()
    panel = panel.sort_values(["time", "candidate_pool_rank", "ticker"]).reset_index(drop=True)
    dates = pd.Series(sorted(panel["time"].unique()))
    date_idx = {pd.Timestamp(date): idx for idx, date in enumerate(dates)}
    panel["date_idx"] = panel["time"].map(date_idx).astype(int)
    panel["row_id"] = np.arange(len(panel), dtype=int)
    panel["in_top5"] = panel["candidate_pool_rank"] <= 5.0
    panel["in_top10"] = panel["candidate_pool_rank"] <= 10.0

    for top_n in [5, 10]:
        in_col = f"in_top{top_n}"
        prev_col = f"prev_top{top_n}_date_idx"
        days_col = f"trading_days_since_top{top_n}"
        top = panel.loc[panel[in_col], ["row_id", "ticker", "date_idx"]].copy()
        top = top.sort_values(["ticker", "date_idx", "row_id"])
        top[prev_col] = top.groupby("ticker")["date_idx"].shift(1)
        top[days_col] = top["date_idx"] - top[prev_col]
        panel = panel.merge(top[["row_id", prev_col, days_col]], on="row_id", how="left", validate="one_to_one")

        active = panel[in_col] & panel["can_buy_next_open"]
        panel[f"top{top_n}_all"] = active
        panel[f"top{top_n}_incumbent"] = active & (panel[days_col] == 1.0)
        panel[f"top{top_n}_stale_repeat"] = (
            active
            & (panel[days_col] >= 2.0)
            & (panel[days_col] <= float(stale_repeat_max_days))
        )
        panel[f"top{top_n}_fresh20"] = active & (panel[days_col] >= float(fresh_dormancy_days))
        panel[f"top{top_n}_first_ever"] = active & panel[days_col].isna()

    panel["year"] = panel["time"].dt.year.astype(int)
    panel = panel.loc[panel["year"].between(int(start_year), int(end_year))].copy()
    return panel.reset_index(drop=True)


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    if state not in panel.columns:
        raise ValueError(f"Unknown state {state!r}")
    return panel[state].fillna(False).astype(bool)


def _metric_record(frame: pd.DataFrame, *, top_n: int | None) -> dict[str, object]:
    days_col = f"trading_days_since_top{top_n}" if top_n else None
    return {
        "rows": int(len(frame)),
        "mean_abs_return": float(frame["cycle_return_net"].mean()) if not frame.empty else None,
        "mean_relative_return": float(frame["cycle_relative_return_vs_vnindex"].mean()) if not frame.empty else None,
        "median_relative_return": float(frame["cycle_relative_return_vs_vnindex"].median()) if not frame.empty else None,
        "hit_rate": float(frame["buy_now_label"].mean()) if not frame.empty else None,
        "mean_candidate_rank": float(frame["candidate_pool_rank"].mean()) if not frame.empty else None,
        "mean_days_since": (
            float(frame[days_col].mean()) if days_col and frame[days_col].notna().any() else None
        ),
        "median_days_since": (
            float(frame[days_col].median()) if days_col and frame[days_col].notna().any() else None
        ),
    }


def _fold_rows(panel: pd.DataFrame, *, min_train_years: int) -> pd.DataFrame:
    years = sorted(int(year) for year in panel["year"].unique())
    rows: list[dict[str, object]] = []
    for test_year in years:
        train_years = [year for year in years if year < int(test_year)]
        if len(train_years) < int(min_train_years):
            continue
        train = panel.loc[panel["year"].isin(train_years)].copy()
        test = panel.loc[panel["year"] == int(test_year)].copy()
        for spec in STATE_SPECS:
            top_n = 5 if spec.family == "top5" else 10
            train_state = train.loc[_state_mask(train, spec.name)].copy()
            test_state = test.loc[_state_mask(test, spec.name)].copy()
            train_metrics = _metric_record(train_state, top_n=top_n)
            test_metrics = _metric_record(test_state, top_n=top_n)
            rows.append(
                {
                    "test_year": int(test_year),
                    "train_start_year": int(min(train_years)),
                    "train_end_year": int(max(train_years)),
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    **{f"train_{key}": value for key, value in train_metrics.items()},
                    **{f"test_{key}": value for key, value in test_metrics.items()},
                }
            )
    return pd.DataFrame(rows)


def _summarize_states(folds: pd.DataFrame, *, min_year_rows: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        state_rows = folds.loc[folds["state"] == spec.name].copy()
        valid = state_rows.loc[state_rows["test_rows"] >= int(min_year_rows)].copy()
        if valid.empty:
            rows.append(
                {
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    "wf_years": 0,
                    "mean_rows": 0.0,
                    "mean_abs_return": None,
                    "mean_relative_return": None,
                    "median_relative_return": None,
                    "mean_hit_rate": None,
                    "mean_candidate_rank": None,
                    "mean_days_since": None,
                    "confirmation_2025_relative_return": None,
                }
            )
            continue
        conf = valid.loc[valid["test_year"] == 2025]
        rows.append(
            {
                "state": spec.name,
                "label": spec.label,
                "family": spec.family,
                "wf_years": int(len(valid)),
                "mean_rows": float(valid["test_rows"].mean()),
                "mean_abs_return": float(valid["test_mean_abs_return"].mean()),
                "mean_relative_return": float(valid["test_mean_relative_return"].mean()),
                "median_relative_return": float(valid["test_median_relative_return"].mean()),
                "mean_hit_rate": float(valid["test_hit_rate"].mean()),
                "mean_candidate_rank": float(valid["test_mean_candidate_rank"].mean()),
                "mean_days_since": (
                    float(valid["test_mean_days_since"].dropna().mean())
                    if valid["test_mean_days_since"].notna().any()
                    else None
                ),
                "confirmation_2025_relative_return": (
                    float(conf.iloc[0]["test_mean_relative_return"]) if not conf.empty else None
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        by=["mean_relative_return", "mean_rows"],
        ascending=[False, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, state: str) -> dict[str, object]:
    row = summary.loc[summary["state"] == state]
    return row.iloc[0].to_dict() if not row.empty else {}


def _safe_scalar(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _lift_stats(folds: pd.DataFrame, state: str, control: str, *, min_year_rows: int) -> dict[str, object]:
    left = folds.loc[
        folds["state"] == state,
        ["test_year", "test_mean_relative_return", "test_rows"],
    ]
    right = folds.loc[
        folds["state"] == control,
        ["test_year", "test_mean_relative_return", "test_rows"],
    ]
    merged = left.merge(right, on="test_year", how="inner", suffixes=("_state", "_control"))
    merged = merged.loc[
        (merged["test_rows_state"] >= int(min_year_rows))
        & (merged["test_rows_control"] >= int(min_year_rows))
    ].copy()
    if merged.empty:
        return {
            "state": state,
            "control": control,
            "years": 0,
            "mean_lift": None,
            "pos_lift_years": 0,
            "pct_pos_lift_years": None,
            "confirmation_2025_lift": None,
        }
    merged["lift"] = merged["test_mean_relative_return_state"] - merged["test_mean_relative_return_control"]
    conf = merged.loc[merged["test_year"] == 2025]
    return {
        "state": state,
        "control": control,
        "years": int(len(merged)),
        "mean_lift": float(merged["lift"].mean()),
        "pos_lift_years": int((merged["lift"] > 0.0).sum()),
        "pct_pos_lift_years": float((merged["lift"] > 0.0).mean()),
        "confirmation_2025_lift": float(conf.iloc[0]["lift"]) if not conf.empty else None,
    }


def _passes_controls(
    folds: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    state: str,
    controls: list[str],
    min_year_rows: int,
    pass_min_lift: float,
) -> tuple[bool, dict[str, dict[str, object]]]:
    state_row = _state_record(summary, state)
    if (
        (_safe_scalar(state_row.get("mean_rows")) or 0.0) < int(min_year_rows)
        or (_safe_scalar(state_row.get("mean_relative_return")) or 0.0) <= 0.0
    ):
        return False, {control: _lift_stats(folds, state, control, min_year_rows=int(min_year_rows)) for control in controls}
    stats = {
        control: _lift_stats(folds, state, control, min_year_rows=int(min_year_rows))
        for control in controls
    }
    for control_stats in stats.values():
        years = int(control_stats.get("years") or 0)
        if years == 0:
            return False, stats
        required_years = max(3, int(np.ceil(0.60 * years)))
        if (_safe_scalar(control_stats.get("mean_lift")) or 0.0) <= float(pass_min_lift):
            return False, stats
        if int(control_stats.get("pos_lift_years") or 0) < required_years:
            return False, stats
        conf = _safe_scalar(control_stats.get("confirmation_2025_lift"))
        if conf is not None and conf <= 0.0:
            return False, stats
    return True, stats


def _verdict(
    folds: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    min_year_rows: int,
    pass_min_lift: float,
) -> tuple[str, str, str, list[str], dict[str, object]]:
    top5_pass, top5_stats = _passes_controls(
        folds,
        summary,
        state="top5_fresh20",
        controls=["top5_all", "top5_incumbent", "top5_stale_repeat"],
        min_year_rows=int(min_year_rows),
        pass_min_lift=float(pass_min_lift),
    )
    top10_pass, top10_stats = _passes_controls(
        folds,
        summary,
        state="top10_fresh20",
        controls=["top10_all", "top10_incumbent", "top10_stale_repeat"],
        min_year_rows=int(min_year_rows),
        pass_min_lift=float(pass_min_lift),
    )
    first5_pass, first5_stats = _passes_controls(
        folds,
        summary,
        state="top5_first_ever",
        controls=["top5_all", "top5_incumbent"],
        min_year_rows=int(min_year_rows),
        pass_min_lift=float(pass_min_lift),
    )
    diagnostics = {
        "top5_fresh20": top5_stats,
        "top10_fresh20": top10_stats,
        "top5_first_ever": first5_stats,
    }
    pass_states: list[str] = []
    if top5_pass:
        pass_states.append("top5_fresh20")
    if top10_pass:
        pass_states.append("top10_fresh20")
    if pass_states:
        return (
            "PASSED",
            "offline_evidence",
            "A fresh selection reappearance state beat all, incumbent, and short-repeat controls.",
            pass_states,
            diagnostics,
        )
    if first5_pass:
        return (
            "MIXED",
            "park_or_narrow",
            "Only first-ever top-5 appearances cleared controls; dormancy reappearances did not.",
            ["top5_first_ever"],
            diagnostics,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "No fresh selection pulse state beat all, incumbent, and short-repeat controls cleanly.",
        [],
        diagnostics,
    )


def main() -> None:
    args = parse_args()
    panel = _load_panel(
        Path(args.candidate_panel),
        Path(args.labels),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        fresh_dormancy_days=int(args.fresh_dormancy_days),
        stale_repeat_max_days=int(args.stale_repeat_max_days),
    )
    if panel.empty:
        raise ValueError("No rows after building H388 panel")
    folds = _fold_rows(panel, min_train_years=int(args.min_train_years))
    if folds.empty:
        raise ValueError("No walk-forward folds produced")
    state_summary = _summarize_states(folds, min_year_rows=int(args.min_year_rows))
    verdict, durable_status, branch_decision, pass_states, lift_diagnostics = _verdict(
        folds,
        state_summary,
        min_year_rows=int(args.min_year_rows),
        pass_min_lift=float(args.pass_min_lift),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    key_states = {
        state: _state_record(state_summary, state)
        for state in [
            "top5_all",
            "top5_incumbent",
            "top5_stale_repeat",
            "top5_fresh20",
            "top5_first_ever",
            "top10_all",
            "top10_incumbent",
            "top10_stale_repeat",
            "top10_fresh20",
        ]
    }
    summary = {
        "branch": "fresh_selection_pulse",
        "experiment_id": "H388",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "pass_states": pass_states,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "fresh_dormancy_days": int(args.fresh_dormancy_days),
            "stale_repeat_max_days": int(args.stale_repeat_max_days),
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "target": "cycle_relative_return_vs_vnindex",
            "scope": "buyable top-5/top-10 candidate rows from entry-alpha panel",
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "key_states": key_states,
        "lift_diagnostics": lift_diagnostics,
        "pass_rule": (
            "PASS if top5_fresh20 or top10_fresh20 has positive mean cycle "
            "relative return and beats all, incumbent, and stale-repeat "
            "controls by more than pass_min_lift on average, with at least 60% "
            "positive-lift years and positive 2025 lifts. MIXED if only "
            "first-ever top5 clears. Otherwise FAILED."
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
        },
        metadata={
            "candidate_panel": Path(args.candidate_panel),
            "labels": Path(args.labels),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "fresh_dormancy_days": int(args.fresh_dormancy_days),
            "stale_repeat_max_days": int(args.stale_repeat_max_days),
            "pass_min_lift": float(args.pass_min_lift),
        },
    )

    print("H388 fresh selection pulse")
    print(f"saved_summary={summary_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(f"verdict={verdict} | pass_states={pass_states}")
    print(
        state_summary[
            [
                "state",
                "family",
                "wf_years",
                "mean_rows",
                "mean_relative_return",
                "mean_abs_return",
                "mean_hit_rate",
                "mean_candidate_rank",
                "mean_days_since",
                "confirmation_2025_relative_return",
            ]
        ].to_string(index=False)
    )
    for state, controls in lift_diagnostics.items():
        print(f"\n{state} lift diagnostics")
        for control, stats in controls.items():
            print(f"  vs {control}: {stats}")


if __name__ == "__main__":
    main()
