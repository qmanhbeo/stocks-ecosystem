from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

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
    safe_spearman,
    summarize_ic_rows,
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


BRANCH_NAME = "h397_barrier_pop_vs_hold_router"
MODE = "research_branch_barrier_pop_vs_hold_router"

C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
NEWS_DAILY_PATH = data_path("features/news/datasets/news_daily_features.parquet")
C16_SCORE_COL = "order_volume_ratio_rank"
C5_SCORE_COL = "c5_positive_size"
H364_SCORE_COL = "h364_official_sentiment_x_earnings_guidance"
COST_BPS = 15.0

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Some states that failed broad 5-day candidate allocation may still be "
        "valid next-day pop signals, while official attention states should be "
        "judged as delayed hold signals."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        C16_SCORE_COL: "C16 order-pressure rank",
        C5_SCORE_COL: "positive clipped C5 insider size",
        H364_SCORE_COL: "H364 official sentiment x earnings/guidance score",
    },
)

NEWS_COLUMNS = [
    "date",
    "ticker",
    "phobert_article_count_1d",
    "phobert_article_count_5d",
    "phobert_sentiment_score_sum",
    "phobert_prob_pos_mean",
    "phobert_prob_neg_mean",
    "phobert_forward_looking_article_count_1d",
    "phobert_forward_looking_prob_mean",
    "phobert_article_scope_article_count_1d",
    "phobert_article_scope_stock_news_prob_mean",
    "phobert_source_type_article_count_1d",
    "phobert_source_type_official_or_regulatory_prob_mean",
    "ollama_guarded_article_count_1d",
    "ollama_guarded_event_family_earnings_share",
    "ollama_guarded_event_family_guidance_share",
]


@dataclass(frozen=True)
class HorizonSpec:
    name: str
    state_col: str
    control_col: str
    score_col: str | None
    expected_horizon: int
    expected_metric: str
    min_expected_lift: float


STATE_SPECS = [
    HorizonSpec("active_news_strong_flow", "active_news_strong_flow", "strong_flow", C16_SCORE_COL, 1, "ic_lift", 0.02),
    HorizonSpec("positive_news_strong_flow", "positive_news_strong_flow", "strong_flow", C16_SCORE_COL, 1, "ic_lift", 0.02),
    HorizonSpec("h364_positive_ranker", "h364_positive", "h364_active_nonpositive", H364_SCORE_COL, 1, "ic_lift", 0.005),
    HorizonSpec("official_supported_delay", "official_supported", "official_no_support", None, 5, "payoff_lift", 0.005),
    HorizonSpec(
        "official_forward_supported_delay",
        "official_forward_supported",
        "official_forward_no_support",
        None,
        5,
        "payoff_lift",
        0.005,
    ),
    HorizonSpec("insider_buy_pop", "insider_buy", "all_buyable", C5_SCORE_COL, 1, "ic_lift", 0.005),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H397: fixed state horizon-router audit.")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--matrix-path", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--news-path", type=str, default=str(NEWS_DAILY_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--cost-bps", type=float, default=COST_BPS)
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


def _clip_years(frame: pd.DataFrame, start_year: int, end_year: int, time_col: str = "time") -> pd.DataFrame:
    if int(end_year) > MAX_RESEARCH_YEAR:
        raise ValueError(f"H397 blocks 2026+; got end_year={end_year}")
    years = pd.to_datetime(frame[time_col], errors="coerce").dt.year
    return frame.loc[years.between(int(start_year), int(end_year))].copy()


def _future_relative_returns(start_year: int, end_year: int) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    vni_close = load_vni_close().sort_index().reindex(close.index)
    out: pd.DataFrame | None = None
    for horizon in [1, 2, 5]:
        stock_future = close.shift(-horizon).div(close).sub(1.0)
        vni_future = vni_close.shift(-horizon).div(vni_close).sub(1.0).reindex(stock_future.index)
        rel = stock_future.sub(vni_future, axis=0)
        part = to_long(rel, f"future_rel_return_{horizon}d")
        part["time"] = pd.to_datetime(part["time"], errors="coerce").dt.normalize()
        part["ticker"] = part["ticker"].astype(str).str.upper()
        part = _clip_years(part, start_year, end_year)
        out = part if out is None else out.merge(part, on=["time", "ticker"], how="inner", validate="one_to_one")
    if out is None:
        raise RuntimeError("No future relative returns produced")
    return out


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
    news[H364_SCORE_COL] = (
        news["phobert_sentiment_score_sum"]
        * news["phobert_source_type_official_or_regulatory_prob_mean"]
        * earnings_guidance
    )
    return news


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    s1 = load_s1_decision_panel(args.s1_path, start_year=spec.start_year, end_year=spec.end_year)
    c16 = pd.read_parquet(
        args.c16_path,
        columns=["time", "ticker", C16_SCORE_COL, "order_pressure_available", "can_buy_next_open"],
    ).copy()
    c16 = normalize_time_ticker(c16, source="C16 order-pressure surface")
    c16 = _clip_years(c16, spec.start_year, spec.end_year)
    c16[C16_SCORE_COL] = _safe_numeric(c16, C16_SCORE_COL, np.nan)
    c16["order_pressure_available"] = c16["order_pressure_available"].fillna(False).astype(bool)
    c16["can_buy_next_open"] = c16["can_buy_next_open"].fillna(False).astype(bool)

    matrix = pd.read_parquet(
        args.matrix_path,
        columns=["time", "ticker", "c5_ins_relative_size_5d", "c5_signal_present"],
    ).copy()
    matrix = normalize_time_ticker(matrix, source="RL matrix C5")
    matrix = _clip_years(matrix, spec.start_year, spec.end_year)
    matrix[C5_SCORE_COL] = _safe_numeric(matrix, "c5_ins_relative_size_5d", 0.0).clip(lower=0.0)
    matrix["c5_signal_present"] = _safe_numeric(matrix, "c5_signal_present", 0.0)

    news = _load_news(args.news_path, spec.start_year, spec.end_year)
    returns = _future_relative_returns(spec.start_year, spec.end_year)

    panel = s1.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(matrix[["time", "ticker", C5_SCORE_COL, "c5_signal_present"]], on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(returns, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.loc[panel["order_pressure_available"] & panel["can_buy_next_open"]].copy()
    panel["year"] = panel["time"].dt.year.astype(int)

    for column in [*NEWS_COLUMNS, H364_SCORE_COL]:
        if column not in {"date", "ticker"} and column in panel.columns:
            panel[column] = _safe_numeric(panel, column)
    panel[C5_SCORE_COL] = _safe_numeric(panel, C5_SCORE_COL)
    panel["strong_flow"] = panel[C16_SCORE_COL] >= 0.80
    active_news = _safe_numeric(panel, "phobert_article_count_1d") > 0.0
    sentiment = _safe_numeric(panel, "phobert_sentiment_score_sum")
    pos_prob = _safe_numeric(panel, "phobert_prob_pos_mean")
    neg_prob = _safe_numeric(panel, "phobert_prob_neg_mean")
    positive_news = active_news & ((sentiment > 0.0) | (pos_prob > neg_prob))
    official = (
        (_safe_numeric(panel, "phobert_source_type_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_source_type_official_or_regulatory_prob_mean") >= 0.50)
    )
    forward = (
        (_safe_numeric(panel, "phobert_forward_looking_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_forward_looking_prob_mean") >= 0.50)
    )
    support = panel["strong_flow"] | (panel[C5_SCORE_COL] > 0.0)
    h364_active = (
        (_safe_numeric(panel, "ollama_guarded_article_count_1d") > 0.0)
        & (_safe_numeric(panel, H364_SCORE_COL) != 0.0)
    )

    panel["all_buyable"] = True
    panel["active_news_strong_flow"] = active_news & panel["strong_flow"]
    panel["positive_news_strong_flow"] = positive_news & panel["strong_flow"]
    panel["h364_positive"] = h364_active & (_safe_numeric(panel, H364_SCORE_COL) > 0.0)
    panel["h364_active_nonpositive"] = h364_active & (_safe_numeric(panel, H364_SCORE_COL) <= 0.0)
    panel["official_no_support"] = official & ~support
    panel["official_supported"] = official & support
    panel["official_forward_no_support"] = (official | forward) & ~support
    panel["official_forward_supported"] = (official | forward) & support
    panel["insider_buy"] = panel[C5_SCORE_COL] > 0.0
    return panel.dropna(subset=[C16_SCORE_COL, "future_rel_return_1d", "future_rel_return_2d", "future_rel_return_5d"])


def _mean_by_year(frame: pd.DataFrame, value_col: str, min_rows: int) -> tuple[float | None, list[dict[str, object]]]:
    rows = []
    for year, group in frame.groupby("year", sort=True):
        clean = pd.to_numeric(group[value_col], errors="coerce").dropna()
        rows.append({"year": int(year), "rows": int(len(clean)), "mean": float(clean.mean()) if len(clean) >= min_rows else None})
    valid = [row["mean"] for row in rows if row["mean"] is not None]
    return (float(np.mean(valid)) if valid else None), rows


def evaluate(panel: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    result_rows = []
    yearly_rows = []
    cost = float(args.cost_bps) / 10_000.0
    for spec in STATE_SPECS:
        state = panel.loc[panel[spec.state_col].fillna(False).astype(bool)].copy()
        control = panel.loc[panel[spec.control_col].fillna(False).astype(bool)].copy()
        for horizon in [1, 2, 5]:
            target_col = f"future_rel_return_{horizon}d"
            net_col = f"net_rel_return_{horizon}d"
            state[net_col] = state[target_col] - cost
            control[net_col] = control[target_col] - cost
            state_payoff, state_years = _mean_by_year(state, net_col, int(args.min_year_rows))
            control_payoff, control_years = _mean_by_year(control, net_col, int(args.min_year_rows))
            payoff_lift = (
                float(state_payoff - control_payoff)
                if state_payoff is not None and control_payoff is not None
                else None
            )
            lift_years = []
            for left, right in zip(state_years, control_years):
                lift = (
                    float(left["mean"] - right["mean"])
                    if left["mean"] is not None and right["mean"] is not None
                    else None
                )
                lift_years.append({"year": left["year"], "lift": lift})
                yearly_rows.append(
                    {
                        "state": spec.name,
                        "horizon": horizon,
                        "metric": "payoff_lift",
                        "year": left["year"],
                        "state_rows": left["rows"],
                        "control_rows": right["rows"],
                        "value": lift,
                    }
                )
            valid_lifts = [row["lift"] for row in lift_years if row["lift"] is not None]
            payoff_pos = sum(1 for value in valid_lifts if value > 0.0)

            ic_lift = None
            ic_pos = None
            state_ic = None
            control_ic = None
            if spec.score_col is not None:
                state_ic_rows = []
                control_ic_rows = []
                for year, group in state.groupby("year", sort=True):
                    stat = safe_spearman(group, spec.score_col, target_col, min_rows=int(args.min_year_rows))
                    state_ic_rows.append({"year": int(year), **stat})
                for year, group in control.groupby("year", sort=True):
                    stat = safe_spearman(group, spec.score_col, target_col, min_rows=int(args.min_year_rows))
                    control_ic_rows.append({"year": int(year), **stat})
                state_summary = summarize_ic_rows(state_ic_rows)
                control_summary = summarize_ic_rows(control_ic_rows)
                state_ic = state_summary["avg_ic"]
                control_ic = control_summary["avg_ic"]
                ic_lift = (
                    float(state_ic - control_ic)
                    if state_ic is not None and control_ic is not None
                    else None
                )
                ic_valid = []
                for left, right in zip(state_ic_rows, control_ic_rows):
                    lift = (
                        float(left["ic"] - right["ic"])
                        if left["ic"] is not None and right["ic"] is not None
                        else None
                    )
                    ic_valid.append(lift)
                    yearly_rows.append(
                        {
                            "state": spec.name,
                            "horizon": horizon,
                            "metric": "ic_lift",
                            "year": left["year"],
                            "state_rows": left["rows"],
                            "control_rows": right["rows"],
                            "value": lift,
                        }
                    )
                ic_pos = sum(1 for value in ic_valid if value is not None and value > 0.0)

            metric_value = ic_lift if spec.expected_metric == "ic_lift" else payoff_lift
            positive_years = ic_pos if spec.expected_metric == "ic_lift" else payoff_pos
            result_rows.append(
                {
                    "state": spec.name,
                    "state_col": spec.state_col,
                    "control_col": spec.control_col,
                    "horizon": horizon,
                    "expected_horizon": spec.expected_horizon,
                    "expected_metric": spec.expected_metric,
                    "state_rows": int(len(state)),
                    "control_rows": int(len(control)),
                    "state_payoff": state_payoff,
                    "control_payoff": control_payoff,
                    "payoff_lift": payoff_lift,
                    "payoff_positive_years": payoff_pos,
                    "state_ic": state_ic,
                    "control_ic": control_ic,
                    "ic_lift": ic_lift,
                    "ic_positive_years": ic_pos,
                    "metric_value": metric_value,
                    "metric_positive_years": positive_years,
                    "expected_pass": (
                        horizon == spec.expected_horizon
                        and metric_value is not None
                        and metric_value >= spec.min_expected_lift
                        and positive_years is not None
                        and positive_years >= 5
                    ),
                }
            )
    return pd.DataFrame(result_rows), pd.DataFrame(yearly_rows)


def choose_decision(results: pd.DataFrame) -> tuple[str, dict[str, object]]:
    expected = results.loc[results["horizon"].eq(results["expected_horizon"])].copy()
    pass_rows = expected.loc[expected["expected_pass"]]
    state_best = (
        results.sort_values("metric_value", ascending=False, na_position="last")
        .groupby("state", sort=False)
        .head(1)
    )
    aligned = int((state_best["horizon"] == state_best["expected_horizon"]).sum())
    if len(pass_rows) >= 3 and aligned >= 3:
        decision = "PASSED"
    elif len(pass_rows) >= 1:
        decision = "MIXED"
    else:
        decision = "FAILED"
    return decision, {
        "expected_pass_count": int(len(pass_rows)),
        "best_horizon_aligned_count": aligned,
        "expected_passes": pass_rows[
            ["state", "horizon", "expected_metric", "metric_value", "metric_positive_years"]
        ].to_dict(orient="records"),
        "best_by_state": state_best[
            ["state", "horizon", "expected_horizon", "expected_metric", "metric_value", "metric_positive_years"]
        ].to_dict(orient="records"),
    }


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
    )
    context = build_experiment_context(spec, artifact_subdir=BRANCH_NAME)
    panel = load_panel(args, spec)
    results, yearly = evaluate(panel, args)
    decision, detail = choose_decision(results)

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "decision_detail": detail,
            "panel_rows": int(len(panel)),
            "test_years": sorted(int(year) for year in panel["year"].unique()),
            "result_rows": results.to_dict(orient="records"),
            "protocol_note": (
                "Fixed state definitions only; buyable rows only; net relative "
                f"returns subtract {float(args.cost_bps):.1f} bps per row."
            ),
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"no_2026_rows": True, "cost_bps": float(args.cost_bps)},
    )

    pd.set_option("display.max_rows", 120)
    pd.set_option("display.width", 240)
    print(results.to_string(index=False))
    print(f"\ndecision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
