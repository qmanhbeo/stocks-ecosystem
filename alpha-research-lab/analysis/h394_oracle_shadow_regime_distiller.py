from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (  # noqa: E402
    MAX_RESEARCH_YEAR,
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    build_experiment_context,
    load_s1_decision_panel,
    normalize_time_ticker,
    rolling_train_test_years,
    safe_spearman,
    summarize_ic_rows,
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close  # noqa: E402


BRANCH_NAME = "h394_oracle_shadow_regime_distiller"
MODE = "research_branch_oracle_shadow_regime_distiller"

C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
NEWS_DAILY_PATH = data_path("features/news/datasets/news_daily_features.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
PRICE_LIMIT_PATH = data_path("features/xs_price_limit_daily.parquet")

C16_SCORE_COL = "order_volume_ratio_rank"
TARGET_BREADTH_COL = "target_hit_rate"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "The invalid S24x target-breadth regimes may contain a real shadow "
        "weather effect if next-day barrier breadth can be predicted from "
        "pre-decision S1, C16, order-stat, news, market, and tradability "
        "aggregates, and the predicted weather then honestly buckets S1/C16 IC."
    ),
    start_year=2015,
    end_year=2025,
    min_train_years=3,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={
        S1_TARGET_COL: "future ticker-level 1d barrier-hit label; target only",
        TARGET_BREADTH_COL: "future date-level mean of S1 target; target only",
    },
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        C16_SCORE_COL: "decision-time C16 order-pressure rank",
    },
)

HONEST_STATE_COLUMNS = [
    "all_rows",
    "ridge_pred_low20",
    "ridge_pred_high80",
    "s1_mean_low20",
    "s1_mean_high80",
    "observed_vni_down",
    "observed_vni_down_2d",
]

DIAGNOSTIC_STATE_COLUMNS = [
    "oracle_target_low20",
    "oracle_target_high80",
]

RANDOM_BENCHMARK_STATES = {
    "ridge_pred_low20",
    "ridge_pred_high80",
    "observed_vni_down",
    "observed_vni_down_2d",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H394: predict target-breadth weather from observable date-level "
            "features, then test whether predicted weather honestly buckets "
            "S1/C16 IC."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-train-years", type=int, default=SPEC.min_train_years)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--low-quantile", type=float, default=0.20)
    parser.add_argument("--high-quantile", type=float, default=0.80)
    parser.add_argument("--ridge-alpha", type=float, default=10.0)
    parser.add_argument("--random-iterations", type=int, default=50)
    parser.add_argument("--random-seed", type=int, default=394)
    return parser.parse_args()


def _ticker(value: object) -> str:
    return str(value).strip().upper()


def _as_time(frame: pd.DataFrame, *, source: str, date_col: str = "time") -> pd.DataFrame:
    out = frame.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce").dt.normalize()
    out = out.dropna(subset=[date_col])
    return out


def _clip_years(frame: pd.DataFrame, *, start_year: int, end_year: int, time_col: str = "time") -> pd.DataFrame:
    if int(end_year) > MAX_RESEARCH_YEAR:
        raise ValueError(f"end_year={end_year} would include 2026+; H394 blocks 2026+")
    years = pd.to_datetime(frame[time_col], errors="coerce").dt.year
    out = frame.loc[years.between(int(start_year), int(end_year))].copy()
    return out


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [
        "_".join(str(part) for part in col if str(part))
        if isinstance(col, tuple)
        else str(col)
        for col in out.columns
    ]
    return out


def _date_spearman(frame: pd.DataFrame, predictor_col: str, target_col: str) -> dict[str, object]:
    clean = frame[[predictor_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 20 or clean[predictor_col].nunique() < 3 or clean[target_col].nunique() < 3:
        return {"dates": int(len(clean)), "ic": None, "p_value": None}
    rho, p_value = spearmanr(clean[predictor_col], clean[target_col])
    rho_value = float(np.asarray(rho).flat[0])
    p_value_value = float(np.asarray(p_value).flat[0])
    if not np.isfinite(rho_value):
        return {"dates": int(len(clean)), "ic": None, "p_value": None}
    return {
        "dates": int(len(clean)),
        "ic": rho_value,
        "p_value": p_value_value if np.isfinite(p_value_value) else None,
    }


def _summarize_date_predictor(frame: pd.DataFrame, predictor_col: str) -> dict[str, object]:
    yearly_rows = []
    for year, group in frame.groupby("year", sort=True):
        stat = _date_spearman(group, predictor_col, TARGET_BREADTH_COL)
        yearly_rows.append({"year": int(year), "rows": stat["dates"], "ic": stat["ic"], "p_value": stat["p_value"]})
    summary = summarize_ic_rows(yearly_rows)
    pooled = _date_spearman(frame, predictor_col, TARGET_BREADTH_COL)
    return {
        "predictor": predictor_col,
        "pooled_dates": pooled["dates"],
        "pooled_ic": pooled["ic"],
        "pooled_p_value": pooled["p_value"],
        **summary,
    }


def _quantiles(grouped: pd.core.groupby.SeriesGroupBy, prefix: str, quantiles: Iterable[float]) -> pd.DataFrame:
    pieces = []
    for q in quantiles:
        part = grouped.quantile(float(q)).rename(f"{prefix}_q{int(round(q * 100)):02d}")
        pieces.append(part)
    return pd.concat(pieces, axis=1)


def load_base_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    c16 = pd.read_parquet(
        C16_PATH,
        columns=["time", "ticker", "order_volume_ratio", C16_SCORE_COL, "order_pressure_available"],
    )
    c16 = normalize_time_ticker(c16, source="C16 order-pressure surface")
    c16 = _clip_years(c16, start_year=spec.start_year, end_year=spec.end_year)
    c16["order_volume_ratio"] = pd.to_numeric(c16["order_volume_ratio"], errors="coerce")
    c16[C16_SCORE_COL] = pd.to_numeric(c16[C16_SCORE_COL], errors="coerce")

    out = panel.merge(
        c16[["time", "ticker", "order_volume_ratio", C16_SCORE_COL, "order_pressure_available"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    out["year"] = out["time"].dt.year.astype(int)
    out = out.sort_values(["time", "ticker"]).reset_index(drop=True)
    return out


def build_panel_date_features(panel: pd.DataFrame) -> pd.DataFrame:
    work = panel.copy()
    work["s1_gt_50"] = work[S1_SCORE_COL] >= 0.50
    work["s1_gt_60"] = work[S1_SCORE_COL] >= 0.60
    work["c16_available"] = work[C16_SCORE_COL].notna()
    work["c16_high80"] = work[C16_SCORE_COL] >= 0.80
    work["c16_low20"] = work[C16_SCORE_COL] <= 0.20

    grouped = work.groupby("time", sort=True)
    base = grouped.agg(
        target_hit_rate=(S1_TARGET_COL, "mean"),
        ticker_count=("ticker", "nunique"),
        s1_mean=(S1_SCORE_COL, "mean"),
        s1_std=(S1_SCORE_COL, "std"),
        s1_gt_50_share=("s1_gt_50", "mean"),
        s1_gt_60_share=("s1_gt_60", "mean"),
        c16_available_share=("c16_available", "mean"),
        c16_rank_mean=(C16_SCORE_COL, "mean"),
        c16_rank_std=(C16_SCORE_COL, "std"),
        c16_high80_share=("c16_high80", "mean"),
        c16_low20_share=("c16_low20", "mean"),
        c16_raw_mean=("order_volume_ratio", "mean"),
        c16_raw_std=("order_volume_ratio", "std"),
    )
    s1_q = _quantiles(grouped[S1_SCORE_COL], "s1", [0.10, 0.25, 0.50, 0.75, 0.90])
    c16_q = _quantiles(grouped[C16_SCORE_COL], "c16_rank", [0.10, 0.25, 0.50, 0.75, 0.90])
    raw_q = _quantiles(grouped["order_volume_ratio"], "c16_raw", [0.10, 0.50, 0.90])
    out = pd.concat([base, s1_q, c16_q, raw_q], axis=1).reset_index()
    out["year"] = out["time"].dt.year.astype(int)
    return out


def build_market_features(start_year: int, end_year: int) -> pd.DataFrame:
    wide = load_ohlcv_wide(min_rows=120)
    close = wide["close"].sort_index()
    vni_close = load_vni_close().sort_index().reindex(close.index)
    stock_ret_1d = close.pct_change(1, fill_method=None)
    stock_ret_5d = close.pct_change(5, fill_method=None)
    vni_ret_1d = vni_close.pct_change(1, fill_method=None)

    out = pd.DataFrame(
        {
            "time": pd.to_datetime(close.index, errors="coerce").normalize(),
            "vni_return_1d": vni_ret_1d.to_numpy(dtype=float),
            "vni_return_2d": vni_close.pct_change(2, fill_method=None).to_numpy(dtype=float),
            "vni_return_5d": vni_close.pct_change(5, fill_method=None).to_numpy(dtype=float),
            "vni_return_20d": vni_close.pct_change(20, fill_method=None).to_numpy(dtype=float),
            "vni_volatility_20d": vni_ret_1d.rolling(20, min_periods=10).std().to_numpy(dtype=float),
            "stock_up_share_1d": (stock_ret_1d > 0).mean(axis=1).to_numpy(dtype=float),
            "stock_down_share_1d": (stock_ret_1d < 0).mean(axis=1).to_numpy(dtype=float),
            "stock_up_share_5d": (stock_ret_5d > 0).mean(axis=1).to_numpy(dtype=float),
            "stock_down_share_5d": (stock_ret_5d < 0).mean(axis=1).to_numpy(dtype=float),
            "stock_return_median_1d": stock_ret_1d.median(axis=1).to_numpy(dtype=float),
            "stock_return_dispersion_1d": stock_ret_1d.std(axis=1).to_numpy(dtype=float),
        }
    )
    out = _clip_years(out, start_year=start_year, end_year=end_year)
    out["observed_vni_down"] = out["vni_return_1d"] < 0.0
    prev_vni_down = out["observed_vni_down"].shift(1, fill_value=False).astype(bool)
    out["observed_vni_down_2d"] = out["observed_vni_down"] & prev_vni_down
    return out


def build_order_stats_features(start_year: int, end_year: int) -> pd.DataFrame:
    raw = pd.read_parquet(ORDER_STATS_PATH)
    raw = raw.rename(columns={"date": "time"})
    raw = _as_time(raw, source="CafeF order stats")
    raw["ticker"] = raw["ticker"].map(_ticker)
    raw = _clip_years(raw, start_year=start_year, end_year=end_year)
    numeric_cols = [
        "buy_order_count",
        "buy_order_volume",
        "avg_buy_order_volume",
        "sell_order_count",
        "sell_order_volume",
        "avg_sell_order_volume",
        "buy_sell_volume_imbalance",
    ]
    for column in numeric_cols:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    raw["total_order_count"] = raw["buy_order_count"] + raw["sell_order_count"]
    raw["total_order_volume"] = raw["buy_order_volume"] + raw["sell_order_volume"]
    raw["buy_count_share"] = raw["buy_order_count"].div(raw["total_order_count"].replace(0, np.nan))
    raw["buy_volume_share"] = raw["buy_order_volume"].div(raw["total_order_volume"].replace(0, np.nan))
    raw["avg_buy_sell_size_ratio"] = raw["avg_buy_order_volume"].div(
        raw["avg_sell_order_volume"].replace(0, np.nan)
    )
    raw["fragmentation"] = raw["total_order_count"].div(raw["total_order_volume"].replace(0, np.nan))

    grouped = raw.groupby("time", sort=True)
    out = grouped.agg(
        order_ticker_count=("ticker", "nunique"),
        buy_order_count_sum=("buy_order_count", "sum"),
        sell_order_count_sum=("sell_order_count", "sum"),
        buy_order_volume_sum=("buy_order_volume", "sum"),
        sell_order_volume_sum=("sell_order_volume", "sum"),
        buy_sell_volume_imbalance_sum=("buy_sell_volume_imbalance", "sum"),
        buy_count_share_mean=("buy_count_share", "mean"),
        buy_volume_share_mean=("buy_volume_share", "mean"),
        avg_buy_order_volume_mean=("avg_buy_order_volume", "mean"),
        avg_sell_order_volume_mean=("avg_sell_order_volume", "mean"),
        avg_buy_sell_size_ratio_mean=("avg_buy_sell_size_ratio", "mean"),
        fragmentation_mean=("fragmentation", "mean"),
        fragmentation_std=("fragmentation", "std"),
    )
    out["market_buy_volume_pressure"] = out["buy_order_volume_sum"].div(
        (out["buy_order_volume_sum"] + out["sell_order_volume_sum"]).replace(0, np.nan)
    )
    return out.reset_index()


def build_news_features(start_year: int, end_year: int) -> pd.DataFrame:
    columns = [
        "ticker",
        "date",
        "phobert_article_count_1d",
        "phobert_article_count_5d",
        "phobert_source_type_official_or_regulatory_count_1d",
        "phobert_forward_looking_true_count_1d",
        "phobert_article_scope_stock_news_count_1d",
        "ollama_guarded_article_count_1d",
        "ollama_guarded_event_family_earnings_share",
        "ollama_guarded_event_family_guidance_share",
        "ollama_guarded_event_family_dividend_share",
        "ollama_guarded_event_family_regulatory_or_legal_share",
        "ollama_guarded_source_authority_official_share",
    ]
    news = pd.read_parquet(NEWS_DAILY_PATH, columns=columns).rename(columns={"date": "time"})
    news = _as_time(news, source="combined local-news daily", date_col="time")
    news["ticker"] = news["ticker"].map(_ticker)
    news = _clip_years(news, start_year=start_year, end_year=end_year)
    for column in columns:
        if column not in {"ticker", "date"} and column in news.columns:
            news[column] = pd.to_numeric(news[column], errors="coerce").fillna(0.0)
    news["phobert_active"] = news["phobert_article_count_1d"] > 0
    news["official_active"] = news["phobert_source_type_official_or_regulatory_count_1d"] > 0
    news["forward_active"] = news["phobert_forward_looking_true_count_1d"] > 0
    news["ollama_active"] = news["ollama_guarded_article_count_1d"] > 0

    grouped = news.groupby("time", sort=True)
    out = grouped.agg(
        phobert_article_count_1d_sum=("phobert_article_count_1d", "sum"),
        phobert_article_count_5d_sum=("phobert_article_count_5d", "sum"),
        phobert_active_ticker_share=("phobert_active", "mean"),
        official_count_1d_sum=("phobert_source_type_official_or_regulatory_count_1d", "sum"),
        official_active_ticker_share=("official_active", "mean"),
        forward_true_count_1d_sum=("phobert_forward_looking_true_count_1d", "sum"),
        forward_active_ticker_share=("forward_active", "mean"),
        stock_news_count_1d_sum=("phobert_article_scope_stock_news_count_1d", "sum"),
        ollama_article_count_1d_sum=("ollama_guarded_article_count_1d", "sum"),
        ollama_active_ticker_share=("ollama_active", "mean"),
        ollama_earnings_share_mean=("ollama_guarded_event_family_earnings_share", "mean"),
        ollama_guidance_share_mean=("ollama_guarded_event_family_guidance_share", "mean"),
        ollama_dividend_share_mean=("ollama_guarded_event_family_dividend_share", "mean"),
        ollama_regulatory_share_mean=("ollama_guarded_event_family_regulatory_or_legal_share", "mean"),
        ollama_official_authority_share_mean=("ollama_guarded_source_authority_official_share", "mean"),
    )
    return out.reset_index()


def build_tradability_features(start_year: int, end_year: int) -> pd.DataFrame:
    trad = pd.read_parquet(TRADABILITY_PATH)
    trad = normalize_time_ticker(trad, source="execution tradability")
    trad = _clip_years(trad, start_year=start_year, end_year=end_year)
    grouped = trad.groupby("time", sort=True)
    out = grouped.agg(
        has_volume_share=("has_volume", "mean"),
        ceiling_share=("is_ceiling", "mean"),
        floor_share=("is_floor", "mean"),
        can_buy_next_open_share=("can_buy_next_open", "mean"),
        can_sell_next_open_share=("can_sell_next_open", "mean"),
    )
    out["boundary_share"] = out["ceiling_share"] + out["floor_share"]
    return out.reset_index()


def build_price_limit_features(start_year: int, end_year: int) -> pd.DataFrame:
    limits = pd.read_parquet(PRICE_LIMIT_PATH)
    limits = normalize_time_ticker(limits, source="price-limit features")
    limits = _clip_years(limits, start_year=start_year, end_year=end_year)
    for column in [
        "xs_ceiling_count_5d",
        "xs_ceiling_count_20d",
        "xs_floor_count_5d",
        "xs_floor_count_20d",
        "xs_limit_net_5d",
    ]:
        limits[column] = pd.to_numeric(limits[column], errors="coerce")
    grouped = limits.groupby("time", sort=True)
    out = grouped.agg(
        ceiling_count_5d_mean=("xs_ceiling_count_5d", "mean"),
        ceiling_count_20d_mean=("xs_ceiling_count_20d", "mean"),
        floor_count_5d_mean=("xs_floor_count_5d", "mean"),
        floor_count_20d_mean=("xs_floor_count_20d", "mean"),
        limit_net_5d_mean=("xs_limit_net_5d", "mean"),
    )
    return out.reset_index()


def build_date_feature_frame(panel: pd.DataFrame, spec: ExperimentSpec) -> pd.DataFrame:
    frames = [
        build_panel_date_features(panel),
        build_market_features(spec.start_year, spec.end_year),
        build_order_stats_features(spec.start_year, spec.end_year),
        build_news_features(spec.start_year, spec.end_year),
        build_tradability_features(spec.start_year, spec.end_year),
        build_price_limit_features(spec.start_year, spec.end_year),
    ]
    out = frames[0].copy()
    for frame in frames[1:]:
        out = out.merge(frame, on="time", how="left", validate="one_to_one")
    out = out.sort_values("time").reset_index(drop=True)
    out["year"] = out["time"].dt.year.astype(int)
    if out["year"].max() > MAX_RESEARCH_YEAR:
        raise ValueError("H394 date features include 2026+ rows")
    return out


def _numeric_feature_columns(frame: pd.DataFrame) -> list[str]:
    blocked = {"time", "year", TARGET_BREADTH_COL}
    cols = [
        col
        for col in frame.columns
        if col not in blocked
        and pd.api.types.is_numeric_dtype(frame[col])
        and frame[col].replace([np.inf, -np.inf], np.nan).notna().any()
    ]
    return sorted(cols)


def run_rolling_regime_model(
    date_features: pd.DataFrame,
    args: argparse.Namespace,
    spec: ExperimentSpec,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_cols = _numeric_feature_columns(date_features)
    folds = rolling_train_test_years(
        start_year=spec.start_year,
        end_year=spec.end_year,
        min_train_years=spec.min_train_years,
    )
    predictions = []
    coefficient_rows = []

    for fold in folds:
        test_year = int(fold["test_year"])
        train_years = tuple(int(year) for year in fold["train_years"])
        train = date_features.loc[date_features["year"].isin(train_years)].dropna(subset=[TARGET_BREADTH_COL]).copy()
        test = date_features.loc[date_features["year"].eq(test_year)].dropna(subset=[TARGET_BREADTH_COL]).copy()
        if len(train) < 100 or len(test) < 20:
            continue

        model = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            Ridge(alpha=float(args.ridge_alpha)),
        )
        model.fit(train[feature_cols], train[TARGET_BREADTH_COL])
        train_pred = model.predict(train[feature_cols])
        test_pred = model.predict(test[feature_cols])

        pred_low = float(np.quantile(train_pred, float(args.low_quantile)))
        pred_high = float(np.quantile(train_pred, float(args.high_quantile)))
        s1_low = float(train["s1_mean"].quantile(float(args.low_quantile)))
        s1_high = float(train["s1_mean"].quantile(float(args.high_quantile)))
        oracle_low = float(train[TARGET_BREADTH_COL].quantile(float(args.low_quantile)))
        oracle_high = float(train[TARGET_BREADTH_COL].quantile(float(args.high_quantile)))

        scored = test[["time", "year", TARGET_BREADTH_COL, "s1_mean", "vni_return_1d", "observed_vni_down", "observed_vni_down_2d"]].copy()
        scored["ridge_pred"] = test_pred
        scored["ridge_pred_low20"] = scored["ridge_pred"] <= pred_low
        scored["ridge_pred_high80"] = scored["ridge_pred"] >= pred_high
        scored["s1_mean_low20"] = scored["s1_mean"] <= s1_low
        scored["s1_mean_high80"] = scored["s1_mean"] >= s1_high
        scored["oracle_target_low20"] = scored[TARGET_BREADTH_COL] <= oracle_low
        scored["oracle_target_high80"] = scored[TARGET_BREADTH_COL] >= oracle_high
        scored["all_rows"] = True
        scored["pred_low_threshold"] = pred_low
        scored["pred_high_threshold"] = pred_high
        scored["s1_low_threshold"] = s1_low
        scored["s1_high_threshold"] = s1_high
        scored["oracle_low_threshold"] = oracle_low
        scored["oracle_high_threshold"] = oracle_high
        predictions.append(scored)

        ridge = model.named_steps["ridge"]
        for feature, coef in zip(feature_cols, ridge.coef_):
            coefficient_rows.append(
                {
                    "test_year": test_year,
                    "feature": feature,
                    "coefficient": float(coef),
                    "abs_coefficient": float(abs(coef)),
                }
            )

    if not predictions:
        raise RuntimeError("No rolling folds produced predictions.")
    prediction_frame = pd.concat(predictions, ignore_index=True).sort_values("time")
    coefficient_frame = pd.DataFrame(coefficient_rows)
    return prediction_frame, coefficient_frame


def evaluate_state_ics(
    panel: pd.DataFrame,
    date_states: pd.DataFrame,
    *,
    min_year_rows: int,
    random_iterations: int,
    random_seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = panel.merge(
        date_states[["time", "year", *HONEST_STATE_COLUMNS, *DIAGNOSTIC_STATE_COLUMNS]],
        on="time",
        how="inner",
        validate="many_to_one",
        suffixes=("", "_state"),
    )
    if "year_state" in merged.columns:
        merged = merged.drop(columns=["year_state"])

    rows = []
    yearly_rows = []
    state_columns = [*HONEST_STATE_COLUMNS, *DIAGNOSTIC_STATE_COLUMNS]
    scores = [
        (S1_SCORE_COL, "s1"),
        (C16_SCORE_COL, "c16"),
    ]

    for score_col, score_name in scores:
        for state_col in state_columns:
            subset = merged.loc[merged[state_col].fillna(False).astype(bool)].copy()
            pooled = safe_spearman(subset, score_col, S1_TARGET_COL, min_rows=int(min_year_rows))
            year_stats = []
            for year, group in subset.groupby("year", sort=True):
                stat = safe_spearman(group, score_col, S1_TARGET_COL, min_rows=int(min_year_rows))
                item = {
                    "state": state_col,
                    "score": score_name,
                    "score_col": score_col,
                    "year": int(year),
                    **stat,
                }
                yearly_rows.append(item)
                year_stats.append({"year": int(year), **stat})
            summary = summarize_ic_rows(year_stats)
            rows.append(
                {
                    "state": state_col,
                    "score": score_name,
                    "score_col": score_col,
                    "state_source": "target_diagnostic" if state_col in DIAGNOSTIC_STATE_COLUMNS else "honest",
                    "rows": int(pooled["rows"]),
                    "dates": int(subset["time"].nunique()) if not subset.empty else 0,
                    "pooled_ic": pooled["ic"],
                    "pooled_p_value": pooled["p_value"],
                    **summary,
                }
            )

    result = pd.DataFrame(rows)
    yearly = pd.DataFrame(yearly_rows)
    baseline = result.loc[result["state"].eq("all_rows"), ["score", "avg_ic"]].rename(
        columns={"avg_ic": "all_rows_avg_ic"}
    )
    result = result.merge(baseline, on="score", how="left", validate="many_to_one")
    result["lift_vs_all_rows_avg_ic"] = result["avg_ic"] - result["all_rows_avg_ic"]

    random_rows = []
    for score_col, score_name in scores:
        for state_col in sorted(RANDOM_BENCHMARK_STATES):
            random_rows.append(
                _random_state_benchmark(
                    merged,
                    date_states,
                    state_col=state_col,
                    score_col=score_col,
                    score_name=score_name,
                    min_year_rows=int(min_year_rows),
                    iterations=int(random_iterations),
                    seed=int(random_seed),
                )
            )
    random_frame = pd.DataFrame(random_rows)
    result = result.merge(
        random_frame,
        on=["state", "score"],
        how="left",
        validate="one_to_one",
    )
    result["lift_vs_random_mean_avg_ic"] = result["avg_ic"] - result["random_mean_avg_ic"]
    return result.sort_values(["score", "avg_ic"], ascending=[True, False]), yearly


def _random_state_benchmark(
    merged_panel: pd.DataFrame,
    date_states: pd.DataFrame,
    *,
    state_col: str,
    score_col: str,
    score_name: str,
    min_year_rows: int,
    iterations: int,
    seed: int,
) -> dict[str, object]:
    stable_key = f"{state_col}:{score_name}"
    stable_offset = sum((idx + 1) * ord(char) for idx, char in enumerate(stable_key)) % 100_000
    rng = np.random.default_rng(int(seed) + stable_offset)
    dates_by_year = {
        int(year): group["time"].drop_duplicates().to_numpy(dtype="datetime64[ns]")
        for year, group in date_states.groupby("year", sort=True)
    }
    counts_by_year = {
        int(year): int(group.loc[group[state_col].fillna(False).astype(bool), "time"].nunique())
        for year, group in date_states.groupby("year", sort=True)
    }
    values = []
    for _ in range(max(0, int(iterations))):
        selected = []
        for year, dates in dates_by_year.items():
            k = min(int(counts_by_year.get(year, 0)), len(dates))
            if k > 0:
                selected.extend(rng.choice(dates, size=k, replace=False))
        if not selected:
            continue
        selected_set = set(pd.to_datetime(selected).normalize())
        random_subset = merged_panel.loc[merged_panel["time"].isin(selected_set)].copy()
        yearly_stats = []
        for year, group in random_subset.groupby("year", sort=True):
            stat = safe_spearman(group, score_col, S1_TARGET_COL, min_rows=int(min_year_rows))
            yearly_stats.append({"year": int(year), **stat})
        summary = summarize_ic_rows(yearly_stats)
        if summary["avg_ic"] is not None:
            values.append(float(summary["avg_ic"]))
    if not values:
        return {
            "state": state_col,
            "score": score_name,
            "random_iterations": int(iterations),
            "random_mean_avg_ic": None,
            "random_p05_avg_ic": None,
            "random_p95_avg_ic": None,
        }
    return {
        "state": state_col,
        "score": score_name,
        "random_iterations": int(iterations),
        "random_mean_avg_ic": float(np.mean(values)),
        "random_p05_avg_ic": float(np.quantile(values, 0.05)),
        "random_p95_avg_ic": float(np.quantile(values, 0.95)),
    }


def summarize_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    predictors = [
        "ridge_pred",
        "s1_mean",
        "vni_return_1d",
    ]
    rows = [_summarize_date_predictor(predictions, col) for col in predictors if col in predictions.columns]
    return pd.DataFrame(rows).sort_values("avg_ic", ascending=False, na_position="last")


def choose_decision(date_summary: pd.DataFrame, state_results: pd.DataFrame) -> tuple[str, dict[str, object]]:
    ridge = date_summary.loc[date_summary["predictor"].eq("ridge_pred")]
    ridge_row = ridge.iloc[0].to_dict() if not ridge.empty else {}
    primary_states = state_results.loc[
        state_results["state"].isin(["ridge_pred_low20", "ridge_pred_high80"])
        & state_results["score"].isin(["s1", "c16"])
        & state_results["state_source"].eq("honest")
    ].copy()
    if primary_states.empty:
        return "FAILED", {"reason": "No primary predicted-weather state results."}

    primary_states["random_lift"] = primary_states["lift_vs_random_mean_avg_ic"]
    best = primary_states.sort_values(
        ["lift_vs_all_rows_avg_ic", "random_lift"],
        ascending=[False, False],
        na_position="last",
    ).iloc[0]
    ridge_avg_ic = ridge_row.get("avg_ic")
    ridge_pos_share = ridge_row.get("pct_positive_years")
    best_lift = best.get("lift_vs_all_rows_avg_ic")
    best_random_lift = best.get("random_lift")
    best_pos_share = best.get("pct_positive_years")

    pass_model = (
        ridge_avg_ic is not None
        and float(ridge_avg_ic) >= 0.10
        and ridge_pos_share is not None
        and float(ridge_pos_share) >= 0.60
    )
    pass_bucket = (
        best_lift is not None
        and float(best_lift) >= 0.01
        and best_random_lift is not None
        and float(best_random_lift) >= 0.005
        and best_pos_share is not None
        and float(best_pos_share) >= 0.60
    )
    mixed_model = (
        ridge_avg_ic is not None
        and float(ridge_avg_ic) > 0.03
        and ridge_pos_share is not None
        and float(ridge_pos_share) >= 0.50
    )
    mixed_bucket = best_lift is not None and float(best_lift) > 0.0

    if pass_model and pass_bucket:
        decision = "PASSED"
    elif pass_model or (mixed_model and mixed_bucket):
        decision = "MIXED"
    else:
        decision = "FAILED"
    return decision, {
        "ridge_date_avg_ic": ridge_avg_ic,
        "ridge_date_positive_years": ridge_row.get("positive_years"),
        "ridge_date_years": ridge_row.get("years"),
        "best_predicted_weather_state": best.get("state"),
        "best_predicted_weather_score": best.get("score"),
        "best_lift_vs_all_rows_avg_ic": best_lift,
        "best_lift_vs_random_mean_avg_ic": best_random_lift,
        "best_positive_years": best.get("positive_years"),
        "best_years": best.get("years"),
        "pass_model_gate": pass_model,
        "pass_bucket_gate": pass_bucket,
    }


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_train_years=int(args.min_train_years),
        min_year_rows=int(args.min_year_rows),
    )
    context = build_experiment_context(spec, artifact_subdir=BRANCH_NAME)

    panel = load_base_panel(args, spec)
    date_features = build_date_feature_frame(panel, spec)
    predictions, coefficients = run_rolling_regime_model(date_features, args, spec)
    date_summary = summarize_predictions(predictions)
    state_results, yearly = evaluate_state_ics(
        panel,
        predictions,
        min_year_rows=spec.min_year_rows,
        random_iterations=int(args.random_iterations),
        random_seed=int(args.random_seed),
    )
    decision, decision_detail = choose_decision(date_summary, state_results)

    date_features_path = write_dataframe_artifact(date_features, context, f"{BRANCH_NAME}_date_features")
    predictions_path = write_dataframe_artifact(predictions, context, f"{BRANCH_NAME}_date_predictions")
    date_summary_path = write_dataframe_artifact(date_summary, context, f"{BRANCH_NAME}_date_prediction_summary")
    state_results_path = write_dataframe_artifact(state_results, context, f"{BRANCH_NAME}_state_ic_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_state_ic_yearly")
    coefficients_path = write_dataframe_artifact(coefficients, context, f"{BRANCH_NAME}_ridge_coefficients")

    top_coefficients = []
    if not coefficients.empty:
        top_coefficients = (
            coefficients.sort_values("abs_coefficient", ascending=False)
            .groupby("test_year", sort=True)
            .head(5)
            .to_dict(orient="records")
        )

    primary_states = state_results.loc[
        state_results["state"].isin(["ridge_pred_low20", "ridge_pred_high80", "observed_vni_down", "observed_vni_down_2d"])
    ].to_dict(orient="records")
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "decision_detail": decision_detail,
            "start_year": spec.start_year,
            "end_year": spec.end_year,
            "test_years": sorted(int(year) for year in predictions["year"].unique()),
            "panel_rows": int(len(panel)),
            "date_rows": int(len(date_features)),
            "prediction_rows": int(len(predictions)),
            "feature_count": int(len(_numeric_feature_columns(date_features))),
            "date_prediction_summary": date_summary.to_dict(orient="records"),
            "primary_state_results": primary_states,
            "top_coefficients_by_fold": top_coefficients,
            "protocol_note": (
                "oracle_target_* states are target-derived upper-bound diagnostics only; "
                "the verdict uses ridge_pred_* honest predicted-weather states."
            ),
        },
        artifacts={
            "date_features": date_features_path,
            "date_predictions": predictions_path,
            "date_prediction_summary": date_summary_path,
            "state_ic_results": state_results_path,
            "state_ic_yearly": yearly_path,
            "ridge_coefficients": coefficients_path,
        },
        metadata={
            "state_columns_honest": HONEST_STATE_COLUMNS,
            "state_columns_target_diagnostic": DIAGNOSTIC_STATE_COLUMNS,
            "random_benchmark_states": sorted(RANDOM_BENCHMARK_STATES),
            "random_iterations": int(args.random_iterations),
            "ridge_alpha": float(args.ridge_alpha),
            "low_quantile": float(args.low_quantile),
            "high_quantile": float(args.high_quantile),
            "no_2026_rows": True,
        },
    )

    pd.set_option("display.max_rows", 80)
    pd.set_option("display.width", 220)
    print("Date prediction summary:")
    print(date_summary.to_string(index=False))
    print("\nState IC results:")
    display_cols = [
        "state",
        "score",
        "state_source",
        "rows",
        "dates",
        "avg_ic",
        "positive_years",
        "years",
        "lift_vs_all_rows_avg_ic",
        "random_mean_avg_ic",
        "lift_vs_random_mean_avg_ic",
    ]
    print(state_results[display_cols].to_string(index=False))
    print(f"\ndecision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
