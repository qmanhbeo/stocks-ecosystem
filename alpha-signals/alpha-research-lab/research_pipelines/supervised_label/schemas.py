"""Typed records used across the supervised labeling pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class SelectedRange:
    start_ts: str
    end_ts: str
    label: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChunkSample:
    ticker: str
    chunk_id: str
    chunk_start: str
    chunk_end: str
    source_file: str
    chunk_length: int
    dataframe: Any = None


@dataclass(slots=True)
class LabelRecord:
    label_id: str
    session_id: str
    ticker: str
    timeframe: str
    chunk_id: str
    chunk_start: str
    chunk_end: str
    source_file: str
    selected_ranges: List[SelectedRange] = field(default_factory=list)
    default_label: int = 0
    confidence: str = "medium"
    notes: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["selected_ranges"] = [item.to_dict() for item in self.selected_ranges]
        return payload


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    created_at: str
    timeframe: str
    split_mode: str
    chunk_length_min: int
    chunk_length_max: int
    random_seed: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BarLabelRow:
    ticker: str
    date: str
    chunk_id: str
    label: int
    confidence: str
    confidence_weight: float
    session_id: str


@dataclass(slots=True)
class SupervisedDatasetRow:
    ticker: str
    date: str
    chunk_id: str
    label: int
    confidence: str
    confidence_weight: float
    features: Dict[str, float]


@dataclass(slots=True)
class PredictionRow:
    ticker: str
    date: str
    signal_prob_buyhold: float
    signal_pred_label: int
    signal_logit: Optional[float] = None
    smoothed_signal_prob: Optional[float] = None
