from __future__ import annotations

import argparse
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (  # noqa: E402
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    build_experiment_context,
    rolling_train_test_years,
    safe_spearman,
    summarize_ic_rows,
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402


BRANCH_NAME = "h400_calendar_as_weak_prior_not_clock"
MODE = "research_branch_calendar_as_weak_prior_not_clock"

H395_PATH = ROOT / "analysis/h395_weak_signal_quorum_sleeve.py"
C16_SCORE_COL = "order_volume_ratio_rank"
CALENDAR_PRIOR_COL = "vote_calendar_weak_prior"
BASE_CALENDAR_COMPONENTS = {"vote_january_first_10_vote", "vote_monday_vote"}
CALENDAR_CONTROL_COLUMNS = [
    "vote_january_first_10_vote",
    "vote_monday_vote",
    "vote_month_end5_vote",
    "vote_t2_weekday_residue_vote",
    CALENDAR_PRIOR_COL,
]

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Exact calendar clocks are too sparse for independent promotion, but "
        "a predeclared calendar-residue vote may add weak incremental context "
        "inside the H395 weak-signal quorum."
    ),
    start_year=2016,
    end_year=2025,
    min_train_years=3,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        "non_calendar_quorum_score": "train-selected H395 weak quorum excluding calendar votes",
        "calendar_quorum_score": "same quorum plus one fixed calendar weak-prior vote",
        CALENDAR_PRIOR_COL: "single predeclared calendar weak-prior vote",
    },
)


def _load_h395_module():
    spec = importlib.util.spec_from_file_location("h395_weak_signal_quorum_sleeve", H395_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load H395 module from {H395_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H400: calendar as one weak prior inside H395 quorum.")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--matrix-path", type=str, default=str(data_path("features/xs_rl_signal_matrix.parquet")))
    parser.add_argument("--c16-path", type=str, default=str(data_path("features/xs_order_pressure_daily.parquet")))
    parser.add_argument("--news-path", type=str, default=str(data_path("features/news/datasets/news_daily_features.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-train-years", type=int, default=SPEC.min_train_years)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-train-avg-ic", type=float, default=0.005)
    parser.add_argument("--min-train-positive-share", type=float, default=0.60)
    parser.add_argument("--max-parent-corr", type=float, default=0.30)
    parser.add_argument("--random-iterations", type=int, default=200)
    parser.add_argument("--random-seed", type=int, default=400)
    return parser.parse_args()


def _calendar_date_frame(panel: pd.DataFrame) -> pd.DataFrame:
    dates = panel[["time"]].drop_duplicates().sort_values("time").reset_index(drop=True)
    dates["year"] = dates["time"].dt.year.astype(int)
    dates["month"] = dates["time"].dt.month.astype(int)
    dates["trading_day_of_year"] = dates.groupby("year").cumcount() + 1
    dates["trading_day_of_month"] = dates.groupby(["year", "month"]).cumcount() + 1
    month_counts = dates.groupby(["year", "month"])["time"].transform("count")
    dates["trading_days_left_in_month"] = month_counts - dates["trading_day_of_month"]
    dates["vote_month_end5_vote"] = (dates["trading_days_left_in_month"] < 5).astype(float)
    dates["vote_t2_weekday_residue_vote"] = dates["time"].dt.dayofweek.isin([2, 4]).astype(float)
    dates["vote_january_first_10_vote"] = (dates["trading_day_of_year"] <= 10).astype(float)
    dates["vote_monday_vote"] = (dates["time"].dt.dayofweek == 0).astype(float)
    dates[CALENDAR_PRIOR_COL] = dates[
        [
            "vote_january_first_10_vote",
            "vote_monday_vote",
            "vote_month_end5_vote",
            "vote_t2_weekday_residue_vote",
        ]
    ].mean(axis=1)
    return dates[["time", *CALENDAR_CONTROL_COLUMNS]]


def add_calendar_prior(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.drop(columns=[col for col in CALENDAR_CONTROL_COLUMNS if col in panel.columns], errors="ignore").copy()
    calendar = _calendar_date_frame(out)
    out = out.merge(calendar, on="time", how="left", validate="many_to_one")
    for column in CALENDAR_CONTROL_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
    return out


def _component_spearman(frame: pd.DataFrame, score_col: str, min_rows: int) -> dict[str, object]:
    return safe_spearman(
        frame,
        score_col,
        S1_TARGET_COL,
        min_rows=int(min_rows),
        min_score_unique=2,
        min_target_unique=2,
    )


def _basket_score(frame: pd.DataFrame, columns: list[str], out_col: str) -> pd.DataFrame:
    out = frame.copy()
    out[out_col] = out[columns].mean(axis=1) if columns else np.nan
    return out


def _avg_positive(values: pd.Series) -> tuple[float | None, int, int, float | None]:
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return None, 0, 0, None
    positives = int((clean > 0.0).sum())
    return float(clean.mean()), positives, int(len(clean)), float(positives / len(clean))


def _yearly_component_summary(panel: pd.DataFrame, component: str, min_year_rows: int) -> dict[str, object]:
    rows = []
    for year, group in panel.groupby("year", sort=True):
        stat = _component_spearman(group, component, int(min_year_rows))
        rows.append({"year": int(year), **stat})
    return summarize_ic_rows(rows)


def _random_extra_control(
    test: pd.DataFrame,
    selected: list[str],
    pool: list[str],
    *,
    base_ic: float | None,
    iterations: int,
    seed: int,
    min_rows: int,
) -> dict[str, object]:
    candidates = [component for component in pool if component not in selected]
    if not candidates or base_ic is None or int(iterations) <= 0:
        return {"random_extra_mean_lift": None, "random_extra_p95_lift": None}
    rng = np.random.default_rng(int(seed))
    lifts = []
    for _ in range(int(iterations)):
        extra = str(rng.choice(candidates))
        scored = _basket_score(test, [*selected, extra], "_random_extra_score")
        stat = _component_spearman(scored, "_random_extra_score", int(min_rows))
        if stat["ic"] is not None:
            lifts.append(float(stat["ic"] - base_ic))
    if not lifts:
        return {"random_extra_mean_lift": None, "random_extra_p95_lift": None}
    return {
        "random_extra_mean_lift": float(np.mean(lifts)),
        "random_extra_p95_lift": float(np.quantile(lifts, 0.95)),
    }


def run_walk_forward(panel: pd.DataFrame, args: argparse.Namespace, spec: ExperimentSpec, h395) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_components = [
        component for component in h395.component_columns() if component not in BASE_CALENDAR_COMPONENTS
    ]
    folds = rolling_train_test_years(
        start_year=spec.start_year,
        end_year=spec.end_year,
        min_train_years=spec.min_train_years,
    )
    fold_rows = []
    selection_rows = []
    scored_tests = []

    for fold in folds:
        test_year = int(fold["test_year"])
        train_years = tuple(int(year) for year in fold["train_years"])
        train = panel.loc[panel["year"].isin(train_years)].copy()
        test = panel.loc[panel["year"].eq(test_year)].copy()
        if train.empty or test.empty:
            continue

        stats = [h395._component_stat(train, component, args) for component in base_components]
        for stat in stats:
            selection_rows.append(
                {
                    "test_year": test_year,
                    "component": stat.name,
                    "train_avg_ic": stat.train_avg_ic,
                    "train_positive_years": stat.train_positive_years,
                    "train_years": stat.train_years,
                    "train_pct_positive_years": stat.train_pct_positive_years,
                    "corr_s1": stat.corr_s1,
                    "corr_c16": stat.corr_c16,
                    "low_corr": stat.low_corr,
                    "selected": stat.selected,
                }
            )

        low_corr_pool = [stat.name for stat in stats if stat.low_corr]
        selected = [stat.name for stat in stats if stat.selected]
        if not selected:
            selected = [
                stat.name
                for stat in sorted(
                    [item for item in stats if item.low_corr and item.train_avg_ic is not None],
                    key=lambda item: float(item.train_avg_ic),
                    reverse=True,
                )[:1]
            ]

        scored = _basket_score(test, selected, "non_calendar_quorum_score")
        scored = _basket_score(scored, [*selected, CALENDAR_PRIOR_COL], "calendar_quorum_score")
        base_stat = _component_spearman(scored, "non_calendar_quorum_score", int(args.min_year_rows))
        calendar_stat = _component_spearman(scored, "calendar_quorum_score", int(args.min_year_rows))
        calendar_only_stat = _component_spearman(scored, CALENDAR_PRIOR_COL, int(args.min_year_rows))
        s1_stat = safe_spearman(scored, S1_SCORE_COL, S1_TARGET_COL, min_rows=int(args.min_year_rows))
        c16_stat = safe_spearman(scored, C16_SCORE_COL, S1_TARGET_COL, min_rows=int(args.min_year_rows))

        control_ics = {}
        for control in CALENDAR_CONTROL_COLUMNS:
            control_ics[control] = _component_spearman(scored, control, int(args.min_year_rows))["ic"]
        valid_control_ics = [float(value) for value in control_ics.values() if value is not None and np.isfinite(float(value))]
        lift = (
            float(calendar_stat["ic"] - base_stat["ic"])
            if calendar_stat["ic"] is not None and base_stat["ic"] is not None
            else None
        )
        random_control = _random_extra_control(
            scored,
            selected,
            low_corr_pool,
            base_ic=base_stat["ic"],
            iterations=int(args.random_iterations),
            seed=int(args.random_seed) + test_year,
            min_rows=int(args.min_year_rows),
        )
        fold_rows.append(
            {
                "test_year": test_year,
                "train_years": ",".join(str(year) for year in train_years),
                "selected_count": int(len(selected)),
                "selected_components": ",".join(selected),
                "non_calendar_ic": base_stat["ic"],
                "calendar_quorum_ic": calendar_stat["ic"],
                "calendar_lift_vs_non_calendar": lift,
                "calendar_only_ic": calendar_only_stat["ic"],
                "best_calendar_control_ic": max(valid_control_ics) if valid_control_ics else None,
                "s1_ic": s1_stat["ic"],
                "c16_ic": c16_stat["ic"],
                **{f"{key}_ic": value for key, value in control_ics.items()},
                **random_control,
            }
        )
        scored["selected_count"] = len(selected)
        scored["selected_components"] = ",".join(selected)
        scored_tests.append(
            scored[
                [
                    "time",
                    "ticker",
                    "year",
                    S1_TARGET_COL,
                    "non_calendar_quorum_score",
                    "calendar_quorum_score",
                    CALENDAR_PRIOR_COL,
                    "selected_count",
                    "selected_components",
                ]
            ].copy()
        )

    if not fold_rows:
        raise RuntimeError("H400 produced no folds.")
    return (
        pd.DataFrame(fold_rows),
        pd.DataFrame(selection_rows),
        pd.concat(scored_tests, ignore_index=True),
    )


def summarize_results(fold_summary: pd.DataFrame, panel: pd.DataFrame, spec: ExperimentSpec) -> dict[str, object]:
    base_avg, base_pos, base_years, base_pct = _avg_positive(fold_summary["non_calendar_ic"])
    cal_avg, cal_pos, cal_years, cal_pct = _avg_positive(fold_summary["calendar_quorum_ic"])
    lift_avg, lift_pos, lift_years, lift_pct = _avg_positive(fold_summary["calendar_lift_vs_non_calendar"])
    calendar_only_avg, calendar_only_pos, calendar_only_years, calendar_only_pct = _avg_positive(
        fold_summary["calendar_only_ic"]
    )
    random_extra_avg, _, _, _ = _avg_positive(fold_summary["random_extra_mean_lift"])
    random_extra_p95_avg, _, _, _ = _avg_positive(fold_summary["random_extra_p95_lift"])
    calendar_summary = {
        component: _yearly_component_summary(panel, component, int(spec.min_year_rows))
        for component in CALENDAR_CONTROL_COLUMNS
    }
    return {
        "non_calendar_avg_ic": base_avg,
        "non_calendar_positive_years": base_pos,
        "non_calendar_years": base_years,
        "non_calendar_pct_positive_years": base_pct,
        "calendar_quorum_avg_ic": cal_avg,
        "calendar_quorum_positive_years": cal_pos,
        "calendar_quorum_years": cal_years,
        "calendar_quorum_pct_positive_years": cal_pct,
        "calendar_lift_avg_ic": lift_avg,
        "calendar_lift_positive_years": lift_pos,
        "calendar_lift_years": lift_years,
        "calendar_lift_pct_positive_years": lift_pct,
        "calendar_only_avg_ic": calendar_only_avg,
        "calendar_only_positive_years": calendar_only_pos,
        "calendar_only_years": calendar_only_years,
        "calendar_only_pct_positive_years": calendar_only_pct,
        "random_extra_mean_lift_avg": random_extra_avg,
        "random_extra_p95_lift_avg": random_extra_p95_avg,
        "calendar_component_summary": calendar_summary,
    }


def choose_decision(detail: dict[str, object]) -> str:
    lift = detail.get("calendar_lift_avg_ic")
    lift_pos = int(detail.get("calendar_lift_positive_years", 0) or 0)
    lift_years = int(detail.get("calendar_lift_years", 0) or 0)
    cal_avg = detail.get("calendar_quorum_avg_ic")
    random_mean = detail.get("random_extra_mean_lift_avg")
    pass_gate = (
        lift is not None
        and float(lift) >= 0.003
        and lift_pos >= 5
        and lift_years >= 7
        and cal_avg is not None
        and float(cal_avg) >= 0.05
        and (random_mean is None or float(lift) >= float(random_mean) + 0.001)
    )
    mixed_gate = (
        lift is not None
        and float(lift) >= 0.001
        and lift_pos >= 4
        and cal_avg is not None
        and float(cal_avg) >= 0.05
    )
    if pass_gate:
        return "PASSED"
    if mixed_gate:
        return "MIXED"
    return "FAILED"


def run_branch(args: argparse.Namespace) -> str:
    h395 = _load_h395_module()
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_train_years=int(args.min_train_years),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=SPEC.min_phase_rows,
    )
    context = build_experiment_context(spec, artifact_subdir=BRANCH_NAME)
    panel = h395.load_panel(args, spec)
    panel = add_calendar_prior(panel)
    fold_summary, selection, test_scores = run_walk_forward(panel, args, spec, h395)
    detail = summarize_results(fold_summary, panel, spec)
    decision = choose_decision(detail)

    fold_summary_path = write_dataframe_artifact(fold_summary, context, f"{BRANCH_NAME}_fold_summary")
    selection_path = write_dataframe_artifact(selection, context, f"{BRANCH_NAME}_component_selection")
    test_scores_path = write_dataframe_artifact(test_scores, context, f"{BRANCH_NAME}_test_scores")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "decision_detail": detail,
            "panel_rows": int(len(panel)),
            "test_rows": int(len(test_scores)),
            "test_years": sorted(int(year) for year in fold_summary["test_year"].unique()),
            "fold_summary": fold_summary.to_dict(orient="records"),
            "decision_rule": (
                "PASSED requires the fixed calendar prior to add >= +0.003 avg "
                "IC over the non-calendar quorum, >= 5/7 positive lift years, "
                "calendar quorum avg IC >= +0.05, and lift above the random "
                "extra weak-vote mean by at least +0.001. MIXED requires >= "
                "+0.001 lift, >= 4 positive lift years, and avg IC >= +0.05."
            ),
        },
        artifacts={
            "fold_summary": fold_summary_path,
            "component_selection": selection_path,
            "test_scores": test_scores_path,
        },
        metadata={
            "no_2026_rows": True,
            "base_calendar_components_removed": sorted(BASE_CALENDAR_COMPONENTS),
            "calendar_control_columns": CALENDAR_CONTROL_COLUMNS,
            "h395_source": str(H395_PATH),
        },
    )

    pd.set_option("display.max_rows", 80)
    pd.set_option("display.width", 240)
    print(fold_summary.to_string(index=False))
    print(f"\ndetail: {detail}")
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
