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

from src.artifact_contract import atomic_write_parquet  # noqa: E402
from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


BRANCH_NAME = "h426_forced_seller_detector"
MODE = "research_branch_forced_seller_detector"
OUT_DIR = artifact_path("entry_alpha")

STATE_CORE = "forced_seller_core_buyable"
STATE_LARGE_DOWN = "forced_seller_large_down_buyable"
STATE_FLOOR = "forced_seller_floor_buyable"
STATE_HARD_RELEASE = "forced_seller_hard_release"
STATE_COLUMNS = [STATE_CORE, STATE_LARGE_DOWN, STATE_FLOOR, STATE_HARD_RELEASE]

DEFAULT_K_VALUES = [1, 2, 3, 5]
CANDIDATE_POOL_RANK_MAX = 20
MIN_ACTIVE_DATES_PER_YEAR = 20
RANDOM_TRIALS = 5000

CANDIDATE_COLUMNS = [
    "time",
    "ticker",
    "candidate_pool_rank",
    "can_buy_next_open",
    "prev_can_buy_next_open",
    "release_flag",
    "ret_1d",
    "ret_3d",
    "xs_ret_1d_rank",
    "xs_ret_3d_rank",
    "xs_c8_rank",
    "c8_vol_zscore_5d",
    "xs_floor_count_5d_rank",
    "xs_floor_count_20d_rank",
]
LABEL_COLUMNS = [
    "cycle_return_net",
    "cycle_relative_return_vs_vnindex",
]
ORDER_COLUMNS = [
    "ticker",
    "date",
    "buy_order_count",
    "buy_order_volume",
    "avg_buy_order_volume",
    "sell_order_count",
    "sell_order_volume",
    "avg_sell_order_volume",
    "buy_sell_volume_imbalance",
]
NEWS_COLUMNS = [
    "date",
    "ticker",
    "phobert_article_count_1d",
    "phobert_prob_neg_mean",
    "phobert_prob_pos_mean",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H426: forced-seller detector candidate-policy audit. Fixed "
            "decision-time states are compared against random same-support and "
            "random-all candidate policies using walk-forward K selection. "
            "No S1/C16 baseline is used because this is not a direct S1/C16 "
            "variation."
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
        "--order-stats",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    parser.add_argument(
        "--news",
        type=str,
        default=str(data_path("features/news/datasets/news_daily_features.parquet")),
    )
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=2)
    parser.add_argument("--candidate-pool-rank-max", type=int, default=CANDIDATE_POOL_RANK_MAX)
    parser.add_argument("--k-values", nargs="+", type=int, default=DEFAULT_K_VALUES)
    parser.add_argument("--random-trials", type=int, default=RANDOM_TRIALS)
    parser.add_argument("--min-active-dates-per-year", type=int, default=MIN_ACTIVE_DATES_PER_YEAR)
    parser.add_argument("--seed", type=int, default=426)
    return parser.parse_args()


def _safe_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).astype(float)


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return _safe_float(frame[column]).fillna(default)


def _safe_bool(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    return frame[column].astype("boolean").fillna(default).astype(bool)


def _require_parquet_columns(path: Path, required: list[str], artifact_name: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{artifact_name} not found: {path}")
    columns = pq.ParquetFile(path).schema.names
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"{artifact_name} missing required columns: {missing}")


def _load_order_features(path: Path, *, start_year: int, end_year: int) -> pd.DataFrame:
    _require_parquet_columns(path, ORDER_COLUMNS, "order-stats parquet")
    order = pd.read_parquet(path, columns=ORDER_COLUMNS).copy()
    order["time"] = pd.to_datetime(order["date"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].astype(str).str.upper()
    order = order.loc[
        (order["time"].dt.year >= int(start_year) - 1)
        & (order["time"].dt.year <= int(end_year))
    ].copy()
    if order.empty:
        raise ValueError("No order-stat rows after date filtering")

    for column in ORDER_COLUMNS:
        if column not in {"ticker", "date"}:
            order[column] = _safe_numeric(order, column)

    volume_denom = (order["buy_order_volume"] + order["sell_order_volume"]).replace(0.0, np.nan)
    count_denom = (order["buy_order_count"] + order["sell_order_count"]).replace(0.0, np.nan)
    order["sell_volume_pressure"] = order["sell_order_volume"] / volume_denom
    order["sell_count_pressure"] = order["sell_order_count"] / count_denom
    order["sell_imbalance_ratio"] = -order["buy_sell_volume_imbalance"] / volume_denom

    order = order.sort_values(["ticker", "time"]).reset_index(drop=True)
    prev_avg_sell = order.groupby("ticker", sort=False)["avg_sell_order_volume"].transform(
        lambda series: series.shift(1).rolling(5, min_periods=3).mean()
    )
    order["avg_sell_size_change"] = (
        order["avg_sell_order_volume"] / prev_avg_sell.replace(0.0, np.nan)
    ) - 1.0

    rank_columns = [
        "sell_volume_pressure",
        "sell_count_pressure",
        "sell_imbalance_ratio",
        "avg_sell_order_volume",
        "avg_sell_size_change",
    ]
    for column in rank_columns:
        order[f"{column}_rank"] = order.groupby("time", sort=False)[column].rank(pct=True)

    return order[
        [
            "time",
            "ticker",
            "buy_sell_volume_imbalance",
            "sell_volume_pressure_rank",
            "sell_count_pressure_rank",
            "sell_imbalance_ratio_rank",
            "avg_sell_order_volume_rank",
            "avg_sell_size_change_rank",
        ]
    ].dropna(subset=["time", "ticker"])


def _load_news_flags(path: Path) -> pd.DataFrame:
    _require_parquet_columns(path, NEWS_COLUMNS, "news daily features parquet")
    news = pd.read_parquet(path, columns=NEWS_COLUMNS).copy()
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    article_count = _safe_numeric(news, "phobert_article_count_1d")
    neg_prob = _safe_numeric(news, "phobert_prob_neg_mean")
    pos_prob = _safe_numeric(news, "phobert_prob_pos_mean")
    news["bad_news_1d"] = (article_count > 0.0) & (neg_prob >= 0.50) & (neg_prob > pos_prob)
    return news[["time", "ticker", "bad_news_1d"]].dropna(subset=["time", "ticker"])


def _load_panel(
    candidate_panel_path: Path,
    labels_path: Path,
    order_stats_path: Path,
    news_path: Path,
    *,
    start_year: int,
    end_year: int,
    candidate_pool_rank_max: int,
) -> pd.DataFrame:
    if int(end_year) >= 2026:
        raise ValueError("H426 must not train or test on 2026+; set --end-year <= 2025")

    _require_parquet_columns(candidate_panel_path, CANDIDATE_COLUMNS, "candidate panel")
    _require_parquet_columns(labels_path, ["time", "ticker", *LABEL_COLUMNS], "entry labels")

    candidate = pd.read_parquet(candidate_panel_path, columns=CANDIDATE_COLUMNS).copy()
    labels = pd.read_parquet(labels_path, columns=["time", "ticker", *LABEL_COLUMNS]).copy()
    order = _load_order_features(order_stats_path, start_year=start_year, end_year=end_year)
    news = _load_news_flags(news_path)

    for frame in [candidate, labels]:
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
        frame["ticker"] = frame["ticker"].astype(str).str.upper()

    panel = candidate.merge(
        labels,
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    panel = panel.merge(order, on=["time", "ticker"], how="left", validate="many_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="many_to_one")
    panel["year"] = panel["time"].dt.year.astype(int)
    panel = panel.loc[
        (panel["year"] >= int(start_year))
        & (panel["year"] <= int(end_year))
        & (_safe_float(panel["candidate_pool_rank"]) <= float(candidate_pool_rank_max))
    ].copy()
    if panel.empty:
        raise ValueError("No candidate rows after year and rank filtering")

    panel["candidate_pool_rank"] = _safe_float(panel["candidate_pool_rank"])
    panel["can_buy_next_open"] = _safe_bool(panel, "can_buy_next_open")
    panel["prev_can_buy_next_open"] = _safe_bool(panel, "prev_can_buy_next_open", default=True)
    panel["release_flag"] = _safe_numeric(panel, "release_flag")
    panel["bad_news_1d"] = _safe_bool(panel, "bad_news_1d")

    for column in [
        "ret_1d",
        "ret_3d",
        "xs_ret_1d_rank",
        "xs_ret_3d_rank",
        "xs_c8_rank",
        "c8_vol_zscore_5d",
        "xs_floor_count_5d_rank",
        "xs_floor_count_20d_rank",
        "buy_sell_volume_imbalance",
        "sell_volume_pressure_rank",
        "sell_count_pressure_rank",
        "sell_imbalance_ratio_rank",
        "avg_sell_order_volume_rank",
        "avg_sell_size_change_rank",
        *LABEL_COLUMNS,
    ]:
        panel[column] = _safe_float(panel[column])

    panel["weak_3d"] = (panel["xs_ret_3d_rank"] <= 0.25) | (panel["ret_3d"] <= -0.03)
    panel["large_down_1d"] = (panel["xs_ret_1d_rank"] <= 0.25) | (panel["ret_1d"] <= -0.03)
    panel["volume_spike"] = (panel["xs_c8_rank"] >= 0.75) | (panel["c8_vol_zscore_5d"] >= 0.75)
    panel["sell_pressure_high"] = (
        (panel["sell_volume_pressure_rank"] >= 0.70)
        | (panel["sell_imbalance_ratio_rank"] >= 0.70)
        | (panel["sell_count_pressure_rank"] >= 0.80)
    )
    panel["avg_sell_size_rising"] = (
        (panel["avg_sell_size_change_rank"] >= 0.65)
        | (panel["avg_sell_order_volume_rank"] >= 0.75)
    )
    panel["floor_pressure"] = (
        (panel["xs_floor_count_5d_rank"] >= 0.70)
        | (panel["xs_floor_count_20d_rank"] >= 0.70)
    )
    panel["literal_tradability_release"] = (
        panel["can_buy_next_open"]
        & ((panel["release_flag"] > 0.0) | (~panel["prev_can_buy_next_open"]))
    )

    core = (
        panel["can_buy_next_open"]
        & panel["weak_3d"]
        & panel["volume_spike"]
        & panel["sell_pressure_high"]
        & panel["avg_sell_size_rising"]
        & (~panel["bad_news_1d"])
    )
    panel[STATE_CORE] = core
    panel[STATE_LARGE_DOWN] = core & panel["large_down_1d"]
    panel[STATE_FLOOR] = core & panel["floor_pressure"]
    panel[STATE_HARD_RELEASE] = core & panel["literal_tradability_release"]

    panel = panel.dropna(
        subset=[
            "cycle_return_net",
            "cycle_relative_return_vs_vnindex",
            "candidate_pool_rank",
            "sell_volume_pressure_rank",
            "avg_sell_order_volume_rank",
        ]
    )
    return panel.sort_values(["time", "candidate_pool_rank", "ticker"]).reset_index(drop=True)


def _selected_return(group: pd.DataFrame, *, state_col: str, k: int) -> dict[str, object]:
    eligible = group.loc[group["can_buy_next_open"]].copy()
    state = eligible.loc[eligible[state_col]].copy()
    selected = state.sort_values(
        ["candidate_pool_rank", "sell_volume_pressure_rank", "ticker"],
        ascending=[True, False, True],
    ).head(int(k))
    prefix = f"{state_col}_top{int(k)}"
    return {
        "time": group["time"].iloc[0],
        "year": int(group["year"].iloc[0]),
        "buyable_candidate_count": int(len(eligible)),
        f"{state_col}_buyable_candidate_count": int(len(state)),
        f"{prefix}_selected_count": int(len(selected)),
        f"{prefix}_abs_return": float(selected["cycle_return_net"].sum() / float(k)),
        f"{prefix}_relative_return": float(selected["cycle_relative_return_vs_vnindex"].sum() / float(k)),
        f"{prefix}_mean_candidate_rank": float(selected["candidate_pool_rank"].mean()) if not selected.empty else 0.0,
        f"{prefix}_mean_sell_pressure_rank": float(selected["sell_volume_pressure_rank"].mean()) if not selected.empty else 0.0,
    }


def _build_daily_policy_returns(panel: pd.DataFrame, k_values: list[int]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, group in panel.groupby("time", sort=True):
        base: dict[str, object] = {
            "time": group["time"].iloc[0],
            "year": int(group["year"].iloc[0]),
        }
        for state_col in STATE_COLUMNS:
            for k in k_values:
                record = _selected_return(group, state_col=state_col, k=int(k))
                if "buyable_candidate_count" not in base:
                    base["buyable_candidate_count"] = record["buyable_candidate_count"]
                base[f"{state_col}_buyable_candidate_count"] = record[f"{state_col}_buyable_candidate_count"]
                prefix = f"{state_col}_top{int(k)}"
                for suffix in [
                    "selected_count",
                    "abs_return",
                    "relative_return",
                    "mean_candidate_rank",
                    "mean_sell_pressure_rank",
                ]:
                    base[f"{prefix}_{suffix}"] = record[f"{prefix}_{suffix}"]
        rows.append(base)
    return pd.DataFrame(rows).sort_values("time").reset_index(drop=True)


def _random_policy_distribution(
    panel: pd.DataFrame,
    *,
    state_col: str,
    k: int,
    pool: str,
    trials: int,
    rng: np.random.Generator,
) -> dict[str, np.ndarray | int]:
    dates = sorted(panel["time"].dropna().unique())
    abs_totals = np.zeros(int(trials), dtype=float)
    rel_totals = np.zeros(int(trials), dtype=float)
    active_dates = 0

    for _, group in panel.groupby("time", sort=True):
        eligible = group.loc[group["can_buy_next_open"]].copy()
        if pool == "state":
            eligible = eligible.loc[eligible[state_col]].copy()
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
        "active_dates": int(active_dates),
    }


def _random_summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "p50": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "p95": float(np.quantile(values, 0.95)),
    }


def _select_k_from_train(train: pd.DataFrame, *, state_col: str, k_values: list[int]) -> int:
    means = {
        int(k): float(_safe_float(train[f"{state_col}_top{int(k)}_abs_return"]).mean())
        for k in k_values
    }
    return max(means, key=means.get)


def _evaluate_state_walk_forward(
    panel: pd.DataFrame,
    daily_policy_returns: pd.DataFrame,
    *,
    state_col: str,
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

        selected_k = _select_k_from_train(train_daily, state_col=state_col, k_values=k_values)
        prefix = f"{state_col}_top{selected_k}"
        policy_abs = _safe_float(test_daily[f"{prefix}_abs_return"])
        policy_rel = _safe_float(test_daily[f"{prefix}_relative_return"])
        active_dates = int((test_daily[f"{state_col}_buyable_candidate_count"] > 0).sum())
        selected_dates = int((_safe_float(test_daily[f"{prefix}_selected_count"]) > 0).sum())

        random_state = _random_policy_distribution(
            test_panel,
            state_col=state_col,
            k=selected_k,
            pool="state",
            trials=int(random_trials),
            rng=rng,
        )
        random_all = _random_policy_distribution(
            test_panel,
            state_col=state_col,
            k=selected_k,
            pool="all",
            trials=int(random_trials),
            rng=rng,
        )
        state_stats = _random_summary(random_state["abs"])  # type: ignore[arg-type]
        all_stats = _random_summary(random_all["abs"])  # type: ignore[arg-type]
        policy_mean = float(policy_abs.mean())
        policy_rel_mean = float(policy_rel.mean())

        row = {
            "state": state_col,
            "test_year": int(test_year),
            "train_start_year": int(min(train_years)),
            "train_end_year": int(max(train_years)),
            "train_dates": int(train_daily["time"].nunique()),
            "test_dates": int(test_daily["time"].nunique()),
            "selected_k": int(selected_k),
            "active_dates": active_dates,
            "selected_dates": selected_dates,
            "mean_state_buyable_candidates": float(test_daily[f"{state_col}_buyable_candidate_count"].mean()),
            "policy_mean_abs_return": policy_mean,
            "policy_mean_relative_return": policy_rel_mean,
            "random_state_mean_abs_return": state_stats["mean"],
            "random_state_p95_abs_return": state_stats["p95"],
            "random_all_mean_abs_return": all_stats["mean"],
            "random_all_p95_abs_return": all_stats["p95"],
            "policy_minus_random_state_mean": policy_mean - state_stats["mean"],
            "policy_minus_random_state_p95": policy_mean - state_stats["p95"],
            "policy_random_state_percentile": float((random_state["abs"] <= policy_mean).mean()),  # type: ignore[index]
            "policy_minus_random_all_mean": policy_mean - all_stats["mean"],
            "policy_minus_random_all_p95": policy_mean - all_stats["p95"],
            "policy_random_all_percentile": float((random_all["abs"] <= policy_mean).mean()),  # type: ignore[index]
        }
        year_rows.append(row)

        out_daily = test_daily[
            [
                "time",
                "year",
                "buyable_candidate_count",
                f"{state_col}_buyable_candidate_count",
                f"{prefix}_selected_count",
                f"{prefix}_abs_return",
                f"{prefix}_relative_return",
                f"{prefix}_mean_candidate_rank",
                f"{prefix}_mean_sell_pressure_rank",
            ]
        ].copy()
        out_daily["state"] = state_col
        out_daily["test_year"] = int(test_year)
        out_daily["selected_k"] = int(selected_k)
        out_daily = out_daily.rename(
            columns={
                f"{state_col}_buyable_candidate_count": "state_buyable_candidate_count",
                f"{prefix}_selected_count": "policy_selected_count",
                f"{prefix}_abs_return": "policy_abs_return",
                f"{prefix}_relative_return": "policy_relative_return",
                f"{prefix}_mean_candidate_rank": "policy_mean_candidate_rank",
                f"{prefix}_mean_sell_pressure_rank": "policy_mean_sell_pressure_rank",
            }
        )
        daily_rows.append(out_daily)

    years_df = pd.DataFrame(year_rows)
    daily_df = pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
    if years_df.empty:
        raise ValueError(f"No walk-forward years available for {state_col}")

    wf_years = int(len(years_df))
    years_gt_state_mean = int((years_df["policy_minus_random_state_mean"] > 0.0).sum())
    years_gt_all_mean = int((years_df["policy_minus_random_all_mean"] > 0.0).sum())
    min_active_dates = int(years_df["active_dates"].min())
    confirmation = years_df.loc[years_df["test_year"] == 2025]
    confirmation_state_lift = None
    confirmation_all_lift = None
    confirmation_all_percentile = None
    if not confirmation.empty:
        confirmation_state_lift = float(confirmation.iloc[0]["policy_minus_random_state_mean"])
        confirmation_all_lift = float(confirmation.iloc[0]["policy_minus_random_all_mean"])
        confirmation_all_percentile = float(confirmation.iloc[0]["policy_random_all_percentile"])

    mean_policy = float(years_df["policy_mean_abs_return"].mean())
    mean_random_state = float(years_df["random_state_mean_abs_return"].mean())
    mean_random_all = float(years_df["random_all_mean_abs_return"].mean())
    mean_lift_state = float(years_df["policy_minus_random_state_mean"].mean())
    mean_lift_all = float(years_df["policy_minus_random_all_mean"].mean())
    required_years = max(3, int(np.ceil(0.60 * wf_years)))
    same_support_gate = bool(
        min_active_dates >= int(min_active_dates_per_year)
        and mean_lift_state > 0.0
        and years_gt_state_mean >= required_years
        and (confirmation_state_lift is None or confirmation_state_lift > 0.0)
    )
    random_all_gate = bool(
        min_active_dates >= int(min_active_dates_per_year)
        and mean_lift_all > 0.0
        and years_gt_all_mean >= required_years
        and (confirmation_all_lift is None or confirmation_all_lift > 0.0)
    )

    summary = {
        "state": state_col,
        "wf_years": wf_years,
        "test_years": [int(year) for year in years_df["test_year"].tolist()],
        "trained_component": "consumer K choice only, selected from prior years for this fixed forced-seller state",
        "deterministic_selector": "lowest candidate_pool_rank first, then highest sell_volume_pressure_rank tie-break",
        "mean_policy_abs_return": mean_policy,
        "mean_policy_relative_return": float(years_df["policy_mean_relative_return"].mean()),
        "mean_random_state_abs_return": mean_random_state,
        "mean_random_all_abs_return": mean_random_all,
        "mean_lift_vs_random_state": mean_lift_state,
        "mean_lift_vs_random_all": mean_lift_all,
        "years_gt_random_state_mean": years_gt_state_mean,
        "years_gt_random_all_mean": years_gt_all_mean,
        "min_active_dates_per_year": min_active_dates,
        "required_min_active_dates_per_year": int(min_active_dates_per_year),
        "confirmation_2025_lift_vs_random_state": confirmation_state_lift,
        "confirmation_2025_lift_vs_random_all": confirmation_all_lift,
        "confirmation_2025_random_all_percentile": confirmation_all_percentile,
        "same_support_gate": same_support_gate,
        "random_all_gate": random_all_gate,
    }
    return years_df, daily_df, summary


def _overall_verdict(state_summaries: dict[str, dict[str, object]]) -> tuple[str, str, str, list[str], list[str]]:
    broad_pass = [
        state
        for state, summary in state_summaries.items()
        if bool(summary.get("same_support_gate")) and bool(summary.get("random_all_gate"))
    ]
    partial_pass = [
        state
        for state, summary in state_summaries.items()
        if bool(summary.get("same_support_gate")) != bool(summary.get("random_all_gate"))
    ]
    if broad_pass:
        return (
            "PASSED",
            "offline_evidence",
            "A fixed forced-seller state beat random same-support and random-all candidate policies.",
            broad_pass,
            partial_pass,
        )
    if partial_pass:
        return (
            "MIXED",
            "park_or_narrow",
            "A fixed forced-seller state cleared only one random-policy gate.",
            broad_pass,
            partial_pass,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "No fixed forced-seller state beat random policy gates cleanly.",
        broad_pass,
        partial_pass,
    )


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
        Path(args.order_stats),
        Path(args.news),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        candidate_pool_rank_max=int(args.candidate_pool_rank_max),
    )
    daily_returns = _build_daily_policy_returns(panel, k_values)
    all_years: list[pd.DataFrame] = []
    all_daily: list[pd.DataFrame] = []
    state_summaries: dict[str, dict[str, object]] = {}

    for idx, state_col in enumerate(STATE_COLUMNS):
        years, daily, state_summary = _evaluate_state_walk_forward(
            panel,
            daily_returns,
            state_col=state_col,
            k_values=k_values,
            min_train_years=int(args.min_train_years),
            random_trials=int(args.random_trials),
            min_active_dates_per_year=int(args.min_active_dates_per_year),
            seed=int(args.seed) + idx,
        )
        all_years.append(years)
        all_daily.append(daily)
        state_summaries[state_col] = state_summary

    years_df = pd.concat(all_years, ignore_index=True)
    daily_df = pd.concat(all_daily, ignore_index=True)
    verdict, durable_status, branch_decision, broad_pass, partial_pass = _overall_verdict(state_summaries)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    years_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_years.parquet"
    daily_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_daily.parquet"
    atomic_write_parquet(years_df, years_path)
    atomic_write_parquet(daily_df, daily_path)

    summary = {
        "branch": "forced_seller_detector",
        "experiment_id": "H426",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "broad_pass_states": broad_pass,
        "partial_pass_states": partial_pass,
        "state_summaries": state_summaries,
        "fixed_states": STATE_COLUMNS,
        "deterministic_selector": "lowest candidate_pool_rank first, then highest sell_volume_pressure_rank tie-break",
        "primary_state": STATE_CORE,
        "literal_release_state": STATE_HARD_RELEASE,
        "primary_benchmark": "random same-K selection among active buyable rows from the same fixed state",
        "secondary_benchmark": "random same-K selection among all buyable candidate-pool rows",
        "no_s1_c16_baseline": True,
        "future_data_guardrail": (
            "The queue memo's next-day C16 confirmation clause is not used here "
            "because it is not decision-time valid for the current T close -> "
            "T+1 open entry-label contract. A delayed-entry protocol would be "
            "needed before testing that clause honestly."
        ),
        "state_contract": {
            "core": (
                "buyable candidate with 3d weakness, volume spike, high sell "
                "pressure, rising/high average sell size, and no active bad "
                "PhoBERT news on the signal date"
            ),
            "large_down": "core plus large same-day down move",
            "floor": "core plus recent floor-limit pressure",
            "hard_release": "core plus literal transition from blocked/not buyable to buyable next open",
        },
        "pass_rule": (
            "PASS if any fixed forced-seller state beats random same-support "
            "and random-all means on average, beats both in at least 60% of WF "
            "years, has positive 2025 lift versus both, and has enough support. "
            "MIXED if only one random-policy gate clears. Otherwise FAILED."
        ),
    }
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
            "order_stats": Path(args.order_stats),
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
            "state_rows": {state: int(panel[state].sum()) for state in STATE_COLUMNS},
            "state_active_dates": {
                state: int(panel.loc[panel[state], "time"].nunique()) for state in STATE_COLUMNS
            },
        },
    )

    print("H426 forced seller detector")
    print(f"saved_summary={summary_path}")
    print(f"years={years_path}")
    print(f"daily={daily_path}")
    print(f"verdict={verdict} | broad_pass={broad_pass} | partial_pass={partial_pass}")
    print(
        years_df[
            [
                "state",
                "test_year",
                "selected_k",
                "active_dates",
                "policy_mean_abs_return",
                "random_state_mean_abs_return",
                "policy_minus_random_state_mean",
                "random_all_mean_abs_return",
                "policy_minus_random_all_mean",
                "policy_random_all_percentile",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
