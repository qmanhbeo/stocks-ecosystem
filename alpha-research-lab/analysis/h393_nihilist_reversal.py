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


BRANCH_NAME = "h393_nihilist_reversal"
MODE = "research_branch_nihilist_reversal"
OUT_DIR = artifact_path("order_pressure")

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
NEWS_PATH = data_path("features/news/datasets/news_daily_features.parquet")

HIGH_FLOW_THRESHOLD = 0.80
BULLISH_NEWS_PROB_THRESHOLD = 0.55
MIN_TRAIN_YEARS = 2
MIN_YEAR_ROWS = 100
PASS_MIN_LIFT_5D = 0.002

NEWS_COLUMNS = [
    "date",
    "ticker",
    "phobert_article_count_1d",
    "phobert_article_count_5d",
    "phobert_prob_pos_mean",
    "phobert_sentiment_5d",
    "phobert_sentiment_score_sum",
]


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    family: str
    primary: bool = False


STATE_SPECS = [
    StateSpec("all_rows", "All ticker-day rows", "all"),
    StateSpec("high_c16", "High C16 rows", "c16"),
    StateSpec("stock_down", "Stock down on both 1d and 3d trailing returns", "weakness"),
    StateSpec("market_down_high_c16", "High C16 during trailing market weakness", "market_c16"),
    StateSpec("stock_down_high_c16", "High C16 after trailing stock weakness", "stock_c16"),
    StateSpec(
        "stock_market_down_high_c16",
        "High C16 after both stock and market weakness",
        "capitulation",
    ),
    StateSpec("active_news_high_c16", "High C16 with any 5d local news", "news_c16"),
    StateSpec("bullish_news_high_c16", "High C16 with bullish 5d local-news support", "news_c16"),
    StateSpec(
        "weak_or_no_bullish_news_high_c16",
        "High C16 without bullish 5d local-news support",
        "news_c16",
    ),
    StateSpec(
        "stock_market_down_high_c16_bullish_news",
        "Capitulation high-C16 rows with bullish news support",
        "control",
    ),
    StateSpec(
        "nihilist_reversal",
        "Stock and market down, high C16, and weak or absent bullish news",
        "nihilist",
        True,
    ),
    StateSpec(
        "nihilist_no_news",
        "Stock and market down, high C16, and no 5d local news",
        "nihilist",
    ),
    StateSpec(
        "nihilist_weak_active_news",
        "Stock and market down, high C16, active news but no bullish support",
        "nihilist",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H393: nihilist reversal audit. Tests high C16 after stock and "
            "market weakness when local news is weak or not bullish, versus "
            "stock-down, market-down, high-C16, and active-news controls."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
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


def _load_returns(start_year: int, end_year: int) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    vni_close = load_vni_close().sort_index().reindex(close.index)
    parts: list[pd.DataFrame] = []
    for periods, column in [(1, "future_rel_return_1d"), (5, "future_rel_return_5d")]:
        stock_future = close.shift(-periods).div(close).sub(1.0)
        vni_future = vni_close.shift(-periods).div(vni_close).sub(1.0).reindex(stock_future.index)
        rel = stock_future.sub(vni_future, axis=0)
        parts.append(to_long(rel, column))
    parts.append(to_long(close.div(close.shift(1)).sub(1.0), "stock_return_1d"))
    parts.append(to_long(close.div(close.shift(3)).sub(1.0), "stock_return_3d"))

    out = parts[0]
    for part in parts[1:]:
        out = out.merge(part, on=["time", "ticker"], how="inner", validate="one_to_one")
    out["time"] = pd.to_datetime(out["time"], errors="coerce").dt.normalize()
    out["ticker"] = out["ticker"].astype(str).str.upper()

    market = pd.DataFrame(
        {
            "time": pd.to_datetime(vni_close.index, errors="coerce").normalize(),
            "vni_return_1d": vni_close.div(vni_close.shift(1)).sub(1.0).to_numpy(dtype=float),
            "vni_return_3d": vni_close.div(vni_close.shift(3)).sub(1.0).to_numpy(dtype=float),
        }
    ).dropna(subset=["time"])
    out = out.merge(market, on="time", how="left", validate="many_to_one")
    out = out.loc[out["time"].dt.year.between(int(start_year), int(end_year))].copy()
    for column in [
        "future_rel_return_1d",
        "future_rel_return_5d",
        "stock_return_1d",
        "stock_return_3d",
        "vni_return_1d",
        "vni_return_3d",
    ]:
        out[column] = (
            pd.to_numeric(out[column], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .astype(float)
        )
    return out.dropna(
        subset=[
            "time",
            "ticker",
            "future_rel_return_1d",
            "future_rel_return_5d",
            "stock_return_1d",
            "stock_return_3d",
            "vni_return_1d",
            "vni_return_3d",
        ]
    )


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
        raise ValueError("H393 must not train or test on 2026+; set --end-year <= 2025")

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

    news = _load_news(Path(args.news_path))
    returns = _load_returns(int(args.start_year), int(args.end_year))

    panel = s1.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(returns, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.loc[panel["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()

    panel["actual"] = _safe_numeric(panel, "actual", np.nan)
    panel["xs_proba"] = _safe_numeric(panel, "xs_proba", np.nan)
    panel["order_volume_ratio_rank"] = _safe_numeric(panel, "order_volume_ratio_rank", np.nan)
    panel["order_pressure_available"] = panel["order_pressure_available"].astype("boolean").fillna(False).astype(bool)
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            panel[column] = _safe_numeric(panel, column)

    panel["high_c16"] = (
        panel["order_pressure_available"]
        & (panel["order_volume_ratio_rank"] >= HIGH_FLOW_THRESHOLD)
    )
    panel["stock_down"] = (panel["stock_return_1d"] < 0.0) & (panel["stock_return_3d"] < 0.0)
    panel["market_down"] = (panel["vni_return_1d"] < 0.0) & (panel["vni_return_3d"] < 0.0)
    panel["active_news_5d"] = panel["phobert_article_count_5d"] > 0.0
    panel["bullish_news_5d"] = panel["active_news_5d"] & (
        (panel["phobert_prob_pos_mean"] >= BULLISH_NEWS_PROB_THRESHOLD)
        | (panel["phobert_sentiment_5d"] > 0.0)
        | (panel["phobert_sentiment_score_sum"] > 0.0)
    )
    panel["weak_or_no_bullish_news"] = ~panel["bullish_news_5d"]
    panel["no_news_5d"] = panel["phobert_article_count_5d"] <= 0.0
    panel["weak_active_news"] = panel["active_news_5d"] & panel["weak_or_no_bullish_news"]
    panel["year"] = panel["time"].dt.year.astype(int)
    return panel.dropna(
        subset=[
            "order_volume_ratio_rank",
            "future_rel_return_1d",
            "future_rel_return_5d",
            "stock_return_1d",
            "stock_return_3d",
            "vni_return_1d",
            "vni_return_3d",
        ]
    ).sort_values(["time", "ticker"]).reset_index(drop=True)


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    high_c16 = panel["high_c16"].fillna(False).astype(bool)
    stock_down = panel["stock_down"].fillna(False).astype(bool)
    market_down = panel["market_down"].fillna(False).astype(bool)
    active_news = panel["active_news_5d"].fillna(False).astype(bool)
    bullish = panel["bullish_news_5d"].fillna(False).astype(bool)
    weak = panel["weak_or_no_bullish_news"].fillna(False).astype(bool)
    no_news = panel["no_news_5d"].fillna(False).astype(bool)
    weak_active = panel["weak_active_news"].fillna(False).astype(bool)
    capitulation = high_c16 & stock_down & market_down
    masks = {
        "all_rows": pd.Series(True, index=panel.index),
        "high_c16": high_c16,
        "stock_down": stock_down,
        "market_down_high_c16": high_c16 & market_down,
        "stock_down_high_c16": high_c16 & stock_down,
        "stock_market_down_high_c16": capitulation,
        "active_news_high_c16": high_c16 & active_news,
        "bullish_news_high_c16": high_c16 & bullish,
        "weak_or_no_bullish_news_high_c16": high_c16 & weak,
        "stock_market_down_high_c16_bullish_news": capitulation & bullish,
        "nihilist_reversal": capitulation & weak,
        "nihilist_no_news": capitulation & no_news,
        "nihilist_weak_active_news": capitulation & weak_active,
    }
    if state not in masks:
        raise ValueError(f"Unknown state {state!r}")
    return masks[state]


def _metric_record(frame: pd.DataFrame, *, min_rows: int) -> dict[str, object]:
    c16_1d = _safe_ic(frame, "order_volume_ratio_rank", "future_rel_return_1d", int(min_rows))
    c16_5d = _safe_ic(frame, "order_volume_ratio_rank", "future_rel_return_5d", int(min_rows))
    return {
        "rows": int(len(frame)),
        "mean_rel_1d": float(frame["future_rel_return_1d"].mean()) if not frame.empty else None,
        "mean_rel_5d": float(frame["future_rel_return_5d"].mean()) if not frame.empty else None,
        "median_rel_5d": float(frame["future_rel_return_5d"].median()) if not frame.empty else None,
        "hit_rate_rel_5d": float((frame["future_rel_return_5d"] > 0.0).mean()) if not frame.empty else None,
        "mean_stock_return_3d": float(frame["stock_return_3d"].mean()) if not frame.empty else None,
        "mean_vni_return_3d": float(frame["vni_return_3d"].mean()) if not frame.empty else None,
        "mean_c16_rank": float(frame["order_volume_ratio_rank"].mean()) if not frame.empty else None,
        "active_news_share": float(frame["active_news_5d"].mean()) if not frame.empty else None,
        "bullish_news_share": float(frame["bullish_news_5d"].mean()) if not frame.empty else None,
        "c16_ic_1d": c16_1d["ic"],
        "c16_ic_5d": c16_5d["ic"],
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
                "mean_stock_return_3d": _mean_or_none(valid["test_mean_stock_return_3d"]),
                "mean_vni_return_3d": _mean_or_none(valid["test_mean_vni_return_3d"]),
                "mean_c16_rank": _mean_or_none(valid["test_mean_c16_rank"]),
                "mean_active_news_share": _mean_or_none(valid["test_active_news_share"]),
                "mean_bullish_news_share": _mean_or_none(valid["test_bullish_news_share"]),
                "mean_c16_ic_1d": _mean_or_none(valid["test_c16_ic_1d"]),
                "mean_c16_ic_5d": _mean_or_none(valid["test_c16_ic_5d"]),
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
    left = folds.loc[folds["state"] == state, ["test_year", "test_mean_rel_1d", "test_mean_rel_5d", "test_rows"]]
    right = folds.loc[folds["state"] == control, ["test_year", "test_mean_rel_1d", "test_mean_rel_5d", "test_rows"]]
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
    if years <= 0 or (_safe_scalar(state_row.get("mean_rel_5d")) or 0.0) <= 0.0:
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
    controls = [
        "stock_market_down_high_c16",
        "stock_down_high_c16",
        "market_down_high_c16",
        "high_c16",
        "active_news_high_c16",
        "stock_market_down_high_c16_bullish_news",
    ]
    primary_pass, primary_stats = _passes_controls(
        summary,
        folds,
        state="nihilist_reversal",
        controls=controls,
        min_year_rows=int(min_year_rows),
        pass_min_lift_5d=float(pass_min_lift_5d),
    )
    no_news_stats = {
        control: _lift_stats(folds, "nihilist_no_news", control, min_year_rows=int(min_year_rows))
        for control in controls
    }
    diagnostics = {
        "nihilist_reversal": primary_stats,
        "nihilist_no_news": no_news_stats,
    }
    if primary_pass:
        return (
            "PASSED",
            "offline_evidence",
            "Nihilist reversal beat stock-down, market-down, raw C16, active-news, and bullish-news controls.",
            ["nihilist_reversal"],
            [],
            diagnostics,
        )
    row = _state_record(summary, "nihilist_reversal")
    mixed_states: list[str] = []
    if (_safe_scalar(row.get("mean_rel_5d")) or 0.0) > 0.0:
        mixed_states.append("nihilist_reversal")
    no_news_row = _state_record(summary, "nihilist_no_news")
    if (_safe_scalar(no_news_row.get("mean_rel_5d")) or 0.0) > 0.0:
        mixed_states.append("nihilist_no_news")
    if mixed_states:
        return (
            "MIXED",
            "park_or_narrow",
            "Nihilist reversal was positive but failed one or more required controls.",
            [],
            mixed_states,
            diagnostics,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "Nihilist reversal did not produce positive payoff or clean control lifts.",
        [],
        [],
        diagnostics,
    )


def main() -> None:
    args = parse_args()
    panel = _load_panel(args)
    if panel.empty:
        raise ValueError("No rows after building H393 panel")
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
        "branch": "nihilist_reversal",
        "experiment_id": "H393",
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
            "bullish_news_prob_threshold": BULLISH_NEWS_PROB_THRESHOLD,
            "high_c16_threshold": HIGH_FLOW_THRESHOLD,
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "key_states": key_states,
        "lift_diagnostics": lift_diagnostics,
        "pass_rule": (
            "PASS if nihilist_reversal has positive mean 5d relative payoff "
            "and beats stock_market_down_high_c16, stock_down_high_c16, "
            "market_down_high_c16, raw high_c16, active_news_high_c16, and "
            "bullish-news capitulation controls by more than pass_min_lift_5d "
            "on average, with at least 60% positive-lift years and positive "
            "2025 lifts. MIXED if only positive but control-incomplete. "
            "Otherwise FAILED."
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
            "pass_min_lift_5d": float(args.pass_min_lift_5d),
        },
    )

    display_states = [
        "nihilist_reversal",
        "nihilist_no_news",
        "nihilist_weak_active_news",
        "stock_market_down_high_c16",
        "stock_down_high_c16",
        "market_down_high_c16",
        "high_c16",
        "active_news_high_c16",
        "stock_market_down_high_c16_bullish_news",
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
            "mean_bullish_news_share",
            "confirmation_2025_rel_5d",
        ],
    ].copy()
    print("H393 nihilist reversal")
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
