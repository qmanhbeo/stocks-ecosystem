from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from h379_dynamic_candidate_thermodynamics import (  # noqa: E402
    _action_k,
    _action_returns_for_date,
    _best_static_action,
    _candidate_bins,
    _random_policy_means,
    _random_summary,
    _safe_float,
)
from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


BRANCH_NAME = "h380_candidate_count_policy_router"
MODE = "research_branch_candidate_count_policy_router"
OUT_DIR = artifact_path("entry_alpha")

DEFAULT_ACTIONS = ["cash", "top1", "top2", "top5", "top10"]
DEFAULT_TRANSFORMS = [
    "candidate_count",
    "candidate_count_delta_1d",
    "candidate_count_delta_5d",
    "candidate_count_vs_20d_mean",
]
DEFAULT_BIN_COUNTS = [2, 3, 4]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H380: candidate-count-only TRUE walk-forward portfolio-policy router. "
            "Learns a narrow K/cash policy from candidate_count and predeclared "
            "candidate_count transformations, then compares out-of-sample cycle "
            "returns to random K/cash policies."
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
    parser.add_argument("--min-train-years", type=int, default=2)
    parser.add_argument("--actions", nargs="+", default=DEFAULT_ACTIONS)
    parser.add_argument("--transforms", nargs="+", default=DEFAULT_TRANSFORMS)
    parser.add_argument("--bin-counts", nargs="+", type=int, default=DEFAULT_BIN_COUNTS)
    parser.add_argument("--min-bin-days", type=int, default=20)
    parser.add_argument("--random-trials", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=380)
    return parser.parse_args()


def _load_panel(candidate_panel_path: Path, labels_path: Path) -> pd.DataFrame:
    candidate = pd.read_parquet(candidate_panel_path)
    labels = pd.read_parquet(labels_path)
    candidate["time"] = pd.to_datetime(candidate["time"])
    labels["time"] = pd.to_datetime(labels["time"])
    label_columns = [
        "cycle_return_net",
        "cycle_relative_return_vs_vnindex",
        "benchmark_entry_open",
        "benchmark_exit_open",
    ]
    missing = [column for column in label_columns if column not in labels.columns]
    if missing:
        raise ValueError(f"Labels file missing required columns: {missing}")
    merged = candidate.merge(
        labels[["time", "ticker"] + label_columns],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    merged["cycle_return_net"] = _safe_float(merged["cycle_return_net"])
    merged["cycle_relative_return_vs_vnindex"] = _safe_float(
        merged["cycle_relative_return_vs_vnindex"]
    )
    merged["benchmark_cycle_return"] = (
        _safe_float(merged["benchmark_exit_open"])
        / _safe_float(merged["benchmark_entry_open"])
        - 1.0
    )
    return merged


def _build_action_returns(panel: pd.DataFrame, actions: list[str]) -> pd.DataFrame:
    rows = [_action_returns_for_date(group, actions) for _, group in panel.groupby("time", sort=True)]
    out = pd.DataFrame(rows)
    out["time"] = pd.to_datetime(out["time"])
    out["year"] = out["time"].dt.year.astype(int)
    return out


def _build_count_features(panel: pd.DataFrame) -> pd.DataFrame:
    required = ["time", "candidate_pool_rank", "candidate_count"]
    missing = [column for column in required if column not in panel.columns]
    if missing:
        raise ValueError(f"Candidate panel missing required columns: {missing}")
    first_rows = panel.sort_values(["time", "candidate_pool_rank"]).groupby("time", as_index=False).first()
    features = first_rows[["time", "candidate_count"]].copy()
    features["time"] = pd.to_datetime(features["time"])
    features = features.sort_values("time").reset_index(drop=True)
    features["candidate_count"] = _safe_float(features["candidate_count"])
    features["candidate_count_delta_1d"] = features["candidate_count"].diff(1)
    features["candidate_count_delta_5d"] = features["candidate_count"].diff(5)
    rolling_mean = features["candidate_count"].rolling(20, min_periods=5).mean()
    features["candidate_count_vs_20d_mean"] = features["candidate_count"] - rolling_mean
    features["year"] = features["time"].dt.year.astype(int)
    return features


def _fit_count_policy(
    train: pd.DataFrame,
    *,
    transform: str,
    bin_count: int,
    actions: list[str],
    min_bin_days: int,
    default_action: str,
) -> dict[str, object]:
    edges = _candidate_bins(train, transform, int(bin_count))
    assigned = pd.Series(
        pd.cut(_safe_float(train[transform]), bins=edges, labels=False, include_lowest=True),
        index=train.index,
    ).astype("Int64")
    bin_actions: dict[int, str] = {}
    train_returns: list[float] = []
    for bin_id in sorted(int(value) for value in assigned.dropna().unique()):
        mask = assigned == int(bin_id)
        if int(mask.sum()) < int(min_bin_days):
            action = str(default_action)
        else:
            means = {
                action: float(_safe_float(train.loc[mask, f"{action}_abs_return"]).mean())
                for action in actions
            }
            action = max(means, key=means.get)
        bin_actions[int(bin_id)] = action
        train_returns.extend(_safe_float(train.loc[mask, f"{action}_abs_return"]).dropna().tolist())
    train_mean = float(np.mean(train_returns)) if train_returns else float("-inf")
    return {
        "transform": transform,
        "bin_count": int(bin_count),
        "edges": edges.tolist(),
        "bin_actions": bin_actions,
        "train_mean_abs_return": train_mean,
    }


def _apply_count_policy(frame: pd.DataFrame, policy: dict[str, object]) -> pd.DataFrame:
    transform = str(policy["transform"])
    edges = np.asarray(policy["edges"], dtype=float)
    assigned = pd.Series(
        pd.cut(_safe_float(frame[transform]), bins=edges, labels=False, include_lowest=True),
        index=frame.index,
    ).astype("Int64")
    bin_actions = {int(key): str(value) for key, value in dict(policy["bin_actions"]).items()}
    out = frame.copy()
    out["selected_bin"] = assigned
    out["policy_action"] = [
        bin_actions.get(int(bin_id), "cash") if not pd.isna(bin_id) else "cash"
        for bin_id in assigned
    ]
    out["policy_abs_return"] = [
        float(row[f"{action}_abs_return"]) for action, (_, row) in zip(out["policy_action"], out.iterrows())
    ]
    out["policy_relative_return"] = [
        float(row[f"{action}_relative_return"]) for action, (_, row) in zip(out["policy_action"], out.iterrows())
    ]
    return out


def _evaluate_walk_forward(
    data: pd.DataFrame,
    *,
    transforms: list[str],
    bin_counts: list[int],
    actions: list[str],
    min_bin_days: int,
    min_train_years: int,
    random_trials: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    rng = np.random.default_rng(int(seed))
    all_years = sorted(int(year) for year in data["year"].unique())
    action_candidates = [action for action in actions if action in DEFAULT_ACTIONS]
    invested_actions = [action for action in action_candidates if action != "cash"]
    rows: list[dict[str, object]] = []
    daily_rows: list[pd.DataFrame] = []

    for test_year in all_years:
        train_years = [year for year in all_years if year < test_year]
        if len(train_years) < int(min_train_years):
            continue
        train = data.loc[data["year"].isin(train_years)].copy()
        test = data.loc[data["year"] == int(test_year)].copy()
        if train.empty or test.empty:
            continue

        default_action = _best_static_action(train, action_candidates)
        policies = [
            _fit_count_policy(
                train,
                transform=transform,
                bin_count=int(bin_count),
                actions=action_candidates,
                min_bin_days=int(min_bin_days),
                default_action=default_action,
            )
            for transform in transforms
            for bin_count in bin_counts
        ]
        selected_policy = max(policies, key=lambda item: float(item["train_mean_abs_return"]))
        tested = _apply_count_policy(test, selected_policy)

        random_all = _random_policy_means(
            test,
            actions=action_candidates,
            trials=int(random_trials),
            rng=rng,
        )
        random_invested = _random_policy_means(
            test,
            actions=invested_actions,
            trials=int(random_trials),
            rng=rng,
        )
        random_all_stats = _random_summary(random_all)
        random_invested_stats = _random_summary(random_invested)
        policy_mean = float(tested["policy_abs_return"].mean())
        policy_rel_mean = float(tested["policy_relative_return"].mean())
        static_action = _best_static_action(train, invested_actions)
        static_mean = float(_safe_float(test[f"{static_action}_abs_return"]).mean())

        row = {
            "test_year": int(test_year),
            "train_start_year": int(min(train_years)),
            "train_end_year": int(max(train_years)),
            "train_dates": int(train["time"].nunique()),
            "test_dates": int(test["time"].nunique()),
            "selected_transform": str(selected_policy["transform"]),
            "selected_bin_count": int(selected_policy["bin_count"]),
            "selected_policy_train_mean_abs_return": float(selected_policy["train_mean_abs_return"]),
            "selected_policy_edges": selected_policy["edges"],
            "selected_policy_bin_actions": selected_policy["bin_actions"],
            "default_train_action": str(default_action),
            "best_static_invested_train_action": str(static_action),
            "policy_mean_abs_return": policy_mean,
            "policy_mean_relative_return": policy_rel_mean,
            "best_static_invested_test_abs_return": static_mean,
            "random_all_mean_abs_return": random_all_stats["mean"],
            "random_all_p95_abs_return": random_all_stats["p95"],
            "random_invested_mean_abs_return": random_invested_stats["mean"],
            "random_invested_p95_abs_return": random_invested_stats["p95"],
            "policy_minus_random_all_mean": policy_mean - random_all_stats["mean"],
            "policy_minus_random_all_p95": policy_mean - random_all_stats["p95"],
            "policy_random_all_percentile": float((random_all <= policy_mean).mean()),
            "policy_minus_random_invested_mean": policy_mean - random_invested_stats["mean"],
            "policy_minus_random_invested_p95": policy_mean - random_invested_stats["p95"],
            "policy_random_invested_percentile": float((random_invested <= policy_mean).mean()),
            "policy_action_counts": tested["policy_action"].value_counts().sort_index().to_dict(),
        }
        rows.append(row)
        daily = tested[
            [
                "time",
                "year",
                "candidate_count",
                "candidate_count_delta_1d",
                "candidate_count_delta_5d",
                "candidate_count_vs_20d_mean",
                "selected_bin",
                "policy_action",
                "policy_abs_return",
                "policy_relative_return",
            ]
        ].copy()
        daily["test_year"] = int(test_year)
        daily["selected_transform"] = str(selected_policy["transform"])
        daily["selected_bin_count"] = int(selected_policy["bin_count"])
        daily_rows.append(daily)

    years = pd.DataFrame(rows)
    daily = pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
    if years.empty:
        raise ValueError("No walk-forward years available after min-train-years filter")

    wf_years = int(len(years))
    years_gt_random_all_mean = int((years["policy_minus_random_all_mean"] > 0.0).sum())
    years_gt_random_all_p95 = int((years["policy_minus_random_all_p95"] > 0.0).sum())
    years_gt_random_invested_mean = int((years["policy_minus_random_invested_mean"] > 0.0).sum())
    years_gt_random_invested_p95 = int((years["policy_minus_random_invested_p95"] > 0.0).sum())
    confirmation = years.loc[years["test_year"] == 2025]
    confirmation_all_lift = None
    confirmation_invested_lift = None
    confirmation_all_percentile = None
    if not confirmation.empty:
        confirmation_all_lift = float(confirmation.iloc[0]["policy_minus_random_all_mean"])
        confirmation_invested_lift = float(confirmation.iloc[0]["policy_minus_random_invested_mean"])
        confirmation_all_percentile = float(confirmation.iloc[0]["policy_random_all_percentile"])

    mean_policy = float(years["policy_mean_abs_return"].mean())
    mean_random_all = float(years["random_all_mean_abs_return"].mean())
    mean_random_invested = float(years["random_invested_mean_abs_return"].mean())
    mean_all_lift = float(years["policy_minus_random_all_mean"].mean())
    mean_invested_lift = float(years["policy_minus_random_invested_mean"].mean())
    min_consistent_years = max(3, int(np.ceil(0.60 * wf_years)))
    if (
        mean_all_lift > 0.0
        and years_gt_random_all_mean >= min_consistent_years
        and (confirmation_all_lift is None or confirmation_all_lift > 0.0)
        and mean_invested_lift > 0.0
    ):
        verdict = "PASSED"
        durable_status = "offline_evidence"
    elif mean_all_lift > 0.0 or years_gt_random_all_mean >= int(np.ceil(0.50 * wf_years)):
        verdict = "MIXED"
        durable_status = "park_or_narrow"
    else:
        verdict = "FAILED"
        durable_status = "branch_kill"

    summary = {
        "branch": "dynamic_breadth_option / candidate_count_policy_router",
        "experiment_id": "H380",
        "verdict": verdict,
        "durable_status": durable_status,
        "wf_years": wf_years,
        "test_years": [int(year) for year in years["test_year"].tolist()],
        "primary_benchmark": "random K/cash action policy over cash/top1/top2/top5/top10",
        "secondary_benchmark": "random invested action policy over top1/top2/top5/top10",
        "mean_policy_abs_return": mean_policy,
        "mean_random_all_abs_return": mean_random_all,
        "mean_random_invested_abs_return": mean_random_invested,
        "mean_lift_vs_random_all": mean_all_lift,
        "mean_lift_vs_random_invested": mean_invested_lift,
        "mean_random_all_percentile": float(years["policy_random_all_percentile"].mean()),
        "mean_random_invested_percentile": float(years["policy_random_invested_percentile"].mean()),
        "years_gt_random_all_mean": years_gt_random_all_mean,
        "years_gt_random_all_p95": years_gt_random_all_p95,
        "years_gt_random_invested_mean": years_gt_random_invested_mean,
        "years_gt_random_invested_p95": years_gt_random_invested_p95,
        "confirmation_2025_lift_vs_random_all": confirmation_all_lift,
        "confirmation_2025_lift_vs_random_invested": confirmation_invested_lift,
        "confirmation_2025_random_all_percentile": confirmation_all_percentile,
        "pass_rule": (
            "PASS if mean lift vs random K/cash is positive, at least 60% of WF years "
            "beat random K/cash mean, 2025 lift vs random K/cash is positive, and mean "
            "lift vs random invested policy is also positive. MIXED if only partial "
            "random-baseline consistency; otherwise FAILED."
        ),
    }
    return years, daily, summary


def main() -> None:
    args = parse_args()
    if int(args.end_year) >= 2026:
        raise ValueError("H380 must not train or test on 2026+; set --end-year <= 2025")
    actions = [str(action) for action in args.actions]
    for action in actions:
        _action_k(action)
    if "cash" not in actions:
        raise ValueError("H380 candidate-count router requires cash in the action set")
    if not any(action != "cash" for action in actions):
        raise ValueError("At least one invested topK action is required")
    transforms = [str(transform) for transform in args.transforms]
    unknown_transforms = [transform for transform in transforms if transform not in DEFAULT_TRANSFORMS]
    if unknown_transforms:
        raise ValueError(f"Unknown transforms {unknown_transforms}; choose from {DEFAULT_TRANSFORMS}")
    bin_counts = [int(bin_count) for bin_count in args.bin_counts]
    if any(bin_count < 2 for bin_count in bin_counts):
        raise ValueError("--bin-counts must be >= 2")

    panel = _load_panel(Path(args.candidate_panel), Path(args.labels))
    panel = panel[
        (panel["time"].dt.year >= int(args.start_year))
        & (panel["time"].dt.year <= int(args.end_year))
    ].copy()
    if panel.empty:
        raise ValueError("No rows after year filtering")
    max_k = max(_action_k(action) for action in actions)
    panel = panel.loc[pd.to_numeric(panel["candidate_pool_rank"], errors="coerce") <= float(max_k)].copy()

    date_features = _build_count_features(panel)
    action_returns = _build_action_returns(panel, actions)
    data = date_features.merge(action_returns, on=["time", "year"], how="inner", validate="one_to_one")
    data = data.sort_values("time").reset_index(drop=True)
    usable = data.dropna(subset=transforms)
    if usable.empty:
        raise ValueError("No rows after candidate-count transform filtering")

    years, daily, summary = _evaluate_walk_forward(
        usable,
        transforms=transforms,
        bin_counts=bin_counts,
        actions=actions,
        min_bin_days=int(args.min_bin_days),
        min_train_years=int(args.min_train_years),
        random_trials=int(args.random_trials),
        seed=int(args.seed),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    years_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_years.parquet"
    daily_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_daily.parquet"
    years_for_artifact = years.copy()
    for column in ["selected_policy_edges", "selected_policy_bin_actions", "policy_action_counts"]:
        if column in years_for_artifact.columns:
            years_for_artifact[column] = years_for_artifact[column].map(
                lambda value: json.dumps(value, sort_keys=True)
            )
    years_for_artifact.to_parquet(years_path, index=False)
    daily.to_parquet(daily_path, index=False)
    summary_path = write_run_summary(
        ts=ts,
        mode=MODE,
        name=BRANCH_NAME,
        summary=summary,
        artifacts={
            "years": years_path,
            "daily": daily_path,
        },
        metadata={
            "candidate_panel": Path(args.candidate_panel),
            "labels": Path(args.labels),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "actions": actions,
            "transforms": transforms,
            "bin_counts": bin_counts,
            "min_bin_days": int(args.min_bin_days),
            "random_trials": int(args.random_trials),
            "seed": int(args.seed),
            "data_rows": int(len(usable)),
        },
    )
    print("H380 candidate-count policy router")
    print(f"saved_summary={summary_path}")
    print(f"years={years_path}")
    print(f"daily={daily_path}")
    print(
        f"verdict={summary['verdict']} | mean_policy={summary['mean_policy_abs_return']:+.5f} | "
        f"random_all={summary['mean_random_all_abs_return']:+.5f} | "
        f"lift_all={summary['mean_lift_vs_random_all']:+.5f} | "
        f"random_invested={summary['mean_random_invested_abs_return']:+.5f} | "
        f"lift_invested={summary['mean_lift_vs_random_invested']:+.5f}"
    )
    print(
        years[
            [
                "test_year",
                "selected_transform",
                "selected_bin_count",
                "policy_mean_abs_return",
                "random_all_mean_abs_return",
                "policy_minus_random_all_mean",
                "policy_random_all_percentile",
                "random_invested_mean_abs_return",
                "policy_minus_random_invested_mean",
                "policy_action_counts",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
