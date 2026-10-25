"""Shared serialization, fingerprint, and metric helpers for Phase 4D."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_stat(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "device": int(stat.st_dev),
        "inode": int(stat.st_ino),
    }


def _prepared_fingerprint(stock) -> str:
    digest = hashlib.sha256()
    digest.update(stock.ticker.encode("utf-8"))
    arrays = (
        np.asarray(stock.dates.asi8, dtype="<i8"),
        stock.opens,
        stock.closes,
        stock.market_features,
        stock.alpha_features,
        stock.daily_volatility_scale,
        stock.can_buy,
        stock.can_sell,
    )
    for values in arrays:
        array = np.ascontiguousarray(values)
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(np.asarray(array.shape, dtype="<i8").tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, na_rep="")


def _policy_metric_row(
    result: dict[str, Any],
    *,
    policy: str,
    ticker_group: str,
    model_id: str | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    return {
        "policy": policy,
        "ticker": result["ticker"],
        "ticker_group": ticker_group,
        "split": result["split"],
        "model_id": model_id,
        "threshold": threshold,
        "final_portfolio_value": result["final_portfolio_value"],
        "total_calendar_return": result["total_calendar_return"],
        "chronological_portfolio_cagr": result["chronological_portfolio_cagr"],
        "maximum_drawdown": result["maximum_drawdown"],
        "exposure_percentage": result["exposure_percentage"],
        "number_of_trades": result["number_of_trades"],
        "win_rate": result["win_rate"],
        "mean_terminal_rl_reward": result["mean_terminal_rl_reward"],
        "median_terminal_rl_reward": result["median_terminal_rl_reward"],
        "mean_holding_duration": result["mean_holding_duration"],
        "median_holding_duration": result["median_holding_duration"],
        "mean_waiting_duration": result["mean_waiting_duration"],
        "incomplete_open_positions": result["incomplete_open_positions"],
        "incomplete_mark_to_market_value": result["incomplete_mark_to_market_value"],
        "scheduled_entry_slots": result["scheduled_entry_slots"],
        "executed_entry_count": result["executed_entry_count"],
        "skipped_while_open_count": result["skipped_while_open_count"],
        "skipped_unbuyable_or_end_count": result["skipped_unbuyable_or_end_count"],
        "forced_exit_count": result["forced_exit_count"],
        "executed_entry_decision_indices": result["executed_entry_decision_indices"],
    }


def _copy_trade_rows(
    rows: list[dict[str, Any]], *, ticker_group: str, model_id: str | None = None
) -> list[dict[str, Any]]:
    copied = []
    for row in rows:
        item = dict(row)
        item["ticker_group"] = ticker_group
        item["model_id"] = model_id
        copied.append(item)
    return copied


def _year_regime_rows(
    result: dict[str, Any], *, ticker_group: str, model_id: str | None = None
) -> list[dict[str, Any]]:
    from vn_stock_rl.trade_episode.phase4d_policy import summarize_year_regime

    rows = summarize_year_regime(result)
    for row in rows:
        row["ticker_group"] = ticker_group
        row["model_id"] = model_id
    return rows


def _regime_map_for_stocks(regime_frame: pd.DataFrame, stocks: dict[str, Any]):
    index_dates = pd.DatetimeIndex(regime_frame["time"])
    values = regime_frame["regime"].astype(str).to_numpy()
    result: dict[str, str] = {}
    for stock in stocks.values():
        for date in stock.dates:
            position = int(index_dates.searchsorted(pd.Timestamp(date), side="right") - 1)
            label = "unknown" if position < 0 else str(values[position])
            if label == "warmup":
                label = "unknown"
            result[str(pd.Timestamp(date).date())] = label
    return result


def _prediction_rows(examples, models) -> list[dict[str, Any]]:
    from vn_stock_rl.trade_episode.phase4d_supervised import prediction_quality

    rows: list[dict[str, Any]] = []
    predictions: dict[str, np.ndarray] = {}
    for model_id, model in models.items():
        features = (
            np.empty((len(examples.target), 0), dtype=np.float64)
            if model.feature_set == "constant"
            else examples.matrix(model.feature_set)
        )
        predictions[model_id] = model.predict(features)

    grouping_columns = ("ticker_group", "ticker", "year")
    grouping_specs = [("all", examples.metadata.index)]
    for key, group in examples.metadata.groupby(list(grouping_columns), sort=True):
        if not isinstance(key, tuple):
            key = (key,)
        label = dict(zip(grouping_columns, key, strict=False))
        grouping_specs.append((label, group.index))

    constant_prediction = predictions["constant_mean"]
    age_prediction = predictions["age_only_ridge"]
    for label, indexes in grouping_specs:
        indices = np.asarray(list(indexes), dtype=np.int64)
        y = examples.target[indices]
        for model_id, model in models.items():
            score = prediction_quality(y, predictions[model_id][indices])
            if model_id not in {"constant_mean", "age_only_ridge"}:
                score["mae_delta_vs_constant"] = (
                    score["mae"] - prediction_quality(y, constant_prediction[indices])["mae"]
                )
                score["mae_delta_vs_age_only"] = (
                    score["mae"] - prediction_quality(y, age_prediction[indices])["mae"]
                )
            rows.append(
                {
                    "split": examples.metadata.iloc[int(indices[0])]["split"],
                    "model_id": model_id,
                    **(label if isinstance(label, dict) else {}),
                    **score,
                }
            )
    return rows


def _mean(values) -> float | None:
    valid = [float(value) for value in values if value is not None and np.isfinite(value)]
    return None if not valid else float(np.mean(valid))


def _group_random_rows(rows: list[dict[str, Any]], model_id: str, ticker_group: str):
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["model_id"] == model_id and row["ticker_group"] == ticker_group:
            by_ticker.setdefault(row["ticker"], []).append(row)
    ticker_rows = []
    for ticker, group in sorted(by_ticker.items()):
        item = {
            "policy": f"random_mean:{model_id}",
            "ticker": ticker,
            "ticker_group": ticker_group,
            "split": "exploratory",
            "model_id": model_id,
            "random_replicates": len(group),
        }
        for field in (
            "chronological_portfolio_cagr",
            "total_calendar_return",
            "maximum_drawdown",
            "exposure_percentage",
            "number_of_trades",
            "win_rate",
            "mean_terminal_rl_reward",
            "mean_holding_duration",
            "mean_waiting_duration",
            "entry_overlap_percentage",
        ):
            item[field] = _mean(row.get(field) for row in group)
        ticker_rows.append(item)
    return ticker_rows


def _group_mean_policy(rows: list[dict[str, Any]], policy: str, ticker_group: str):
    selected = [
        row
        for row in rows
        if row.get("policy") == policy and row.get("ticker_group") == ticker_group
    ]
    return {
        "policy": policy,
        "ticker_group": ticker_group,
        "ticker_count": len(selected),
        **{
            field: _mean(row.get(field) for row in selected)
            for field in (
                "chronological_portfolio_cagr",
                "total_calendar_return",
                "maximum_drawdown",
                "exposure_percentage",
                "number_of_trades",
                "win_rate",
                "mean_terminal_rl_reward",
                "mean_holding_duration",
                "mean_waiting_duration",
                "entry_overlap_percentage",
            )
        },
    }
