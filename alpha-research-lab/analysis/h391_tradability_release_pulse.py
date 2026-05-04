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


BRANCH_NAME = "h391_tradability_release_pulse"
MODE = "research_branch_tradability_release_pulse"
OUT_DIR = artifact_path("entry_alpha")

CANDIDATE_PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")
LABELS_PATH = data_path("features/entry_alpha/entry_labels_cycle5.parquet")

MIN_TRAIN_YEARS = 2
MIN_YEAR_ROWS = 8
PASS_MIN_LIFT = 0.002
MIN_CAN_SELL_RATE = 0.90

LABEL_COLUMNS = [
    "cycle_return_net",
    "cycle_relative_return_vs_vnindex",
    "buy_now_label",
]

REQUIRED_CANDIDATE_COLUMNS = [
    "time",
    "ticker",
    "candidate_pool_rank",
    "can_buy_next_open",
    "prev_can_buy_next_open",
    "release_flag",
    "can_sell_next_open",
]

OPTIONAL_CANDIDATE_COLUMNS = [
    "selection_score",
    "selection_score_gap_to_top_k_cutoff",
    "h152_limit_release_pressure",
    "h199_floor_release_rebound",
    "h199_ceiling_release_followthrough",
    "h204_sector_accel_release",
    "h204_release_after_floor_pressure",
    "xs_ceiling_count_5d",
    "xs_floor_count_5d",
    "xs_limit_net_5d",
    "full_top5_blocked_buy_count",
    "full_top10_blocked_buy_count",
]

DIAGNOSTIC_COLUMNS = [
    "h152_limit_release_pressure",
    "h199_floor_release_rebound",
    "h199_ceiling_release_followthrough",
    "h204_sector_accel_release",
    "h204_release_after_floor_pressure",
    "xs_ceiling_count_5d",
    "xs_floor_count_5d",
    "xs_limit_net_5d",
    "full_top5_blocked_buy_count",
    "full_top10_blocked_buy_count",
]


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    top_n: int
    kind: str
    primary: bool = False


STATE_SPECS = [
    StateSpec("top5_release", "Top-5 row becomes buyable after prior blocked-buy state", 5, "release", True),
    StateSpec("top5_stable_buyable", "Top-5 row buyable now and on prior decision", 5, "stable"),
    StateSpec("top5_nonrelease_buyable", "Top-5 buyable row that is not a release", 5, "nonrelease"),
    StateSpec("top5_still_blocked", "Top-5 row still blocked after prior blocked-buy state", 5, "blocked"),
    StateSpec("top10_release", "Top-10 row becomes buyable after prior blocked-buy state", 10, "release", True),
    StateSpec("top10_stable_buyable", "Top-10 row buyable now and on prior decision", 10, "stable"),
    StateSpec("top10_nonrelease_buyable", "Top-10 buyable row that is not a release", 10, "nonrelease"),
    StateSpec("top10_still_blocked", "Top-10 row still blocked after prior blocked-buy state", 10, "blocked"),
    StateSpec("top20_release", "Top-20 row becomes buyable after prior blocked-buy state", 20, "release"),
    StateSpec("top20_stable_buyable", "Top-20 row buyable now and on prior decision", 20, "stable"),
    StateSpec("top20_nonrelease_buyable", "Top-20 buyable row that is not a release", 20, "nonrelease"),
    StateSpec("top20_still_blocked", "Top-20 row still blocked after prior blocked-buy state", 20, "blocked"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H391: tradability-release pulse audit. Tests whether high-ranked "
            "entry candidates that become buyable after a prior blocked-buy "
            "state beat rank-matched stable and non-release buyable controls."
        )
    )
    parser.add_argument("--candidate-panel", type=str, default=str(CANDIDATE_PANEL_PATH))
    parser.add_argument("--labels", type=str, default=str(LABELS_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-year-rows", type=int, default=MIN_YEAR_ROWS)
    parser.add_argument("--pass-min-lift", type=float, default=PASS_MIN_LIFT)
    parser.add_argument("--min-can-sell-rate", type=float, default=MIN_CAN_SELL_RATE)
    return parser.parse_args()


def _safe_float(series: pd.Series, default: float = np.nan) -> pd.Series:
    return (
        pd.to_numeric(series, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _safe_bool(series: pd.Series, default: bool = False) -> pd.Series:
    return series.fillna(default).astype(bool)


def _available_columns(path: Path) -> list[str]:
    return list(pd.read_parquet(path).columns)


def _load_panel(candidate_panel_path: Path, labels_path: Path, *, start_year: int, end_year: int) -> pd.DataFrame:
    if int(end_year) >= 2026:
        raise ValueError("H391 must not train or test on 2026+; set --end-year <= 2025")

    candidate_columns = _available_columns(candidate_panel_path)
    missing_candidate = [column for column in REQUIRED_CANDIDATE_COLUMNS if column not in candidate_columns]
    if missing_candidate:
        raise ValueError(f"Candidate panel missing required columns: {missing_candidate}")
    read_columns = REQUIRED_CANDIDATE_COLUMNS + [
        column for column in OPTIONAL_CANDIDATE_COLUMNS if column in candidate_columns
    ]
    candidate = pd.read_parquet(candidate_panel_path, columns=read_columns).copy()

    labels = pd.read_parquet(labels_path).copy()
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
    panel = panel.loc[panel["time"].dt.year.between(int(start_year), int(end_year))].copy()
    panel["candidate_pool_rank"] = _safe_float(panel["candidate_pool_rank"])
    panel["rank_bucket"] = panel["candidate_pool_rank"].round().astype("Int64")
    for column in LABEL_COLUMNS:
        panel[column] = _safe_float(panel[column])
    for column in OPTIONAL_CANDIDATE_COLUMNS:
        if column not in panel.columns:
            panel[column] = np.nan
        panel[column] = _safe_float(panel[column])
    panel["can_buy_next_open"] = _safe_bool(panel["can_buy_next_open"])
    panel["prev_can_buy_next_open"] = _safe_bool(panel["prev_can_buy_next_open"])
    panel["release_flag"] = _safe_bool(panel["release_flag"])
    panel["can_sell_next_open"] = _safe_bool(panel["can_sell_next_open"])
    panel["release_calc"] = (~panel["prev_can_buy_next_open"]) & panel["can_buy_next_open"]
    panel["release"] = panel["release_flag"] & panel["release_calc"]
    panel["release_flag_mismatch"] = panel["release_flag"] != panel["release_calc"]
    panel["stable_buyable"] = panel["prev_can_buy_next_open"] & panel["can_buy_next_open"]
    panel["nonrelease_buyable"] = panel["can_buy_next_open"] & (~panel["release"])
    panel["still_blocked"] = (~panel["prev_can_buy_next_open"]) & (~panel["can_buy_next_open"])

    for top_n in [5, 10, 20]:
        rank_mask = panel["candidate_pool_rank"] <= float(top_n)
        panel[f"top{top_n}_release"] = rank_mask & panel["release"]
        panel[f"top{top_n}_stable_buyable"] = rank_mask & panel["stable_buyable"]
        panel[f"top{top_n}_nonrelease_buyable"] = rank_mask & panel["nonrelease_buyable"]
        panel[f"top{top_n}_still_blocked"] = rank_mask & panel["still_blocked"]

    panel = panel.dropna(
        subset=[
            "time",
            "ticker",
            "candidate_pool_rank",
            "cycle_return_net",
            "cycle_relative_return_vs_vnindex",
        ]
    ).copy()
    panel["year"] = panel["time"].dt.year.astype(int)
    return panel.sort_values(["time", "candidate_pool_rank", "ticker"]).reset_index(drop=True)


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    if state not in panel.columns:
        raise ValueError(f"Unknown state {state!r}")
    return panel[state].fillna(False).astype(bool)


def _metric_record(frame: pd.DataFrame) -> dict[str, object]:
    record: dict[str, object] = {
        "rows": int(len(frame)),
        "mean_abs_return": float(frame["cycle_return_net"].mean()) if not frame.empty else None,
        "mean_relative_return": float(frame["cycle_relative_return_vs_vnindex"].mean()) if not frame.empty else None,
        "median_relative_return": float(frame["cycle_relative_return_vs_vnindex"].median()) if not frame.empty else None,
        "hit_rate": float(frame["buy_now_label"].mean()) if not frame.empty else None,
        "mean_candidate_rank": float(frame["candidate_pool_rank"].mean()) if not frame.empty else None,
        "can_sell_next_open_rate": float(frame["can_sell_next_open"].mean()) if not frame.empty else None,
        "release_flag_mismatch_rate": float(frame["release_flag_mismatch"].mean()) if not frame.empty else None,
    }
    for column in DIAGNOSTIC_COLUMNS:
        record[f"mean_{column}"] = float(frame[column].mean()) if not frame.empty else None
    return record


def _matched_control_mean(
    state_frame: pd.DataFrame,
    control_frame: pd.DataFrame,
    value_col: str,
) -> tuple[float | None, float | None]:
    state = state_frame[["rank_bucket"]].copy()
    control = control_frame[["rank_bucket", value_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if state.empty or control.empty:
        return None, None
    rank_means = control.groupby("rank_bucket")[value_col].mean()
    matched = state["rank_bucket"].map(rank_means).dropna()
    if matched.empty:
        return None, 0.0
    return float(matched.mean()), float(len(matched) / len(state))


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
            train_state = train.loc[_state_mask(train, spec.name)].copy()
            test_state = test.loc[_state_mask(test, spec.name)].copy()
            train_metrics = _metric_record(train_state)
            test_metrics = _metric_record(test_state)
            row = {
                "test_year": int(test_year),
                "train_start_year": int(min(train_years)),
                "train_end_year": int(max(train_years)),
                "state": spec.name,
                "label": spec.label,
                "top_n": int(spec.top_n),
                "kind": spec.kind,
                "primary": bool(spec.primary),
                **{f"train_{key}": value for key, value in train_metrics.items()},
                **{f"test_{key}": value for key, value in test_metrics.items()},
            }
            if spec.kind == "release":
                stable = test.loc[_state_mask(test, f"top{spec.top_n}_stable_buyable")].copy()
                nonrelease = test.loc[_state_mask(test, f"top{spec.top_n}_nonrelease_buyable")].copy()
                blocked = test.loc[_state_mask(test, f"top{spec.top_n}_still_blocked")].copy()
                stable_mean, stable_coverage = _matched_control_mean(
                    test_state,
                    stable,
                    "cycle_relative_return_vs_vnindex",
                )
                nonrelease_mean, nonrelease_coverage = _matched_control_mean(
                    test_state,
                    nonrelease,
                    "cycle_relative_return_vs_vnindex",
                )
                blocked_mean, blocked_coverage = _matched_control_mean(
                    test_state,
                    blocked,
                    "cycle_relative_return_vs_vnindex",
                )
                state_mean = test_metrics.get("mean_relative_return")
                row.update(
                    {
                        "matched_stable_mean_relative_return": stable_mean,
                        "matched_stable_coverage": stable_coverage,
                        "lift_vs_matched_stable": (
                            float(state_mean) - float(stable_mean)
                            if state_mean is not None and stable_mean is not None
                            else None
                        ),
                        "matched_nonrelease_mean_relative_return": nonrelease_mean,
                        "matched_nonrelease_coverage": nonrelease_coverage,
                        "lift_vs_matched_nonrelease": (
                            float(state_mean) - float(nonrelease_mean)
                            if state_mean is not None and nonrelease_mean is not None
                            else None
                        ),
                        "matched_still_blocked_mean_relative_return": blocked_mean,
                        "matched_still_blocked_coverage": blocked_coverage,
                        "lift_vs_matched_still_blocked": (
                            float(state_mean) - float(blocked_mean)
                            if state_mean is not None and blocked_mean is not None
                            else None
                        ),
                    }
                )
            rows.append(row)
    return pd.DataFrame(rows)


def _mean_or_none(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return None
    return float(clean.mean())


def _safe_scalar(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _summarize_states(folds: pd.DataFrame, *, min_year_rows: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        state_rows = folds.loc[folds["state"] == spec.name].copy()
        valid = state_rows.loc[state_rows["test_rows"] >= int(min_year_rows)].copy()
        conf = valid.loc[valid["test_year"] == 2025]
        record = {
            "state": spec.name,
            "label": spec.label,
            "top_n": int(spec.top_n),
            "kind": spec.kind,
            "primary": bool(spec.primary),
            "wf_years": int(len(valid)),
            "mean_rows": float(valid["test_rows"].mean()) if not valid.empty else 0.0,
            "mean_abs_return": _mean_or_none(valid["test_mean_abs_return"]),
            "mean_relative_return": _mean_or_none(valid["test_mean_relative_return"]),
            "median_relative_return": _mean_or_none(valid["test_median_relative_return"]),
            "mean_hit_rate": _mean_or_none(valid["test_hit_rate"]),
            "mean_candidate_rank": _mean_or_none(valid["test_mean_candidate_rank"]),
            "mean_can_sell_next_open_rate": _mean_or_none(valid["test_can_sell_next_open_rate"]),
            "confirmation_2025_relative_return": (
                float(conf.iloc[0]["test_mean_relative_return"])
                if not conf.empty and pd.notna(conf.iloc[0]["test_mean_relative_return"])
                else None
            ),
        }
        for column in DIAGNOSTIC_COLUMNS:
            record[f"mean_{column}"] = _mean_or_none(valid[f"test_mean_{column}"])
        if spec.kind == "release":
            for suffix in ["stable", "nonrelease", "still_blocked"]:
                lift_col = f"lift_vs_matched_{suffix}"
                coverage_col = f"matched_{suffix}_coverage"
                if lift_col in valid.columns:
                    record[f"mean_lift_vs_matched_{suffix}"] = _mean_or_none(valid[lift_col])
                    record[f"pos_lift_vs_matched_{suffix}_years"] = int(
                        (_safe_float(valid[lift_col], np.nan) > 0.0).sum()
                    )
                    record[f"mean_matched_{suffix}_coverage"] = _mean_or_none(valid[coverage_col])
                    record[f"confirmation_2025_lift_vs_matched_{suffix}"] = (
                        float(conf.iloc[0][lift_col])
                        if not conf.empty and pd.notna(conf.iloc[0].get(lift_col))
                        else None
                    )
        rows.append(record)
    return pd.DataFrame(rows).sort_values(
        by=["kind", "top_n", "mean_relative_return"],
        ascending=[True, True, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, state: str) -> dict[str, object]:
    row = summary.loc[summary["state"] == state]
    return row.iloc[0].to_dict() if not row.empty else {}


def _release_passes(
    summary: pd.DataFrame,
    *,
    state: str,
    min_year_rows: int,
    pass_min_lift: float,
    min_can_sell_rate: float,
) -> bool:
    row = _state_record(summary, state)
    years = int(row.get("wf_years") or 0)
    if years <= 0:
        return False
    required_years = max(3, int(np.ceil(0.60 * years)))
    if (_safe_scalar(row.get("mean_rows")) or 0.0) < int(min_year_rows):
        return False
    if (_safe_scalar(row.get("mean_relative_return")) or 0.0) <= 0.0:
        return False
    if (_safe_scalar(row.get("mean_can_sell_next_open_rate")) or 0.0) < float(min_can_sell_rate):
        return False
    for suffix in ["stable", "nonrelease"]:
        if (_safe_scalar(row.get(f"mean_lift_vs_matched_{suffix}")) or 0.0) <= float(pass_min_lift):
            return False
        if int(row.get(f"pos_lift_vs_matched_{suffix}_years") or 0) < required_years:
            return False
        conf = _safe_scalar(row.get(f"confirmation_2025_lift_vs_matched_{suffix}"))
        if conf is not None and conf <= 0.0:
            return False
    return True


def _release_mixed(summary: pd.DataFrame, *, state: str) -> bool:
    row = _state_record(summary, state)
    return (
        int(row.get("wf_years") or 0) > 0
        and (_safe_scalar(row.get("mean_relative_return")) or 0.0) > 0.0
        and (
            (_safe_scalar(row.get("mean_lift_vs_matched_stable")) or 0.0) > 0.0
            or (_safe_scalar(row.get("mean_lift_vs_matched_nonrelease")) or 0.0) > 0.0
        )
    )


def _verdict(
    summary: pd.DataFrame,
    *,
    min_year_rows: int,
    pass_min_lift: float,
    min_can_sell_rate: float,
) -> tuple[str, str, str, list[str], list[str]]:
    primary_states = [spec.name for spec in STATE_SPECS if spec.primary]
    pass_states = [
        state
        for state in primary_states
        if _release_passes(
            summary,
            state=state,
            min_year_rows=int(min_year_rows),
            pass_min_lift=float(pass_min_lift),
            min_can_sell_rate=float(min_can_sell_rate),
        )
    ]
    if pass_states:
        return (
            "PASSED",
            "offline_evidence",
            "A high-ranked tradability-release state beat rank-matched stable and non-release buyable controls.",
            pass_states,
            [],
        )
    mixed_states = [state for state in primary_states if _release_mixed(summary, state=state)]
    if mixed_states:
        return (
            "MIXED",
            "park_or_narrow",
            "A release state was directionally positive but failed matched-control consistency.",
            [],
            mixed_states,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "High-ranked tradability-release rows did not beat rank-matched stable or non-release buyable controls.",
        [],
        [],
    )


def main() -> None:
    args = parse_args()
    panel = _load_panel(
        Path(args.candidate_panel),
        Path(args.labels),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    if panel.empty:
        raise ValueError("No rows after building H391 panel")
    folds = _fold_rows(panel, min_train_years=int(args.min_train_years))
    if folds.empty:
        raise ValueError("No walk-forward folds produced")
    state_summary = _summarize_states(folds, min_year_rows=int(args.min_year_rows))
    verdict, durable_status, branch_decision, pass_states, mixed_states = _verdict(
        state_summary,
        min_year_rows=int(args.min_year_rows),
        pass_min_lift=float(args.pass_min_lift),
        min_can_sell_rate=float(args.min_can_sell_rate),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    key_states = {spec.name: _state_record(state_summary, spec.name) for spec in STATE_SPECS}
    summary = {
        "branch": "tradability_release_pulse",
        "experiment_id": "H391",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "pass_states": pass_states,
        "mixed_states": mixed_states,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "pass_min_lift": float(args.pass_min_lift),
            "min_can_sell_rate": float(args.min_can_sell_rate),
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "primary_states": [spec.name for spec in STATE_SPECS if spec.primary],
            "primary_target": "cycle_relative_return_vs_vnindex",
            "matched_controls": [
                "same-year same-rank stable_buyable",
                "same-year same-rank nonrelease_buyable",
            ],
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "release_rows": int(panel["release"].sum()),
        "release_flag_mismatches": int(panel["release_flag_mismatch"].sum()),
        "key_states": key_states,
        "pass_rule": (
            "PASS if top5_release or top10_release has positive mean relative "
            "return, can-sell rate above min_can_sell_rate, mean lift above "
            "pass_min_lift versus both same-rank stable and same-rank "
            "non-release buyable controls, at least 60% positive-lift years, "
            "and positive 2025 matched-control lifts. MIXED if a primary "
            "release state is only directionally positive. Otherwise FAILED."
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
            "candidate_panel": Path(args.candidate_panel),
            "labels": Path(args.labels),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "pass_min_lift": float(args.pass_min_lift),
            "min_can_sell_rate": float(args.min_can_sell_rate),
        },
    )

    display_columns = [
        "state",
        "wf_years",
        "mean_rows",
        "mean_relative_return",
        "mean_hit_rate",
        "mean_can_sell_next_open_rate",
        "mean_candidate_rank",
        "mean_lift_vs_matched_stable",
        "pos_lift_vs_matched_stable_years",
        "confirmation_2025_lift_vs_matched_stable",
        "mean_lift_vs_matched_nonrelease",
        "pos_lift_vs_matched_nonrelease_years",
        "confirmation_2025_lift_vs_matched_nonrelease",
    ]
    display = state_summary.loc[state_summary["kind"] == "release", display_columns].copy()
    print("H391 tradability release pulse")
    print(f"saved_summary={summary_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(f"verdict={verdict} | pass_states={pass_states} | mixed_states={mixed_states}")
    print(display.to_string(index=False))


if __name__ == "__main__":
    main()
