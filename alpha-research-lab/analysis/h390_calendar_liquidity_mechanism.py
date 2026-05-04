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


BRANCH_NAME = "h390_calendar_liquidity_mechanism"
MODE = "research_branch_calendar_liquidity_mechanism"
OUT_DIR = artifact_path("timing_data")

C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
CANDIDATE_PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")

START_YEAR = 2016
END_YEAR = 2025
MIN_TRAIN_YEARS = 2
MIN_DAILY_ROWS = 50
PASS_MIN_RESIDUAL_LIFT_1D_IC = 0.010
PASS_MIN_RESIDUAL_LIFT_5D_IC = 0.000
MIXED_MIN_RAW_LIFT_1D_IC = 0.010

CONTROL_COLUMNS = [
    "candidate_count",
    "candidate_pool_size",
    "buyable_breadth_all",
    "liq_open_breadth_all",
    "full_top10_buyable_count",
    "full_top10_liq_open_count",
    "news_surge_5d",
    "xs_breadth_up_1d",
    "xs_breadth_up_5d_y",
    "xs_breadth_down_1d",
    "xs_dispersion_z20_y",
    "vni_ret_5d",
    "vni_ret_20d",
    "vni_realized_vol_20d",
    "vni_drawdown_60d",
    "mean_tv_to_adv20",
    "median_tv_to_adv20",
    "mean_traded_value_vnd",
    "c16_row_count",
    "c16_buyable_share",
    "c16_mean_abs_order_volume_ratio",
    "down_market_5d",
]


@dataclass(frozen=True)
class CalendarSpec:
    name: str
    label: str
    family: str
    primary: bool = True


CALENDAR_SPECS = [
    CalendarSpec(
        "monday_jan_combo",
        "Monday inside the first 10 calendar days of January",
        "january",
    ),
    CalendarSpec(
        "quarter_start",
        "First five calendar days of quarter-start months",
        "quarter",
    ),
    CalendarSpec(
        "late_quarter_month",
        "Last five calendar days of quarter-end months",
        "quarter",
    ),
    CalendarSpec("january_monday", "Any Monday in January", "diagnostic", False),
    CalendarSpec("monday", "Any Monday", "diagnostic", False),
    CalendarSpec("january_first_10", "First 10 calendar days of January", "diagnostic", False),
]

TARGET_COLUMNS = [
    "future_rel_return_1d",
    "future_rel_return_5d",
    "actual",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H390: calendar-as-liquidity-mechanism audit. Retests the old "
            "calendar C16 edges as daily IC uplifts after walk-forward "
            "residualization on liquidity, breadth, news, buyability, and "
            "trailing down-market controls. Excludes 2026+."
        )
    )
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--s1-path", type=str, default=str(S1_PATH))
    parser.add_argument("--candidate-panel", type=str, default=str(CANDIDATE_PANEL_PATH))
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-daily-rows", type=int, default=MIN_DAILY_ROWS)
    parser.add_argument("--pass-min-residual-lift-1d-ic", type=float, default=PASS_MIN_RESIDUAL_LIFT_1D_IC)
    parser.add_argument("--pass-min-residual-lift-5d-ic", type=float, default=PASS_MIN_RESIDUAL_LIFT_5D_IC)
    parser.add_argument("--mixed-min-raw-lift-1d-ic", type=float, default=MIXED_MIN_RAW_LIFT_1D_IC)
    return parser.parse_args()


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _safe_bool(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    return frame[column].fillna(default).astype(bool)


def _spearman_ic(frame: pd.DataFrame, score_col: str, target_col: str, min_rows: int) -> float | None:
    clean = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < int(min_rows):
        return None
    if clean[score_col].nunique() < 3 or clean[target_col].nunique() < 2:
        return None
    score_rank = clean[score_col].rank(method="average", pct=True)
    target_rank = clean[target_col].rank(method="average", pct=True)
    value = score_rank.corr(target_rank)
    return None if pd.isna(value) or not np.isfinite(float(value)) else float(value)


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


def _candidate_daily_controls(path: Path, start_year: int, end_year: int) -> pd.DataFrame:
    raw_columns = pd.read_parquet(path, columns=None).columns
    requested = [
        "time",
        "candidate_count",
        "candidate_pool_size",
        "buyable_breadth_all",
        "liq_open_breadth_all",
        "full_top10_buyable_count",
        "full_top10_liq_open_count",
        "news_surge_5d",
        "xs_breadth_up_1d",
        "xs_breadth_up_5d_y",
        "xs_breadth_down_1d",
        "xs_dispersion_z20_y",
        "vni_ret_5d",
        "vni_ret_20d",
        "vni_realized_vol_20d",
        "vni_drawdown_60d",
        "tv_to_adv20",
        "traded_value_vnd",
    ]
    columns = [column for column in requested if column in raw_columns]
    panel = pd.read_parquet(path, columns=columns).copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel = panel.loc[panel["time"].dt.year.between(int(start_year), int(end_year))].copy()
    for column in columns:
        if column != "time":
            panel[column] = _safe_numeric(panel, column)

    aggregations: dict[str, str | list[str]] = {}
    for column in columns:
        if column == "time":
            continue
        if column in {"tv_to_adv20", "traded_value_vnd"}:
            aggregations[column] = ["mean", "median"] if column == "tv_to_adv20" else ["mean"]
        else:
            aggregations[column] = "median"
    daily = panel.groupby("time", as_index=False).agg(aggregations)
    daily.columns = [
        column if isinstance(column, str) else "_".join(part for part in column if part)
        for column in daily.columns
    ]
    rename = {
        "candidate_count_median": "candidate_count",
        "candidate_pool_size_median": "candidate_pool_size",
        "buyable_breadth_all_median": "buyable_breadth_all",
        "liq_open_breadth_all_median": "liq_open_breadth_all",
        "full_top10_buyable_count_median": "full_top10_buyable_count",
        "full_top10_liq_open_count_median": "full_top10_liq_open_count",
        "news_surge_5d_median": "news_surge_5d",
        "xs_breadth_up_1d_median": "xs_breadth_up_1d",
        "xs_breadth_up_5d_y_median": "xs_breadth_up_5d_y",
        "xs_breadth_down_1d_median": "xs_breadth_down_1d",
        "xs_dispersion_z20_y_median": "xs_dispersion_z20_y",
        "vni_ret_5d_median": "vni_ret_5d",
        "vni_ret_20d_median": "vni_ret_20d",
        "vni_realized_vol_20d_median": "vni_realized_vol_20d",
        "vni_drawdown_60d_median": "vni_drawdown_60d",
        "tv_to_adv20_mean": "mean_tv_to_adv20",
        "tv_to_adv20_median": "median_tv_to_adv20",
        "traded_value_vnd_mean": "mean_traded_value_vnd",
    }
    daily = daily.rename(columns=rename)
    daily["down_market_5d"] = (_safe_numeric(daily, "vni_ret_5d", 0.0) < 0.0).astype(float)
    return daily


def _load_ticker_panel(args: argparse.Namespace) -> pd.DataFrame:
    if int(args.end_year) >= 2026:
        raise ValueError("H390 must not train or test on 2026+; set --end-year <= 2025")

    c16 = pd.read_parquet(
        args.c16_path,
        columns=[
            "time",
            "ticker",
            "order_volume_ratio",
            "order_volume_ratio_rank",
            "order_pressure_available",
            "can_buy_next_open",
        ],
    ).copy()
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()
    c16 = c16.loc[c16["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()
    c16 = c16.loc[_safe_bool(c16, "order_pressure_available")].copy()
    c16["order_volume_ratio"] = _safe_numeric(c16, "order_volume_ratio")
    c16["order_volume_ratio_rank"] = _safe_numeric(c16, "order_volume_ratio_rank")
    c16["can_buy_next_open"] = _safe_bool(c16, "can_buy_next_open")

    s1 = pd.read_parquet(args.s1_path, columns=["time", "ticker", "actual"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()
    s1 = s1.loc[s1["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()
    s1["actual"] = _safe_numeric(s1, "actual")

    rel = _load_future_relative_returns(int(args.start_year), int(args.end_year))
    panel = c16.merge(s1, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(rel, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.dropna(
        subset=[
            "time",
            "ticker",
            "order_volume_ratio_rank",
            "future_rel_return_1d",
            "future_rel_return_5d",
            "actual",
        ]
    )
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _daily_c16_diagnostics(panel: pd.DataFrame, *, min_daily_rows: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for time, frame in panel.groupby("time", sort=True):
        row: dict[str, object] = {
            "time": pd.Timestamp(time).normalize(),
            "target_rows": int(len(frame)),
            "c16_row_count": int(len(frame)),
            "c16_buyable_share": float(frame["can_buy_next_open"].mean()),
            "c16_mean_abs_order_volume_ratio": float(frame["order_volume_ratio"].abs().mean()),
        }
        for target in TARGET_COLUMNS:
            row[f"daily_ic_{target}"] = _spearman_ic(
                frame,
                "order_volume_ratio_rank",
                target,
                min_rows=int(min_daily_rows),
            )
        rows.append(row)
    daily = pd.DataFrame(rows)
    daily["year"] = daily["time"].dt.year.astype(int)
    return daily


def _add_calendar_states(daily: pd.DataFrame) -> pd.DataFrame:
    out = daily.copy()
    time = pd.to_datetime(out["time"], errors="coerce")
    out["weekday"] = time.dt.weekday
    out["month"] = time.dt.month
    out["day"] = time.dt.day
    out["days_in_month"] = time.dt.days_in_month
    out["monday_jan_combo"] = (out["month"] == 1) & (out["day"] <= 10) & (out["weekday"] == 0)
    out["quarter_start"] = out["month"].isin([1, 4, 7, 10]) & (out["day"] <= 5)
    out["late_quarter_month"] = out["month"].isin([3, 6, 9, 12]) & ((out["days_in_month"] - out["day"]) <= 5)
    out["january_monday"] = (out["month"] == 1) & (out["weekday"] == 0)
    out["monday"] = out["weekday"] == 0
    out["january_first_10"] = (out["month"] == 1) & (out["day"] <= 10)
    return out


def _build_daily_frame(args: argparse.Namespace) -> pd.DataFrame:
    ticker_panel = _load_ticker_panel(args)
    daily = _daily_c16_diagnostics(ticker_panel, min_daily_rows=int(args.min_daily_rows))
    controls = _candidate_daily_controls(Path(args.candidate_panel), int(args.start_year), int(args.end_year))
    daily = daily.merge(controls, on="time", how="inner", validate="one_to_one")
    daily = _add_calendar_states(daily)
    for column in CONTROL_COLUMNS:
        if column not in daily.columns:
            daily[column] = np.nan
        daily[column] = _safe_numeric(daily, column)
    for target in TARGET_COLUMNS:
        daily[f"daily_ic_{target}"] = _safe_numeric(daily, f"daily_ic_{target}")
    return daily.sort_values("time").reset_index(drop=True)


def _standardized_design(train: pd.DataFrame, test: pd.DataFrame, columns: list[str]) -> tuple[np.ndarray, np.ndarray]:
    train_values = train[columns].replace([np.inf, -np.inf], np.nan).copy()
    medians = train_values.median(numeric_only=True).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    train_values = train_values.fillna(medians)
    test_values = test[columns].replace([np.inf, -np.inf], np.nan).fillna(medians)
    means = train_values.mean(axis=0)
    stds = train_values.std(axis=0, ddof=0).replace(0.0, 1.0).fillna(1.0)
    x_train = ((train_values - means) / stds).to_numpy(dtype=float)
    x_test = ((test_values - means) / stds).to_numpy(dtype=float)
    x_train = np.column_stack([np.ones(len(x_train), dtype=float), x_train])
    x_test = np.column_stack([np.ones(len(x_test), dtype=float), x_test])
    return x_train, x_test


def _residualize_folds(
    daily: pd.DataFrame,
    *,
    target_ic_col: str,
    min_train_years: int,
) -> pd.DataFrame:
    years = sorted(int(year) for year in daily["year"].unique())
    pieces: list[pd.DataFrame] = []
    for test_year in years:
        train_years = [year for year in years if year < int(test_year)]
        if len(train_years) < int(min_train_years):
            continue
        train = daily.loc[daily["year"].isin(train_years)].copy()
        test = daily.loc[daily["year"] == int(test_year)].copy()
        train = train.dropna(subset=[target_ic_col])
        test = test.dropna(subset=[target_ic_col])
        if len(train) <= len(CONTROL_COLUMNS) + 2 or test.empty:
            continue
        x_train, x_test = _standardized_design(train, test, CONTROL_COLUMNS)
        y_train = train[target_ic_col].to_numpy(dtype=float)
        beta = np.linalg.lstsq(x_train, y_train, rcond=None)[0]
        pred = x_test @ beta
        out = test.copy()
        out["test_year"] = int(test_year)
        out["train_start_year"] = int(min(train_years))
        out["train_end_year"] = int(max(train_years))
        out["target"] = target_ic_col.replace("daily_ic_", "")
        out["predicted_ic"] = pred.astype(float)
        out["residual_ic"] = out[target_ic_col].astype(float) - out["predicted_ic"].astype(float)
        out = out.rename(columns={target_ic_col: "daily_ic"})
        pieces.append(out)
    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, ignore_index=True)


def _mean_or_none(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return None
    return float(clean.mean())


def _summarize_state_years(residuals: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for target, target_frame in residuals.groupby("target", sort=True):
        for spec in CALENDAR_SPECS:
            for test_year, year_frame in target_frame.groupby("test_year", sort=True):
                state = year_frame.loc[year_frame[spec.name].fillna(False).astype(bool)].copy()
                other = year_frame.loc[~year_frame[spec.name].fillna(False).astype(bool)].copy()
                rows.append(
                    {
                        "target": str(target),
                        "state": spec.name,
                        "label": spec.label,
                        "family": spec.family,
                        "primary": bool(spec.primary),
                        "test_year": int(test_year),
                        "train_start_year": int(year_frame["train_start_year"].iloc[0]),
                        "train_end_year": int(year_frame["train_end_year"].iloc[0]),
                        "state_dates": int(len(state)),
                        "control_dates": int(len(other)),
                        "state_mean_daily_ic": _mean_or_none(state["daily_ic"]),
                        "control_mean_daily_ic": _mean_or_none(other["daily_ic"]),
                        "raw_ic_lift": (
                            _mean_or_none(state["daily_ic"]) - _mean_or_none(other["daily_ic"])
                            if _mean_or_none(state["daily_ic"]) is not None
                            and _mean_or_none(other["daily_ic"]) is not None
                            else None
                        ),
                        "state_mean_residual_ic": _mean_or_none(state["residual_ic"]),
                        "control_mean_residual_ic": _mean_or_none(other["residual_ic"]),
                        "residual_ic_lift": (
                            _mean_or_none(state["residual_ic"]) - _mean_or_none(other["residual_ic"])
                            if _mean_or_none(state["residual_ic"]) is not None
                            and _mean_or_none(other["residual_ic"]) is not None
                            else None
                        ),
                        "state_mean_predicted_ic": _mean_or_none(state["predicted_ic"]),
                        "control_mean_predicted_ic": _mean_or_none(other["predicted_ic"]),
                    }
                )
    return pd.DataFrame(rows)


def _summarize_states(folds: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for target, target_frame in folds.groupby("target", sort=True):
        for spec in CALENDAR_SPECS:
            frame = target_frame.loc[target_frame["state"] == spec.name].copy()
            valid = frame.loc[frame["state_dates"] > 0].copy()
            conf = valid.loc[valid["test_year"] == 2025]
            rows.append(
                {
                    "target": str(target),
                    "state": spec.name,
                    "label": spec.label,
                    "family": spec.family,
                    "primary": bool(spec.primary),
                    "wf_years": int(len(valid)),
                    "mean_state_dates": float(valid["state_dates"].mean()) if not valid.empty else 0.0,
                    "mean_control_dates": float(valid["control_dates"].mean()) if not valid.empty else 0.0,
                    "mean_state_daily_ic": _mean_or_none(valid["state_mean_daily_ic"]),
                    "mean_control_daily_ic": _mean_or_none(valid["control_mean_daily_ic"]),
                    "mean_raw_ic_lift": _mean_or_none(valid["raw_ic_lift"]),
                    "pos_raw_lift_years": int((_safe_numeric(valid, "raw_ic_lift", np.nan) > 0.0).sum()),
                    "mean_state_residual_ic": _mean_or_none(valid["state_mean_residual_ic"]),
                    "mean_control_residual_ic": _mean_or_none(valid["control_mean_residual_ic"]),
                    "mean_residual_ic_lift": _mean_or_none(valid["residual_ic_lift"]),
                    "pos_residual_lift_years": int((_safe_numeric(valid, "residual_ic_lift", np.nan) > 0.0).sum()),
                    "confirmation_2025_raw_ic_lift": (
                        float(conf.iloc[0]["raw_ic_lift"])
                        if not conf.empty and pd.notna(conf.iloc[0]["raw_ic_lift"])
                        else None
                    ),
                    "confirmation_2025_residual_ic_lift": (
                        float(conf.iloc[0]["residual_ic_lift"])
                        if not conf.empty and pd.notna(conf.iloc[0]["residual_ic_lift"])
                        else None
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(
        by=["target", "primary", "mean_residual_ic_lift", "mean_raw_ic_lift"],
        ascending=[True, False, False, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, target: str, state: str) -> dict[str, object]:
    rows = summary.loc[(summary["target"] == target) & (summary["state"] == state)]
    return rows.iloc[0].to_dict() if not rows.empty else {}


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _passes_primary(
    summary: pd.DataFrame,
    *,
    state: str,
    min_residual_lift_1d: float,
    min_residual_lift_5d: float,
) -> bool:
    one_day = _state_record(summary, "future_rel_return_1d", state)
    five_day = _state_record(summary, "future_rel_return_5d", state)
    years = int(one_day.get("wf_years") or 0)
    required_pos_years = max(2, int(np.ceil(0.60 * years)))
    if years <= 0:
        return False
    if (_safe_float(one_day.get("mean_residual_ic_lift")) or 0.0) <= float(min_residual_lift_1d):
        return False
    if int(one_day.get("pos_residual_lift_years") or 0) < required_pos_years:
        return False
    conf_2025 = _safe_float(one_day.get("confirmation_2025_residual_ic_lift"))
    if conf_2025 is not None and conf_2025 <= 0.0:
        return False
    if (_safe_float(five_day.get("mean_residual_ic_lift")) or 0.0) <= float(min_residual_lift_5d):
        return False
    return True


def _mixed_primary(summary: pd.DataFrame, *, state: str, min_raw_lift_1d: float) -> bool:
    row = _state_record(summary, "future_rel_return_1d", state)
    return (
        int(row.get("wf_years") or 0) > 0
        and (_safe_float(row.get("mean_raw_ic_lift")) or 0.0) > float(min_raw_lift_1d)
        and (_safe_float(row.get("mean_residual_ic_lift")) or 0.0) > 0.0
    )


def _verdict(
    summary: pd.DataFrame,
    *,
    min_residual_lift_1d: float,
    min_residual_lift_5d: float,
    min_raw_lift_1d: float,
) -> tuple[str, str, str, list[str], list[str]]:
    primary_states = [spec.name for spec in CALENDAR_SPECS if spec.primary]
    pass_states = [
        state
        for state in primary_states
        if _passes_primary(
            summary,
            state=state,
            min_residual_lift_1d=float(min_residual_lift_1d),
            min_residual_lift_5d=float(min_residual_lift_5d),
        )
    ]
    if pass_states:
        return (
            "PASSED",
            "offline_evidence",
            "At least one old calendar edge retained residual C16 IC uplift after liquidity, breadth, news, buyability, and down-market controls.",
            pass_states,
            [],
        )
    mixed_states = [
        state
        for state in primary_states
        if _mixed_primary(summary, state=state, min_raw_lift_1d=float(min_raw_lift_1d))
    ]
    if mixed_states:
        return (
            "MIXED",
            "park_or_reframe",
            "Calendar dates still show some raw C16 IC lift, but the residual effect is too small or unstable for independent promotion.",
            [],
            mixed_states,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "Old calendar edges did not retain a clean residual C16 IC lift after mechanism controls.",
        [],
        [],
    )


def main() -> None:
    args = parse_args()
    daily = _build_daily_frame(args)
    if daily.empty:
        raise ValueError("No daily rows after building H390 panel")

    residual_frames = []
    for target in TARGET_COLUMNS:
        frame = _residualize_folds(
            daily,
            target_ic_col=f"daily_ic_{target}",
            min_train_years=int(args.min_train_years),
        )
        if not frame.empty:
            residual_frames.append(frame)
    if not residual_frames:
        raise ValueError("No residualized walk-forward folds produced")
    residuals = pd.concat(residual_frames, ignore_index=True)
    folds = _summarize_state_years(residuals)
    state_summary = _summarize_states(folds)
    verdict, durable_status, branch_decision, pass_states, mixed_states = _verdict(
        state_summary,
        min_residual_lift_1d=float(args.pass_min_residual_lift_1d_ic),
        min_residual_lift_5d=float(args.pass_min_residual_lift_5d_ic),
        min_raw_lift_1d=float(args.mixed_min_raw_lift_1d_ic),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_daily.parquet"
    residuals_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_residuals.parquet"
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    daily.to_parquet(daily_path, index=False)
    residuals.to_parquet(residuals_path, index=False)
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    key_states = {
        target: {
            spec.name: _state_record(state_summary, target, spec.name)
            for spec in CALENDAR_SPECS
        }
        for target in TARGET_COLUMNS
    }
    summary = {
        "branch": "calendar_as_liquidity_mechanism",
        "experiment_id": "H390",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "pass_states": pass_states,
        "mixed_states": mixed_states,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_daily_rows": int(args.min_daily_rows),
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "primary_target": "daily C16 IC vs future_rel_return_1d",
            "payoff_check_target": "daily C16 IC vs future_rel_return_5d",
            "s1_reference_target": "daily C16 IC vs actual",
            "control_columns": CONTROL_COLUMNS,
            "primary_states": [spec.name for spec in CALENDAR_SPECS if spec.primary],
        },
        "prior_calendar_references": {
            "monday_jan_combo_old_ic": 0.1109,
            "quarter_start_old_ic": 0.098,
            "late_month_references": {
                "march_late_old_ic": 0.0833,
                "sept_late_old_ic": 0.0791,
                "yearend_20_plus_old_ic": 0.0652,
            },
        },
        "daily_rows": int(len(daily)),
        "daily_date_range": {
            "min": str(daily["time"].min().date()),
            "max": str(daily["time"].max().date()),
        },
        "key_states": key_states,
        "pass_rule": (
            "PASS if monday_jan_combo, quarter_start, or late_quarter_month "
            "retains future_rel_return_1d residual daily-C16-IC lift above "
            "pass_min_residual_lift_1d_ic, has at least 60% positive residual "
            "lift years and non-negative 2025 confirmation, and also has "
            "positive 5d residual lift. MIXED if only raw 1d IC lift remains. "
            "Otherwise FAILED."
        ),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode=MODE,
        name=BRANCH_NAME,
        summary=summary,
        artifacts={
            "daily": daily_path,
            "residuals": residuals_path,
            "folds": folds_path,
            "states": states_path,
            "c16": Path(args.c16_path),
            "s1": Path(args.s1_path),
            "candidate_panel": Path(args.candidate_panel),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_daily_rows": int(args.min_daily_rows),
            "pass_min_residual_lift_1d_ic": float(args.pass_min_residual_lift_1d_ic),
            "pass_min_residual_lift_5d_ic": float(args.pass_min_residual_lift_5d_ic),
            "mixed_min_raw_lift_1d_ic": float(args.mixed_min_raw_lift_1d_ic),
        },
    )

    display = state_summary.loc[
        state_summary["state"].isin([spec.name for spec in CALENDAR_SPECS if spec.primary]),
        [
            "target",
            "state",
            "wf_years",
            "mean_state_dates",
            "mean_state_daily_ic",
            "mean_raw_ic_lift",
            "pos_raw_lift_years",
            "mean_residual_ic_lift",
            "pos_residual_lift_years",
            "confirmation_2025_residual_ic_lift",
        ],
    ].copy()
    print("H390 calendar liquidity mechanism")
    print(f"saved_summary={summary_path}")
    print(f"daily={daily_path}")
    print(f"residuals={residuals_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(f"verdict={verdict} | pass_states={pass_states} | mixed_states={mixed_states}")
    print(display.to_string(index=False))


if __name__ == "__main__":
    main()
