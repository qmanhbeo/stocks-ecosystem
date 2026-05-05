from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

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
from src.standalone_signal_utils import load_vni_close  # noqa: E402


BRANCH_NAME = "h395_weak_signal_quorum_sleeve"
MODE = "research_branch_weak_signal_quorum_sleeve"

MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
NEWS_DAILY_PATH = data_path("features/news/datasets/news_daily_features.parquet")

C16_SCORE_COL = "order_volume_ratio_rank"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Independent weak signals with IC around 0.01-0.05 may become a "
        "stronger context when they agree, as long as the quorum is selected "
        "train-before-test and remains low-correlation to S1/C16 parents."
    ),
    start_year=2016,
    end_year=2025,
    min_train_years=3,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        C16_SCORE_COL: "decision-time C16 order-pressure rank",
        "weak_quorum_score": "train-selected equal-weight weak-vote quorum score",
    },
)

MATRIX_COMPONENTS = {
    "c4_oc_asym": "c4_oc_asym_5d",
    "c5_positive_size": "c5_positive_size",
    "c6_sector_laggard": "c6_contrarian_intra_5d",
    "c7_ceiling_count": "c7_ceiling_count_5d",
    "c8_volume_z": "c8_vol_zscore_5d",
    "c9_reversal": "c9_reversal_1d",
    "c10_illiq": "c10_illiq_level_rank",
    "c11_ret_lag": "c11_ret_60d_lag_rank",
    "c12_gap_absorb": "c12_gap_absorb_3",
    "c13_compression": "c13_compress_blowoff_2",
    "c14_clv_volconf": "c14_clv_volconf_resid_rank",
}

NEWS_COLUMNS = [
    "date",
    "ticker",
    "phobert_article_count_1d",
    "phobert_sentiment_score_sum",
    "phobert_forward_looking_article_count_1d",
    "phobert_forward_looking_prob_mean",
    "phobert_article_scope_article_count_1d",
    "phobert_source_type_article_count_1d",
    "phobert_source_type_official_or_regulatory_prob_mean",
    "ollama_guarded_article_count_1d",
    "ollama_guarded_event_family_earnings_share",
    "ollama_guarded_event_family_guidance_share",
]

BINARY_COMPONENTS = [
    "official_supported_delay_vote",
    "h364_positive_vote",
    "observed_vni_down_2d_vote",
    "january_first_10_vote",
    "monday_vote",
]


@dataclass(frozen=True)
class ComponentStat:
    name: str
    train_avg_ic: float | None
    train_positive_years: int
    train_years: int
    train_pct_positive_years: float | None
    corr_s1: float | None
    corr_c16: float | None
    low_corr: bool
    selected: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H395: train-selected weak-signal quorum sleeve. Candidate weak "
            "votes are predeclared; selection uses only prior years."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--matrix-path", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--news-path", type=str, default=str(NEWS_DAILY_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-train-years", type=int, default=SPEC.min_train_years)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-train-avg-ic", type=float, default=0.005)
    parser.add_argument("--min-train-positive-share", type=float, default=0.60)
    parser.add_argument("--max-parent-corr", type=float, default=0.30)
    parser.add_argument("--random-iterations", type=int, default=200)
    parser.add_argument("--random-seed", type=int, default=395)
    return parser.parse_args()


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _safe_corr(frame: pd.DataFrame, left: str, right: str, min_rows: int) -> float | None:
    clean = frame[[left, right]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < int(min_rows) or clean[left].nunique() < 2 or clean[right].nunique() < 2:
        return None
    rho, _ = spearmanr(clean[left], clean[right])
    value = float(np.asarray(rho).flat[0])
    return value if np.isfinite(value) else None


def _component_spearman(frame: pd.DataFrame, score_col: str, min_rows: int) -> dict[str, object]:
    return safe_spearman(
        frame,
        score_col,
        S1_TARGET_COL,
        min_rows=int(min_rows),
        min_score_unique=2,
        min_target_unique=2,
    )


def _daily_rank(frame: pd.DataFrame, raw_col: str) -> pd.Series:
    raw = _safe_numeric(frame, raw_col, np.nan).replace([np.inf, -np.inf], np.nan)
    ranked = raw.groupby(frame["time"], sort=False).rank(method="average", pct=True)
    return ranked.fillna(0.5).astype(float)


def _clip_years(frame: pd.DataFrame, start_year: int, end_year: int, time_col: str = "time") -> pd.DataFrame:
    if int(end_year) > MAX_RESEARCH_YEAR:
        raise ValueError(f"H395 blocks 2026+; got end_year={end_year}")
    years = pd.to_datetime(frame[time_col], errors="coerce").dt.year
    return frame.loc[years.between(int(start_year), int(end_year))].copy()


def _load_news(path: str | Path, start_year: int, end_year: int) -> pd.DataFrame:
    news = pd.read_parquet(path, columns=NEWS_COLUMNS).copy()
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    news = news.drop(columns=["date"]).dropna(subset=["time", "ticker"])
    news = _clip_years(news, start_year, end_year)
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            news[column] = _safe_numeric(news, column)

    earnings_guidance = (
        news["ollama_guarded_event_family_earnings_share"]
        + news["ollama_guarded_event_family_guidance_share"]
    ).clip(lower=0.0, upper=1.0)
    news["h364_official_sentiment_x_earnings_guidance"] = (
        news["phobert_sentiment_score_sum"]
        * news["phobert_source_type_official_or_regulatory_prob_mean"]
        * earnings_guidance
    )
    return news


def _add_date_votes(panel: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    out = panel.copy()
    vni = load_vni_close().sort_index()
    market = pd.DataFrame(
        {
            "time": pd.to_datetime(vni.index, errors="coerce").normalize(),
            "vni_return_1d": vni.pct_change(1, fill_method=None).to_numpy(dtype=float),
        }
    )
    market = _clip_years(market, start_year, end_year)
    market["observed_vni_down"] = market["vni_return_1d"] < 0.0
    market["observed_vni_down_2d_vote"] = (
        market["observed_vni_down"] & market["observed_vni_down"].shift(1, fill_value=False).astype(bool)
    ).astype(float)

    day_index = (
        out[["time"]]
        .drop_duplicates()
        .sort_values("time")
        .assign(year=lambda frame: frame["time"].dt.year)
    )
    day_index["trading_day_of_year"] = day_index.groupby("year").cumcount() + 1
    day_index["january_first_10_vote"] = (day_index["trading_day_of_year"] <= 10).astype(float)
    day_index["monday_vote"] = (day_index["time"].dt.dayofweek == 0).astype(float)

    out = out.merge(
        market[["time", "observed_vni_down_2d_vote"]],
        on="time",
        how="left",
        validate="many_to_one",
    )
    out = out.merge(
        day_index[["time", "january_first_10_vote", "monday_vote"]],
        on="time",
        how="left",
        validate="many_to_one",
    )
    for column in ["observed_vni_down_2d_vote", "january_first_10_vote", "monday_vote"]:
        out[column] = _safe_numeric(out, column)
    return out


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    s1 = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    matrix_cols = ["time", "ticker", *[col for col in MATRIX_COMPONENTS.values() if col != "c5_positive_size"]]
    matrix = pd.read_parquet(args.matrix_path, columns=matrix_cols).copy()
    matrix = normalize_time_ticker(matrix, source="RL signal matrix weak components")
    matrix = _clip_years(matrix, spec.start_year, spec.end_year)
    matrix["c5_positive_size"] = _safe_numeric(matrix, "c5_ins_relative_size_5d").clip(lower=0.0)

    c16 = pd.read_parquet(
        args.c16_path,
        columns=["time", "ticker", C16_SCORE_COL, "order_pressure_available"],
    ).copy()
    c16 = normalize_time_ticker(c16, source="C16 order-pressure surface")
    c16 = _clip_years(c16, spec.start_year, spec.end_year)
    c16[C16_SCORE_COL] = _safe_numeric(c16, C16_SCORE_COL, np.nan)
    c16["order_pressure_available"] = c16["order_pressure_available"].fillna(False).astype(bool)

    news = _load_news(args.news_path, spec.start_year, spec.end_year)

    panel = s1.merge(matrix, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.loc[panel["order_pressure_available"].fillna(False).astype(bool)].copy()
    panel = panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL, C16_SCORE_COL])

    panel["year"] = panel["time"].dt.year.astype(int)
    panel["h364_positive_vote"] = (
        (_safe_numeric(panel, "h364_official_sentiment_x_earnings_guidance") > 0.0)
        & (_safe_numeric(panel, "ollama_guarded_article_count_1d") > 0.0)
    ).astype(float)
    official = (
        (_safe_numeric(panel, "phobert_source_type_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_source_type_official_or_regulatory_prob_mean") >= 0.50)
    )
    forward = (
        (_safe_numeric(panel, "phobert_forward_looking_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_forward_looking_prob_mean") >= 0.50)
    )
    c16_support = _safe_numeric(panel, C16_SCORE_COL, np.nan) >= 0.80
    insider_support = _safe_numeric(panel, "c5_positive_size") > 0.0
    panel["official_supported_delay_vote"] = ((official | forward) & (c16_support | insider_support)).astype(float)
    panel = _add_date_votes(panel, spec.start_year, spec.end_year)

    for name, raw_col in MATRIX_COMPONENTS.items():
        panel[f"vote_{name}"] = _daily_rank(panel, raw_col)
    for name in BINARY_COMPONENTS:
        panel[f"vote_{name}"] = _safe_numeric(panel, name).clip(lower=0.0, upper=1.0)

    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def component_columns() -> list[str]:
    return [f"vote_{name}" for name in [*MATRIX_COMPONENTS.keys(), *BINARY_COMPONENTS]]


def _yearly_ic(frame: pd.DataFrame, score_col: str, min_year_rows: int) -> list[dict[str, object]]:
    rows = []
    for year, group in frame.groupby("year", sort=True):
        stat = _component_spearman(group, score_col, int(min_year_rows))
        rows.append({"year": int(year), **stat})
    return rows


def _component_stat(
    train: pd.DataFrame,
    component_col: str,
    args: argparse.Namespace,
) -> ComponentStat:
    yearly = _yearly_ic(train, component_col, int(args.min_year_rows))
    summary = summarize_ic_rows(yearly)
    corr_s1 = _safe_corr(train, component_col, S1_SCORE_COL, int(args.min_year_rows))
    corr_c16 = _safe_corr(train, component_col, C16_SCORE_COL, int(args.min_year_rows))
    low_corr = (
        corr_s1 is not None
        and corr_c16 is not None
        and abs(float(corr_s1)) < float(args.max_parent_corr)
        and abs(float(corr_c16)) < float(args.max_parent_corr)
    )
    selected = (
        low_corr
        and summary["avg_ic"] is not None
        and float(summary["avg_ic"]) >= float(args.min_train_avg_ic)
        and summary["pct_positive_years"] is not None
        and float(summary["pct_positive_years"]) >= float(args.min_train_positive_share)
    )
    return ComponentStat(
        name=component_col,
        train_avg_ic=summary["avg_ic"],
        train_positive_years=int(summary["positive_years"]),
        train_years=int(summary["years"]),
        train_pct_positive_years=summary["pct_positive_years"],
        corr_s1=corr_s1,
        corr_c16=corr_c16,
        low_corr=low_corr,
        selected=selected,
    )


def _basket_ic(frame: pd.DataFrame, columns: list[str], score_name: str) -> tuple[pd.DataFrame, dict[str, object]]:
    out = frame.copy()
    out[score_name] = out[columns].mean(axis=1) if columns else np.nan
    stat = safe_spearman(out, score_name, S1_TARGET_COL, min_rows=500)
    return out, stat


def _random_basket_control(
    test: pd.DataFrame,
    pool: list[str],
    k: int,
    *,
    iterations: int,
    seed: int,
    min_rows: int,
) -> dict[str, object]:
    if k <= 0 or len(pool) < k or int(iterations) <= 0:
        return {"random_mean_ic": None, "random_p05_ic": None, "random_p95_ic": None}
    rng = np.random.default_rng(int(seed))
    values = []
    for _ in range(int(iterations)):
        columns = list(rng.choice(pool, size=k, replace=False))
        scored, stat = _basket_ic(test, columns, "_random_basket_score")
        if stat["ic"] is not None:
            values.append(float(stat["ic"]))
    if not values:
        return {"random_mean_ic": None, "random_p05_ic": None, "random_p95_ic": None}
    return {
        "random_mean_ic": float(np.mean(values)),
        "random_p05_ic": float(np.quantile(values, 0.05)),
        "random_p95_ic": float(np.quantile(values, 0.95)),
    }


def run_walk_forward(panel: pd.DataFrame, args: argparse.Namespace, spec: ExperimentSpec) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    components = component_columns()
    folds = rolling_train_test_years(
        start_year=spec.start_year,
        end_year=spec.end_year,
        min_train_years=spec.min_train_years,
    )
    fold_rows = []
    selection_rows = []
    component_test_rows = []
    scored_tests = []

    for fold in folds:
        test_year = int(fold["test_year"])
        train_years = tuple(int(year) for year in fold["train_years"])
        train = panel.loc[panel["year"].isin(train_years)].copy()
        test = panel.loc[panel["year"].eq(test_year)].copy()
        if train.empty or test.empty:
            continue

        stats = [_component_stat(train, component, args) for component in components]
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

        scored, quorum_stat = _basket_ic(test, selected, "weak_quorum_score")
        scored["weak_quorum_selected_count"] = len(selected)
        scored["weak_quorum_selected_components"] = ",".join(selected)
        scored_tests.append(
            scored[
                [
                    "time",
                    "ticker",
                    "year",
                    S1_TARGET_COL,
                    S1_SCORE_COL,
                    C16_SCORE_COL,
                    "weak_quorum_score",
                    "weak_quorum_selected_count",
                    "weak_quorum_selected_components",
                ]
            ].copy()
        )

        s1_stat = safe_spearman(test, S1_SCORE_COL, S1_TARGET_COL, min_rows=int(args.min_year_rows))
        c16_stat = safe_spearman(test, C16_SCORE_COL, S1_TARGET_COL, min_rows=int(args.min_year_rows))
        component_test_stats = []
        for component in components:
            stat = _component_spearman(test, component, int(args.min_year_rows))
            component_test_rows.append(
                {
                    "test_year": test_year,
                    "component": component,
                    "selected": component in selected,
                    **stat,
                }
            )
            if stat["ic"] is not None:
                component_test_stats.append(float(stat["ic"]))

        random_control = _random_basket_control(
            test,
            low_corr_pool,
            len(selected),
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
                "low_corr_pool_count": int(len(low_corr_pool)),
                "quorum_rows": quorum_stat["rows"],
                "quorum_ic": quorum_stat["ic"],
                "quorum_p_value": quorum_stat["p_value"],
                "s1_ic": s1_stat["ic"],
                "c16_ic": c16_stat["ic"],
                "best_component_ic": max(component_test_stats) if component_test_stats else None,
                **random_control,
            }
        )

    if not scored_tests:
        raise RuntimeError("H395 produced no test folds.")
    return (
        pd.DataFrame(fold_rows),
        pd.DataFrame(selection_rows),
        pd.DataFrame(component_test_rows),
        pd.concat(scored_tests, ignore_index=True),
    )


def _avg_positive(values: pd.Series) -> tuple[float | None, int, int, float | None]:
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return None, 0, 0, None
    positives = int((clean > 0.0).sum())
    return float(clean.mean()), positives, int(len(clean)), float(positives / len(clean))


def summarize_results(
    fold_summary: pd.DataFrame,
    component_test: pd.DataFrame,
    test_scores: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    component_rows = []
    for component, group in component_test.groupby("component", sort=True):
        avg, positives, years, pct = _avg_positive(group["ic"])
        component_rows.append(
            {
                "component": component,
                "avg_ic": avg,
                "positive_years": positives,
                "years": years,
                "pct_positive_years": pct,
                "selected_years": int(group["selected"].sum()),
            }
        )
    component_summary = pd.DataFrame(component_rows).sort_values("avg_ic", ascending=False, na_position="last")

    quorum_avg, quorum_pos, quorum_years, quorum_pct = _avg_positive(fold_summary["quorum_ic"])
    random_avg, _, _, _ = _avg_positive(fold_summary["random_mean_ic"])
    best_component_avg = component_summary["avg_ic"].dropna().max() if not component_summary.empty else None
    s1_avg, _, _, _ = _avg_positive(fold_summary["s1_ic"])
    c16_avg, _, _, _ = _avg_positive(fold_summary["c16_ic"])
    corr_s1 = _safe_corr(test_scores, "weak_quorum_score", S1_SCORE_COL, 500)
    corr_c16 = _safe_corr(test_scores, "weak_quorum_score", C16_SCORE_COL, 500)
    lift_vs_random = (
        float(quorum_avg - random_avg)
        if quorum_avg is not None and random_avg is not None
        else None
    )
    lift_vs_best_component = (
        float(quorum_avg - best_component_avg)
        if quorum_avg is not None and best_component_avg is not None and np.isfinite(best_component_avg)
        else None
    )

    detail = {
        "quorum_avg_ic": quorum_avg,
        "quorum_positive_years": quorum_pos,
        "quorum_years": quorum_years,
        "quorum_pct_positive_years": quorum_pct,
        "random_basket_mean_ic": random_avg,
        "best_component_avg_ic": float(best_component_avg) if best_component_avg is not None and np.isfinite(best_component_avg) else None,
        "s1_avg_ic": s1_avg,
        "c16_avg_ic": c16_avg,
        "corr_s1": corr_s1,
        "corr_c16": corr_c16,
        "lift_vs_random_mean_ic": lift_vs_random,
        "lift_vs_best_component_ic": lift_vs_best_component,
    }
    return component_summary, detail


def choose_decision(detail: dict[str, object]) -> str:
    quorum_avg = detail.get("quorum_avg_ic")
    quorum_pct = detail.get("quorum_pct_positive_years")
    corr_s1 = detail.get("corr_s1")
    corr_c16 = detail.get("corr_c16")
    lift_random = detail.get("lift_vs_random_mean_ic")
    lift_component = detail.get("lift_vs_best_component_ic")

    strong = (
        quorum_avg is not None
        and float(quorum_avg) > 0.05
        and quorum_pct is not None
        and float(quorum_pct) >= 0.60
        and corr_s1 is not None
        and abs(float(corr_s1)) < 0.30
        and corr_c16 is not None
        and abs(float(corr_c16)) < 0.30
        and lift_random is not None
        and float(lift_random) >= 0.005
        and lift_component is not None
        and float(lift_component) >= 0.005
    )
    weak = (
        quorum_avg is not None
        and float(quorum_avg) > 0.01
        and quorum_pct is not None
        and float(quorum_pct) >= 0.60
    )
    if strong:
        return "PASSED"
    if weak:
        return "MIXED"
    return "FAILED"


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_train_years=int(args.min_train_years),
        min_year_rows=int(args.min_year_rows),
    )
    context = build_experiment_context(spec, artifact_subdir=BRANCH_NAME)

    panel = load_panel(args, spec)
    fold_summary, selection, component_test, test_scores = run_walk_forward(panel, args, spec)
    component_summary, detail = summarize_results(fold_summary, component_test, test_scores)
    decision = choose_decision(detail)

    fold_summary_path = write_dataframe_artifact(fold_summary, context, f"{BRANCH_NAME}_fold_summary")
    selection_path = write_dataframe_artifact(selection, context, f"{BRANCH_NAME}_component_selection")
    component_test_path = write_dataframe_artifact(component_test, context, f"{BRANCH_NAME}_component_test_yearly")
    component_summary_path = write_dataframe_artifact(component_summary, context, f"{BRANCH_NAME}_component_summary")
    test_scores_path = write_dataframe_artifact(test_scores, context, f"{BRANCH_NAME}_test_scores")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "decision_detail": detail,
            "panel_rows": int(len(panel)),
            "test_rows": int(len(test_scores)),
            "test_years": sorted(int(year) for year in fold_summary["test_year"].unique()),
            "candidate_components": component_columns(),
            "fold_summary": fold_summary.to_dict(orient="records"),
            "component_summary_top": component_summary.head(12).to_dict(orient="records"),
            "protocol_note": (
                "Components are selected using only prior years, with low "
                "train correlation to S1/C16 and equal weights in the test year."
            ),
        },
        artifacts={
            "fold_summary": fold_summary_path,
            "component_selection": selection_path,
            "component_test_yearly": component_test_path,
            "component_summary": component_summary_path,
            "test_scores": test_scores_path,
        },
        metadata={
            "no_2026_rows": True,
            "min_train_avg_ic": float(args.min_train_avg_ic),
            "min_train_positive_share": float(args.min_train_positive_share),
            "max_parent_corr": float(args.max_parent_corr),
            "random_iterations": int(args.random_iterations),
        },
    )

    pd.set_option("display.max_rows", 80)
    pd.set_option("display.width", 220)
    print("Fold summary:")
    print(fold_summary.to_string(index=False))
    print("\nComponent summary:")
    print(component_summary.head(20).to_string(index=False))
    print(f"\ndecision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
