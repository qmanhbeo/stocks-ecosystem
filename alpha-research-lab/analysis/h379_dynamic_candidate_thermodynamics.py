from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path
from src.run_summary import write_run_summary


BRANCH_NAME = "h379_dynamic_candidate_thermodynamics"
MODE = "research_branch_dynamic_candidate_thermodynamics"
OUT_DIR = artifact_path("entry_alpha")

DEFAULT_FEATURE_COLUMNS = [
    "full_top1_minus_top5_spread",
    "full_top5_score_std",
    "full_top10_score_entropy",
    "full_top5_buyable_count",
    "full_top10_buyable_count",
    "full_top5_blocked_buy_count",
    "full_top10_blocked_buy_count",
    "buyable_breadth_all",
    "liq_open_breadth_all",
    "candidate_count",
    "selector_confidence_combo",
    "selector_entry_quality_combo",
]

DEFAULT_ACTIONS = ["cash", "top1", "top2", "top5", "top10"]
INVESTED_ACTIONS = ["top1", "top2", "top5", "top10"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H379: TRUE walk-forward dynamic candidate thermodynamics policy. "
            "Learns a tiny date-level K/cash router from pre-decision candidate-panel "
            "features and compares out-of-sample performance to random action policies."
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
    parser.add_argument("--feature-columns", nargs="+", default=DEFAULT_FEATURE_COLUMNS)
    parser.add_argument("--quantile-bins", type=int, default=3)
    parser.add_argument("--min-bin-days", type=int, default=20)
    parser.add_argument("--random-trials", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=379)
    return parser.parse_args()


def _safe_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def _action_k(action: str) -> int:
    if action == "cash":
        return 0
    if not action.startswith("top"):
        raise ValueError(f"Unknown action {action!r}; expected cash/topK")
    return int(action.replace("top", ""))


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
    merged["cycle_relative_return_vs_vnindex"] = _safe_float(merged["cycle_relative_return_vs_vnindex"])
    merged["benchmark_cycle_return"] = (
        _safe_float(merged["benchmark_exit_open"]) / _safe_float(merged["benchmark_entry_open"]) - 1.0
    )
    return merged


def _build_date_features(panel: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    missing = [column for column in feature_columns if column not in panel.columns]
    if missing:
        raise ValueError(f"Candidate panel missing feature columns: {missing}")
    first_rows = panel.sort_values(["time", "candidate_pool_rank"]).groupby("time", as_index=False).first()
    features = first_rows[["time"] + feature_columns].copy()
    for column in feature_columns:
        features[column] = _safe_float(features[column])
    features["year"] = pd.to_datetime(features["time"]).dt.year.astype(int)
    return features


def _action_returns_for_date(group: pd.DataFrame, actions: list[str]) -> dict[str, float]:
    group = group.sort_values("candidate_pool_rank").copy()
    group["candidate_pool_rank"] = pd.to_numeric(group["candidate_pool_rank"], errors="coerce")
    group["cycle_return_net"] = _safe_float(group["cycle_return_net"])
    group["cycle_relative_return_vs_vnindex"] = _safe_float(group["cycle_relative_return_vs_vnindex"])
    group["can_buy_next_open"] = group["can_buy_next_open"].fillna(False).astype(bool)
    benchmark_return = float(_safe_float(group["benchmark_cycle_return"]).dropna().iloc[0])
    row: dict[str, float] = {
        "time": group["time"].iloc[0],
        "benchmark_cycle_return": benchmark_return,
    }
    for action in actions:
        k = _action_k(action)
        if k <= 0:
            row[f"{action}_abs_return"] = 0.0
            row[f"{action}_relative_return"] = -benchmark_return
            row[f"{action}_selected_count"] = 0.0
            continue
        selected = group.loc[
            (group["candidate_pool_rank"] <= float(k)) & group["can_buy_next_open"],
            ["cycle_return_net", "cycle_relative_return_vs_vnindex"],
        ]
        # Missing buyable slots are cash, so divide by target K instead of only
        # selected rows. This keeps top5 from silently becoming top2 on blocked days.
        row[f"{action}_abs_return"] = float(selected["cycle_return_net"].sum() / float(k))
        row[f"{action}_relative_return"] = float(selected["cycle_relative_return_vs_vnindex"].sum() / float(k))
        row[f"{action}_selected_count"] = float(len(selected))
    return row


def _build_action_returns(panel: pd.DataFrame, actions: list[str]) -> pd.DataFrame:
    rows = [_action_returns_for_date(group, actions) for _, group in panel.groupby("time", sort=True)]
    out = pd.DataFrame(rows)
    out["time"] = pd.to_datetime(out["time"])
    out["year"] = out["time"].dt.year.astype(int)
    return out


def _candidate_bins(train: pd.DataFrame, feature: str, bins: int) -> np.ndarray:
    values = _safe_float(train[feature]).replace([np.inf, -np.inf], np.nan).dropna()
    if values.nunique() < 2:
        return np.asarray([-np.inf, np.inf], dtype=float)
    quantiles = np.linspace(0.0, 1.0, int(bins) + 1)[1:-1]
    edges = np.unique(values.quantile(quantiles).to_numpy(dtype=float))
    return np.asarray([-np.inf, *edges.tolist(), np.inf], dtype=float)


def _assign_bins(values: pd.Series, edges: np.ndarray) -> pd.Series:
    return pd.Series(
        pd.cut(_safe_float(values), bins=edges, labels=False, include_lowest=True),
        index=values.index,
    ).astype("Int64")


def _fit_feature_policy(
    train: pd.DataFrame,
    *,
    feature: str,
    actions: list[str],
    bins: int,
    min_bin_days: int,
    default_action: str,
) -> dict[str, object]:
    edges = _candidate_bins(train, feature, bins)
    assigned = _assign_bins(train[feature], edges)
    bin_actions: dict[int, str] = {}
    train_policy_returns: list[float] = []
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
        train_policy_returns.extend(_safe_float(train.loc[mask, f"{action}_abs_return"]).dropna().tolist())
    train_mean = float(np.mean(train_policy_returns)) if train_policy_returns else float("-inf")
    return {
        "feature": feature,
        "edges": edges.tolist(),
        "bin_actions": bin_actions,
        "train_mean_abs_return": train_mean,
    }


def _apply_policy(frame: pd.DataFrame, policy: dict[str, object]) -> pd.DataFrame:
    feature = str(policy["feature"])
    edges = np.asarray(policy["edges"], dtype=float)
    bin_actions = {int(key): str(value) for key, value in dict(policy["bin_actions"]).items()}
    assigned = _assign_bins(frame[feature], edges)
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


def _random_policy_means(
    test: pd.DataFrame,
    *,
    actions: list[str],
    trials: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if test.empty:
        return np.asarray([], dtype=float)
    returns = test[[f"{action}_abs_return" for action in actions]].to_numpy(dtype=float)
    choices = rng.integers(0, len(actions), size=(int(trials), len(test)))
    sampled = np.take_along_axis(returns.T[None, :, :], choices[:, :, None].transpose(0, 2, 1), axis=1)
    return sampled.reshape(int(trials), len(test)).mean(axis=1)


def _random_summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "p50": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "p95": float(np.quantile(values, 0.95)),
    }


def _best_static_action(train: pd.DataFrame, actions: list[str]) -> str:
    means = {
        action: float(_safe_float(train[f"{action}_abs_return"]).mean())
        for action in actions
    }
    return max(means, key=means.get)


def _evaluate_walk_forward(
    data: pd.DataFrame,
    *,
    feature_columns: list[str],
    actions: list[str],
    quantile_bins: int,
    min_bin_days: int,
    min_train_years: int,
    random_trials: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    rng = np.random.default_rng(int(seed))
    all_years = sorted(int(year) for year in data["year"].unique())
    rows: list[dict[str, object]] = []
    daily_rows: list[pd.DataFrame] = []
    action_candidates = [action for action in actions if action in DEFAULT_ACTIONS]
    invested_actions = [action for action in action_candidates if action != "cash"]
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
            _fit_feature_policy(
                train,
                feature=feature,
                actions=action_candidates,
                bins=int(quantile_bins),
                min_bin_days=int(min_bin_days),
                default_action=default_action,
            )
            for feature in feature_columns
        ]
        selected_policy = max(policies, key=lambda item: float(item["train_mean_abs_return"]))
        tested = _apply_policy(test, selected_policy)

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
            "selected_feature": str(selected_policy["feature"]),
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
                "selected_bin",
                "policy_action",
                "policy_abs_return",
                "policy_relative_return",
            ]
        ].copy()
        daily["test_year"] = int(test_year)
        daily["selected_feature"] = str(selected_policy["feature"])
        daily_rows.append(daily)

    years = pd.DataFrame(rows)
    daily = pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
    if years.empty:
        raise ValueError("No walk-forward years available after min-train-years filter")

    wf_years = int(len(years))
    years_gt_random_mean = int((years["policy_minus_random_invested_mean"] > 0.0).sum())
    years_gt_random_p95 = int((years["policy_minus_random_invested_p95"] > 0.0).sum())
    confirmation = years.loc[years["test_year"] == 2025]
    confirmation_lift = None
    confirmation_percentile = None
    if not confirmation.empty:
        confirmation_lift = float(confirmation.iloc[0]["policy_minus_random_invested_mean"])
        confirmation_percentile = float(confirmation.iloc[0]["policy_random_invested_percentile"])

    mean_policy = float(years["policy_mean_abs_return"].mean())
    mean_random = float(years["random_invested_mean_abs_return"].mean())
    mean_lift = float(years["policy_minus_random_invested_mean"].mean())
    mean_percentile = float(years["policy_random_invested_percentile"].mean())
    if mean_lift > 0.0 and years_gt_random_mean >= max(3, int(np.ceil(0.60 * wf_years))) and (
        confirmation_lift is None or confirmation_lift > 0.0
    ):
        verdict = "PASSED"
        durable_status = "offline_evidence"
    elif mean_lift > 0.0 or years_gt_random_mean >= int(np.ceil(0.50 * wf_years)):
        verdict = "MIXED"
        durable_status = "park_or_narrow"
    else:
        verdict = "FAILED"
        durable_status = "branch_kill"

    summary = {
        "branch": "dynamic_breadth_option / dynamic_candidate_thermodynamics",
        "experiment_id": "H379",
        "verdict": verdict,
        "durable_status": durable_status,
        "wf_years": wf_years,
        "test_years": [int(year) for year in years["test_year"].tolist()],
        "primary_benchmark": "random invested action policy over top1/top2/top5/top10",
        "secondary_benchmark": "random action policy including cash",
        "mean_policy_abs_return": mean_policy,
        "mean_random_invested_abs_return": mean_random,
        "mean_lift_vs_random_invested": mean_lift,
        "mean_random_invested_percentile": mean_percentile,
        "years_gt_random_invested_mean": years_gt_random_mean,
        "years_gt_random_invested_p95": years_gt_random_p95,
        "confirmation_2025_lift_vs_random_invested": confirmation_lift,
        "confirmation_2025_random_invested_percentile": confirmation_percentile,
        "pass_rule": (
            "PASS if mean lift vs random invested policy is positive, at least 60% "
            "of WF years beat random invested mean, and 2025 confirmation lift is positive; "
            "MIXED if only partial consistency; otherwise FAILED."
        ),
    }
    return years, daily, summary


def main() -> None:
    args = parse_args()
    if int(args.end_year) >= 2026:
        raise ValueError("H379 must not train or test on 2026+; set --end-year <= 2025")
    actions = [str(action) for action in args.actions]
    for action in actions:
        _action_k(action)
    if not any(action != "cash" for action in actions):
        raise ValueError("At least one invested topK action is required")

    panel = _load_panel(Path(args.candidate_panel), Path(args.labels))
    panel = panel[
        (panel["time"].dt.year >= int(args.start_year))
        & (panel["time"].dt.year <= int(args.end_year))
    ].copy()
    if panel.empty:
        raise ValueError("No rows after year filtering")

    max_k = max(_action_k(action) for action in actions)
    panel = panel.loc[pd.to_numeric(panel["candidate_pool_rank"], errors="coerce") <= float(max_k)].copy()
    date_features = _build_date_features(panel, list(args.feature_columns))
    action_returns = _build_action_returns(panel, actions)
    data = date_features.merge(action_returns, on=["time", "year"], how="inner", validate="one_to_one")
    data = data.sort_values("time").reset_index(drop=True)

    years, daily, summary = _evaluate_walk_forward(
        data,
        feature_columns=list(args.feature_columns),
        actions=actions,
        quantile_bins=int(args.quantile_bins),
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
            "feature_columns": list(args.feature_columns),
            "quantile_bins": int(args.quantile_bins),
            "min_bin_days": int(args.min_bin_days),
            "random_trials": int(args.random_trials),
            "seed": int(args.seed),
            "data_rows": int(len(data)),
        },
    )
    print("H379 dynamic candidate thermodynamics")
    print(f"saved_summary={summary_path}")
    print(f"years={years_path}")
    print(f"daily={daily_path}")
    print(
        f"verdict={summary['verdict']} | mean_policy={summary['mean_policy_abs_return']:+.5f} | "
        f"random_invested={summary['mean_random_invested_abs_return']:+.5f} | "
        f"lift={summary['mean_lift_vs_random_invested']:+.5f} | "
        f"years_gt_random={summary['years_gt_random_invested_mean']}/{summary['wf_years']}"
    )
    print(years[
        [
            "test_year",
            "selected_feature",
            "policy_mean_abs_return",
            "random_invested_mean_abs_return",
            "policy_minus_random_invested_mean",
            "policy_random_invested_percentile",
            "policy_action_counts",
        ]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
