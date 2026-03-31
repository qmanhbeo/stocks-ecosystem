from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from data_tools import adjust_cafef_intraday_to_vci as cafef_adjust


DEFAULT_RAW_LABEL = "1H_CAFEF"
COMPLETE_DAY_BAR_COUNT = 5
PILOT_BANK_SECTOR = "Ngân hàng"
PILOT_INDUSTRIAL_SECTOR = "Hàng & Dịch vụ Công nghiệp"
INTRADAY_BAR_LABELS = ("10:00:00", "11:00:00", "12:00:00", "13:00:00", "14:00:00")


@dataclass(frozen=True)
class PilotTickerBundle:
    features: pd.DataFrame
    factors: pd.DataFrame
    summary_row: dict[str, object]


def build_raw_intraday_path(stock_dir: Path, ticker: str, raw_label: str = DEFAULT_RAW_LABEL) -> Path:
    return Path(stock_dir) / f"gia_lich_su_{ticker}_{raw_label}.parquet"


def build_daily_path(stock_dir: Path, ticker: str) -> Path:
    return Path(stock_dir) / f"gia_lich_su_{ticker}_1D.parquet"


def list_available_intraday_tickers(stock_dir: Path, raw_label: str = DEFAULT_RAW_LABEL) -> list[str]:
    tickers: list[str] = []
    for path in sorted(Path(stock_dir).glob(f"gia_lich_su_*_{raw_label}.parquet")):
        ticker = path.stem.replace("gia_lich_su_", "").replace(f"_{raw_label}", "")
        if ticker in {"VNINDEX", "VN30"}:
            continue
        tickers.append(ticker)
    return tickers


def load_sector_map(sector_path: Path) -> pd.DataFrame:
    sector = pd.read_parquet(sector_path).copy()
    if "symbol" in sector.columns:
        sector = sector.rename(columns={"symbol": "ticker"})
    if "ticker" not in sector.columns:
        raise ValueError(f"Sector file is missing a ticker column: {sector_path}")
    keep = [column for column in ("ticker", "icb_name2", "icb_name3", "icb_name4") if column in sector.columns]
    return sector[keep].drop_duplicates(subset=["ticker"]).reset_index(drop=True)


def load_recent_liquidity_snapshot(
    *,
    stock_dir: Path,
    tickers: list[str],
    liquidity_start_date: str = "2025-01-01",
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker in tickers:
        path = build_daily_path(stock_dir, ticker)
        if not path.exists():
            continue
        daily = pd.read_parquet(path, columns=["time", "close", "volume"]).copy()
        if daily.empty:
            continue
        daily["time"] = pd.to_datetime(daily["time"], errors="coerce").dt.normalize()
        daily = daily.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
        recent = daily.loc[daily["time"] >= pd.Timestamp(liquidity_start_date)].copy()
        if recent.empty:
            recent = daily.tail(120).copy()
        if recent.empty:
            continue
        traded_value = pd.to_numeric(recent["close"], errors="coerce") * pd.to_numeric(recent["volume"], errors="coerce")
        rows.append(
            {
                "ticker": ticker,
                "median_daily_value": float(traded_value.median()),
                "recent_days": int(len(recent)),
            }
        )
    return pd.DataFrame(rows)


def select_pilot_tickers(
    *,
    stock_dir: Path,
    sector_path: Path,
    raw_label: str = DEFAULT_RAW_LABEL,
    sample_size: int = 20,
) -> pd.DataFrame:
    available = list_available_intraday_tickers(stock_dir, raw_label=raw_label)
    if not available:
        raise ValueError(f"No raw intraday files were found under {stock_dir} for label {raw_label}")

    liquidity = load_recent_liquidity_snapshot(stock_dir=stock_dir, tickers=available)
    sector = load_sector_map(sector_path)
    candidates = liquidity.merge(sector, on="ticker", how="left").sort_values(
        ["median_daily_value", "ticker"],
        ascending=[False, True],
    )
    if candidates.empty:
        raise ValueError("Could not build a representative pilot universe from the available intraday files")

    selected_rows: list[dict[str, object]] = []
    selected: set[str] = set()

    def take(frame: pd.DataFrame, *, role: str, limit: int) -> None:
        taken = 0
        for row in frame.itertuples(index=False):
            if row.ticker in selected:
                continue
            payload = dict(row._asdict())
            payload["pilot_role"] = role
            selected_rows.append(payload)
            selected.add(row.ticker)
            taken += 1
            if taken >= limit or len(selected) >= int(sample_size):
                break

    take(candidates.loc[candidates["icb_name2"] == PILOT_BANK_SECTOR].copy(), role="liquid_bank", limit=min(4, sample_size))
    take(
        candidates.loc[candidates["icb_name2"] == PILOT_INDUSTRIAL_SECTOR].copy(),
        role="liquid_industrial",
        limit=min(4, max(int(sample_size) - len(selected), 0)),
    )
    take(
        candidates.sort_values(["median_daily_value", "ticker"], ascending=[True, True]).copy(),
        role="small_tail",
        limit=min(8, max(int(sample_size) - len(selected), 0)),
    )
    take(
        candidates.copy(),
        role="liquid_fill",
        limit=max(int(sample_size) - len(selected), 0),
    )

    selected_frame = pd.DataFrame(selected_rows).drop_duplicates(subset=["ticker"]).head(int(sample_size)).copy()
    selected_frame["pilot_order"] = np.arange(1, len(selected_frame) + 1, dtype=int)
    return selected_frame.reset_index(drop=True)


def load_intraday_window(
    *,
    stock_dir: Path,
    ticker: str,
    start_date: str,
    end_date: str,
    raw_label: str = DEFAULT_RAW_LABEL,
) -> pd.DataFrame:
    path = build_raw_intraday_path(stock_dir, ticker, raw_label=raw_label)
    intraday = pd.read_parquet(path, columns=list(cafef_adjust.BAR_COLUMNS)).copy()
    intraday["time"] = pd.to_datetime(intraday["time"], errors="coerce")
    intraday = intraday.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    intraday["session_date"] = intraday["time"].dt.normalize()
    mask = (intraday["session_date"] >= pd.Timestamp(start_date)) & (intraday["session_date"] <= pd.Timestamp(end_date))
    return intraday.loc[mask].reset_index(drop=True)


def load_daily_window(
    *,
    stock_dir: Path,
    ticker: str,
    start_date: str,
    end_date: str,
    include_lookback_days: int = 0,
) -> pd.DataFrame:
    path = build_daily_path(stock_dir, ticker)
    daily = pd.read_parquet(path, columns=["time", "open", "high", "low", "close", "volume"]).copy()
    daily["time"] = pd.to_datetime(daily["time"], errors="coerce").dt.normalize()
    daily = daily.dropna(subset=["time"]).drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    start_ts = pd.Timestamp(start_date) - pd.Timedelta(days=int(include_lookback_days))
    end_ts = pd.Timestamp(end_date)
    daily = daily.loc[(daily["time"] >= start_ts) & (daily["time"] <= end_ts)].copy()
    return daily.rename(
        columns={
            "time": "session_date",
            "open": "vci_open_adj",
            "high": "vci_high_adj",
            "low": "vci_low_adj",
            "close": "vci_close_adj",
            "volume": "vci_volume",
        }
    ).reset_index(drop=True)


def build_intraday_pilot_bundle(
    *,
    stock_dir: Path,
    ticker: str,
    start_date: str,
    end_date: str,
    raw_label: str = DEFAULT_RAW_LABEL,
) -> PilotTickerBundle:
    intraday = load_intraday_window(
        stock_dir=stock_dir,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        raw_label=raw_label,
    )
    daily = load_daily_window(
        stock_dir=stock_dir,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        include_lookback_days=10,
    )
    if intraday.empty or daily.empty:
        return PilotTickerBundle(
            features=pd.DataFrame(),
            factors=pd.DataFrame(),
            summary_row={
                "ticker": ticker,
                "overlap_days": 0,
                "complete_day_share": None,
                "error": "empty_intraday_or_daily_window",
            },
        )

    factors = cafef_adjust.build_daily_factor_frame(intraday, daily)
    if factors.empty:
        return PilotTickerBundle(
            features=pd.DataFrame(),
            factors=pd.DataFrame(),
            summary_row={
                "ticker": ticker,
                "overlap_days": 0,
                "complete_day_share": None,
                "error": "no_overlapping_valid_factor_days",
            },
        )
    adjusted = cafef_adjust.apply_adjustment(intraday, factors)
    adjusted["session_date"] = pd.to_datetime(adjusted["time"], errors="coerce").dt.normalize()
    adjusted["bar_label"] = adjusted["time"].dt.strftime("%H:%M:%S")

    first_bar = (
        adjusted.sort_values("time")
        .groupby("session_date", sort=True)
        .agg(
            first_open=("open", "first"),
            first_high=("high", "max"),
            first_low=("low", "min"),
            first_close=("close", "first"),
            first_bar_time=("bar_label", "first"),
            day_volume=("volume", "sum"),
            n_bars=("time", "size"),
        )
        .reset_index()
    )
    last_bar = (
        adjusted.sort_values("time")
        .groupby("session_date", sort=True)
        .agg(
            last_open=("open", "last"),
            last_close=("close", "last"),
            last_bar_time=("bar_label", "last"),
        )
        .reset_index()
    )
    penultimate_close = (
        adjusted.sort_values("time")
        .groupby("session_date", sort=True)
        .nth(-2)
        .reset_index()[["session_date", "close"]]
        .rename(columns={"close": "penultimate_close"})
    )
    presence = (
        adjusted.assign(has_bar=1)
        .pivot_table(
            index="session_date",
            columns="bar_label",
            values="has_bar",
            aggfunc="max",
            fill_value=0,
        )
        .reset_index()
    )
    for label in INTRADAY_BAR_LABELS:
        if label not in presence.columns:
            presence[label] = 0

    prev_close = daily[["session_date", "vci_close_adj"]].drop_duplicates(subset=["session_date"], keep="last").copy()
    prev_close = prev_close.sort_values("session_date").reset_index(drop=True)
    prev_close["prev_vci_close_adj"] = prev_close["vci_close_adj"].shift(1)

    features = (
        first_bar.merge(last_bar, on="session_date", how="left")
        .merge(penultimate_close, on="session_date", how="left")
        .merge(prev_close[["session_date", "prev_vci_close_adj", "vci_close_adj"]], on="session_date", how="left")
        .merge(factors[["session_date", "price_factor", "open_gap_pct", "high_gap_pct", "low_gap_pct", "volume_ratio_vs_vci"]], on="session_date", how="left")
        .merge(presence, on="session_date", how="left")
        .sort_values("session_date")
        .reset_index(drop=True)
    )
    features["ticker"] = ticker
    features["complete_day"] = pd.to_numeric(features["n_bars"], errors="coerce").fillna(0).eq(COMPLETE_DAY_BAR_COUNT)
    features["has_midday_window"] = (
        pd.to_numeric(features["12:00:00"], errors="coerce").fillna(0).astype(int).gt(0)
        & pd.to_numeric(features["13:00:00"], errors="coerce").fillna(0).astype(int).gt(0)
    )
    prev_close_nonzero = pd.to_numeric(features["prev_vci_close_adj"], errors="coerce").replace(0.0, np.nan)
    features["open_gap_vs_prev_close"] = (pd.to_numeric(features["first_open"], errors="coerce") / prev_close_nonzero) - 1.0
    first_open_nonzero = pd.to_numeric(features["first_open"], errors="coerce").replace(0.0, np.nan)
    last_open_nonzero = pd.to_numeric(features["last_open"], errors="coerce").replace(0.0, np.nan)
    penultimate_close_nonzero = pd.to_numeric(features["penultimate_close"], errors="coerce").replace(0.0, np.nan)
    features["first_60m_return"] = (pd.to_numeric(features["first_close"], errors="coerce") / first_open_nonzero) - 1.0
    features["first_60m_range_pct"] = (
        (pd.to_numeric(features["first_high"], errors="coerce") - pd.to_numeric(features["first_low"], errors="coerce"))
        / first_open_nonzero
    )
    features["close_hour_return"] = (pd.to_numeric(features["last_close"], errors="coerce") / last_open_nonzero) - 1.0
    features["close_repair_return"] = (pd.to_numeric(features["last_close"], errors="coerce") / penultimate_close_nonzero) - 1.0
    features["full_session_return"] = (pd.to_numeric(features["last_close"], errors="coerce") / first_open_nonzero) - 1.0

    def _finite_fraction(series: pd.Series) -> float:
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.empty:
            return 0.0
        return float(np.isfinite(numeric.to_numpy(dtype=float)).mean())

    summary_row = {
        "ticker": ticker,
        "raw_intraday_days": int(intraday["session_date"].nunique()),
        "overlap_days": int(features["session_date"].nunique()),
        "first_session_date": features["session_date"].min().strftime("%Y-%m-%d") if not features.empty else None,
        "last_session_date": features["session_date"].max().strftime("%Y-%m-%d") if not features.empty else None,
        "median_bars_per_day": float(pd.to_numeric(features["n_bars"], errors="coerce").median()) if not features.empty else None,
        "complete_day_share": float(features["complete_day"].mean()) if not features.empty else None,
        "midday_window_share": float(features["has_midday_window"].mean()) if not features.empty else None,
        "open_gap_feature_share": _finite_fraction(features["open_gap_vs_prev_close"]),
        "first_60m_feature_share": _finite_fraction(features["first_60m_return"]),
        "close_hour_feature_share": _finite_fraction(features["close_hour_return"]),
        "median_abs_open_gap_bp": float(np.nanmedian(np.abs(pd.to_numeric(features["open_gap_pct"], errors="coerce").to_numpy(dtype=float))) * 1e4),
        "median_abs_high_gap_bp": float(np.nanmedian(np.abs(pd.to_numeric(features["high_gap_pct"], errors="coerce").to_numpy(dtype=float))) * 1e4),
        "median_abs_low_gap_bp": float(np.nanmedian(np.abs(pd.to_numeric(features["low_gap_pct"], errors="coerce").to_numpy(dtype=float))) * 1e4),
    }
    return PilotTickerBundle(features=features, factors=factors.copy(), summary_row=summary_row)


def load_tradability_window(
    *,
    tradability_path: Path,
    start_date: str,
    end_date: str,
    tickers: list[str],
) -> pd.DataFrame:
    tradability = pd.read_parquet(tradability_path, columns=["time", "ticker", "has_volume"]).copy()
    tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce").dt.normalize()
    tradability = tradability.dropna(subset=["time"]).copy()
    tradability = tradability.loc[
        (tradability["time"] >= pd.Timestamp(start_date))
        & (tradability["time"] <= pd.Timestamp(end_date))
        & (tradability["ticker"].isin(tickers))
    ].copy()
    return tradability.rename(columns={"time": "session_date"}).reset_index(drop=True)


def build_intraday_coverage_taxonomy(
    *,
    stock_dir: Path,
    tradability: pd.DataFrame,
    start_date: str,
    end_date: str,
    raw_label: str = DEFAULT_RAW_LABEL,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    coverage_rows: list[pd.DataFrame] = []
    ticker_summaries: list[dict[str, object]] = []
    available_tickers = list_available_intraday_tickers(stock_dir, raw_label=raw_label)
    tradability = tradability.copy()
    tradability["session_date"] = pd.to_datetime(tradability["session_date"], errors="coerce").dt.normalize()

    for ticker in available_tickers:
        daily = load_daily_window(
            stock_dir=stock_dir,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
        )
        if daily.empty:
            continue
        try:
            intraday = load_intraday_window(
                stock_dir=stock_dir,
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                raw_label=raw_label,
            )
        except Exception:
            intraday = pd.DataFrame(columns=["session_date", "time"])
        presence = intraday.groupby("session_date", sort=True).size().rename("n_bars").reset_index()
        overlap_dates = sorted(set(daily["session_date"].tolist()) & set(presence["session_date"].tolist()))
        first_present = pd.Timestamp(overlap_dates[0]) if overlap_dates else pd.NaT
        last_present = pd.Timestamp(overlap_dates[-1]) if overlap_dates else pd.NaT

        daily_grid = daily[["session_date", "vci_volume"]].copy()
        daily_grid["ticker"] = ticker
        daily_grid = daily_grid.merge(
            tradability.loc[tradability["ticker"] == ticker, ["session_date", "has_volume"]],
            on="session_date",
            how="left",
        )
        daily_grid["has_volume"] = daily_grid["has_volume"].fillna(pd.to_numeric(daily_grid["vci_volume"], errors="coerce").fillna(0).gt(0))
        daily_grid = daily_grid.merge(presence, on="session_date", how="left")

        if pd.isna(first_present):
            daily_grid["coverage_bucket"] = "source_empty_prefix"
        else:
            observed_mask = daily_grid["n_bars"].notna()
            prefix_mask = daily_grid["session_date"] < first_present
            tail_mask = daily_grid["session_date"] > last_present
            in_window_mask = ~(prefix_mask | tail_mask)
            no_volume_mask = in_window_mask & (~daily_grid["has_volume"].astype(bool)) & (~observed_mask)
            missing_with_volume_mask = in_window_mask & daily_grid["has_volume"].astype(bool) & (~observed_mask)
            observed_complete_mask = observed_mask & (pd.to_numeric(daily_grid["n_bars"], errors="coerce").fillna(0) >= COMPLETE_DAY_BAR_COUNT)

            daily_grid["coverage_bucket"] = "observed_incomplete"
            daily_grid.loc[prefix_mask, "coverage_bucket"] = "source_empty_prefix"
            daily_grid.loc[tail_mask, "coverage_bucket"] = "source_tail_gap"
            daily_grid.loc[observed_complete_mask, "coverage_bucket"] = "observed_complete"
            daily_grid.loc[no_volume_mask, "coverage_bucket"] = "missing_no_volume"
            daily_grid.loc[missing_with_volume_mask, "coverage_bucket"] = "missing_with_volume"

        coverage_rows.append(daily_grid.copy())

        summary = {
            "ticker": ticker,
            "first_present_date": first_present.strftime("%Y-%m-%d") if not pd.isna(first_present) else None,
            "last_present_date": last_present.strftime("%Y-%m-%d") if not pd.isna(last_present) else None,
            "daily_days": int(len(daily_grid)),
            "overlap_days": int(daily_grid["coverage_bucket"].isin(["observed_complete", "observed_incomplete"]).sum()),
            "complete_days": int((daily_grid["coverage_bucket"] == "observed_complete").sum()),
            "prefix_days": int((daily_grid["coverage_bucket"] == "source_empty_prefix").sum()),
            "tail_gap_days": int((daily_grid["coverage_bucket"] == "source_tail_gap").sum()),
            "missing_with_volume_days": int((daily_grid["coverage_bucket"] == "missing_with_volume").sum()),
            "missing_no_volume_days": int((daily_grid["coverage_bucket"] == "missing_no_volume").sum()),
        }
        in_window_volume_days = summary["overlap_days"] + summary["missing_with_volume_days"]
        summary["missing_session_rate_in_window"] = (
            float(summary["missing_with_volume_days"] / in_window_volume_days) if in_window_volume_days > 0 else None
        )
        observed_days = summary["overlap_days"]
        summary["complete_day_share_present"] = (
            float(summary["complete_days"] / observed_days) if observed_days > 0 else None
        )
        ticker_summaries.append(summary)

    coverage = pd.concat(coverage_rows, ignore_index=True) if coverage_rows else pd.DataFrame()
    return coverage, pd.DataFrame(ticker_summaries)


def summarize_coverage_against_continuation(
    *,
    coverage_frame: pd.DataFrame,
    ticker_summary: pd.DataFrame,
    continuation_panel: pd.DataFrame,
) -> dict[str, object]:
    coverage = coverage_frame.copy()
    coverage["session_date"] = pd.to_datetime(coverage["session_date"], errors="coerce").dt.normalize()
    continuation = continuation_panel[["time", "ticker"]].copy()
    continuation["time"] = pd.to_datetime(continuation["time"], errors="coerce").dt.normalize()

    observed = coverage.loc[coverage["coverage_bucket"].isin(["observed_complete", "observed_incomplete"]), ["session_date", "ticker"]].drop_duplicates()
    observed_complete = coverage.loc[coverage["coverage_bucket"] == "observed_complete", ["session_date", "ticker"]].drop_duplicates()
    held_merge = continuation.merge(
        observed.rename(columns={"session_date": "time"}),
        on=["time", "ticker"],
        how="left",
        indicator=True,
    )
    held_complete_merge = continuation.merge(
        observed_complete.rename(columns={"session_date": "time"}),
        on=["time", "ticker"],
        how="left",
        indicator=True,
    )

    in_window_volume_days = coverage["coverage_bucket"].isin(["observed_complete", "observed_incomplete", "missing_with_volume"]).sum()
    observed_days = coverage["coverage_bucket"].isin(["observed_complete", "observed_incomplete"]).sum()
    available_tickers = int(ticker_summary["ticker"].nunique()) if not ticker_summary.empty else 0

    return {
        "available_raw_tickers": available_tickers,
        "tickers_with_any_overlap": int((pd.to_numeric(ticker_summary["overlap_days"], errors="coerce").fillna(0) > 0).sum()) if not ticker_summary.empty else 0,
        "tickers_with_60_overlap_days": int((pd.to_numeric(ticker_summary["overlap_days"], errors="coerce").fillna(0) >= 60).sum()) if not ticker_summary.empty else 0,
        "held_row_coverage_lower_bound": float((held_merge["_merge"] == "both").mean()) if len(held_merge) else 0.0,
        "held_row_complete_day_coverage_lower_bound": float((held_complete_merge["_merge"] == "both").mean()) if len(held_complete_merge) else 0.0,
        "missing_session_rate_in_window": float((coverage["coverage_bucket"] == "missing_with_volume").sum() / in_window_volume_days) if in_window_volume_days else 0.0,
        "complete_day_share_present": float((coverage["coverage_bucket"] == "observed_complete").sum() / observed_days) if observed_days else 0.0,
        "prefix_gap_share": float((coverage["coverage_bucket"] == "source_empty_prefix").mean()) if len(coverage) else 0.0,
        "tail_gap_share": float((coverage["coverage_bucket"] == "source_tail_gap").mean()) if len(coverage) else 0.0,
        "no_volume_missing_share": float((coverage["coverage_bucket"] == "missing_no_volume").mean()) if len(coverage) else 0.0,
    }
