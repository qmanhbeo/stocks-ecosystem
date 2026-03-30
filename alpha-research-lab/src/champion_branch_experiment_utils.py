from __future__ import annotations

import json
from typing import Iterable

import numpy as np
import pandas as pd

from src.activation_alpha import compute_cycle_metrics


def jsonable(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    return value


def slice_execution_year(daily: pd.DataFrame, year: int) -> pd.DataFrame:
    work = daily.copy()
    work["signal_date"] = pd.to_datetime(work["signal_date"])
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    return work.loc[work["execution_date"].dt.year == int(year)].reset_index(drop=True)


def latest_execution_window(daily: pd.DataFrame, execution_days: int) -> pd.DataFrame:
    work = daily.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    keep_dates = set(sorted(work["execution_date"].drop_duplicates())[-max(int(execution_days), 1):])
    return work.loc[work["execution_date"].isin(keep_dates)].reset_index(drop=True)


def summarize_latest_recommendation(
    daily: pd.DataFrame,
    blotter: pd.DataFrame | None = None,
) -> dict[str, object]:
    if daily.empty:
        return {}

    work = daily.copy()
    work["signal_date"] = pd.to_datetime(work["signal_date"])
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    latest = work.sort_values("execution_date").tail(1).iloc[0]

    summary = {
        "signal_date": str(pd.Timestamp(latest["signal_date"]).date()),
        "execution_date": str(pd.Timestamp(latest["execution_date"]).date()),
        "activation_on": bool(latest["activation_on"]) if "activation_on" in latest else None,
        "rebalance_triggered": bool(latest["rebalance_triggered"]) if "rebalance_triggered" in latest else None,
        "requested_tickers": jsonable(latest.get("requested_tickers", [])),
        "held_tickers_after_execution": jsonable(latest.get("held_tickers", [])),
        "cash_weight_after_execution": (
            float(latest["cash_weight"]) if "cash_weight" in latest and pd.notna(latest["cash_weight"]) else None
        ),
        "num_holdings_after_execution": (
            int(latest["num_holdings"]) if "num_holdings" in latest and pd.notna(latest["num_holdings"]) else None
        ),
        "avg_holding_age_after_execution": (
            float(latest["avg_holding_age"])
            if "avg_holding_age" in latest and pd.notna(latest["avg_holding_age"])
            else None
        ),
        "orders": [],
        "positions_after_execution": [],
    }
    if blotter is None or blotter.empty or "execution_date" not in blotter.columns:
        return summary

    detail = blotter.copy()
    detail["execution_date"] = pd.to_datetime(detail["execution_date"])
    detail = detail.loc[detail["execution_date"] == pd.Timestamp(latest["execution_date"])].copy()
    if detail.empty:
        return summary

    cols = [
        "ticker",
        "requested_action",
        "executed_action",
        "current_weight",
        "desired_weight",
        "executed_weight",
        "current_notional_vnd",
        "target_notional_vnd",
        "executed_notional_vnd",
        "buy_blocked",
        "sell_blocked",
        "capacity_clipped",
        "holding_age_before",
        "signal_score",
        "score_rank",
    ]
    existing_cols = [col for col in cols if col in detail.columns]
    detail = detail.sort_values(
        ["executed_weight", "desired_weight", "ticker"],
        ascending=[False, False, True],
    )
    positions = detail.loc[detail["executed_weight"] > 1e-12, existing_cols].copy()
    orders = detail.loc[
        (detail["requested_action"] != "hold") | (detail["executed_action"] != "hold"),
        existing_cols,
    ].copy()

    numeric_cols = [
        "current_weight",
        "desired_weight",
        "executed_weight",
        "current_notional_vnd",
        "target_notional_vnd",
        "executed_notional_vnd",
        "signal_score",
        "score_rank",
    ]
    for frame in (orders, positions):
        if frame.empty:
            continue
        for col in [col for col in numeric_cols if col in frame.columns]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    summary["orders"] = jsonable(orders.to_dict(orient="records"))
    summary["positions_after_execution"] = jsonable(positions.to_dict(orient="records"))
    return summary


def summarize_daily_slice(daily: pd.DataFrame) -> dict[str, object]:
    if daily.empty:
        return {
            "days": 0,
            "portfolio_total_return": None,
            "benchmark_total_return": None,
            "relative_total_return": None,
            "information_ratio_annualized": None,
            "max_drawdown": None,
            "avg_cash_weight": None,
            "avg_num_holdings": None,
            "latest_day": {},
            "cycle_metrics": compute_cycle_metrics(daily),
        }

    portfolio_curve = np.cumprod(1.0 + daily["portfolio_return"].to_numpy(dtype=np.float64))
    benchmark_curve = np.cumprod(1.0 + daily["benchmark_return"].to_numpy(dtype=np.float64))
    relative_curve = np.cumprod(1.0 + daily["relative_return"].to_numpy(dtype=np.float64))
    latest = daily.iloc[-1].to_dict()
    latest["signal_date"] = pd.Timestamp(latest["signal_date"])
    latest["execution_date"] = pd.Timestamp(latest["execution_date"])
    ir = None
    rel_arr = daily["relative_return"].to_numpy(dtype=np.float64)
    if len(rel_arr) > 1 and np.std(rel_arr, ddof=0) > 0:
        ir = float(np.mean(rel_arr) / np.std(rel_arr, ddof=0) * np.sqrt(252.0))
    peaks = np.maximum.accumulate(portfolio_curve)
    drawdown = float(np.min(portfolio_curve / np.clip(peaks, 1e-12, None) - 1.0))
    return {
        "days": int(len(daily)),
        "portfolio_total_return": float(portfolio_curve[-1] - 1.0),
        "benchmark_total_return": float(benchmark_curve[-1] - 1.0),
        "relative_total_return": float(relative_curve[-1] - 1.0),
        "information_ratio_annualized": ir,
        "max_drawdown": drawdown,
        "avg_cash_weight": float(pd.to_numeric(daily["cash_weight"], errors="coerce").mean()),
        "avg_num_holdings": float(pd.to_numeric(daily["num_holdings"], errors="coerce").mean()),
        "latest_day": jsonable(latest),
        "cycle_metrics": compute_cycle_metrics(daily),
    }


def rebalance_monitor_window_days(*, rebalance_every: int, min_trading_days: int = 20, min_cycles: int = 6) -> int:
    return max(int(min_trading_days), int(rebalance_every) * int(min_cycles))


def _normalize_value(value):
    if isinstance(value, np.ndarray):
        return tuple(_normalize_value(item) for item in value.tolist())
    if isinstance(value, list):
        return tuple(_normalize_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _normalize_value(item)) for key, item in value.items()))
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def compare_daily_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    on: Iterable[str],
    columns: Iterable[str],
) -> dict[str, object]:
    keys = list(on)
    compare_cols = list(columns)
    left_work = left.copy()
    right_work = right.copy()
    for key in keys:
        if key in left_work.columns:
            left_work[key] = pd.to_datetime(left_work[key]) if "date" in key else left_work[key]
        if key in right_work.columns:
            right_work[key] = pd.to_datetime(right_work[key]) if "date" in key else right_work[key]
    merged = left_work.merge(
        right_work,
        on=keys,
        how="outer",
        suffixes=("_left", "_right"),
        indicator=True,
    )
    only_left = merged.loc[merged["_merge"] == "left_only", keys].to_dict("records")
    only_right = merged.loc[merged["_merge"] == "right_only", keys].to_dict("records")
    diffs: list[dict[str, object]] = []
    both = merged.loc[merged["_merge"] == "both"].copy()
    for column in compare_cols:
        left_col = f"{column}_left"
        right_col = f"{column}_right"
        if left_col not in both.columns or right_col not in both.columns:
            continue
        mismatched = both.loc[
            both.apply(
                lambda row: _normalize_value(row[left_col]) != _normalize_value(row[right_col]),
                axis=1,
            )
        ]
        if mismatched.empty:
            continue
        for _, row in mismatched.head(20).iterrows():
            entry = {key: jsonable(row[key]) for key in keys}
            entry.update(
                {
                    "column": column,
                    "left": jsonable(row[left_col]),
                    "right": jsonable(row[right_col]),
                }
            )
            diffs.append(entry)
    return {
        "matches": not only_left and not only_right and not diffs,
        "rows_left_only": only_left[:20],
        "rows_right_only": only_right[:20],
        "value_diffs": diffs[:20],
        "left_count": int(len(left_work)),
        "right_count": int(len(right_work)),
    }
