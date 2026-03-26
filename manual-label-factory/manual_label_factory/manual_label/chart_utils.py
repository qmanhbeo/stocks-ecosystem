"""Chart rendering and selection parsing helpers."""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
from plotly import graph_objects as go
from plotly.subplots import make_subplots

from .state import normalize_ranges, store_to_chunk_sample


def _build_date_rangebreaks(time_values: pd.Series) -> List[Dict[str, object]]:
    timestamps = pd.to_datetime(time_values).dropna().sort_values()
    if timestamps.empty:
        return []

    normalized = timestamps.dt.normalize()
    full_calendar = pd.date_range(normalized.iloc[0], normalized.iloc[-1], freq="D")
    missing_dates = full_calendar.difference(pd.DatetimeIndex(normalized.unique()))
    holiday_breaks = [
        timestamp.strftime("%Y-%m-%d")
        for timestamp in missing_dates
        if timestamp.weekday() < 5
    ]

    rangebreaks: List[Dict[str, object]] = [{"bounds": ["sat", "mon"]}]
    if holiday_breaks:
        rangebreaks.append({"values": holiday_breaks})
    return rangebreaks


def build_chunk_figure(
    chunk_payload: Dict[str, object],
    selected_ranges: Optional[List[Dict[str, object]]] = None,
):
    chunk = store_to_chunk_sample(chunk_payload)
    df = chunk.dataframe.copy()
    if df.empty:
        return go.Figure()
    df["time"] = pd.to_datetime(df["time"])

    has_volume = "volume" in df.columns and df["volume"].notna().any()
    if has_volume:
        figure = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.75, 0.25],
            vertical_spacing=0.04,
        )
    else:
        figure = make_subplots(rows=1, cols=1)

    figure.add_trace(
        go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )
    if has_volume:
        figure.add_trace(go.Bar(x=df["time"], y=df["volume"], name="Volume"), row=2, col=1)

    for item in normalize_ranges(selected_ranges):
        figure.add_vrect(
            x0=item["start_ts"],
            x1=item["end_ts"],
            fillcolor="rgba(33, 150, 243, 0.18)",
            line_width=1,
            line_color="rgba(33, 150, 243, 0.65)",
        )

    figure.update_layout(
        dragmode="drawrect",
        hovermode="x unified",
        template="plotly_white",
        margin={"l": 24, "r": 24, "t": 48, "b": 24},
        newshape={"line": {"color": "rgba(33, 150, 243, 0.8)", "width": 2}},
        title=f"{chunk.ticker} | {chunk.chunk_id}",
    )
    figure.update_xaxes(rangebreaks=_build_date_rangebreaks(df["time"]))
    figure.update_xaxes(title_text="Date", row=2 if has_volume else 1, col=1)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    if has_volume:
        figure.update_yaxes(title_text="Volume", row=2, col=1)
    return figure


def _extract_shape_from_relayout(relayout_data: Dict[str, object]) -> Optional[Dict[str, object]]:
    if not relayout_data:
        return None
    if "shapes" in relayout_data and isinstance(relayout_data["shapes"], list) and relayout_data["shapes"]:
        candidate = relayout_data["shapes"][-1]
        if isinstance(candidate, dict):
            return candidate

    shape_groups: Dict[str, Dict[str, object]] = {}
    for key, value in relayout_data.items():
        if not isinstance(key, str) or not key.startswith("shapes["):
            continue
        index = key.split("]")[0].replace("shapes[", "")
        field_name = key.split("].", 1)[1]
        shape_groups.setdefault(index, {})[field_name] = value
    if not shape_groups:
        return None
    last_index = sorted(shape_groups.keys(), key=lambda token: int(token))[-1]
    return shape_groups[last_index]


def extract_range_from_relayout(
    relayout_data: Optional[Dict[str, object]],
    chunk_payload: Dict[str, object],
) -> Optional[Dict[str, object]]:
    shape = _extract_shape_from_relayout(relayout_data or {})
    if not shape or "x0" not in shape or "x1" not in shape:
        return None

    chunk = store_to_chunk_sample(chunk_payload)
    start_ts = pd.Timestamp(str(shape["x0"]))
    end_ts = pd.Timestamp(str(shape["x1"]))
    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    chunk_start = pd.Timestamp(chunk.chunk_start)
    chunk_end = pd.Timestamp(chunk.chunk_end)
    start_ts = max(start_ts, chunk_start)
    end_ts = min(end_ts, chunk_end)
    if start_ts > end_ts:
        return None

    return {
        "start_ts": start_ts.strftime("%Y-%m-%d"),
        "end_ts": end_ts.strftime("%Y-%m-%d"),
        "label": 1,
    }


def format_ranges_text(selected_ranges: Optional[List[Dict[str, object]]]) -> str:
    ranges = normalize_ranges(selected_ranges)
    if not ranges:
        return "No ranges selected."
    return "\n".join(
        f"{index + 1}. {item['start_ts']} -> {item['end_ts']}"
        for index, item in enumerate(ranges)
    )
