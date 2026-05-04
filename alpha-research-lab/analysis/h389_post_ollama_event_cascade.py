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
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


BRANCH_NAME = "h389_post_ollama_event_cascade"
MODE = "research_branch_post_ollama_event_cascade"
OUT_DIR = artifact_path("news_flow")

NEWS_PATH = data_path("features/news/datasets/news_daily_features.parquet")

FIRST_EVENT_QUIET_DAYS = 20
REPEAT_EVENT_DAYS = 5
MIN_YEAR_ROWS = 50
MIN_TRAIN_YEARS = 2
PASS_MIN_LIFT_5D = 0.002
KNOWN_EVENT_SHARE_THRESHOLD = 0.50

EVENT_FAMILY_COLUMNS = [
    "ollama_guarded_event_family_earnings_share",
    "ollama_guarded_event_family_dividend_share",
    "ollama_guarded_event_family_guidance_share",
    "ollama_guarded_event_family_capital_raise_or_debt_share",
    "ollama_guarded_event_family_mna_or_asset_share",
    "ollama_guarded_event_family_regulatory_or_legal_share",
    "ollama_guarded_event_family_other_company_event_share",
    "ollama_guarded_event_family_macro_or_sector_share",
]
NEWS_COLUMNS = [
    "date",
    "ticker",
    "ollama_guarded_article_count_1d",
    "ollama_guarded_confidence_mean",
    "ollama_guarded_abstain_share",
    "ollama_guarded_parse_fail_share",
    *EVENT_FAMILY_COLUMNS,
]


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    family: str


STATE_SPECS = [
    StateSpec("no_event_today", "No guarded Ollama known event today", "control"),
    StateSpec("event_any", "Any guarded Ollama known event today", "event"),
    StateSpec("event_first20", "Known event after 20 trading days without prior known event", "first"),
    StateSpec("event_repeat5", "Known event within 5 trading days of prior known event", "repeat"),
    StateSpec("event_same_family_repeat5", "Known event repeats same family within 5 trading days", "repeat"),
    StateSpec("event_family_transition5", "Known event changes family within 5 trading days", "transition"),
    StateSpec("event_earnings_guidance", "Earnings or guidance event today", "family"),
    StateSpec("event_mna_asset", "M&A or asset event today", "family"),
    StateSpec("event_capital_raise", "Capital raise or debt event today", "family"),
    StateSpec("event_regulatory_legal", "Regulatory or legal event today", "family"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H389: post-Ollama event cascade audit. Tests first/repeat/family "
            "transition states from the guarded local Ollama event-family "
            "surface against generic event and old event-v2 benchmark lifts."
        )
    )
    parser.add_argument("--news-path", type=str, default=str(NEWS_PATH))
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-year-rows", type=int, default=MIN_YEAR_ROWS)
    parser.add_argument("--first-event-quiet-days", type=int, default=FIRST_EVENT_QUIET_DAYS)
    parser.add_argument("--repeat-event-days", type=int, default=REPEAT_EVENT_DAYS)
    parser.add_argument("--pass-min-lift-5d", type=float, default=PASS_MIN_LIFT_5D)
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


def _family_name(column: str) -> str:
    return (
        column.replace("ollama_guarded_event_family_", "")
        .replace("_share", "")
    )


def _load_future_relative_returns(start_year: int, end_year: int) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    vni_close = load_vni_close().sort_index().reindex(close.index)
    out: pd.DataFrame | None = None
    for periods, column in [(1, "future_rel_return_1d"), (5, "future_rel_return_5d")]:
        stock_future = close.shift(-periods).div(close).sub(1.0)
        vni_future = vni_close.shift(-periods).div(vni_close).sub(1.0).reindex(stock_future.index)
        rel = stock_future.sub(vni_future, axis=0)
        part = to_long(rel, column)
        part["time"] = pd.to_datetime(part["time"], errors="coerce").dt.normalize()
        part["ticker"] = part["ticker"].astype(str).str.upper()
        part = part.loc[part["time"].dt.year.between(int(start_year), int(end_year))].copy()
        out = part if out is None else out.merge(part, on=["time", "ticker"], how="inner", validate="one_to_one")
    if out is None:
        raise ValueError("No future relative returns built")
    for column in ["future_rel_return_1d", "future_rel_return_5d"]:
        out[column] = (
            pd.to_numeric(out[column], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .astype(float)
        )
    return out.dropna(subset=["time", "ticker", "future_rel_return_1d", "future_rel_return_5d"])


def _load_panel(args: argparse.Namespace) -> pd.DataFrame:
    if int(args.end_year) >= 2026:
        raise ValueError("H389 must not train or test on 2026+; set --end-year <= 2025")

    news = pd.read_parquet(args.news_path, columns=NEWS_COLUMNS).copy()
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    news = news.drop(columns=["date"]).dropna(subset=["time", "ticker"])
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            news[column] = _safe_numeric(news, column)
    news["known_event_share"] = news[EVENT_FAMILY_COLUMNS].sum(axis=1)
    news["event_today"] = (
        (news["ollama_guarded_article_count_1d"] > 0.0)
        & (news["known_event_share"] >= KNOWN_EVENT_SHARE_THRESHOLD)
    )
    family_values = news[EVENT_FAMILY_COLUMNS].to_numpy(dtype=float)
    family_idx = np.nanargmax(np.where(np.isfinite(family_values), family_values, -np.inf), axis=1)
    family_names = np.array([_family_name(column) for column in EVENT_FAMILY_COLUMNS], dtype=object)
    news["dominant_family"] = np.where(news["event_today"], family_names[family_idx], None)

    dates = pd.Series(sorted(news["time"].unique()))
    date_idx = {pd.Timestamp(date): idx for idx, date in enumerate(dates)}
    news["date_idx"] = news["time"].map(date_idx).astype(int)
    news["row_id"] = np.arange(len(news), dtype=int)

    events = news.loc[news["event_today"], ["row_id", "ticker", "date_idx", "dominant_family"]].copy()
    events = events.sort_values(["ticker", "date_idx", "row_id"])
    events["prev_event_date_idx"] = events.groupby("ticker")["date_idx"].shift(1)
    events["prev_event_family"] = events.groupby("ticker")["dominant_family"].shift(1)
    events["trading_days_since_event"] = events["date_idx"] - events["prev_event_date_idx"]
    news = news.merge(
        events[["row_id", "prev_event_date_idx", "prev_event_family", "trading_days_since_event"]],
        on="row_id",
        how="left",
        validate="one_to_one",
    )

    repeat = news["event_today"] & (news["trading_days_since_event"] <= int(args.repeat_event_days))
    news["no_event_today"] = ~news["event_today"]
    news["event_any"] = news["event_today"]
    news["event_first20"] = news["event_today"] & (
        news["trading_days_since_event"].isna()
        | (news["trading_days_since_event"] > int(args.first_event_quiet_days))
    )
    news["event_repeat5"] = repeat
    news["event_same_family_repeat5"] = repeat & (news["dominant_family"] == news["prev_event_family"])
    news["event_family_transition5"] = repeat & (news["dominant_family"] != news["prev_event_family"])
    news["event_earnings_guidance"] = news["event_today"] & (
        (news["ollama_guarded_event_family_earnings_share"] > 0.0)
        | (news["ollama_guarded_event_family_guidance_share"] > 0.0)
    )
    news["event_mna_asset"] = news["event_today"] & (news["ollama_guarded_event_family_mna_or_asset_share"] > 0.0)
    news["event_capital_raise"] = news["event_today"] & (
        news["ollama_guarded_event_family_capital_raise_or_debt_share"] > 0.0
    )
    news["event_regulatory_legal"] = news["event_today"] & (
        news["ollama_guarded_event_family_regulatory_or_legal_share"] > 0.0
    )

    rel = _load_future_relative_returns(int(args.start_year), int(args.end_year))
    panel = news.merge(rel, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.loc[panel["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()
    panel["year"] = panel["time"].dt.year.astype(int)
    return panel.dropna(subset=["future_rel_return_1d", "future_rel_return_5d"])


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    if state not in panel.columns:
        raise ValueError(f"Unknown state {state!r}")
    return panel[state].fillna(False).astype(bool)


def _metric_record(frame: pd.DataFrame) -> dict[str, object]:
    return {
        "rows": int(len(frame)),
        "mean_rel_1d": float(frame["future_rel_return_1d"].mean()) if not frame.empty else None,
        "mean_rel_5d": float(frame["future_rel_return_5d"].mean()) if not frame.empty else None,
        "median_rel_5d": float(frame["future_rel_return_5d"].median()) if not frame.empty else None,
        "mean_article_count_1d": float(frame["ollama_guarded_article_count_1d"].mean()) if not frame.empty else None,
        "mean_confidence": float(frame["ollama_guarded_confidence_mean"].mean()) if not frame.empty else None,
        "mean_days_since_event": (
            float(frame["trading_days_since_event"].mean())
            if not frame.empty and frame["trading_days_since_event"].notna().any()
            else None
        ),
    }


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
            rows.append(
                {
                    "test_year": int(test_year),
                    "train_start_year": int(min(train_years)),
                    "train_end_year": int(max(train_years)),
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    **{f"train_{key}": value for key, value in train_metrics.items()},
                    **{f"test_{key}": value for key, value in test_metrics.items()},
                }
            )
    return pd.DataFrame(rows)


def _summarize_states(folds: pd.DataFrame, *, min_year_rows: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        state_rows = folds.loc[folds["state"] == spec.name].copy()
        valid = state_rows.loc[state_rows["test_rows"] >= int(min_year_rows)].copy()
        if valid.empty:
            rows.append(
                {
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    "wf_years": 0,
                    "mean_rows": 0.0,
                    "mean_rel_1d": None,
                    "mean_rel_5d": None,
                    "median_rel_5d": None,
                    "mean_article_count_1d": None,
                    "mean_confidence": None,
                    "mean_days_since_event": None,
                    "confirmation_2025_rel_5d": None,
                }
            )
            continue
        conf = valid.loc[valid["test_year"] == 2025]
        rows.append(
            {
                "state": spec.name,
                "label": spec.label,
                "family": spec.family,
                "wf_years": int(len(valid)),
                "mean_rows": float(valid["test_rows"].mean()),
                "mean_rel_1d": float(valid["test_mean_rel_1d"].mean()),
                "mean_rel_5d": float(valid["test_mean_rel_5d"].mean()),
                "median_rel_5d": float(valid["test_median_rel_5d"].mean()),
                "mean_article_count_1d": float(valid["test_mean_article_count_1d"].mean()),
                "mean_confidence": float(valid["test_mean_confidence"].mean()),
                "mean_days_since_event": (
                    float(valid["test_mean_days_since_event"].dropna().mean())
                    if valid["test_mean_days_since_event"].notna().any()
                    else None
                ),
                "confirmation_2025_rel_5d": (
                    float(conf.iloc[0]["test_mean_rel_5d"]) if not conf.empty else None
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        by=["mean_rel_5d", "mean_rows"],
        ascending=[False, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, state: str) -> dict[str, object]:
    row = summary.loc[summary["state"] == state]
    return row.iloc[0].to_dict() if not row.empty else {}


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _lift_stats(folds: pd.DataFrame, state: str, control: str, *, min_year_rows: int) -> dict[str, object]:
    left = folds.loc[folds["state"] == state, ["test_year", "test_mean_rel_5d", "test_rows"]]
    right = folds.loc[folds["state"] == control, ["test_year", "test_mean_rel_5d", "test_rows"]]
    merged = left.merge(right, on="test_year", how="inner", suffixes=("_state", "_control"))
    merged = merged.loc[
        (merged["test_rows_state"] >= int(min_year_rows))
        & (merged["test_rows_control"] >= int(min_year_rows))
    ].copy()
    if merged.empty:
        return {
            "state": state,
            "control": control,
            "years": 0,
            "mean_lift_5d": None,
            "pos_lift_5d_years": 0,
            "pct_pos_lift_5d_years": None,
            "confirmation_2025_lift_5d": None,
        }
    merged["lift_5d"] = merged["test_mean_rel_5d_state"] - merged["test_mean_rel_5d_control"]
    conf = merged.loc[merged["test_year"] == 2025]
    return {
        "state": state,
        "control": control,
        "years": int(len(merged)),
        "mean_lift_5d": float(merged["lift_5d"].mean()),
        "pos_lift_5d_years": int((merged["lift_5d"] > 0.0).sum()),
        "pct_pos_lift_5d_years": float((merged["lift_5d"] > 0.0).mean()),
        "confirmation_2025_lift_5d": float(conf.iloc[0]["lift_5d"]) if not conf.empty else None,
    }


def _passes_controls(
    folds: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    state: str,
    controls: list[str],
    min_year_rows: int,
    min_lift_5d: float,
) -> tuple[bool, dict[str, dict[str, object]]]:
    state_row = _state_record(summary, state)
    stats = {
        control: _lift_stats(folds, state, control, min_year_rows=int(min_year_rows))
        for control in controls
    }
    if (
        (_safe_float(state_row.get("mean_rows")) or 0.0) < int(min_year_rows)
        or (_safe_float(state_row.get("mean_rel_5d")) or 0.0) <= 0.0
    ):
        return False, stats
    for control_stats in stats.values():
        years = int(control_stats.get("years") or 0)
        if years == 0:
            return False, stats
        required_years = max(3, int(np.ceil(0.60 * years)))
        if (_safe_float(control_stats.get("mean_lift_5d")) or 0.0) <= float(min_lift_5d):
            return False, stats
        if int(control_stats.get("pos_lift_5d_years") or 0) < required_years:
            return False, stats
        conf = _safe_float(control_stats.get("confirmation_2025_lift_5d"))
        if conf is not None and conf <= 0.0:
            return False, stats
    return True, stats


def _verdict(
    folds: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    min_year_rows: int,
    min_lift_5d: float,
) -> tuple[str, str, str, list[str], dict[str, object]]:
    transition_pass, transition_stats = _passes_controls(
        folds,
        summary,
        state="event_family_transition5",
        controls=["event_any", "event_same_family_repeat5", "no_event_today"],
        min_year_rows=int(min_year_rows),
        min_lift_5d=float(min_lift_5d),
    )
    first_pass, first_stats = _passes_controls(
        folds,
        summary,
        state="event_first20",
        controls=["event_any", "event_repeat5", "no_event_today"],
        min_year_rows=int(min_year_rows),
        min_lift_5d=float(min_lift_5d),
    )
    repeat_pass, repeat_stats = _passes_controls(
        folds,
        summary,
        state="event_repeat5",
        controls=["event_any", "event_first20", "no_event_today"],
        min_year_rows=int(min_year_rows),
        min_lift_5d=float(min_lift_5d),
    )
    diagnostics = {
        "event_family_transition5": transition_stats,
        "event_first20": first_stats,
        "event_repeat5": repeat_stats,
    }
    pass_states: list[str] = []
    if transition_pass:
        pass_states.append("event_family_transition5")
    if first_pass:
        pass_states.append("event_first20")
    if repeat_pass:
        pass_states.append("event_repeat5")
    if pass_states:
        return (
            "PASSED",
            "offline_evidence",
            "A guarded Ollama event cascade state beat generic event and non-event controls.",
            pass_states,
            diagnostics,
        )
    family_candidates = [
        state
        for state in [
            "event_earnings_guidance",
            "event_mna_asset",
            "event_capital_raise",
            "event_regulatory_legal",
        ]
        if (_safe_float(_state_record(summary, state).get("mean_rel_5d")) or 0.0)
        > ((_safe_float(_state_record(summary, "event_any").get("mean_rel_5d")) or 0.0) + float(min_lift_5d))
    ]
    if family_candidates:
        return (
            "MIXED",
            "park_or_narrow",
            "No cascade state cleared, but at least one event-family pocket beat generic event rows.",
            family_candidates,
            diagnostics,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "No guarded Ollama first/repeat/transition event state beat controls cleanly.",
        [],
        diagnostics,
    )


def main() -> None:
    args = parse_args()
    panel = _load_panel(args)
    if panel.empty:
        raise ValueError("No rows after building H389 panel")
    folds = _fold_rows(panel, min_train_years=int(args.min_train_years))
    if folds.empty:
        raise ValueError("No walk-forward folds produced")
    state_summary = _summarize_states(folds, min_year_rows=int(args.min_year_rows))
    verdict, durable_status, branch_decision, pass_states, lift_diagnostics = _verdict(
        folds,
        state_summary,
        min_year_rows=int(args.min_year_rows),
        min_lift_5d=float(args.pass_min_lift_5d),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    key_states = {state: _state_record(state_summary, state) for state in [spec.name for spec in STATE_SPECS]}
    summary = {
        "branch": "post_ollama_event_cascade",
        "experiment_id": "H389",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "pass_states": pass_states,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "first_event_quiet_days": int(args.first_event_quiet_days),
            "repeat_event_days": int(args.repeat_event_days),
            "known_event_share_threshold": KNOWN_EVENT_SHARE_THRESHOLD,
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "primary_target": "future_rel_return_5d",
        },
        "old_event_v2_reference": {
            "H321_best_state": "today_self_accel_high",
            "H321_validation_fwd5_uplift_vs_control": 0.001418696270164649,
            "H321_confirmation_fwd5_uplift_vs_control": 0.0008847554257748187,
            "H361_sparse_clock_verdict": "FAILED",
            "H361_validation_relative_delta": -0.04963134132554359,
            "H361_confirmation_relative_delta": -0.026578422062054297,
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "event_today_share": float(panel["event_today"].mean()),
        "key_states": key_states,
        "lift_diagnostics": lift_diagnostics,
        "pass_rule": (
            "PASS if event_family_transition5, event_first20, or event_repeat5 "
            "has positive mean 5d payoff and beats generic event, relevant "
            "cascade control, and no-event rows by more than pass_min_lift_5d "
            "on average, with at least 60% positive-lift years and positive "
            "2025 lifts. MIXED if only an event-family pocket beats generic "
            "event rows. Otherwise FAILED."
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
            "news": Path(args.news_path),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "first_event_quiet_days": int(args.first_event_quiet_days),
            "repeat_event_days": int(args.repeat_event_days),
            "pass_min_lift_5d": float(args.pass_min_lift_5d),
        },
    )

    print("H389 post-Ollama event cascade")
    print(f"saved_summary={summary_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(f"verdict={verdict} | pass_states={pass_states}")
    print(
        state_summary[
            [
                "state",
                "family",
                "wf_years",
                "mean_rows",
                "mean_rel_1d",
                "mean_rel_5d",
                "median_rel_5d",
                "mean_article_count_1d",
                "mean_days_since_event",
                "confirmation_2025_rel_5d",
            ]
        ].to_string(index=False)
    )
    for state, controls in lift_diagnostics.items():
        print(f"\n{state} lift diagnostics")
        for control, stats in controls.items():
            print(f"  vs {control}: {stats}")


if __name__ == "__main__":
    main()
