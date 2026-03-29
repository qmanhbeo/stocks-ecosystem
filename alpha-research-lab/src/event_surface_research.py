from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DIVIDEND_CODES = {"DIV"}
ISSUANCE_CODES = {"ISS", "AIS", "NLIS"}
DEFAULT_MAX_EVENT_GAP_DAYS = 999
EVENT_PRE_WINDOW_DAYS = 20
EVENT_POST_WINDOW_DAYS = 5
EVENT_CORE_FEATURES = [
    "days_to_next_dividend",
    "days_since_dividend",
    "dividend_window_pre_20d",
    "dividend_window_post_5d",
    "days_to_next_issuance",
    "days_since_issuance",
    "issuance_window_pre_20d",
    "issuance_window_post_5d",
    "recent_insider_filing_5d",
    "recent_insider_filing_20d",
    "recent_major_holder_filing_5d",
    "recent_major_holder_filing_20d",
    "recent_any_filing_5d",
    "recent_any_filing_20d",
    "dividend_event_density_20d",
    "issuance_event_density_20d",
    "event_density_20d",
    "days_since_q_end",
    "days_to_next_q_end",
    "in_report_w15_45",
    "in_report_w30_60",
    "pre_q_end_10d",
    "post_q_end_10d",
    "quarter_phase_sin",
    "quarter_phase_cos",
]
EARNINGS_COLUMNS = [
    "days_since_q_end",
    "days_to_next_q_end",
    "in_report_w15_45",
    "in_report_w30_60",
    "pre_q_end_10d",
    "post_q_end_10d",
    "quarter_phase_sin",
    "quarter_phase_cos",
]


@dataclass(frozen=True)
class EventSurfaceBundle:
    surface: pd.DataFrame
    coverage_summary: dict[str, object]


@dataclass(frozen=True)
class EventSurfaceCoverage:
    merged_panel: pd.DataFrame
    coverage_summary: dict[str, object]


@dataclass(frozen=True)
class EventRuleSpec:
    variant: str
    exit_rule_name: str
    exit_rule_params: dict[str, object]


def load_matrix_spine(
    matrix_path: Path,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pd.DataFrame:
    spine = pd.read_parquet(matrix_path, columns=["time", "ticker"])
    spine["time"] = pd.to_datetime(spine["time"])
    if start_year is not None:
        spine = spine.loc[spine["time"].dt.year >= int(start_year)].copy()
    if end_year is not None:
        spine = spine.loc[spine["time"].dt.year <= int(end_year)].copy()
    spine = spine.drop_duplicates(["time", "ticker"]).sort_values(["ticker", "time"]).reset_index(drop=True)
    return spine


def _coerce_timestamp(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, errors="coerce")
    ts = ts.where(ts >= pd.Timestamp("2000-01-01"))
    ts = ts.where(ts <= pd.Timestamp("2035-12-31"))
    return ts.dt.normalize()


def _load_corporate_events(cache_dir: Path) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for path in sorted(cache_dir.glob("*_events.parquet")):
        ticker = path.name.replace("_events.parquet", "")
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        work = frame.copy()
        work["ticker"] = ticker
        work["public_date"] = _coerce_timestamp(work.get("public_date"))
        work["issue_date"] = _coerce_timestamp(work.get("issue_date"))
        work["exright_date"] = _coerce_timestamp(work.get("exright_date"))
        work = work.loc[work["public_date"].notna()].copy()
        if work.empty:
            continue

        dividend = work.loc[work["event_list_code"].isin(DIVIDEND_CODES)].copy()
        if not dividend.empty:
            dividend["event_family"] = "dividend"
            dividend["effective_date"] = dividend["exright_date"].where(dividend["exright_date"].notna(), dividend["public_date"])
            dividend["effective_date"] = dividend[["effective_date", "public_date"]].max(axis=1)
            rows.append(dividend[["ticker", "event_family", "public_date", "effective_date", "event_list_code"]])

        issuance = work.loc[work["event_list_code"].isin(ISSUANCE_CODES)].copy()
        if not issuance.empty:
            issuance["event_family"] = "issuance"
            issuance["effective_date"] = issuance["issue_date"].where(issuance["issue_date"].notna(), issuance["public_date"])
            issuance["effective_date"] = issuance[["effective_date", "public_date"]].max(axis=1)
            rows.append(issuance[["ticker", "event_family", "public_date", "effective_date", "event_list_code"]])

    if not rows:
        return pd.DataFrame(columns=["ticker", "event_family", "public_date", "effective_date", "event_list_code"])

    events = pd.concat(rows, ignore_index=True)
    events = events.dropna(subset=["ticker", "event_family", "public_date", "effective_date"])
    events = events.sort_values(["ticker", "event_family", "public_date", "effective_date"]).reset_index(drop=True)
    return events


def _build_family_surface(
    spine: pd.DataFrame,
    events: pd.DataFrame,
    *,
    family: str,
    pre_window_days: int = EVENT_PRE_WINDOW_DAYS,
    post_window_days: int = EVENT_POST_WINDOW_DAYS,
) -> pd.DataFrame:
    out_parts: list[pd.DataFrame] = []
    family_events = events.loc[events["event_family"] == family].copy()
    family_label = str(family)

    for ticker, group in spine.groupby("ticker", sort=False):
        ticker_dates = pd.to_datetime(group["time"]).dt.normalize().to_numpy(dtype="datetime64[ns]")
        days_to = np.full(len(group), DEFAULT_MAX_EVENT_GAP_DAYS, dtype=np.int64)
        days_since = np.full(len(group), DEFAULT_MAX_EVENT_GAP_DAYS, dtype=np.int64)
        pre_window = np.zeros(len(group), dtype=np.int8)
        post_window = np.zeros(len(group), dtype=np.int8)
        density_20d = np.zeros(len(group), dtype=np.int64)
        has_history = False

        ticker_events = family_events.loc[family_events["ticker"] == ticker].copy()
        if not ticker_events.empty:
            has_history = True
            announced = pd.to_datetime(ticker_events["public_date"]).dt.normalize().to_numpy(dtype="datetime64[ns]")
            effective = pd.to_datetime(ticker_events["effective_date"]).dt.normalize().to_numpy(dtype="datetime64[ns]")
            for idx, current_date in enumerate(ticker_dates):
                known_mask = announced <= current_date
                if np.any(known_mask):
                    known_effective = effective[known_mask]
                    future = known_effective[known_effective >= current_date]
                    past = known_effective[known_effective <= current_date]
                    if future.size > 0:
                        next_event = future.min()
                        delta = int((next_event - current_date) / np.timedelta64(1, "D"))
                        days_to[idx] = max(delta, 0)
                        pre_window[idx] = int(0 <= delta <= pre_window_days)
                    if past.size > 0:
                        prev_event = past.max()
                        delta = int((current_date - prev_event) / np.timedelta64(1, "D"))
                        days_since[idx] = max(delta, 0)
                        post_window[idx] = int(0 <= delta <= post_window_days)
                    density_20d[idx] = int(np.count_nonzero(known_mask & (announced > current_date - np.timedelta64(20, "D"))))

        part = group[["time", "ticker"]].copy()
        part[f"days_to_next_{family_label}"] = days_to
        part[f"days_since_{family_label}"] = days_since
        part[f"{family_label}_window_pre_{pre_window_days}d"] = pre_window.astype(float)
        part[f"{family_label}_window_post_{post_window_days}d"] = post_window.astype(float)
        part[f"{family_label}_event_density_20d"] = density_20d.astype(float)
        part[f"has_{family_label}_event_history"] = float(has_history)
        out_parts.append(part)

    return pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame(columns=["time", "ticker"])


def _build_insider_surface(spine: pd.DataFrame, insider_raw_path: Path) -> pd.DataFrame:
    raw = pd.read_parquet(insider_raw_path)
    work = raw[["ticker", "published_date", "is_insider"]].copy()
    work["time"] = _coerce_timestamp(work["published_date"])
    work = work.dropna(subset=["ticker", "time"]).copy()
    work["insider_count"] = work["is_insider"].fillna(False).astype(int)
    work["major_holder_count"] = (~work["is_insider"].fillna(False).astype(bool)).astype(int)
    work["any_count"] = 1
    daily = work.groupby(["time", "ticker"], as_index=False)[["insider_count", "major_holder_count", "any_count"]].sum()

    merged = spine[["time", "ticker"]].merge(daily, on=["time", "ticker"], how="left")
    for column in ["insider_count", "major_holder_count", "any_count"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)
    grouped = merged.groupby("ticker", group_keys=False)
    for window in (5, 20):
        merged[f"recent_insider_filing_{window}d"] = grouped["insider_count"].rolling(window=window, min_periods=1).sum().reset_index(level=0, drop=True)
        merged[f"recent_major_holder_filing_{window}d"] = grouped["major_holder_count"].rolling(window=window, min_periods=1).sum().reset_index(level=0, drop=True)
        merged[f"recent_any_filing_{window}d"] = grouped["any_count"].rolling(window=window, min_periods=1).sum().reset_index(level=0, drop=True)
    merged["has_insider_event_history"] = grouped["any_count"].transform("sum").gt(0).astype(float)
    keep = [
        "time",
        "ticker",
        "recent_insider_filing_5d",
        "recent_insider_filing_20d",
        "recent_major_holder_filing_5d",
        "recent_major_holder_filing_20d",
        "recent_any_filing_5d",
        "recent_any_filing_20d",
        "has_insider_event_history",
    ]
    return merged[keep].copy()


def _load_earnings_surface(spine: pd.DataFrame, earnings_calendar_path: Path) -> pd.DataFrame:
    earnings = pd.read_parquet(earnings_calendar_path)
    earnings["time"] = pd.to_datetime(earnings["time"]).dt.normalize()
    keep = ["time"] + [column for column in EARNINGS_COLUMNS if column in earnings.columns]
    earnings = earnings[keep].drop_duplicates("time").copy()
    surface = spine[["time", "ticker"]].merge(earnings, on="time", how="left")
    for column in EARNINGS_COLUMNS:
        if column not in surface.columns:
            surface[column] = 0.0
        surface[column] = pd.to_numeric(surface[column], errors="coerce").fillna(0.0)
    return surface[["time", "ticker"] + EARNINGS_COLUMNS].copy()


def build_event_surface(
    *,
    spine: pd.DataFrame,
    dividend_cache_dir: Path,
    earnings_calendar_path: Path,
    insider_raw_path: Path,
) -> EventSurfaceBundle:
    spine = spine[["time", "ticker"]].copy()
    spine["time"] = pd.to_datetime(spine["time"]).dt.normalize()
    spine = spine.drop_duplicates(["time", "ticker"]).sort_values(["ticker", "time"]).reset_index(drop=True)
    events = _load_corporate_events(dividend_cache_dir)
    dividend_surface = _build_family_surface(spine, events, family="dividend")
    issuance_surface = _build_family_surface(spine, events, family="issuance")
    insider_surface = _build_insider_surface(spine, insider_raw_path)
    earnings_surface = _load_earnings_surface(spine, earnings_calendar_path)

    surface = spine.copy()
    for other in (dividend_surface, issuance_surface, insider_surface, earnings_surface):
        surface = surface.merge(other, on=["time", "ticker"], how="left", validate="one_to_one")

    numeric_columns = [column for column in surface.columns if column not in {"time", "ticker"}]
    for column in numeric_columns:
        if column.startswith("days_to_next_") or column.startswith("days_since_"):
            surface[column] = pd.to_numeric(surface[column], errors="coerce").fillna(DEFAULT_MAX_EVENT_GAP_DAYS).clip(lower=0.0, upper=float(DEFAULT_MAX_EVENT_GAP_DAYS))
        else:
            surface[column] = pd.to_numeric(surface[column], errors="coerce").fillna(0.0)

    surface["event_density_20d"] = (
        surface.get("dividend_event_density_20d", 0.0)
        + surface.get("issuance_event_density_20d", 0.0)
        + surface.get("recent_any_filing_20d", 0.0)
    )
    surface["has_any_event_history"] = (
        surface.get("has_dividend_event_history", 0.0)
        + surface.get("has_issuance_event_history", 0.0)
        + surface.get("has_insider_event_history", 0.0)
        > 0.0
    ).astype(float)

    coverage_summary = {
        "rows": int(len(surface)),
        "tickers": int(surface["ticker"].nunique()),
        "dates": int(surface["time"].nunique()),
        "dividend_event_tickers": int(surface.loc[surface["has_dividend_event_history"] > 0.0, "ticker"].nunique()),
        "issuance_event_tickers": int(surface.loc[surface["has_issuance_event_history"] > 0.0, "ticker"].nunique()),
        "insider_event_tickers": int(surface.loc[surface["has_insider_event_history"] > 0.0, "ticker"].nunique()),
        "any_event_tickers": int(surface.loc[surface["has_any_event_history"] > 0.0, "ticker"].nunique()),
    }
    return EventSurfaceBundle(surface=surface.sort_values(["time", "ticker"]).reset_index(drop=True), coverage_summary=coverage_summary)


def merge_event_surface(
    panel: pd.DataFrame,
    event_surface: pd.DataFrame,
    *,
    date_column: str = "time",
) -> EventSurfaceCoverage:
    work = panel.copy()
    work[date_column] = pd.to_datetime(work[date_column]).dt.normalize()
    surface = event_surface.copy()
    surface["time"] = pd.to_datetime(surface["time"]).dt.normalize()
    merged = work.merge(surface, left_on=[date_column, "ticker"], right_on=["time", "ticker"], how="left")
    feature_columns = [column for column in surface.columns if column not in {"time", "ticker"}]
    coverage_mask = merged[feature_columns].notna().all(axis=1) if feature_columns else pd.Series(True, index=merged.index)
    for column in feature_columns:
        if column.startswith("days_to_next_") or column.startswith("days_since_"):
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(DEFAULT_MAX_EVENT_GAP_DAYS)
        else:
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged = merged.drop(columns=["time_y"], errors="ignore").rename(columns={"time_x": "time"})
    summary = {
        "panel_rows": int(len(work)),
        "covered_rows": int(coverage_mask.sum()),
        "coverage_share": float(coverage_mask.mean()) if len(coverage_mask) else 0.0,
        "covered_tickers": int(merged.loc[coverage_mask, "ticker"].nunique()) if len(merged) else 0,
    }
    return EventSurfaceCoverage(merged_panel=merged, coverage_summary=summary)


def build_event_hazard_params(
    model_row: pd.Series,
    *,
    continue_prob_threshold: float,
) -> dict[str, object]:
    params: dict[str, object] = {
        "intercept": float(pd.to_numeric(model_row.get("intercept"), errors="coerce")),
        "continue_prob_threshold": float(continue_prob_threshold),
    }
    for key, value in model_row.items():
        if not str(key).startswith("coef__"):
            continue
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.isna(numeric):
            continue
        params[str(key)] = float(numeric)
    return params
