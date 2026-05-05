from __future__ import annotations

import argparse
import glob
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


BRANCH_NAME = "h398_insider_pre_reaction_clock"
MODE = "research_branch_insider_pre_reaction_clock"

C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
NEWS_DAILY_PATH = data_path("features/news/datasets/news_daily_features.parquet")
INSIDER_GLOB = str(data_path("insider_cache/*.parquet"))
C16_SCORE_COL = "order_volume_ratio_rank"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "S272 insider lead may be strongest before news/order-count reaction "
        "is visible; event-time insider states should improve C16 quality most "
        "on the next trading day and in pre-reaction rows."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=50,
    min_phase_rows=200,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={C16_SCORE_COL: "decision-time C16 order-pressure rank"},
)


@dataclass(frozen=True)
class StateSpec:
    name: str
    mask_col: str
    baseline_col: str
    primary: bool = False


STATE_SPECS = [
    StateSpec("insider_tminus1", "insider_tminus1", "same_ticker_non_event"),
    StateSpec("insider_t0", "insider_t0", "same_ticker_non_event"),
    StateSpec("insider_tplus1", "insider_tplus1", "same_ticker_non_event", primary=True),
    StateSpec("insider_tplus1_pre_reaction", "insider_tplus1_pre_reaction", "insider_tplus1_reacted", primary=True),
    StateSpec("insider_tplus1_reacted", "insider_tplus1_reacted", "insider_tplus1_pre_reaction"),
    StateSpec("insider_tplus1_c16_support", "insider_tplus1_c16_support", "insider_tplus1_no_c16_support"),
    StateSpec("insider_tplus1_order_count_high", "insider_tplus1_order_count_high", "insider_tplus1_order_count_not_high"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H398: insider event-time pre-reaction clock audit.")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--order-stats-path", type=str, default=str(ORDER_STATS_PATH))
    parser.add_argument("--news-path", type=str, default=str(NEWS_DAILY_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    return parser.parse_args()


def _ticker(value: object) -> str:
    return str(value).strip().upper()


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
        raise ValueError(f"H398 blocks 2026+; got end_year={end_year}")
    years = pd.to_datetime(frame[time_col], errors="coerce").dt.year
    return frame.loc[years.between(int(start_year), int(end_year))].copy()


def _load_positive_insider_events() -> pd.DataFrame:
    frames = []
    for path in glob.glob(INSIDER_GLOB):
        try:
            frame = pd.read_parquet(path, columns=["ticker", "published_date", "RealBuyVolume", "RealSellVolume"])
        except Exception:
            continue
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["ticker", "published_date"])
    insider = pd.concat(frames, ignore_index=True)
    insider["ticker"] = insider["ticker"].map(_ticker)
    insider["published_date"] = pd.to_datetime(insider["published_date"], errors="coerce").dt.normalize()
    insider["net_real_buy"] = _safe_numeric(insider, "RealBuyVolume") - _safe_numeric(insider, "RealSellVolume")
    return insider.loc[insider["net_real_buy"] > 0].dropna(subset=["ticker", "published_date"])[
        ["ticker", "published_date"]
    ].drop_duplicates()


def _event_offset_keys(events: pd.DataFrame, trading_dates: np.ndarray, offset: int) -> pd.DataFrame:
    rows = []
    for ticker, published_date in events[["ticker", "published_date"]].itertuples(index=False):
        event_date = np.datetime64(pd.Timestamp(published_date).normalize())
        if offset < 0:
            idx = int(np.searchsorted(trading_dates, event_date, side="left")) + offset
        elif offset == 0:
            idx = int(np.searchsorted(trading_dates, event_date, side="left"))
        else:
            idx = int(np.searchsorted(trading_dates, event_date, side="right")) + offset - 1
        if 0 <= idx < len(trading_dates):
            rows.append({"ticker": ticker, "time": pd.Timestamp(trading_dates[idx]).normalize()})
    if not rows:
        return pd.DataFrame(columns=["ticker", "time"])
    return pd.DataFrame(rows).drop_duplicates()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(args.s1_path, start_year=spec.start_year, end_year=spec.end_year)
    c16 = pd.read_parquet(args.c16_path, columns=["time", "ticker", C16_SCORE_COL, "order_pressure_available"])
    c16 = normalize_time_ticker(c16, source="C16 order-pressure surface")
    c16 = _clip_years(c16, spec.start_year, spec.end_year)
    c16[C16_SCORE_COL] = _safe_numeric(c16, C16_SCORE_COL, np.nan)
    c16["order_pressure_available"] = c16["order_pressure_available"].eq(True)

    order = pd.read_parquet(args.order_stats_path, columns=["date", "ticker", "buy_order_count", "buy_order_volume", "sell_order_volume"])
    order = order.rename(columns={"date": "time"})
    order["time"] = pd.to_datetime(order["time"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].map(_ticker)
    order = _clip_years(order, spec.start_year, spec.end_year)
    order["buy_order_count"] = _safe_numeric(order, "buy_order_count", np.nan)
    order["buy_order_volume"] = _safe_numeric(order, "buy_order_volume", np.nan)
    order["sell_order_volume"] = _safe_numeric(order, "sell_order_volume", np.nan)
    order["buy_count_rank"] = order.groupby("time")["buy_order_count"].rank(pct=True)
    denom = (order["buy_order_volume"] + order["sell_order_volume"]).replace(0, np.nan)
    order["buy_volume_pressure"] = (order["buy_order_volume"] - order["sell_order_volume"]).div(denom)

    news = pd.read_parquet(args.news_path, columns=["date", "ticker", "phobert_article_count_1d"])
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].map(_ticker)
    news = news.drop(columns=["date"]).dropna(subset=["time", "ticker"])
    news = _clip_years(news, spec.start_year, spec.end_year)
    news["news_active"] = _safe_numeric(news, "phobert_article_count_1d") > 0.0

    panel = panel.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(order[["time", "ticker", "buy_count_rank", "buy_volume_pressure"]], on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(news[["time", "ticker", "news_active"]], on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.loc[panel["order_pressure_available"]].copy()
    panel["news_active"] = panel["news_active"].eq(True)
    panel["buy_count_high80"] = _safe_numeric(panel, "buy_count_rank", np.nan) >= 0.80
    panel["buy_volume_pressure_pos"] = _safe_numeric(panel, "buy_volume_pressure", np.nan) > 0.0
    panel["c16_support"] = _safe_numeric(panel, C16_SCORE_COL, np.nan) >= 0.80

    trading_dates = np.array(sorted(panel["time"].dropna().unique()), dtype="datetime64[ns]")
    events = _load_positive_insider_events()
    event_cols = []
    for name, offset in [("insider_tminus1", -1), ("insider_t0", 0), ("insider_tplus1", 1)]:
        keys = _event_offset_keys(events, trading_dates, offset)
        keys[name] = True
        panel = panel.merge(keys, on=["time", "ticker"], how="left", validate="one_to_one")
        panel[name] = panel[name].eq(True)
        event_cols.append(name)

    panel["insider_event_window"] = panel[event_cols].any(axis=1)
    event_ticker_year = panel.loc[panel["insider_event_window"], ["ticker", "time"]].copy()
    event_ticker_year["year"] = event_ticker_year["time"].dt.year.astype(int)
    event_ticker_year = event_ticker_year[["ticker", "year"]].drop_duplicates()
    panel["year"] = panel["time"].dt.year.astype(int)
    panel = panel.merge(
        event_ticker_year.assign(has_insider_event_ticker_year=True),
        on=["ticker", "year"],
        how="left",
        validate="many_to_one",
    )
    panel["same_ticker_non_event"] = panel["has_insider_event_ticker_year"].eq(True) & ~panel["insider_event_window"]
    panel["insider_tplus1_pre_reaction"] = panel["insider_tplus1"] & ~panel["news_active"] & ~panel["buy_count_high80"]
    panel["insider_tplus1_reacted"] = panel["insider_tplus1"] & (panel["news_active"] | panel["buy_count_high80"])
    panel["insider_tplus1_c16_support"] = panel["insider_tplus1"] & panel["c16_support"]
    panel["insider_tplus1_no_c16_support"] = panel["insider_tplus1"] & ~panel["c16_support"]
    panel["insider_tplus1_order_count_high"] = panel["insider_tplus1"] & panel["buy_count_high80"]
    panel["insider_tplus1_order_count_not_high"] = panel["insider_tplus1"] & ~panel["buy_count_high80"]
    return panel.dropna(subset=[C16_SCORE_COL, S1_TARGET_COL])


def _evaluate_mask(panel: pd.DataFrame, mask_col: str, min_year_rows: int) -> tuple[dict[str, object], pd.DataFrame]:
    subset = panel.loc[panel[mask_col].eq(True)].copy()
    pooled = safe_spearman(subset, C16_SCORE_COL, S1_TARGET_COL, min_rows=int(min_year_rows))
    yearly_rows = []
    for year, group in subset.groupby("year", sort=True):
        stat = safe_spearman(group, C16_SCORE_COL, S1_TARGET_COL, min_rows=int(min_year_rows))
        hit = _safe_numeric(group, S1_TARGET_COL, np.nan).dropna()
        yearly_rows.append(
            {
                "year": int(year),
                **stat,
                "hit_rate": float(hit.mean()) if len(hit) >= int(min_year_rows) else None,
            }
        )
    summary = summarize_ic_rows(yearly_rows)
    hit_all = _safe_numeric(subset, S1_TARGET_COL, np.nan).dropna()
    out = {
        "rows": int(pooled["rows"]),
        "dates": int(subset["time"].nunique()) if not subset.empty else 0,
        "tickers": int(subset["ticker"].nunique()) if not subset.empty else 0,
        "pooled_ic": pooled["ic"],
        "pooled_p_value": pooled["p_value"],
        "hit_rate": float(hit_all.mean()) if len(hit_all) else None,
        **summary,
    }
    return out, pd.DataFrame(yearly_rows)


def run_audit(panel: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    result_rows = []
    yearly_frames = []
    cache: dict[str, dict[str, object]] = {}
    for spec in STATE_SPECS:
        for col in [spec.mask_col, spec.baseline_col]:
            if col not in cache:
                summary, yearly = _evaluate_mask(panel, col, int(args.min_year_rows))
                cache[col] = summary
                yearly["mask"] = col
                yearly_frames.append(yearly)
        state = cache[spec.mask_col]
        base = cache[spec.baseline_col]
        result_rows.append(
            {
                "state": spec.name,
                "mask_col": spec.mask_col,
                "baseline_col": spec.baseline_col,
                "primary": spec.primary,
                "rows": state["rows"],
                "dates": state["dates"],
                "tickers": state["tickers"],
                "avg_ic": state["avg_ic"],
                "positive_years": state["positive_years"],
                "years": state["years"],
                "hit_rate": state["hit_rate"],
                "baseline_avg_ic": base["avg_ic"],
                "baseline_hit_rate": base["hit_rate"],
                "lift_vs_baseline_avg_ic": (
                    float(state["avg_ic"] - base["avg_ic"])
                    if state["avg_ic"] is not None and base["avg_ic"] is not None
                    else None
                ),
                "hit_rate_lift": (
                    float(state["hit_rate"] - base["hit_rate"])
                    if state["hit_rate"] is not None and base["hit_rate"] is not None
                    else None
                ),
            }
        )
    return pd.DataFrame(result_rows), pd.concat(yearly_frames, ignore_index=True)


def choose_decision(results: pd.DataFrame) -> tuple[str, dict[str, object]]:
    tplus = results.loc[results["state"].eq("insider_tplus1")]
    pre = results.loc[results["state"].eq("insider_tplus1_pre_reaction")]
    reacted = results.loc[results["state"].eq("insider_tplus1_reacted")]
    tplus_row = tplus.iloc[0].to_dict() if not tplus.empty else {}
    pre_row = pre.iloc[0].to_dict() if not pre.empty else {}
    reacted_row = reacted.iloc[0].to_dict() if not reacted.empty else {}
    tplus_pass = (
        tplus_row.get("avg_ic") is not None
        and float(tplus_row["avg_ic"]) >= 0.10
        and int(tplus_row.get("positive_years", 0)) >= 8
    )
    pre_reaction_pass = (
        pre_row.get("avg_ic") is not None
        and reacted_row.get("avg_ic") is not None
        and float(pre_row["avg_ic"]) >= float(reacted_row["avg_ic"]) + 0.01
        and int(pre_row.get("positive_years", 0)) >= 8
    )
    if tplus_pass and pre_reaction_pass:
        decision = "PASSED"
    elif tplus_pass:
        decision = "MIXED"
    else:
        decision = "FAILED"
    return decision, {
        "insider_tplus1_avg_ic": tplus_row.get("avg_ic"),
        "insider_tplus1_positive_years": tplus_row.get("positive_years"),
        "insider_tplus1_lift_vs_non_event": tplus_row.get("lift_vs_baseline_avg_ic"),
        "pre_reaction_avg_ic": pre_row.get("avg_ic"),
        "reacted_avg_ic": reacted_row.get("avg_ic"),
        "pre_minus_reacted_avg_ic": (
            float(pre_row["avg_ic"] - reacted_row["avg_ic"])
            if pre_row.get("avg_ic") is not None and reacted_row.get("avg_ic") is not None
            else None
        ),
        "tplus_gate": tplus_pass,
        "pre_reaction_gate": pre_reaction_pass,
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
    results, yearly = run_audit(panel, args)
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
                "T+1 mapping follows S272: first trading day strictly after "
                "published_date for calendar trading days, or next available "
                "trading day for non-trading publication dates."
            ),
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"no_2026_rows": True},
    )

    pd.set_option("display.max_rows", 80)
    pd.set_option("display.width", 220)
    print(results.to_string(index=False))
    print(f"\ndecision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
