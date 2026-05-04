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


BRANCH_NAME = "h392_source_triangle_sparse"
MODE = "research_branch_source_triangle_sparse"
OUT_DIR = artifact_path("news_flow")

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
NEWS_PATH = data_path("features/news/datasets/news_daily_features.parquet")

HIGH_FLOW_THRESHOLD = 0.80
NEWS_PROB_THRESHOLD = 0.50
MIN_TRAIN_YEARS = 2
MIN_YEAR_ROWS = 10
PASS_MIN_LIFT_5D = 0.002

NEWS_COLUMNS = [
    "date",
    "ticker",
    "phobert_forward_looking_article_count_1d",
    "phobert_forward_looking_prob_mean",
    "phobert_article_scope_article_count_1d",
    "phobert_article_scope_stock_news_prob_mean",
    "phobert_source_type_article_count_1d",
    "phobert_source_type_official_or_regulatory_prob_mean",
]


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    family: str
    primary: bool = False


STATE_SPECS = [
    StateSpec("all_rows", "All ticker-day rows", "all"),
    StateSpec("c16_high", "High C16 rows", "single"),
    StateSpec("insider_buy", "Positive prior C5 insider rows", "single"),
    StateSpec("source_news", "Official/regulatory or stock-scope local-news rows", "single"),
    StateSpec("forward_text", "Forward-looking local-news rows", "single"),
    StateSpec("exactly_one_sensor", "Exactly one of C16, insider, source-news, forward-text", "sensor_count"),
    StateSpec("exactly_two_sensors", "Exactly two source-triangle sensors", "sensor_count"),
    StateSpec("three_plus_sensors", "At least three source-triangle sensors", "sensor_count"),
    StateSpec("c16_insider", "High C16 plus positive insider", "pair"),
    StateSpec("c16_any_news", "High C16 plus source or forward local news", "pair"),
    StateSpec("insider_any_news", "Positive insider plus source or forward local news", "pair"),
    StateSpec("source_forward_news", "Stock/official source news plus forward-looking text", "pair"),
    StateSpec("c16_insider_no_news", "High C16 plus insider without source/forward news", "control"),
    StateSpec("c16_any_news_no_insider", "High C16 plus news without insider", "control"),
    StateSpec("insider_any_news_no_c16", "Insider plus news without high C16", "control"),
    StateSpec(
        "c16_insider_any_news",
        "High C16 plus positive insider plus source or forward local news",
        "triangle",
        True,
    ),
    StateSpec("c16_insider_source", "High C16 plus insider plus source-news", "triangle", True),
    StateSpec("c16_insider_forward", "High C16 plus insider plus forward-looking text", "triangle"),
    StateSpec("c16_source_forward", "High C16 plus source-news plus forward-looking text", "triangle"),
    StateSpec("insider_source_forward", "Insider plus source-news plus forward-looking text", "triangle"),
    StateSpec("all_four_sensors", "High C16 plus insider plus source-news plus forward text", "triangle"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H392: source-triangle sparse audit. Tests whether high C16, "
            "positive insider, and local-news source/type agreement form a "
            "sparse high-conviction state beyond two-way controls."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--matrix-path", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--news-path", type=str, default=str(NEWS_PATH))
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-year-rows", type=int, default=MIN_YEAR_ROWS)
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


def _safe_ic(frame: pd.DataFrame, score_col: str, target_col: str, min_rows: int) -> dict[str, object]:
    clean = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < int(min_rows) or clean[score_col].nunique() < 3 or clean[target_col].nunique() < 3:
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    rho, p_value = spearmanr(clean[score_col], clean[target_col])
    rho_value = float(np.asarray(rho).flat[0])
    if not np.isfinite(rho_value):
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    return {"rows": int(len(clean)), "ic": rho_value, "p_value": float(np.asarray(p_value).flat[0])}


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


def _load_news(path: Path) -> pd.DataFrame:
    news = pd.read_parquet(path, columns=NEWS_COLUMNS).copy()
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    news = news.drop(columns=["date"]).dropna(subset=["time", "ticker"])
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            news[column] = _safe_numeric(news, column)
    return news


def _load_panel(args: argparse.Namespace) -> pd.DataFrame:
    if int(args.end_year) >= 2026:
        raise ValueError("H392 must not train or test on 2026+; set --end-year <= 2025")

    s1 = pd.read_parquet(args.s1_path, columns=["time", "ticker", "actual", "xs_proba"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()
    s1 = s1.loc[s1["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()

    c16 = pd.read_parquet(
        args.c16_path,
        columns=["time", "ticker", "order_volume_ratio_rank", "order_pressure_available"],
    ).copy()
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()

    matrix = pd.read_parquet(
        args.matrix_path,
        columns=["time", "ticker", "c5_ins_relative_size_5d", "c5_signal_present"],
    ).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    matrix["c5_ins_relative_size_5d"] = _safe_numeric(matrix, "c5_ins_relative_size_5d")
    matrix["c5_signal_present"] = _safe_numeric(matrix, "c5_signal_present")

    news = _load_news(Path(args.news_path))
    rel = _load_future_relative_returns(int(args.start_year), int(args.end_year))

    panel = s1.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(matrix, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(rel, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.loc[panel["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()

    panel["order_volume_ratio_rank"] = _safe_numeric(panel, "order_volume_ratio_rank", np.nan)
    panel["order_pressure_available"] = panel["order_pressure_available"].astype("boolean").fillna(False).astype(bool)
    panel["actual"] = _safe_numeric(panel, "actual", np.nan)
    panel["xs_proba"] = _safe_numeric(panel, "xs_proba", np.nan)
    panel["c5_ins_relative_size_5d"] = _safe_numeric(panel, "c5_ins_relative_size_5d")
    panel["c5_signal_present"] = _safe_numeric(panel, "c5_signal_present")
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            panel[column] = _safe_numeric(panel, column)

    source_type = (
        (panel["phobert_source_type_article_count_1d"] > 0.0)
        & (panel["phobert_source_type_official_or_regulatory_prob_mean"] >= NEWS_PROB_THRESHOLD)
    )
    stock_scope = (
        (panel["phobert_article_scope_article_count_1d"] > 0.0)
        & (panel["phobert_article_scope_stock_news_prob_mean"] >= NEWS_PROB_THRESHOLD)
    )
    panel["source_news"] = source_type | stock_scope
    panel["forward_text"] = (
        (panel["phobert_forward_looking_article_count_1d"] > 0.0)
        & (panel["phobert_forward_looking_prob_mean"] >= NEWS_PROB_THRESHOLD)
    )
    panel["c16_high"] = (
        panel["order_pressure_available"]
        & (panel["order_volume_ratio_rank"] >= HIGH_FLOW_THRESHOLD)
    )
    panel["insider_buy"] = (
        (panel["c5_signal_present"] > 0.0)
        & (panel["c5_ins_relative_size_5d"] > 0.0)
    )
    panel["any_news"] = panel["source_news"] | panel["forward_text"]
    panel["sensor_count"] = (
        panel[["c16_high", "insider_buy", "source_news", "forward_text"]]
        .astype(int)
        .sum(axis=1)
    )
    panel["year"] = panel["time"].dt.year.astype(int)
    return panel.dropna(
        subset=[
            "order_volume_ratio_rank",
            "future_rel_return_1d",
            "future_rel_return_5d",
            "actual",
            "xs_proba",
        ]
    ).sort_values(["time", "ticker"]).reset_index(drop=True)


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    c16 = panel["c16_high"].fillna(False).astype(bool)
    insider = panel["insider_buy"].fillna(False).astype(bool)
    source = panel["source_news"].fillna(False).astype(bool)
    forward = panel["forward_text"].fillna(False).astype(bool)
    any_news = source | forward
    count = _safe_numeric(panel, "sensor_count")
    masks = {
        "all_rows": pd.Series(True, index=panel.index),
        "c16_high": c16,
        "insider_buy": insider,
        "source_news": source,
        "forward_text": forward,
        "exactly_one_sensor": count == 1.0,
        "exactly_two_sensors": count == 2.0,
        "three_plus_sensors": count >= 3.0,
        "c16_insider": c16 & insider,
        "c16_any_news": c16 & any_news,
        "insider_any_news": insider & any_news,
        "source_forward_news": source & forward,
        "c16_insider_no_news": c16 & insider & ~any_news,
        "c16_any_news_no_insider": c16 & any_news & ~insider,
        "insider_any_news_no_c16": insider & any_news & ~c16,
        "c16_insider_any_news": c16 & insider & any_news,
        "c16_insider_source": c16 & insider & source,
        "c16_insider_forward": c16 & insider & forward,
        "c16_source_forward": c16 & source & forward,
        "insider_source_forward": insider & source & forward,
        "all_four_sensors": c16 & insider & source & forward,
    }
    if state not in masks:
        raise ValueError(f"Unknown state {state!r}")
    return masks[state]


def _metric_record(frame: pd.DataFrame, *, min_rows: int) -> dict[str, object]:
    c16_1d = _safe_ic(frame, "order_volume_ratio_rank", "future_rel_return_1d", int(min_rows))
    c16_5d = _safe_ic(frame, "order_volume_ratio_rank", "future_rel_return_5d", int(min_rows))
    c5_5d = _safe_ic(frame, "c5_ins_relative_size_5d", "future_rel_return_5d", int(min_rows))
    return {
        "rows": int(len(frame)),
        "mean_rel_1d": float(frame["future_rel_return_1d"].mean()) if not frame.empty else None,
        "mean_rel_5d": float(frame["future_rel_return_5d"].mean()) if not frame.empty else None,
        "median_rel_5d": float(frame["future_rel_return_5d"].median()) if not frame.empty else None,
        "hit_rate_rel_5d": float((frame["future_rel_return_5d"] > 0.0).mean()) if not frame.empty else None,
        "mean_c16_rank": float(frame["order_volume_ratio_rank"].mean()) if not frame.empty else None,
        "mean_c5": float(frame["c5_ins_relative_size_5d"].mean()) if not frame.empty else None,
        "mean_sensor_count": float(frame["sensor_count"].mean()) if not frame.empty else None,
        "c16_share": float(frame["c16_high"].mean()) if not frame.empty else None,
        "insider_share": float(frame["insider_buy"].mean()) if not frame.empty else None,
        "source_share": float(frame["source_news"].mean()) if not frame.empty else None,
        "forward_share": float(frame["forward_text"].mean()) if not frame.empty else None,
        "c16_ic_1d": c16_1d["ic"],
        "c16_ic_5d": c16_5d["ic"],
        "c5_ic_5d": c5_5d["ic"],
    }


def _fold_rows(panel: pd.DataFrame, *, min_train_years: int, min_year_rows: int) -> pd.DataFrame:
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
            train_metrics = _metric_record(train_state, min_rows=int(min_year_rows))
            test_metrics = _metric_record(test_state, min_rows=int(min_year_rows))
            rows.append(
                {
                    "test_year": int(test_year),
                    "train_start_year": int(min(train_years)),
                    "train_end_year": int(max(train_years)),
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    "primary": bool(spec.primary),
                    **{f"train_{key}": value for key, value in train_metrics.items()},
                    **{f"test_{key}": value for key, value in test_metrics.items()},
                }
            )
    return pd.DataFrame(rows)


def _mean_or_none(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return None
    return float(clean.mean())


def _summarize_states(folds: pd.DataFrame, *, min_year_rows: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        state_rows = folds.loc[folds["state"] == spec.name].copy()
        valid = state_rows.loc[state_rows["test_rows"] >= int(min_year_rows)].copy()
        conf = valid.loc[valid["test_year"] == 2025]
        rows.append(
            {
                "state": spec.name,
                "label": spec.label,
                "family": spec.family,
                "primary": bool(spec.primary),
                "wf_years": int(len(valid)),
                "mean_rows": float(valid["test_rows"].mean()) if not valid.empty else 0.0,
                "mean_rel_1d": _mean_or_none(valid["test_mean_rel_1d"]),
                "mean_rel_5d": _mean_or_none(valid["test_mean_rel_5d"]),
                "median_rel_5d": _mean_or_none(valid["test_median_rel_5d"]),
                "mean_hit_rate_rel_5d": _mean_or_none(valid["test_hit_rate_rel_5d"]),
                "mean_c16_rank": _mean_or_none(valid["test_mean_c16_rank"]),
                "mean_c5": _mean_or_none(valid["test_mean_c5"]),
                "mean_sensor_count": _mean_or_none(valid["test_mean_sensor_count"]),
                "mean_c16_share": _mean_or_none(valid["test_c16_share"]),
                "mean_insider_share": _mean_or_none(valid["test_insider_share"]),
                "mean_source_share": _mean_or_none(valid["test_source_share"]),
                "mean_forward_share": _mean_or_none(valid["test_forward_share"]),
                "mean_c16_ic_1d": _mean_or_none(valid["test_c16_ic_1d"]),
                "mean_c16_ic_5d": _mean_or_none(valid["test_c16_ic_5d"]),
                "mean_c5_ic_5d": _mean_or_none(valid["test_c5_ic_5d"]),
                "confirmation_2025_rel_5d": (
                    float(conf.iloc[0]["test_mean_rel_5d"])
                    if not conf.empty and pd.notna(conf.iloc[0]["test_mean_rel_5d"])
                    else None
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        by=["primary", "mean_rel_5d", "mean_rows"],
        ascending=[False, False, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, state: str) -> dict[str, object]:
    row = summary.loc[summary["state"] == state]
    return row.iloc[0].to_dict() if not row.empty else {}


def _safe_scalar(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _lift_stats(folds: pd.DataFrame, state: str, control: str, *, min_year_rows: int) -> dict[str, object]:
    left = folds.loc[
        folds["state"] == state,
        ["test_year", "test_mean_rel_1d", "test_mean_rel_5d", "test_rows"],
    ]
    right = folds.loc[
        folds["state"] == control,
        ["test_year", "test_mean_rel_1d", "test_mean_rel_5d", "test_rows"],
    ]
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
            "mean_lift_1d": None,
            "mean_lift_5d": None,
            "pos_lift_5d_years": 0,
            "pct_pos_lift_5d_years": None,
            "confirmation_2025_lift_5d": None,
        }
    merged["lift_1d"] = merged["test_mean_rel_1d_state"] - merged["test_mean_rel_1d_control"]
    merged["lift_5d"] = merged["test_mean_rel_5d_state"] - merged["test_mean_rel_5d_control"]
    conf = merged.loc[merged["test_year"] == 2025]
    return {
        "state": state,
        "control": control,
        "years": int(len(merged)),
        "mean_lift_1d": float(merged["lift_1d"].mean()),
        "mean_lift_5d": float(merged["lift_5d"].mean()),
        "pos_lift_5d_years": int((merged["lift_5d"] > 0.0).sum()),
        "pct_pos_lift_5d_years": float((merged["lift_5d"] > 0.0).mean()),
        "confirmation_2025_lift_5d": float(conf.iloc[0]["lift_5d"]) if not conf.empty else None,
    }


def _passes_controls(
    summary: pd.DataFrame,
    folds: pd.DataFrame,
    *,
    state: str,
    controls: list[str],
    min_year_rows: int,
    pass_min_lift_5d: float,
) -> tuple[bool, dict[str, dict[str, object]]]:
    state_row = _state_record(summary, state)
    stats = {
        control: _lift_stats(folds, state, control, min_year_rows=int(min_year_rows))
        for control in controls
    }
    years = int(state_row.get("wf_years") or 0)
    if years <= 0 or (_safe_scalar(state_row.get("mean_rows")) or 0.0) < int(min_year_rows):
        return False, stats
    if (_safe_scalar(state_row.get("mean_rel_5d")) or 0.0) <= 0.0:
        return False, stats
    for control_stats in stats.values():
        years = int(control_stats.get("years") or 0)
        required_years = max(3, int(np.ceil(0.60 * years))) if years else 3
        if years == 0:
            return False, stats
        if (_safe_scalar(control_stats.get("mean_lift_5d")) or 0.0) <= float(pass_min_lift_5d):
            return False, stats
        if int(control_stats.get("pos_lift_5d_years") or 0) < required_years:
            return False, stats
        conf = _safe_scalar(control_stats.get("confirmation_2025_lift_5d"))
        if conf is not None and conf <= 0.0:
            return False, stats
    return True, stats


def _verdict(
    summary: pd.DataFrame,
    folds: pd.DataFrame,
    *,
    min_year_rows: int,
    pass_min_lift_5d: float,
) -> tuple[str, str, str, list[str], list[str], dict[str, object]]:
    primary_controls = [
        "c16_insider_no_news",
        "c16_any_news_no_insider",
        "insider_any_news_no_c16",
        "exactly_two_sensors",
    ]
    core_pass, core_stats = _passes_controls(
        summary,
        folds,
        state="c16_insider_any_news",
        controls=primary_controls,
        min_year_rows=int(min_year_rows),
        pass_min_lift_5d=float(pass_min_lift_5d),
    )
    source_pass, source_stats = _passes_controls(
        summary,
        folds,
        state="c16_insider_source",
        controls=primary_controls,
        min_year_rows=int(min_year_rows),
        pass_min_lift_5d=float(pass_min_lift_5d),
    )
    diagnostics = {
        "c16_insider_any_news": core_stats,
        "c16_insider_source": source_stats,
        "three_plus_sensors": {
            "exactly_two_sensors": _lift_stats(
                folds,
                "three_plus_sensors",
                "exactly_two_sensors",
                min_year_rows=int(min_year_rows),
            )
        },
    }
    pass_states: list[str] = []
    if core_pass:
        pass_states.append("c16_insider_any_news")
    if source_pass:
        pass_states.append("c16_insider_source")
    if pass_states:
        return (
            "PASSED",
            "offline_evidence",
            "A C16-plus-insider-plus-local-news triangle state beat pair and two-sensor controls.",
            pass_states,
            [],
            diagnostics,
        )

    mixed_states: list[str] = []
    three_row = _state_record(summary, "three_plus_sensors")
    three_lift = diagnostics["three_plus_sensors"]["exactly_two_sensors"]
    if (
        (_safe_scalar(three_row.get("mean_rel_5d")) or 0.0) > 0.0
        and (_safe_scalar(three_lift.get("mean_lift_5d")) or 0.0) > 0.0
    ):
        mixed_states.append("three_plus_sensors")
    for state in ["c16_source_forward", "insider_source_forward"]:
        row = _state_record(summary, state)
        if (_safe_scalar(row.get("mean_rel_5d")) or 0.0) > 0.0:
            mixed_states.append(state)
    if mixed_states:
        return (
            "MIXED",
            "park_or_narrow",
            "A broader three-sensor or news-triangle pocket was positive, but the required C16-plus-insider core did not clear controls.",
            [],
            mixed_states,
            diagnostics,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "No source-triangle state with the required C16-plus-insider core beat pair and two-sensor controls cleanly.",
        [],
        [],
        diagnostics,
    )


def main() -> None:
    args = parse_args()
    panel = _load_panel(args)
    if panel.empty:
        raise ValueError("No rows after building H392 panel")
    folds = _fold_rows(
        panel,
        min_train_years=int(args.min_train_years),
        min_year_rows=int(args.min_year_rows),
    )
    if folds.empty:
        raise ValueError("No walk-forward folds produced")
    state_summary = _summarize_states(folds, min_year_rows=int(args.min_year_rows))
    verdict, durable_status, branch_decision, pass_states, mixed_states, lift_diagnostics = _verdict(
        state_summary,
        folds,
        min_year_rows=int(args.min_year_rows),
        pass_min_lift_5d=float(args.pass_min_lift_5d),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    key_states = {spec.name: _state_record(state_summary, spec.name) for spec in STATE_SPECS}
    summary = {
        "branch": "source_triangle_sparse",
        "experiment_id": "H392",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "pass_states": pass_states,
        "mixed_states": mixed_states,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "pass_min_lift_5d": float(args.pass_min_lift_5d),
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "primary_target": "future_rel_return_5d",
            "ic_targets": ["future_rel_return_1d", "future_rel_return_5d"],
            "primary_states": [spec.name for spec in STATE_SPECS if spec.primary],
            "primary_controls": [
                "c16_insider_no_news",
                "c16_any_news_no_insider",
                "insider_any_news_no_c16",
                "exactly_two_sensors",
            ],
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "sensor_shares": {
            "c16_high": float(panel["c16_high"].mean()),
            "insider_buy": float(panel["insider_buy"].mean()),
            "source_news": float(panel["source_news"].mean()),
            "forward_text": float(panel["forward_text"].mean()),
            "two_plus": float((panel["sensor_count"] >= 2).mean()),
            "three_plus": float((panel["sensor_count"] >= 3).mean()),
        },
        "key_states": key_states,
        "lift_diagnostics": lift_diagnostics,
        "pass_rule": (
            "PASS if c16_insider_any_news or c16_insider_source has positive "
            "mean 5d relative payoff and beats c16_insider_no_news, "
            "c16_any_news_no_insider, insider_any_news_no_c16, and "
            "exactly_two_sensors by more than pass_min_lift_5d on average, "
            "with at least 60% positive-lift years and positive 2025 lifts. "
            "MIXED if only a broader three-sensor or news-triangle pocket is "
            "positive. Otherwise FAILED."
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
            "matrix": Path(args.matrix_path),
            "news": Path(args.news_path),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "pass_min_lift_5d": float(args.pass_min_lift_5d),
        },
    )

    display_states = [
        "c16_insider_any_news",
        "c16_insider_source",
        "three_plus_sensors",
        "c16_source_forward",
        "insider_source_forward",
        "exactly_two_sensors",
        "c16_insider_no_news",
        "c16_any_news_no_insider",
        "insider_any_news_no_c16",
    ]
    display = state_summary.loc[
        state_summary["state"].isin(display_states),
        [
            "state",
            "wf_years",
            "mean_rows",
            "mean_rel_1d",
            "mean_rel_5d",
            "mean_hit_rate_rel_5d",
            "mean_c16_ic_1d",
            "mean_c16_ic_5d",
            "confirmation_2025_rel_5d",
        ],
    ].copy()
    print("H392 source triangle sparse")
    print(f"saved_summary={summary_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(f"verdict={verdict} | pass_states={pass_states} | mixed_states={mixed_states}")
    print(display.to_string(index=False))
    for state, controls in lift_diagnostics.items():
        print(f"\n{state} lift diagnostics")
        for control, stats in controls.items():
            print(f"  vs {control}: {stats}")


if __name__ == "__main__":
    main()
