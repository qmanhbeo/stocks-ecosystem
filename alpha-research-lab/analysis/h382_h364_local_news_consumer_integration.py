from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path
from src.run_summary import write_run_summary


BRANCH_NAME = "h382_h364_local_news_consumer_integration"
MODE = "research_branch_h364_local_news_consumer_integration"
OUT_DIR = artifact_path("entry_alpha")

DEFAULT_K_VALUES = [1, 2, 3, 5]
H364_SCORE_COLUMN = "h364_official_sentiment_x_earnings_guidance"
NEWS_COLUMNS = [
    "ticker",
    "date",
    "phobert_article_count_1d",
    "phobert_sentiment_score_sum",
    "phobert_forward_looking_article_count_1d",
    "phobert_article_scope_article_count_1d",
    "phobert_source_type_article_count_1d",
    "phobert_source_type_official_or_regulatory_prob_mean",
    "ollama_guarded_article_count_1d",
    "ollama_guarded_event_family_earnings_share",
    "ollama_guarded_event_family_guidance_share",
]
LABEL_COLUMNS = [
    "cycle_return_net",
    "cycle_relative_return_vs_vnindex",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H382: TRUE walk-forward consumer integration audit for the fixed H364 "
            "local-news feature. Learns only the consumer K choice from prior years, "
            "then compares out-of-sample top-H364 candidate selection against random "
            "candidate policies with the same K."
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
    parser.add_argument(
        "--news",
        type=str,
        default=str(data_path("features/news/datasets/news_daily_features.parquet")),
    )
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=2)
    parser.add_argument("--candidate-pool-rank-max", type=int, default=20)
    parser.add_argument("--k-values", nargs="+", type=int, default=DEFAULT_K_VALUES)
    parser.add_argument("--random-trials", type=int, default=5000)
    parser.add_argument("--min-active-dates-per-year", type=int, default=20)
    parser.add_argument("--seed", type=int, default=382)
    return parser.parse_args()


def _safe_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def _load_news_features(path: Path) -> pd.DataFrame:
    columns = pq.ParquetFile(path).schema.names
    missing = [column for column in NEWS_COLUMNS if column not in columns]
    if missing:
        raise ValueError(f"News feature file missing required columns: {missing}")

    news = pd.read_parquet(path, columns=NEWS_COLUMNS).copy()
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    for column in NEWS_COLUMNS:
        if column not in {"ticker", "date"}:
            news[column] = _safe_float(news[column]).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    earnings_guidance = (
        news["ollama_guarded_event_family_earnings_share"]
        + news["ollama_guarded_event_family_guidance_share"]
    ).clip(lower=0.0, upper=1.0)
    news[H364_SCORE_COLUMN] = (
        news["phobert_sentiment_score_sum"]
        * news["phobert_source_type_official_or_regulatory_prob_mean"]
        * earnings_guidance
    )
    news["h364_active"] = (
        (news["phobert_article_count_1d"] > 0.0)
        & (news["phobert_forward_looking_article_count_1d"] > 0.0)
        & (news["phobert_article_scope_article_count_1d"] > 0.0)
        & (news["phobert_source_type_article_count_1d"] > 0.0)
        & (news["ollama_guarded_article_count_1d"] > 0.0)
    )
    return news[["time", "ticker", H364_SCORE_COLUMN, "h364_active"]].dropna(subset=["time", "ticker"])


def _load_panel(
    candidate_panel_path: Path,
    labels_path: Path,
    news_path: Path,
    *,
    start_year: int,
    end_year: int,
    candidate_pool_rank_max: int,
) -> pd.DataFrame:
    if int(end_year) >= 2026:
        raise ValueError("H382 must not train or test on 2026+; set --end-year <= 2025")

    candidate = pd.read_parquet(candidate_panel_path).copy()
    labels = pd.read_parquet(labels_path).copy()
    news = _load_news_features(news_path)
    candidate["time"] = pd.to_datetime(candidate["time"], errors="coerce").dt.normalize()
    labels["time"] = pd.to_datetime(labels["time"], errors="coerce").dt.normalize()
    candidate["ticker"] = candidate["ticker"].astype(str).str.upper()
    labels["ticker"] = labels["ticker"].astype(str).str.upper()

    required_candidate = ["time", "ticker", "candidate_pool_rank", "can_buy_next_open"]
    missing_candidate = [column for column in required_candidate if column not in candidate.columns]
    if missing_candidate:
        raise ValueError(f"Candidate panel missing required columns: {missing_candidate}")
    missing_labels = [column for column in LABEL_COLUMNS if column not in labels.columns]
    if missing_labels:
        raise ValueError(f"Labels file missing required columns: {missing_labels}")

    panel = candidate.merge(
        labels[["time", "ticker", *LABEL_COLUMNS]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    panel = panel.merge(
        news,
        on=["time", "ticker"],
        how="left",
        validate="many_to_one",
    )
    panel["year"] = panel["time"].dt.year.astype(int)
    panel = panel.loc[
        (panel["year"] >= int(start_year))
        & (panel["year"] <= int(end_year))
        & (_safe_float(panel["candidate_pool_rank"]) <= float(candidate_pool_rank_max))
    ].copy()
    if panel.empty:
        raise ValueError("No candidate rows after year and rank filtering")

    panel["can_buy_next_open"] = panel["can_buy_next_open"].fillna(False).astype(bool)
    panel["h364_active"] = panel["h364_active"].astype("boolean").fillna(False).astype(bool)
    panel[H364_SCORE_COLUMN] = _safe_float(panel[H364_SCORE_COLUMN]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    for column in LABEL_COLUMNS:
        panel[column] = _safe_float(panel[column]).replace([np.inf, -np.inf], np.nan)
    panel = panel.dropna(subset=["cycle_return_net", "cycle_relative_return_vs_vnindex"])
    return panel.sort_values(["time", "candidate_pool_rank", "ticker"]).reset_index(drop=True)


def _selected_return(group: pd.DataFrame, *, k: int) -> dict[str, object]:
    eligible = group.loc[group["can_buy_next_open"]].copy()
    active = eligible.loc[eligible["h364_active"]].copy()
    selected = active.sort_values(
        [H364_SCORE_COLUMN, "candidate_pool_rank", "ticker"],
        ascending=[False, True, True],
    ).head(int(k))
    return {
        "time": group["time"].iloc[0],
        "year": int(group["year"].iloc[0]),
        "buyable_candidate_count": int(len(eligible)),
        "active_buyable_candidate_count": int(len(active)),
        f"h364_top{k}_selected_count": int(len(selected)),
        f"h364_top{k}_abs_return": float(selected["cycle_return_net"].sum() / float(k)),
        f"h364_top{k}_relative_return": float(selected["cycle_relative_return_vs_vnindex"].sum() / float(k)),
        f"h364_top{k}_mean_score": (
            float(selected[H364_SCORE_COLUMN].mean()) if not selected.empty else 0.0
        ),
    }


def _build_daily_policy_returns(panel: pd.DataFrame, k_values: list[int]) -> pd.DataFrame:
    per_k_frames: list[pd.DataFrame] = []
    for k in k_values:
        rows = [_selected_return(group, k=int(k)) for _, group in panel.groupby("time", sort=True)]
        per_k = pd.DataFrame(rows)
        per_k_frames.append(per_k)
    daily = per_k_frames[0]
    key_columns = ["time", "year", "buyable_candidate_count", "active_buyable_candidate_count"]
    for per_k in per_k_frames[1:]:
        daily = daily.merge(
            per_k.drop(columns=["buyable_candidate_count", "active_buyable_candidate_count"]),
            on=["time", "year"],
            how="inner",
            validate="one_to_one",
        )
    return daily.sort_values("time").reset_index(drop=True)[
        key_columns
        + [
            column
            for column in daily.columns
            if column not in key_columns
        ]
    ]


def _random_policy_distribution(
    panel: pd.DataFrame,
    *,
    k: int,
    pool: str,
    trials: int,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    dates = sorted(panel["time"].dropna().unique())
    abs_totals = np.zeros(int(trials), dtype=float)
    rel_totals = np.zeros(int(trials), dtype=float)
    active_dates = 0
    for _, group in panel.groupby("time", sort=True):
        eligible = group.loc[group["can_buy_next_open"]].copy()
        if pool == "active":
            eligible = eligible.loc[eligible["h364_active"]].copy()
        elif pool != "all":
            raise ValueError(f"Unknown random pool: {pool}")
        n = int(len(eligible))
        if n <= 0:
            continue
        active_dates += 1
        sample_size = min(int(k), n)
        abs_values = eligible["cycle_return_net"].to_numpy(dtype=float)
        rel_values = eligible["cycle_relative_return_vs_vnindex"].to_numpy(dtype=float)
        if sample_size == n:
            abs_totals += float(abs_values.sum() / float(k))
            rel_totals += float(rel_values.sum() / float(k))
        elif sample_size == 1:
            choices = rng.integers(0, n, size=int(trials))
            abs_totals += abs_values[choices] / float(k)
            rel_totals += rel_values[choices] / float(k)
        else:
            for trial in range(int(trials)):
                choices = rng.choice(n, size=sample_size, replace=False)
                abs_totals[trial] += float(abs_values[choices].sum() / float(k))
                rel_totals[trial] += float(rel_values[choices].sum() / float(k))
    divisor = float(len(dates)) if dates else 1.0
    return {
        "abs": abs_totals / divisor,
        "relative": rel_totals / divisor,
        "active_dates": np.asarray([active_dates], dtype=int),
    }


def _random_summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "p50": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "p95": float(np.quantile(values, 0.95)),
    }


def _select_k_from_train(train: pd.DataFrame, k_values: list[int]) -> int:
    means = {
        int(k): float(_safe_float(train[f"h364_top{int(k)}_abs_return"]).mean())
        for k in k_values
    }
    return max(means, key=means.get)


def _evaluate_walk_forward(
    panel: pd.DataFrame,
    daily_policy_returns: pd.DataFrame,
    *,
    k_values: list[int],
    min_train_years: int,
    random_trials: int,
    min_active_dates_per_year: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    rng = np.random.default_rng(int(seed))
    years = sorted(int(year) for year in daily_policy_returns["year"].unique())
    year_rows: list[dict[str, object]] = []
    daily_rows: list[pd.DataFrame] = []

    for test_year in years:
        train_years = [year for year in years if year < int(test_year)]
        if len(train_years) < int(min_train_years):
            continue
        train_daily = daily_policy_returns.loc[daily_policy_returns["year"].isin(train_years)].copy()
        test_daily = daily_policy_returns.loc[daily_policy_returns["year"] == int(test_year)].copy()
        test_panel = panel.loc[panel["year"] == int(test_year)].copy()
        if train_daily.empty or test_daily.empty or test_panel.empty:
            continue

        selected_k = _select_k_from_train(train_daily, k_values)
        policy_abs = _safe_float(test_daily[f"h364_top{selected_k}_abs_return"])
        policy_rel = _safe_float(test_daily[f"h364_top{selected_k}_relative_return"])
        active_dates = int((test_daily["active_buyable_candidate_count"] > 0).sum())
        selected_dates = int((_safe_float(test_daily[f"h364_top{selected_k}_selected_count"]) > 0).sum())

        random_active = _random_policy_distribution(
            test_panel,
            k=selected_k,
            pool="active",
            trials=int(random_trials),
            rng=rng,
        )
        random_all = _random_policy_distribution(
            test_panel,
            k=selected_k,
            pool="all",
            trials=int(random_trials),
            rng=rng,
        )
        active_stats = _random_summary(random_active["abs"])
        all_stats = _random_summary(random_all["abs"])
        policy_mean = float(policy_abs.mean())
        policy_rel_mean = float(policy_rel.mean())

        row = {
            "test_year": int(test_year),
            "train_start_year": int(min(train_years)),
            "train_end_year": int(max(train_years)),
            "train_dates": int(train_daily["time"].nunique()),
            "test_dates": int(test_daily["time"].nunique()),
            "selected_k": int(selected_k),
            "active_dates": active_dates,
            "selected_dates": selected_dates,
            "mean_active_buyable_candidates": float(test_daily["active_buyable_candidate_count"].mean()),
            "policy_mean_abs_return": policy_mean,
            "policy_mean_relative_return": policy_rel_mean,
            "random_active_mean_abs_return": active_stats["mean"],
            "random_active_p95_abs_return": active_stats["p95"],
            "random_all_mean_abs_return": all_stats["mean"],
            "random_all_p95_abs_return": all_stats["p95"],
            "policy_minus_random_active_mean": policy_mean - active_stats["mean"],
            "policy_minus_random_active_p95": policy_mean - active_stats["p95"],
            "policy_random_active_percentile": float((random_active["abs"] <= policy_mean).mean()),
            "policy_minus_random_all_mean": policy_mean - all_stats["mean"],
            "policy_minus_random_all_p95": policy_mean - all_stats["p95"],
            "policy_random_all_percentile": float((random_all["abs"] <= policy_mean).mean()),
        }
        year_rows.append(row)
        out_daily = test_daily[
            [
                "time",
                "year",
                "buyable_candidate_count",
                "active_buyable_candidate_count",
                f"h364_top{selected_k}_selected_count",
                f"h364_top{selected_k}_abs_return",
                f"h364_top{selected_k}_relative_return",
                f"h364_top{selected_k}_mean_score",
            ]
        ].copy()
        out_daily["test_year"] = int(test_year)
        out_daily["selected_k"] = int(selected_k)
        out_daily = out_daily.rename(
            columns={
                f"h364_top{selected_k}_selected_count": "policy_selected_count",
                f"h364_top{selected_k}_abs_return": "policy_abs_return",
                f"h364_top{selected_k}_relative_return": "policy_relative_return",
                f"h364_top{selected_k}_mean_score": "policy_mean_score",
            }
        )
        daily_rows.append(out_daily)

    years_df = pd.DataFrame(year_rows)
    daily_df = pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
    if years_df.empty:
        raise ValueError("No walk-forward years available after min-train-years filter")

    wf_years = int(len(years_df))
    years_gt_active_mean = int((years_df["policy_minus_random_active_mean"] > 0.0).sum())
    years_gt_active_p95 = int((years_df["policy_minus_random_active_p95"] > 0.0).sum())
    years_gt_all_mean = int((years_df["policy_minus_random_all_mean"] > 0.0).sum())
    min_active_dates = int(years_df["active_dates"].min())
    confirmation = years_df.loc[years_df["test_year"] == 2025]
    confirmation_lift = None
    confirmation_percentile = None
    if not confirmation.empty:
        confirmation_lift = float(confirmation.iloc[0]["policy_minus_random_active_mean"])
        confirmation_percentile = float(confirmation.iloc[0]["policy_random_active_percentile"])

    mean_policy = float(years_df["policy_mean_abs_return"].mean())
    mean_random_active = float(years_df["random_active_mean_abs_return"].mean())
    mean_random_all = float(years_df["random_all_mean_abs_return"].mean())
    mean_lift_active = float(years_df["policy_minus_random_active_mean"].mean())
    mean_lift_all = float(years_df["policy_minus_random_all_mean"].mean())
    enough_support = bool(min_active_dates >= int(min_active_dates_per_year))
    required_years = max(3, int(np.ceil(0.60 * wf_years)))
    if (
        enough_support
        and mean_lift_active > 0.0
        and years_gt_active_mean >= required_years
        and (confirmation_lift is None or confirmation_lift > 0.0)
    ):
        verdict = "PASSED"
        durable_status = "offline_evidence"
    elif enough_support and (mean_lift_active > 0.0 or years_gt_active_mean >= int(np.ceil(0.50 * wf_years))):
        verdict = "MIXED"
        durable_status = "park_or_narrow"
    else:
        verdict = "FAILED"
        durable_status = "branch_kill_or_offline_only"

    summary = {
        "branch": "h364_consumer_integration",
        "experiment_id": "H382",
        "verdict": verdict,
        "durable_status": durable_status,
        "wf_years": wf_years,
        "test_years": [int(year) for year in years_df["test_year"].tolist()],
        "fixed_feature": H364_SCORE_COLUMN,
        "feature_formula": (
            "phobert_sentiment_score_sum * "
            "phobert_source_type_official_or_regulatory_prob_mean * "
            "clip(ollama_guarded_event_family_earnings_share + "
            "ollama_guarded_event_family_guidance_share, 0, 1)"
        ),
        "trained_component": "consumer K choice only, selected from prior years",
        "primary_benchmark": "random same-K selection among active buyable H364 candidates",
        "secondary_benchmark": "random same-K selection among all buyable candidate-pool rows",
        "mean_policy_abs_return": mean_policy,
        "mean_random_active_abs_return": mean_random_active,
        "mean_random_all_abs_return": mean_random_all,
        "mean_lift_vs_random_active": mean_lift_active,
        "mean_lift_vs_random_all": mean_lift_all,
        "years_gt_random_active_mean": years_gt_active_mean,
        "years_gt_random_active_p95": years_gt_active_p95,
        "years_gt_random_all_mean": years_gt_all_mean,
        "min_active_dates_per_year": min_active_dates,
        "required_min_active_dates_per_year": int(min_active_dates_per_year),
        "confirmation_2025_lift_vs_random_active": confirmation_lift,
        "confirmation_2025_random_active_percentile": confirmation_percentile,
        "pass_rule": (
            "PASS if support is sufficient, mean lift vs random active same-K "
            "policy is positive, at least 60% of WF years beat random active mean, "
            "and 2025 confirmation lift is positive; MIXED if only partial "
            "consistency; otherwise FAILED."
        ),
    }
    return years_df, daily_df, summary


def main() -> None:
    args = parse_args()
    k_values = sorted({int(k) for k in args.k_values})
    if not k_values or min(k_values) <= 0:
        raise ValueError("--k-values must contain positive integers")
    if max(k_values) > int(args.candidate_pool_rank_max):
        raise ValueError("--k-values cannot exceed --candidate-pool-rank-max")

    panel = _load_panel(
        Path(args.candidate_panel),
        Path(args.labels),
        Path(args.news),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        candidate_pool_rank_max=int(args.candidate_pool_rank_max),
    )
    daily_returns = _build_daily_policy_returns(panel, k_values)
    years, daily, summary = _evaluate_walk_forward(
        panel,
        daily_returns,
        k_values=k_values,
        min_train_years=int(args.min_train_years),
        random_trials=int(args.random_trials),
        min_active_dates_per_year=int(args.min_active_dates_per_year),
        seed=int(args.seed),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    years_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_years.parquet"
    daily_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_daily.parquet"
    years.to_parquet(years_path, index=False)
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
            "news": Path(args.news),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "candidate_pool_rank_max": int(args.candidate_pool_rank_max),
            "k_values": k_values,
            "random_trials": int(args.random_trials),
            "min_active_dates_per_year": int(args.min_active_dates_per_year),
            "seed": int(args.seed),
            "panel_rows": int(len(panel)),
            "daily_rows": int(len(daily_returns)),
        },
    )
    print("H382 H364 local-news consumer integration")
    print(f"saved_summary={summary_path}")
    print(f"years={years_path}")
    print(f"daily={daily_path}")
    print(
        f"verdict={summary['verdict']} | mean_policy={summary['mean_policy_abs_return']:+.5f} | "
        f"random_active={summary['mean_random_active_abs_return']:+.5f} | "
        f"lift_active={summary['mean_lift_vs_random_active']:+.5f} | "
        f"years_gt_random_active={summary['years_gt_random_active_mean']}/{summary['wf_years']}"
    )
    print(
        years[
            [
                "test_year",
                "selected_k",
                "active_dates",
                "policy_mean_abs_return",
                "random_active_mean_abs_return",
                "policy_minus_random_active_mean",
                "policy_random_active_percentile",
                "random_all_mean_abs_return",
                "policy_minus_random_all_mean",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
