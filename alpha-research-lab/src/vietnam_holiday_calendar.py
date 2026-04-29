from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PRE_POST_OFFSETS = (1, 2, 3, 5)

TET_FIRST_DAY = {
    2015: "2015-02-19",
    2016: "2016-02-08",
    2017: "2017-01-28",
    2018: "2018-02-16",
    2019: "2019-02-05",
    2020: "2020-01-25",
    2021: "2021-02-12",
    2022: "2022-02-01",
    2023: "2023-01-22",
    2024: "2024-02-10",
    2025: "2025-01-29",
}

HUNG_KINGS_DAY = {
    2015: "2015-04-28",
    2016: "2016-04-16",
    2017: "2017-04-06",
    2018: "2018-04-25",
    2019: "2019-04-14",
    2020: "2020-04-02",
    2021: "2021-04-21",
    2022: "2022-04-10",
    2023: "2023-04-29",
    2024: "2024-04-18",
    2025: "2025-04-07",
}

FAMILY_LABELS = {
    "new_year": "New Year Jan 1",
    "tet": "Tet Lunar New Year",
    "hung_kings": "Hung Kings Commemoration Day",
    "reunification_labor": "Reunification Day Apr 30 / Labor Day May 1",
    "national_day": "National Day Sep 2 plus adjacent official day",
}


@dataclass(frozen=True)
class HolidayAnchor:
    holiday_year: int
    holiday_family: str
    anchor_date: pd.Timestamp
    legal_name: str


def normalize_trading_dates(values: pd.Series | pd.Index | list[object]) -> pd.DatetimeIndex:
    dates = pd.to_datetime(pd.Series(values), errors="coerce").dt.normalize().dropna()
    return pd.DatetimeIndex(sorted(dates.drop_duplicates().tolist()))


def load_vnindex_trading_dates(path: str | Path) -> pd.DatetimeIndex:
    frame = pd.read_parquet(path, columns=["time"])
    return normalize_trading_dates(frame["time"])


def major_holiday_anchors(start_year: int = 2015, end_year: int = 2025) -> pd.DataFrame:
    rows: list[HolidayAnchor] = []
    for year in range(int(start_year), int(end_year) + 1):
        rows.append(
            HolidayAnchor(
                holiday_year=year,
                holiday_family="new_year",
                anchor_date=pd.Timestamp(year=year, month=1, day=1),
                legal_name=FAMILY_LABELS["new_year"],
            )
        )
        rows.append(
            HolidayAnchor(
                holiday_year=year,
                holiday_family="tet",
                anchor_date=pd.Timestamp(TET_FIRST_DAY[year]),
                legal_name=FAMILY_LABELS["tet"],
            )
        )
        rows.append(
            HolidayAnchor(
                holiday_year=year,
                holiday_family="hung_kings",
                anchor_date=pd.Timestamp(HUNG_KINGS_DAY[year]),
                legal_name=FAMILY_LABELS["hung_kings"],
            )
        )
        for month, day in ((4, 30), (5, 1)):
            rows.append(
                HolidayAnchor(
                    holiday_year=year,
                    holiday_family="reunification_labor",
                    anchor_date=pd.Timestamp(year=year, month=month, day=day),
                    legal_name=FAMILY_LABELS["reunification_labor"],
                )
            )
        rows.append(
            HolidayAnchor(
                holiday_year=year,
                holiday_family="national_day",
                anchor_date=pd.Timestamp(year=year, month=9, day=2),
                legal_name=FAMILY_LABELS["national_day"],
            )
        )
    return pd.DataFrame([row.__dict__ for row in rows])


def _calendar_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    if pd.isna(start) or pd.isna(end) or start > end:
        return pd.DatetimeIndex([])
    return pd.date_range(start, end, freq="D")


def _weekday_closure_count(
    start: pd.Timestamp,
    end: pd.Timestamp,
    trading_dates: pd.DatetimeIndex,
) -> int:
    trading_set = set(trading_dates)
    return int(sum(day.weekday() < 5 and day not in trading_set for day in _calendar_days(start, end)))


def _anchor_interval(
    anchor: pd.Timestamp,
    trading_dates: pd.DatetimeIndex,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp, int, int] | None:
    pos_left = int(trading_dates.searchsorted(anchor, side="left"))
    pos_right = int(trading_dates.searchsorted(anchor, side="right"))
    if pos_left <= 0 or pos_right >= len(trading_dates):
        return None

    if pos_left < len(trading_dates) and trading_dates[pos_left] == anchor:
        return None

    prev_trade = pd.Timestamp(trading_dates[pos_left - 1])
    next_trade = pd.Timestamp(trading_dates[pos_right])
    closed_start = prev_trade + pd.Timedelta(days=1)
    closed_end = next_trade - pd.Timedelta(days=1)
    closure_length = int((closed_end - closed_start).days + 1)
    closure_weekdays = _weekday_closure_count(closed_start, closed_end, trading_dates)
    if closure_length <= 0 or closure_weekdays <= 0:
        return None
    return prev_trade, next_trade, closed_start, closed_end, closure_length, closure_weekdays


def _merge_family_intervals(intervals: pd.DataFrame) -> pd.DataFrame:
    if intervals.empty:
        return intervals
    rows: list[dict[str, object]] = []
    for (holiday_year, holiday_family), group in intervals.groupby(["holiday_year", "holiday_family"], sort=True):
        current: dict[str, object] | None = None
        for row in group.sort_values(["closed_start", "closed_end"]).to_dict(orient="records"):
            if current is None:
                current = dict(row)
                current["anchor_dates"] = [row["anchor_date"]]
                current["legal_names"] = [row["legal_name"]]
                continue
            if pd.Timestamp(row["closed_start"]) <= pd.Timestamp(current["closed_end"]) + pd.Timedelta(days=1):
                current["closed_end"] = max(pd.Timestamp(current["closed_end"]), pd.Timestamp(row["closed_end"]))
                current["closed_start"] = min(pd.Timestamp(current["closed_start"]), pd.Timestamp(row["closed_start"]))
                current["anchor_dates"].append(row["anchor_date"])
                current["legal_names"].append(row["legal_name"])
            else:
                rows.append(current)
                current = dict(row)
                current["anchor_dates"] = [row["anchor_date"]]
                current["legal_names"] = [row["legal_name"]]
        if current is not None:
            rows.append(current)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["anchor_dates"] = out["anchor_dates"].map(
        lambda dates: ",".join(pd.Timestamp(value).strftime("%Y-%m-%d") for value in sorted(set(dates)))
    )
    out["legal_names"] = out["legal_names"].map(lambda values: "; ".join(sorted(set(map(str, values)))))
    return out


def _family_intervals(
    trading_dates: pd.DatetimeIndex,
    *,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    anchors = major_holiday_anchors(start_year=start_year, end_year=end_year)
    rows: list[dict[str, object]] = []
    for row in anchors.itertuples(index=False):
        interval = _anchor_interval(pd.Timestamp(row.anchor_date), trading_dates)
        if interval is None:
            continue
        prev_trade, next_trade, closed_start, closed_end, closure_length, closure_weekdays = interval
        rows.append(
            {
                "holiday_year": int(row.holiday_year),
                "holiday_family": str(row.holiday_family),
                "legal_name": str(row.legal_name),
                "anchor_date": pd.Timestamp(row.anchor_date),
                "prev_trade": prev_trade,
                "next_trade": next_trade,
                "closed_start": closed_start,
                "closed_end": closed_end,
                "closure_length": closure_length,
                "closure_weekdays": closure_weekdays,
            }
        )
    return _merge_family_intervals(pd.DataFrame(rows))


def _merge_clusters(family_intervals: pd.DataFrame, trading_dates: pd.DatetimeIndex) -> pd.DataFrame:
    if family_intervals.empty:
        return family_intervals
    clusters: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for row in family_intervals.sort_values(["closed_start", "closed_end", "holiday_family"]).to_dict(orient="records"):
        if current is None:
            current = {
                "holiday_year": int(row["holiday_year"]),
                "closed_start": pd.Timestamp(row["closed_start"]),
                "closed_end": pd.Timestamp(row["closed_end"]),
                "holiday_families": {str(row["holiday_family"])},
                "anchor_dates": set(str(row["anchor_dates"]).split(",")),
                "legal_names": {str(row["legal_names"])},
            }
            continue
        if pd.Timestamp(row["closed_start"]) <= pd.Timestamp(current["closed_end"]) + pd.Timedelta(days=1):
            current["closed_start"] = min(pd.Timestamp(current["closed_start"]), pd.Timestamp(row["closed_start"]))
            current["closed_end"] = max(pd.Timestamp(current["closed_end"]), pd.Timestamp(row["closed_end"]))
            current["holiday_families"].add(str(row["holiday_family"]))
            current["anchor_dates"].update(str(row["anchor_dates"]).split(","))
            current["legal_names"].add(str(row["legal_names"]))
        else:
            clusters.append(current)
            current = {
                "holiday_year": int(row["holiday_year"]),
                "closed_start": pd.Timestamp(row["closed_start"]),
                "closed_end": pd.Timestamp(row["closed_end"]),
                "holiday_families": {str(row["holiday_family"])},
                "anchor_dates": set(str(row["anchor_dates"]).split(",")),
                "legal_names": {str(row["legal_names"])},
            }
    if current is not None:
        clusters.append(current)

    out_rows: list[dict[str, object]] = []
    for item in clusters:
        closed_start = pd.Timestamp(item["closed_start"])
        closed_end = pd.Timestamp(item["closed_end"])
        prev_candidates = trading_dates[trading_dates < closed_start]
        next_candidates = trading_dates[trading_dates > closed_end]
        if len(prev_candidates) == 0 or len(next_candidates) == 0:
            continue
        families = sorted(item["holiday_families"])
        family_slug = "_".join(families)
        closure_length = int((closed_end - closed_start).days + 1)
        closure_weekdays = _weekday_closure_count(closed_start, closed_end, trading_dates)
        out_rows.append(
            {
                "holiday_cluster": f"{int(item['holiday_year'])}_{closed_start:%Y%m%d}_{closed_end:%Y%m%d}_{family_slug}",
                "holiday_year": int(item["holiday_year"]),
                "holiday_families": ",".join(families),
                "legal_names": "; ".join(sorted(item["legal_names"])),
                "anchor_dates": ",".join(sorted(date for date in item["anchor_dates"] if date)),
                "closed_start": closed_start,
                "closed_end": closed_end,
                "prev_trade": pd.Timestamp(prev_candidates[-1]),
                "next_trade": pd.Timestamp(next_candidates[0]),
                "closure_length": closure_length,
                "closure_weekdays": closure_weekdays,
            }
        )
    return pd.DataFrame(out_rows)


def build_vietnam_major_holiday_states(
    trading_dates: pd.DatetimeIndex | pd.Series | list[object],
    *,
    start_year: int = 2015,
    end_year: int = 2025,
    offsets: tuple[int, ...] = PRE_POST_OFFSETS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = normalize_trading_dates(trading_dates)
    family_intervals = _family_intervals(dates, start_year=start_year, end_year=end_year)
    clusters = _merge_clusters(family_intervals, dates)
    if clusters.empty:
        return (
            pd.DataFrame(
                columns=[
                    "time",
                    "holiday_state",
                    "holiday_side",
                    "holiday_offset",
                    "holiday_family",
                    "holiday_family_label",
                    "holiday_group",
                    "holiday_cluster",
                    "holiday_year",
                    "closure_length",
                    "closure_weekdays",
                    "closed_start",
                    "closed_end",
                    "prev_trade",
                    "next_trade",
                    "holiday_families",
                    "anchor_dates",
                    "legal_names",
                ]
            ),
            clusters,
        )

    rows: list[dict[str, object]] = []
    for cluster in clusters.to_dict(orient="records"):
        families = [family for family in str(cluster["holiday_families"]).split(",") if family]
        closed_start = pd.Timestamp(cluster["closed_start"])
        closed_end = pd.Timestamp(cluster["closed_end"])
        pre_candidates = dates[dates < closed_start]
        post_candidates = dates[dates > closed_end]
        for family in families:
            for side, candidates in (("pre", pre_candidates), ("post", post_candidates)):
                for offset in offsets:
                    if len(candidates) < offset:
                        continue
                    state_time = pd.Timestamp(candidates[-offset] if side == "pre" else candidates[offset - 1])
                    if not (int(start_year) <= state_time.year <= int(end_year)):
                        continue
                    rows.append(
                        {
                            "time": state_time,
                            "holiday_state": f"{side}_{offset}",
                            "holiday_side": side,
                            "holiday_offset": int(offset),
                            "holiday_family": family,
                            "holiday_family_label": FAMILY_LABELS.get(family, family),
                            "holiday_group": "tet" if family == "tet" else "civil_holidays",
                            "holiday_cluster": cluster["holiday_cluster"],
                            "holiday_year": int(cluster["holiday_year"]),
                            "closure_length": int(cluster["closure_length"]),
                            "closure_weekdays": int(cluster["closure_weekdays"]),
                            "closed_start": closed_start,
                            "closed_end": closed_end,
                            "prev_trade": pd.Timestamp(cluster["prev_trade"]),
                            "next_trade": pd.Timestamp(cluster["next_trade"]),
                            "holiday_families": str(cluster["holiday_families"]),
                            "anchor_dates": str(cluster["anchor_dates"]),
                            "legal_names": str(cluster["legal_names"]),
                        }
                    )
    states = pd.DataFrame(rows)
    if not states.empty:
        states = (
            states.sort_values(["time", "holiday_family", "holiday_state", "holiday_cluster"])
            .drop_duplicates(["time", "holiday_family", "holiday_state", "holiday_cluster"])
            .reset_index(drop=True)
        )
    return states, clusters.sort_values(["closed_start", "holiday_cluster"]).reset_index(drop=True)


def holiday_state_data_checks(
    states: pd.DataFrame,
    trading_dates: pd.DatetimeIndex | pd.Series | list[object],
    *,
    start_year: int = 2015,
    end_year: int = 2025,
) -> dict[str, object]:
    dates = normalize_trading_dates(trading_dates)
    trading_set = set(dates)
    if states.empty:
        return {
            "state_rows": 0,
            "state_dates": 0,
            "min_state_date": None,
            "max_state_date": None,
            "all_state_dates_in_trading_calendar": True,
            "state_rows_with_2026_or_later": 0,
            "state_rows_outside_requested_years": 0,
        }
    state_times = pd.to_datetime(states["time"], errors="coerce").dt.normalize()
    years = state_times.dt.year
    missing = [day for day in state_times.dropna().drop_duplicates().tolist() if day not in trading_set]
    out_of_range = int((~years.between(int(start_year), int(end_year))).sum())
    forward_rows = int((years >= 2026).sum())
    return {
        "state_rows": int(len(states)),
        "state_dates": int(state_times.nunique()),
        "min_state_date": state_times.min().date().isoformat(),
        "max_state_date": state_times.max().date().isoformat(),
        "all_state_dates_in_trading_calendar": len(missing) == 0,
        "missing_trading_calendar_dates": [pd.Timestamp(day).date().isoformat() for day in missing[:20]],
        "state_rows_with_2026_or_later": forward_rows,
        "state_rows_outside_requested_years": out_of_range,
    }
