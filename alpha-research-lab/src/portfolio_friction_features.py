from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _pct_rank_by_time(frame: pd.DataFrame, column: str, *, fill_value: float = 0.5) -> pd.Series:
    ranked = pd.to_numeric(frame[column], errors="coerce").groupby(frame["time"], sort=False).rank(
        method="average",
        pct=True,
    )
    return ranked.fillna(float(fill_value)).astype(float)


def _minmax_scale_by_time(frame: pd.DataFrame, column: str, *, fill_value: float = 0.5) -> pd.Series:
    series = pd.to_numeric(frame[column], errors="coerce").astype(float)

    def _scale(group: pd.Series) -> pd.Series:
        finite = group[np.isfinite(group)]
        if finite.empty:
            return pd.Series(np.full(len(group), float(fill_value)), index=group.index, dtype=float)
        lo = float(finite.min())
        hi = float(finite.max())
        if hi <= lo:
            return pd.Series(np.full(len(group), float(fill_value)), index=group.index, dtype=float)
        return ((group - lo) / (hi - lo)).clip(0.0, 1.0)

    return series.groupby(frame["time"], sort=False).transform(_scale).fillna(float(fill_value)).astype(float)


def build_friction_feature_frame(
    scored: pd.DataFrame,
    price_panel: pd.DataFrame,
    tradability: pd.DataFrame,
) -> pd.DataFrame:
    features = price_panel[
        [
            "time",
            "ticker",
            "close",
            "volume",
            "traded_value_vnd",
            "adv20_value",
            "adv5_value",
            "clv",
        ]
    ].copy()
    merged = scored.merge(features, on=["time", "ticker"], how="left", validate="one_to_one")
    merged = merged.merge(
        tradability[
            [
                "time",
                "ticker",
                "can_buy_next_open",
                "can_sell_next_open",
            ]
        ],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    merged["can_buy_next_open"] = merged["can_buy_next_open"].fillna(False).astype(bool)
    merged["can_sell_next_open"] = merged["can_sell_next_open"].fillna(False).astype(bool)
    merged["traded_value_vnd"] = pd.to_numeric(merged["traded_value_vnd"], errors="coerce")
    merged["adv20_value"] = pd.to_numeric(merged["adv20_value"], errors="coerce")
    merged["adv5_value"] = pd.to_numeric(merged["adv5_value"], errors="coerce")
    merged["clv"] = pd.to_numeric(merged["clv"], errors="coerce").fillna(0.5).clip(0.0, 1.0)
    merged["tv_to_adv20"] = merged["traded_value_vnd"] / merged["adv20_value"]
    merged["tv_to_adv5"] = merged["traded_value_vnd"] / merged["adv5_value"]
    merged["xs_adv20_rank"] = _pct_rank_by_time(merged, "adv20_value")
    merged["xs_tv_to_adv20_rank"] = _pct_rank_by_time(merged, "tv_to_adv20")
    merged["xs_tv_to_adv5_rank"] = _pct_rank_by_time(merged, "tv_to_adv5")
    merged["xs_clv_rank"] = _pct_rank_by_time(merged, "clv")
    merged["xs_log_adv_scaled"] = _minmax_scale_by_time(
        merged.assign(log_adv20=np.log1p(np.clip(merged["adv20_value"], 0.0, None))),
        "log_adv20",
    )
    merged["buyable_score"] = merged["can_buy_next_open"].astype(float)
    merged["xs_tradability_rank"] = (
        merged["xs_adv20_rank"] + merged["xs_tv_to_adv20_rank"] + merged["buyable_score"]
    ) / 3.0
    return merged


def add_liquidity_aware_score_variants(
    frame: pd.DataFrame,
    *,
    base_score_column: str,
    prefix: str = "liq",
) -> tuple[pd.DataFrame, list[str]]:
    work = frame.copy()
    base = pd.to_numeric(work[base_score_column], errors="coerce").fillna(0.5).clip(0.0, 1.0)
    work[f"score__{prefix}_base"] = base
    work[f"score__{prefix}_x_adv_rank"] = (base * work["xs_adv20_rank"]).clip(0.0, 1.0)
    work[f"score__{prefix}_x_tradability_rank"] = (base * work["xs_tradability_rank"]).clip(0.0, 1.0)
    work[f"score__{prefix}_blend_70_30"] = (0.7 * base + 0.3 * work["xs_tradability_rank"]).clip(0.0, 1.0)
    work[f"score__{prefix}_blend_50_50"] = (0.5 * base + 0.5 * work["xs_tradability_rank"]).clip(0.0, 1.0)
    work[f"score__{prefix}_log_adv"] = (base * (0.25 + 0.75 * work["xs_log_adv_scaled"])).clip(0.0, 1.0)
    variants = [
        f"{prefix}_base",
        f"{prefix}_x_adv_rank",
        f"{prefix}_x_tradability_rank",
        f"{prefix}_blend_70_30",
        f"{prefix}_blend_50_50",
        f"{prefix}_log_adv",
    ]
    return work, variants


def build_boolean_matrix(
    frame: pd.DataFrame,
    *,
    value_column: str,
    dates: Iterable[pd.Timestamp],
    tickers: Iterable[str],
    fill_value: bool = False,
) -> np.ndarray:
    matrix = (
        frame.assign(_value=frame[value_column].astype(bool))
        .pivot(index="time", columns="ticker", values="_value")
        .reindex(index=pd.to_datetime(list(dates)), columns=list(tickers))
        .sort_index()
    )
    return matrix.where(pd.notna(matrix), fill_value).astype(bool).to_numpy()


def best_variant_rows(results: pd.DataFrame, *, variant_column: str = "score_variant") -> pd.DataFrame:
    if results.empty:
        return results.copy()
    ordered = results.sort_values(
        by=[
            "relative_total_return",
            "portfolio_total_return",
            "information_ratio_annualized",
            "avg_cash_weight",
            "avg_daily_turnover",
        ],
        ascending=[False, False, False, True, True],
        ignore_index=True,
    )
    return ordered.groupby(variant_column, as_index=False, sort=False).head(1).reset_index(drop=True)
