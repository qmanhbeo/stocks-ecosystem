from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


BRANCH_NAME = "h383_news_flow_disagreement"
MODE = "research_branch_news_flow_disagreement"
OUT_DIR = artifact_path("order_pressure")

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
NEWS_PATH = data_path("features/news/datasets/news_daily_features.parquet")

MIN_YEAR_ROWS = 500
MIN_TRAIN_YEARS = 2
HIGH_FLOW_THRESHOLD = 0.80
WEAK_FLOW_THRESHOLD = 0.40
NEWS_PROB_THRESHOLD = 0.50


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    peer: str | None = None
    baseline: str = "c16_all"
    family: str = "control"


STATE_SPECS = [
    StateSpec("c16_all", "All C16 rows", None, "c16_all", "control"),
    StateSpec("active_news", "Any 1d PhoBERT news", "no_news_5d", "c16_all", "control"),
    StateSpec("no_news_5d", "No 5d PhoBERT news", "active_news", "c16_all", "control"),
    StateSpec("strong_flow", "C16 rank >= 0.80", "weak_flow", "c16_all", "flow_bucket"),
    StateSpec("weak_flow", "C16 rank <= 0.40", "strong_flow", "c16_all", "flow_bucket"),
    StateSpec(
        "bullish_flow_negative_news",
        "Strong C16 with negative PhoBERT sentiment",
        "active_news_strong_flow",
        "strong_flow",
        "disagreement",
    ),
    StateSpec(
        "bullish_flow_no_news",
        "Strong C16 with no 5d PhoBERT news",
        "active_news_strong_flow",
        "strong_flow",
        "disagreement",
    ),
    StateSpec(
        "positive_news_weak_flow",
        "Positive PhoBERT news with weak C16 support",
        "positive_news_strong_flow",
        "weak_flow",
        "disagreement",
    ),
    StateSpec(
        "active_news_strong_flow",
        "Active PhoBERT news with strong C16",
        "bullish_flow_no_news",
        "strong_flow",
        "confirmation",
    ),
    StateSpec(
        "positive_news_strong_flow",
        "Positive PhoBERT news with strong C16",
        "positive_news_weak_flow",
        "strong_flow",
        "confirmation",
    ),
    StateSpec(
        "forward_stock_strong_flow",
        "Forward-looking stock-scope news with strong C16",
        "positive_news_weak_flow",
        "strong_flow",
        "confirmation",
    ),
    StateSpec(
        "official_strong_flow",
        "Official/regulatory-source news with strong C16",
        "bullish_flow_negative_news",
        "strong_flow",
        "confirmation",
    ),
    StateSpec(
        "h364_strong_flow",
        "H364 official earnings/guidance news with strong C16",
        "official_strong_flow",
        "strong_flow",
        "confirmation",
    ),
]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H383: fixed news-flow disagreement test. Buckets C16 order pressure "
            "against local-news sentiment, forward-looking, article-scope, and "
            "source-type states; evaluates 1d relative-return IC with 2016-2025 "
            "data only."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--news-path", type=str, default=str(NEWS_PATH))
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-year-rows", type=int, default=MIN_YEAR_ROWS)
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


def _safe_ic(frame: pd.DataFrame, score_col: str, target_col: str, min_rows: int) -> dict[str, object]:
    clean = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < int(min_rows) or clean[score_col].nunique() < 3 or clean[target_col].nunique() < 2:
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    rho, p_value = spearmanr(clean[score_col], clean[target_col])
    rho_value = float(np.asarray(rho).flat[0])
    p_value_float = float(np.asarray(p_value).flat[0])
    if not np.isfinite(rho_value):
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    return {"rows": int(len(clean)), "ic": rho_value, "p_value": p_value_float}


def _load_future_relative_returns(start_year: int, end_year: int) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    vni_close = load_vni_close().sort_index()
    stock_future = close.shift(-1).div(close).sub(1.0)
    vni_future = vni_close.shift(-1).div(vni_close).sub(1.0).reindex(stock_future.index)
    rel = stock_future.sub(vni_future, axis=0)
    out = to_long(rel, "future_rel_return_1d")
    out["time"] = pd.to_datetime(out["time"], errors="coerce").dt.normalize()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out = out.loc[out["time"].dt.year.between(int(start_year), int(end_year))].copy()
    return out.dropna(subset=["time", "ticker", "future_rel_return_1d"])


def _load_news(path: Path) -> pd.DataFrame:
    news = pd.read_parquet(path, columns=NEWS_COLUMNS).copy()
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    news = news.drop(columns=["date"]).dropna(subset=["time", "ticker"])
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


def _load_panel(args: argparse.Namespace) -> pd.DataFrame:
    if int(args.end_year) >= 2026:
        raise ValueError("H383 must not train or test on 2026+; set --end-year <= 2025")

    s1 = pd.read_parquet(args.s1_path, columns=["time", "ticker", "actual"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()
    s1 = s1.loc[s1["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()

    c16 = pd.read_parquet(
        args.c16_path,
        columns=[
            "time",
            "ticker",
            "order_volume_ratio_rank",
            "order_pressure_available",
            "can_buy_next_open",
        ],
    ).copy()
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()

    news = _load_news(Path(args.news_path))
    rel = _load_future_relative_returns(int(args.start_year), int(args.end_year))

    panel = s1.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(rel, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.loc[panel["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()
    panel = panel.loc[panel["order_pressure_available"].fillna(False).astype(bool)].copy()
    panel["order_volume_ratio_rank"] = _safe_numeric(panel, "order_volume_ratio_rank", np.nan)
    panel["future_rel_return_1d"] = _safe_numeric(panel, "future_rel_return_1d", np.nan)
    panel["actual"] = _safe_numeric(panel, "actual", np.nan)
    panel["can_buy_next_open"] = panel["can_buy_next_open"].fillna(False).astype(bool)
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            panel[column] = _safe_numeric(panel, column)
    panel["h364_official_sentiment_x_earnings_guidance"] = _safe_numeric(
        panel, "h364_official_sentiment_x_earnings_guidance"
    )
    panel = panel.dropna(subset=["order_volume_ratio_rank", "future_rel_return_1d"])
    panel["year"] = panel["time"].dt.year.astype(int)
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    base = pd.Series(True, index=panel.index)
    flow = _safe_numeric(panel, "order_volume_ratio_rank", np.nan)
    strong_flow = flow >= HIGH_FLOW_THRESHOLD
    weak_flow = flow <= WEAK_FLOW_THRESHOLD

    article_1d = _safe_numeric(panel, "phobert_article_count_1d")
    article_5d = _safe_numeric(panel, "phobert_article_count_5d")
    active_news = article_1d > 0.0
    no_news_5d = article_5d <= 0.0

    sentiment_sum = _safe_numeric(panel, "phobert_sentiment_score_sum")
    pos_prob = _safe_numeric(panel, "phobert_prob_pos_mean")
    neg_prob = _safe_numeric(panel, "phobert_prob_neg_mean")
    positive_news = active_news & ((sentiment_sum > 0.0) | (pos_prob > neg_prob))
    negative_news = active_news & ((sentiment_sum < 0.0) | (neg_prob > pos_prob))

    forward_stock = (
        (_safe_numeric(panel, "phobert_forward_looking_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_forward_looking_prob_mean") >= NEWS_PROB_THRESHOLD)
        & (_safe_numeric(panel, "phobert_article_scope_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_article_scope_stock_news_prob_mean") >= NEWS_PROB_THRESHOLD)
    )
    official_news = (
        (_safe_numeric(panel, "phobert_source_type_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_source_type_official_or_regulatory_prob_mean") >= NEWS_PROB_THRESHOLD)
    )
    h364_active = (
        (_safe_numeric(panel, "ollama_guarded_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_forward_looking_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_article_scope_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "phobert_source_type_article_count_1d") > 0.0)
        & (_safe_numeric(panel, "h364_official_sentiment_x_earnings_guidance") > 0.0)
    )

    masks = {
        "c16_all": base,
        "active_news": active_news,
        "no_news_5d": no_news_5d,
        "strong_flow": strong_flow,
        "weak_flow": weak_flow,
        "bullish_flow_negative_news": strong_flow & negative_news,
        "bullish_flow_no_news": strong_flow & no_news_5d,
        "positive_news_weak_flow": positive_news & weak_flow,
        "active_news_strong_flow": active_news & strong_flow,
        "positive_news_strong_flow": positive_news & strong_flow,
        "forward_stock_strong_flow": forward_stock & strong_flow,
        "official_strong_flow": official_news & strong_flow,
        "h364_strong_flow": h364_active & strong_flow,
    }
    if state not in masks:
        raise ValueError(f"Unknown state {state!r}")
    return masks[state].fillna(False).astype(bool)


def _fold_rows(panel: pd.DataFrame, *, min_train_years: int, min_year_rows: int) -> pd.DataFrame:
    years = sorted(int(year) for year in panel["year"].unique())
    rows: list[dict[str, object]] = []
    for test_year in years:
        train_years = [year for year in years if year < int(test_year)]
        if len(train_years) < int(min_train_years):
            continue
        train = panel.loc[panel["year"].isin(train_years)].copy()
        test = panel.loc[panel["year"] == int(test_year)].copy()
        if train.empty or test.empty:
            continue
        for spec in STATE_SPECS:
            train_state = train.loc[_state_mask(train, spec.name)].copy()
            test_state = test.loc[_state_mask(test, spec.name)].copy()
            train_rel = _safe_ic(train_state, "order_volume_ratio_rank", "future_rel_return_1d", int(min_year_rows))
            test_rel = _safe_ic(test_state, "order_volume_ratio_rank", "future_rel_return_1d", int(min_year_rows))
            train_s1 = _safe_ic(train_state, "order_volume_ratio_rank", "actual", int(min_year_rows))
            test_s1 = _safe_ic(test_state, "order_volume_ratio_rank", "actual", int(min_year_rows))
            rows.append(
                {
                    "test_year": int(test_year),
                    "train_start_year": int(min(train_years)),
                    "train_end_year": int(max(train_years)),
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    "peer": spec.peer,
                    "baseline": spec.baseline,
                    "train_rows": int(train_rel["rows"]),
                    "train_rel_ic": train_rel["ic"],
                    "train_rel_p_value": train_rel["p_value"],
                    "train_s1_ic": train_s1["ic"],
                    "train_s1_p_value": train_s1["p_value"],
                    "test_rows": int(test_rel["rows"]),
                    "test_rel_ic": test_rel["ic"],
                    "test_rel_p_value": test_rel["p_value"],
                    "test_s1_ic": test_s1["ic"],
                    "test_s1_p_value": test_s1["p_value"],
                    "test_mean_future_rel_return_1d": (
                        float(test_state["future_rel_return_1d"].mean()) if not test_state.empty else None
                    ),
                    "test_median_future_rel_return_1d": (
                        float(test_state["future_rel_return_1d"].median()) if not test_state.empty else None
                    ),
                }
            )
    return pd.DataFrame(rows)


def _summarize_states(folds: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        state_rows = folds.loc[folds["state"] == spec.name].copy()
        valid = state_rows.dropna(subset=["test_rel_ic"]).copy()
        if valid.empty:
            rel_mean_ic = None
            s1_mean_ic = None
            pos_years = 0
            confirmation_2025 = None
            confirmation_s1 = None
        else:
            rel_mean_ic = float(valid["test_rel_ic"].mean())
            s1_mean_ic = float(valid["test_s1_ic"].dropna().mean()) if valid["test_s1_ic"].notna().any() else None
            pos_years = int((valid["test_rel_ic"] > 0.0).sum())
            conf = valid.loc[valid["test_year"] == 2025, "test_rel_ic"]
            confirmation_2025 = float(conf.iloc[0]) if not conf.empty else None
            conf_s1 = valid.loc[valid["test_year"] == 2025, "test_s1_ic"]
            confirmation_s1 = float(conf_s1.iloc[0]) if not conf_s1.empty and pd.notna(conf_s1.iloc[0]) else None
        rows.append(
            {
                "state": spec.name,
                "label": spec.label,
                "family": spec.family,
                "peer": spec.peer,
                "baseline": spec.baseline,
                "wf_mean_rel_ic": rel_mean_ic,
                "wf_mean_s1_ic": s1_mean_ic,
                "wf_years": int(len(valid)),
                "wf_pos_years": pos_years,
                "wf_pct_pos_years": float(pos_years / len(valid)) if len(valid) else None,
                "confirmation_2025_rel_ic": confirmation_2025,
                "confirmation_2025_s1_ic": confirmation_s1,
                "mean_test_rows": float(valid["test_rows"].mean()) if not valid.empty else 0.0,
                "mean_future_rel_return_1d": (
                    float(valid["test_mean_future_rel_return_1d"].mean()) if not valid.empty else None
                ),
            }
        )
    summary = pd.DataFrame(rows)
    mean_by_state = summary.set_index("state")["wf_mean_rel_ic"].to_dict()
    conf_by_state = summary.set_index("state")["confirmation_2025_rel_ic"].to_dict()
    summary["lift_vs_baseline_rel_ic"] = [
        (row["wf_mean_rel_ic"] - mean_by_state.get(row["baseline"]))
        if row["wf_mean_rel_ic"] is not None and mean_by_state.get(row["baseline"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    summary["lift_vs_peer_rel_ic"] = [
        (row["wf_mean_rel_ic"] - mean_by_state.get(row["peer"]))
        if row["peer"] and row["wf_mean_rel_ic"] is not None and mean_by_state.get(row["peer"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    summary["lift_vs_baseline_2025_rel_ic"] = [
        (row["confirmation_2025_rel_ic"] - conf_by_state.get(row["baseline"]))
        if row["confirmation_2025_rel_ic"] is not None and conf_by_state.get(row["baseline"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    return summary.sort_values(
        by=["wf_mean_rel_ic", "lift_vs_baseline_rel_ic", "mean_test_rows"],
        ascending=[False, False, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, state: str) -> dict[str, object]:
    row = summary.loc[summary["state"] == state]
    if row.empty:
        return {}
    return row.iloc[0].to_dict()


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _candidate_pass(row: dict[str, object], *, require_peer: bool) -> bool:
    peer_lift = _safe_float(row.get("lift_vs_peer_rel_ic"))
    return bool(
        (_safe_float(row.get("wf_mean_rel_ic")) or 0.0) > 0.0
        and (_safe_float(row.get("lift_vs_baseline_rel_ic")) or 0.0) > 0.005
        and (not require_peer or (peer_lift is not None and peer_lift > 0.0))
        and (_safe_float(row.get("wf_pct_pos_years")) or 0.0) >= 0.60
        and (_safe_float(row.get("confirmation_2025_rel_ic")) or 0.0) > 0.0
        and (_safe_float(row.get("mean_test_rows")) or 0.0) >= MIN_YEAR_ROWS
    )


def _verdict(summary: pd.DataFrame) -> tuple[str, str, str, list[str]]:
    primary_states = [
        "bullish_flow_negative_news",
        "bullish_flow_no_news",
        "positive_news_weak_flow",
        "active_news_strong_flow",
    ]
    secondary_states = [
        "positive_news_strong_flow",
        "forward_stock_strong_flow",
        "official_strong_flow",
        "h364_strong_flow",
    ]
    passed_primary = [
        state for state in primary_states if _candidate_pass(_state_record(summary, state), require_peer=False)
    ]
    passed_secondary = [
        state for state in secondary_states if _candidate_pass(_state_record(summary, state), require_peer=False)
    ]
    if passed_primary:
        return (
            "PASSED",
            "offline_evidence",
            "A predeclared news-flow disagreement/confirmation state beat its fixed C16 baseline.",
            passed_primary,
        )
    if passed_secondary:
        return (
            "MIXED",
            "park_or_narrow",
            "Only a secondary stronger-news confirmation state passed; narrow before promotion.",
            passed_secondary,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "No fixed news-flow disagreement state beat the C16 baseline cleanly enough.",
        [],
    )


def main() -> None:
    args = parse_args()
    panel = _load_panel(args)
    if panel.empty:
        raise ValueError("No rows after building H383 panel")
    folds = _fold_rows(
        panel,
        min_train_years=int(args.min_train_years),
        min_year_rows=int(args.min_year_rows),
    )
    if folds.empty:
        raise ValueError("No walk-forward fold rows produced")
    state_summary = _summarize_states(folds)
    verdict, durable_status, branch_decision, passed_states = _verdict(state_summary)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    key_states = {
        state: _state_record(state_summary, state)
        for state in [
            "c16_all",
            "active_news",
            "no_news_5d",
            "strong_flow",
            "bullish_flow_negative_news",
            "bullish_flow_no_news",
            "positive_news_weak_flow",
            "active_news_strong_flow",
            "positive_news_strong_flow",
            "forward_stock_strong_flow",
            "official_strong_flow",
            "h364_strong_flow",
        ]
    }
    summary = {
        "branch": "news_flow_disagreement",
        "experiment_id": "H383",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "passed_states": passed_states,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "score": "order_volume_ratio_rank",
            "primary_target": "future_rel_return_1d_close_to_close_vs_vnindex",
            "secondary_target": "actual",
            "fixed_high_flow_threshold": HIGH_FLOW_THRESHOLD,
            "fixed_weak_flow_threshold": WEAK_FLOW_THRESHOLD,
            "fixed_news_probability_threshold": NEWS_PROB_THRESHOLD,
            "direct_baseline": "c16_all",
            "strong_flow_baseline": "strong_flow",
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "active_news_share": float((_state_mask(panel, "active_news")).mean()),
        "strong_flow_share": float((_state_mask(panel, "strong_flow")).mean()),
        "key_states": key_states,
        "pass_rule": (
            "PASS if one predeclared primary news-flow state has positive WF mean "
            "1d relative-return IC, beats its fixed baseline by >0.005, has >=60% "
            "positive WF years, positive 2025 confirmation IC, and average test "
            "support >= min-year-rows. MIXED if only a secondary stronger-news "
            "confirmation state clears the same gate. Otherwise FAILED."
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
            "s1": Path(args.s1_path),
            "c16": Path(args.c16_path),
            "news": Path(args.news_path),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
        },
    )

    c16_all = _state_record(state_summary, "c16_all")
    active_confirm = _state_record(state_summary, "active_news_strong_flow")
    neg_disagree = _state_record(state_summary, "bullish_flow_negative_news")
    weak_disagree = _state_record(state_summary, "positive_news_weak_flow")
    print("H383 news-flow disagreement")
    print(f"saved_summary={summary_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(
        f"verdict={verdict} | c16_all_rel_ic={_safe_float(c16_all.get('wf_mean_rel_ic')) or 0.0:+.4f} | "
        f"active_news_strong_flow={_safe_float(active_confirm.get('wf_mean_rel_ic')) or 0.0:+.4f} | "
        f"bullish_flow_negative_news={_safe_float(neg_disagree.get('wf_mean_rel_ic')) or 0.0:+.4f} | "
        f"positive_news_weak_flow={_safe_float(weak_disagree.get('wf_mean_rel_ic')) or 0.0:+.4f}"
    )
    print(
        state_summary[
            [
                "state",
                "family",
                "wf_mean_rel_ic",
                "wf_mean_s1_ic",
                "wf_years",
                "wf_pos_years",
                "confirmation_2025_rel_ic",
                "lift_vs_baseline_rel_ic",
                "lift_vs_peer_rel_ic",
                "mean_test_rows",
                "mean_future_rel_return_1d",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
