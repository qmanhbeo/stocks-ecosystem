"""State serialization helpers for the labeling UI."""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from manual_label_factory.schemas import ChunkSample


def chunk_sample_to_store(chunk: ChunkSample) -> Dict[str, object]:
    dataframe = chunk.dataframe.copy()
    if "time" in dataframe.columns:
        dataframe["time"] = pd.to_datetime(dataframe["time"]).dt.strftime("%Y-%m-%d")
    return {
        "ticker": chunk.ticker,
        "chunk_id": chunk.chunk_id,
        "chunk_start": chunk.chunk_start,
        "chunk_end": chunk.chunk_end,
        "source_file": chunk.source_file,
        "chunk_length": chunk.chunk_length,
        "dataframe": dataframe.to_dict(orient="records"),
    }


def store_to_chunk_sample(payload: Dict[str, object]) -> ChunkSample:
    dataframe = pd.DataFrame(payload.get("dataframe", []))
    if not dataframe.empty and "time" in dataframe.columns:
        dataframe["time"] = pd.to_datetime(dataframe["time"])
    return ChunkSample(
        ticker=str(payload["ticker"]),
        chunk_id=str(payload["chunk_id"]),
        chunk_start=str(payload["chunk_start"]),
        chunk_end=str(payload["chunk_end"]),
        source_file=str(payload["source_file"]),
        chunk_length=int(payload["chunk_length"]),
        dataframe=dataframe,
    )


def normalize_ranges(ranges: Optional[List[Dict[str, object]]]) -> List[Dict[str, object]]:
    normalized: List[Dict[str, object]] = []
    seen = set()
    for item in ranges or []:
        start_ts = pd.Timestamp(str(item["start_ts"])).strftime("%Y-%m-%d")
        end_ts = pd.Timestamp(str(item["end_ts"])).strftime("%Y-%m-%d")
        if start_ts > end_ts:
            start_ts, end_ts = end_ts, start_ts
        key = (start_ts, end_ts)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"start_ts": start_ts, "end_ts": end_ts, "label": int(item.get("label", 1))})
    normalized.sort(key=lambda item: (item["start_ts"], item["end_ts"]))
    return normalized


def progress_state(saved: int = 0, skipped: int = 0, viewed: int = 0) -> Dict[str, int]:
    return {"saved": int(saved), "skipped": int(skipped), "viewed": int(viewed)}
