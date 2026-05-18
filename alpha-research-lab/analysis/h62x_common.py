from __future__ import annotations

from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import S1_DEFAULT_PATH, load_s1_decision_panel  # noqa: E402
from src.repo_paths import data_path  # noqa: E402


def _compute_amihud(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["daily_return"] = out.groupby("ticker")["close"].pct_change(fill_method=None)
    out["daily_return_abs"] = out["daily_return"].abs()
    out["turnover_bil"] = (out["close"] * out["volume"]) / 1e9
    out["amihud"] = out["daily_return_abs"] / (out["turnover_bil"] + 1e-9)
    out["amihud_20d_avg"] = out.groupby("ticker")["amihud"].transform(
        lambda s: s.rolling(window=20, min_periods=10).mean()
    )
    return out


def _parse_price_change(value: object) -> float:
    if pd.isna(value):
        return np.nan
    match = re.search(r"\(\s*([+-]?[\d,]+)\s*%\)", str(value))
    if not match:
        return np.nan
    return float(match.group(1).replace(",", "."))


def _load_ohlcv(end_year: int) -> pd.DataFrame:
    stock_dir = data_path("stock")
    ohlcv_parts: list[pd.DataFrame] = []
    for parquet_path in Path(stock_dir).glob("gia_lich_su_*_1D.parquet"):
        try:
            one = pd.read_parquet(parquet_path)
            ticker = parquet_path.stem.replace("gia_lich_su_", "").replace("_1D", "")
            one["ticker"] = ticker
            ohlcv_parts.append(one)
        except Exception:
            continue
    if not ohlcv_parts:
        raise RuntimeError("No OHLCV files available under data/stock")
    ohlcv = pd.concat(ohlcv_parts, ignore_index=True)
    ohlcv = ohlcv.rename(columns={"date": "time"})
    ohlcv["time"] = pd.to_datetime(ohlcv["time"])
    ohlcv = ohlcv[ohlcv["time"].dt.year <= end_year].copy()
    return _compute_amihud(ohlcv)


def _load_order_stats(order_stats_path: str, end_year: int) -> pd.DataFrame:
    order_stats = pd.read_parquet(order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= end_year].copy()
    order_stats["pct_change"] = order_stats["price_change_raw"].apply(_parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    return order_stats


def build_base_panel(
    start_year: int,
    end_year: int,
    order_stats_path: str | None = None,
    cache_path: str | None = None,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    if order_stats_path is None:
        order_stats_path = str(data_path("order_stats/cafef/order_stats_daily.parquet"))
    if cache_path and (not force_rebuild):
        cache_file = Path(cache_path)
        if cache_file.exists():
            cached = pd.read_parquet(cache_file)
            cached["time"] = pd.to_datetime(cached["time"])
            if "year" not in cached.columns:
                cached["year"] = cached["time"].dt.year
            return cached

    panel = load_s1_decision_panel(
        S1_DEFAULT_PATH,
        start_year=start_year,
        end_year=end_year,
    )
    if "year" not in panel.columns:
        panel["year"] = panel["time"].dt.year

    ohlcv = _load_ohlcv(end_year=end_year)
    panel = panel.merge(ohlcv[["time", "ticker", "amihud_20d_avg", "close"]], on=["time", "ticker"], how="left")

    order_stats = _load_order_stats(order_stats_path, end_year=end_year)
    panel = panel.merge(
        order_stats[
            ["time", "ticker", "pct_change", "total_volume", "buy_order_volume", "sell_order_volume"]
        ],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.dropna(subset=["pct_change", "total_volume", "amihud_20d_avg"]).copy()
    panel = panel[panel["total_volume"] > 0].copy()
    panel = panel.sort_values(["ticker", "time"]).copy()

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda s: s.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(lambda s: s.diff())
    panel = panel.dropna(subset=["vol_change"]).copy()

    panel["vol_rank"] = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["amihud_rank"] = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
    panel["pct_rank"] = panel.groupby("time", sort=False)["pct_change"].rank(method="average", pct=True)

    panel["vol_expansion"] = panel["vol_rank"] >= 0.8
    panel["high_illiq"] = panel["amihud_rank"] >= 0.8
    panel["buy_sell_imbalance"] = (
        (panel["buy_order_volume"] - panel["sell_order_volume"])
        / (panel["buy_order_volume"] + panel["sell_order_volume"] + 1)
    )
    panel["imbalance_rank"] = panel.groupby("time", sort=False)["buy_sell_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = panel["imbalance_rank"] >= 0.8

    panel["c23"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["c24"] = (panel["pct_change"] >= 5.0) & panel["vol_expansion"]
    panel["c25"] = (panel["pct_change"] <= -2.0) & panel["vol_expansion"]
    panel["c26"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]

    panel["signal_count"] = (
        panel["c23"].astype(int)
        + panel["c24"].astype(int)
        + panel["c25"].astype(int)
        + panel["c26"].astype(int)
    )
    panel["composite_2plus"] = panel["signal_count"] >= 2

    panel["market_active_fraction"] = panel.groupby("time")["composite_2plus"].transform("mean")
    low_cut = panel[["time", "market_active_fraction"]].drop_duplicates()["market_active_fraction"].quantile(0.2)
    panel["low_breadth"] = panel["market_active_fraction"] <= low_cut

    panel = panel.sort_values(["ticker", "time"]).copy()
    panel["signal_count_30d_avg"] = panel.groupby("ticker")["signal_count"].transform(
        lambda s: s.rolling(window=30, min_periods=10).mean()
    )
    panel["self_breadth_ratio"] = panel["signal_count"] / (panel["signal_count_30d_avg"] + 1e-6)

    panel["mag_score"] = panel["amihud_rank"] + panel["vol_rank"] + panel["pct_rank"]

    # date-level concentration from signal_count mass.
    date_mass = panel.groupby("time", as_index=False)["signal_count"].sum().rename(columns={"signal_count": "sum_signal_count"})
    top_mass = (
        panel.sort_values(["time", "signal_count"], ascending=[True, False])
        .groupby("time")
        .head(5)
        .groupby("time", as_index=False)["signal_count"]
        .sum()
        .rename(columns={"signal_count": "top5_signal_count"})
    )
    conc = date_mass.merge(top_mass, on="time", how="left")
    conc["signal_concentration"] = conc["top5_signal_count"] / (conc["sum_signal_count"] + 1e-6)
    panel = panel.merge(conc[["time", "signal_concentration"]], on="time", how="left")
    conc_cut = conc["signal_concentration"].quantile(0.7)
    panel["high_concentration"] = panel["signal_concentration"] >= conc_cut

    # Breadth expansion marker for hypothesis H627.
    panel = panel.sort_values(["ticker", "time"]).copy()
    panel["entry_breadth"] = panel.groupby("ticker")["market_active_fraction"].transform(
        lambda s: s.where(panel.loc[s.index, "composite_2plus"]).ffill()
    )
    panel["breadth_expansion_150"] = panel["market_active_fraction"] > (1.5 * panel["entry_breadth"])

    if cache_path:
        cache_file = Path(cache_path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        if "year" not in panel.columns:
            panel["year"] = panel["time"].dt.year
        panel.to_parquet(cache_file, index=False)

    return panel


def state_ic(df: pd.DataFrame, state_col: str, score_col: str, target_col: str) -> dict[str, float]:
    sub = df[df[state_col].fillna(False)].copy()
    if sub.empty:
        return {"rows": 0, "avg_ic": np.nan}
    ic = sub[score_col].corr(sub[target_col], method="spearman")
    return {"rows": int(len(sub)), "avg_ic": float(ic) if pd.notna(ic) else np.nan}


def evaluate_states(
    df: pd.DataFrame,
    state_names: list[str],
    score_col: str,
    target_col: str,
    min_year_rows: int = 100,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    result_rows: list[dict[str, object]] = []
    yearly_rows: list[dict[str, object]] = []

    for state in state_names:
        sub = df[df[state].fillna(False)].copy()
        if sub.empty:
            result_rows.append(
                {"name": state, "rows": 0, "avg_ic": np.nan, "pos_years": 0, "valid_years": 0}
            )
            continue

        pooled_ic = sub[score_col].corr(sub[target_col], method="spearman")
        pos_years = 0
        valid_years = 0
        for year, group in sub.groupby("year"):
            if len(group) < min_year_rows:
                ic = np.nan
            else:
                ic = group[score_col].corr(group[target_col], method="spearman")
                valid_years += 1
                if pd.notna(ic) and ic > 0:
                    pos_years += 1
            yearly_rows.append(
                {"name": state, "year": int(year), "rows": int(len(group)), "ic": float(ic) if pd.notna(ic) else np.nan}
            )

        result_rows.append(
            {
                "name": state,
                "rows": int(len(sub)),
                "avg_ic": float(pooled_ic) if pd.notna(pooled_ic) else np.nan,
                "pos_years": int(pos_years),
                "valid_years": int(valid_years),
            }
        )

    return pd.DataFrame(result_rows), pd.DataFrame(yearly_rows)
