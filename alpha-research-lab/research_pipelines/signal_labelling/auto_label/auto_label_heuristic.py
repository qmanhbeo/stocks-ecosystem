"""Generate hindsight-assisted range labels from future price-path heuristics."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig, get_default_config
from research_pipelines.supervised_label.io_utils import get_ticker_to_path_map, load_market_dataframe, make_relative_to_repo
from research_pipelines.supervised_label.schemas import ChunkSample, LabelRecord, SelectedRange
from research_pipelines.supervised_label.split_utils import create_or_load_splits, get_split_tickers
from research_pipelines.supervised_label.core.chunk_sampler import build_chunk_id
from research_pipelines.supervised_label.core.label_storage import (
    append_label_record,
    create_session_record,
    utc_now_iso,
)
from research_pipelines.supervised_label.core.validation import iter_label_records


@dataclass(slots=True)
class AutoLabelSummary:
    session_id: str
    split_name: str
    tickers_seen: int
    eligible_tickers: int
    scanned_chunks: int
    labeled_chunks: int
    skipped_existing_chunks: int
    skipped_empty_chunks: int
    total_positive_ranges: int


def _current_max_label_number(labels_jsonl_path: Path) -> int:
    max_number = 0
    for _, record in iter_label_records(labels_jsonl_path):
        raw_label_id = str(record.get("label_id", ""))
        if not raw_label_id.startswith("lbl_"):
            continue
        suffix = raw_label_id.replace("lbl_", "", 1)
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return max_number


def _compute_forward_metrics(close: Sequence[float], horizon: int) -> pd.DataFrame:
    close_values = np.asarray(close, dtype=float)
    total = len(close_values)
    forward_return = np.full(total, np.nan, dtype=float)
    forward_drawdown = np.full(total, np.nan, dtype=float)

    if horizon <= 0:
        raise ValueError("horizon must be positive")

    for idx in range(total):
        end_idx = idx + 1 + horizon
        if end_idx > total:
            continue
        future_path = close_values[idx + 1 : end_idx]
        if future_path.size == 0:
            continue
        entry_price = close_values[idx]
        forward_return[idx] = (future_path[-1] / entry_price) - 1.0
        forward_drawdown[idx] = (future_path.min() / entry_price) - 1.0

    return pd.DataFrame(
        {
            "forward_return": forward_return,
            "forward_drawdown": forward_drawdown,
        }
    )


def _build_positive_mask(
    frame: pd.DataFrame,
    horizon: int,
    min_forward_return: float,
    max_forward_drawdown: float,
    benchmark_forward_return: Optional[pd.Series] = None,
    min_excess_return: float = 0.0,
) -> pd.DataFrame:
    metrics = _compute_forward_metrics(frame["close"], horizon=horizon)
    labeled = frame.copy().reset_index(drop=True)
    labeled["forward_return"] = metrics["forward_return"]
    labeled["forward_drawdown"] = metrics["forward_drawdown"]

    if benchmark_forward_return is not None:
        labeled["benchmark_forward_return"] = benchmark_forward_return.reset_index(drop=True)
        labeled["forward_excess_return"] = labeled["forward_return"] - labeled["benchmark_forward_return"]
    else:
        labeled["benchmark_forward_return"] = np.nan
        labeled["forward_excess_return"] = np.nan

    positive_mask = labeled["forward_return"].ge(min_forward_return) & labeled["forward_drawdown"].ge(max_forward_drawdown)
    if benchmark_forward_return is not None:
        positive_mask &= labeled["forward_excess_return"].ge(min_excess_return)
    labeled["positive_label"] = positive_mask.fillna(False).astype(bool)
    return labeled


def _contiguous_positive_ranges(chunk_df: pd.DataFrame, min_range_bars: int) -> List[SelectedRange]:
    if "positive_label" not in chunk_df.columns:
        raise ValueError("chunk_df must contain a positive_label column")

    ranges: List[SelectedRange] = []
    current_start: Optional[int] = None
    flags = chunk_df["positive_label"].astype(bool).tolist()
    dates = pd.to_datetime(chunk_df["time"])

    for idx, is_positive in enumerate(flags):
        if is_positive and current_start is None:
            current_start = idx
            continue
        if is_positive:
            continue
        if current_start is None:
            continue
        current_end = idx - 1
        if (current_end - current_start + 1) >= min_range_bars:
            ranges.append(
                SelectedRange(
                    start_ts=dates.iloc[current_start].strftime("%Y-%m-%d"),
                    end_ts=dates.iloc[current_end].strftime("%Y-%m-%d"),
                    label=1,
                )
            )
        current_start = None

    if current_start is not None:
        current_end = len(flags) - 1
        if (current_end - current_start + 1) >= min_range_bars:
            ranges.append(
                SelectedRange(
                    start_ts=dates.iloc[current_start].strftime("%Y-%m-%d"),
                    end_ts=dates.iloc[current_end].strftime("%Y-%m-%d"),
                    label=1,
                )
            )

    return ranges


def _iter_sequential_chunks(
    frame: pd.DataFrame,
    chunk_length: int,
    stride: int,
    min_chunk_length: int,
) -> Iterable[pd.DataFrame]:
    if chunk_length <= 0:
        raise ValueError("chunk_length must be positive")
    if stride <= 0:
        raise ValueError("stride must be positive")

    total = len(frame)
    for start_idx in range(0, total, stride):
        end_idx = min(total, start_idx + chunk_length)
        chunk_df = frame.iloc[start_idx:end_idx].copy().reset_index(drop=True)
        if len(chunk_df) < min_chunk_length:
            continue
        yield chunk_df


def _load_benchmark_forward_returns(
    benchmark_ticker: str,
    ticker_paths: Dict[str, Path],
    horizon: int,
) -> pd.DataFrame:
    normalized_benchmark = str(benchmark_ticker).upper()
    if normalized_benchmark not in ticker_paths:
        raise FileNotFoundError(f"Benchmark ticker '{normalized_benchmark}' was not found in stock data.")

    benchmark_df = load_market_dataframe(ticker_paths[normalized_benchmark]).reset_index(drop=True)
    benchmark_metrics = _compute_forward_metrics(benchmark_df["close"], horizon=horizon)
    return pd.DataFrame(
        {
            "time": benchmark_df["time"],
            "benchmark_forward_return": benchmark_metrics["forward_return"],
        }
    )


def generate_auto_labels(
    config: Optional[SupervisedLabelConfig] = None,
    *,
    split_name: str = "train",
    chunk_length: Optional[int] = None,
    stride: Optional[int] = None,
    horizon: int = 20,
    min_forward_return: float = 0.08,
    max_forward_drawdown: float = -0.05,
    min_range_bars: int = 3,
    benchmark_ticker: Optional[str] = None,
    min_excess_return: float = 0.0,
    confidence: str = "medium",
    skip_existing: bool = True,
) -> AutoLabelSummary:
    config = config or get_default_config()
    create_or_load_splits(config=config, overwrite=False)
    ticker_paths = get_ticker_to_path_map(config=config, timeframe=config.timeframe)
    tickers = get_split_tickers(split_name, config=config)

    if not tickers:
        raise ValueError(f"No tickers found for split '{split_name}'.")

    resolved_chunk_length = int(chunk_length or config.default_chunk_length)
    resolved_stride = int(stride or resolved_chunk_length)
    min_chunk_length = min(config.chunk_length_min, resolved_chunk_length)
    existing_chunk_ids = set()
    if skip_existing:
        from research_pipelines.supervised_label.core.label_storage import list_labeled_chunk_ids

        existing_chunk_ids = list_labeled_chunk_ids(config=config)

    benchmark_forward_df: Optional[pd.DataFrame] = None
    if benchmark_ticker:
        benchmark_forward_df = _load_benchmark_forward_returns(
            benchmark_ticker=benchmark_ticker,
            ticker_paths=ticker_paths,
            horizon=horizon,
        )

    session = create_session_record(config=config)
    next_label_number = _current_max_label_number(config.labels_jsonl_path) + 1

    tickers_seen = 0
    eligible_tickers = 0
    scanned_chunks = 0
    labeled_chunks = 0
    skipped_existing_chunks = 0
    skipped_empty_chunks = 0
    total_positive_ranges = 0

    for ticker in tickers:
        tickers_seen += 1
        path = ticker_paths.get(str(ticker).upper())
        if path is None:
            continue
        frame = load_market_dataframe(path).reset_index(drop=True)
        if len(frame) < max(min_chunk_length, horizon + 1):
            continue
        eligible_tickers += 1

        benchmark_forward_return: Optional[pd.Series] = None
        if benchmark_forward_df is not None:
            benchmark_aligned = frame[["time"]].merge(benchmark_forward_df, on="time", how="left")
            benchmark_forward_return = benchmark_aligned["benchmark_forward_return"]

        labeled_frame = _build_positive_mask(
            frame=frame,
            horizon=horizon,
            min_forward_return=min_forward_return,
            max_forward_drawdown=max_forward_drawdown,
            benchmark_forward_return=benchmark_forward_return,
            min_excess_return=min_excess_return,
        )

        source_file = make_relative_to_repo(path, config=config)
        for chunk_df in _iter_sequential_chunks(
            labeled_frame,
            chunk_length=resolved_chunk_length,
            stride=resolved_stride,
            min_chunk_length=min_chunk_length,
        ):
            scanned_chunks += 1
            chunk_start = pd.Timestamp(chunk_df.iloc[0]["time"]).strftime("%Y-%m-%d")
            chunk_end = pd.Timestamp(chunk_df.iloc[-1]["time"]).strftime("%Y-%m-%d")
            chunk_id = build_chunk_id(
                ticker=str(ticker).upper(),
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                chunk_length=len(chunk_df),
            )
            if chunk_id in existing_chunk_ids:
                skipped_existing_chunks += 1
                continue

            selected_ranges = _contiguous_positive_ranges(chunk_df, min_range_bars=min_range_bars)
            if not selected_ranges:
                skipped_empty_chunks += 1
                continue

            positive_rows = chunk_df.loc[chunk_df["positive_label"]].copy()
            notes = (
                "heuristic_auto_label "
                f"horizon={horizon} "
                f"min_forward_return={min_forward_return:.4f} "
                f"max_forward_drawdown={max_forward_drawdown:.4f}"
            )
            if benchmark_ticker:
                median_excess = float(positive_rows["forward_excess_return"].median())
                notes += (
                    f" benchmark_ticker={str(benchmark_ticker).upper()} "
                    f"min_excess_return={min_excess_return:.4f} "
                    f"median_excess_return={median_excess:.4f}"
                )
            median_return = float(positive_rows["forward_return"].median())
            median_drawdown = float(positive_rows["forward_drawdown"].median())
            notes += f" median_forward_return={median_return:.4f} median_forward_drawdown={median_drawdown:.4f}"

            chunk_sample = ChunkSample(
                ticker=str(ticker).upper(),
                chunk_id=chunk_id,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                source_file=source_file,
                chunk_length=len(chunk_df),
                dataframe=chunk_df,
            )
            record = LabelRecord(
                label_id=f"lbl_{next_label_number:06d}",
                session_id=session.session_id,
                ticker=chunk_sample.ticker,
                timeframe=config.timeframe,
                chunk_id=chunk_sample.chunk_id,
                chunk_start=chunk_sample.chunk_start,
                chunk_end=chunk_sample.chunk_end,
                source_file=chunk_sample.source_file,
                ticker_split=str(split_name).lower(),
                selected_ranges=selected_ranges,
                default_label=config.default_label,
                confidence=confidence,
                notes=notes,
                created_at=utc_now_iso(),
            )
            append_label_record(record, config=config)
            next_label_number += 1
            existing_chunk_ids.add(chunk_id)
            labeled_chunks += 1
            total_positive_ranges += len(selected_ranges)

    return AutoLabelSummary(
        session_id=session.session_id,
        split_name=split_name,
        tickers_seen=tickers_seen,
        eligible_tickers=eligible_tickers,
        scanned_chunks=scanned_chunks,
        labeled_chunks=labeled_chunks,
        skipped_existing_chunks=skipped_existing_chunks,
        skipped_empty_chunks=skipped_empty_chunks,
        total_positive_ranges=total_positive_ranges,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto-generate hindsight-assisted heuristic labels.")
    parser.add_argument("--split", default="train", choices=("train", "val", "test"), help="Ticker split to label.")
    parser.add_argument("--chunk-length", type=int, default=None, help="Sequential chunk length. Defaults to config.")
    parser.add_argument(
        "--stride",
        type=int,
        default=None,
        help="Sequential chunk stride. Defaults to chunk length for non-overlapping chunks.",
    )
    parser.add_argument("--horizon", type=int, default=20, help="Forward bar horizon used to score favorable regions.")
    parser.add_argument(
        "--min-forward-return",
        type=float,
        default=0.08,
        help="Minimum forward close-to-close return required for a positive label.",
    )
    parser.add_argument(
        "--max-forward-drawdown",
        type=float,
        default=-0.05,
        help="Worst tolerated forward drawdown. Example: -0.05 means no worse than -5%%.",
    )
    parser.add_argument(
        "--min-range-bars",
        type=int,
        default=3,
        help="Minimum contiguous positive bars required to keep a selected range.",
    )
    parser.add_argument(
        "--benchmark-ticker",
        type=str,
        default=None,
        help="Optional benchmark ticker for excess-return filtering, for example VNINDEX.",
    )
    parser.add_argument(
        "--min-excess-return",
        type=float,
        default=0.0,
        help="Minimum forward outperformance versus the benchmark when benchmark_ticker is used.",
    )
    parser.add_argument(
        "--confidence",
        choices=("low", "medium", "high"),
        default="medium",
        help="Confidence tag written into saved label records.",
    )
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Append even when the chunk_id already exists in the labels JSONL.",
    )
    parser.add_argument(
        "--labels-jsonl-path",
        type=Path,
        default=None,
        help="Optional override output JSONL path so auto labels can live beside manual labels.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = get_default_config()
    if args.labels_jsonl_path is not None:
        config.labels_jsonl_path = Path(args.labels_jsonl_path)
        config.labels_dir = config.labels_jsonl_path.parent
        config.ensure_directories()

    summary = generate_auto_labels(
        config=config,
        split_name=args.split,
        chunk_length=args.chunk_length,
        stride=args.stride,
        horizon=args.horizon,
        min_forward_return=args.min_forward_return,
        max_forward_drawdown=args.max_forward_drawdown,
        min_range_bars=args.min_range_bars,
        benchmark_ticker=args.benchmark_ticker,
        min_excess_return=args.min_excess_return,
        confidence=args.confidence,
        skip_existing=not args.allow_duplicates,
    )

    print(f"session_id={summary.session_id}")
    print(f"split={summary.split_name}")
    print(f"tickers_seen={summary.tickers_seen}")
    print(f"eligible_tickers={summary.eligible_tickers}")
    print(f"scanned_chunks={summary.scanned_chunks}")
    print(f"labeled_chunks={summary.labeled_chunks}")
    print(f"skipped_existing_chunks={summary.skipped_existing_chunks}")
    print(f"skipped_empty_chunks={summary.skipped_empty_chunks}")
    print(f"total_positive_ranges={summary.total_positive_ranges}")
    print(f"labels_jsonl={config.labels_jsonl_path}")


if __name__ == "__main__":
    main()
