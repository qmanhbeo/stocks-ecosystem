"""Sample chart chunks for manual labeling."""

from __future__ import annotations

import random
from dataclasses import asdict
from typing import Dict, List, Optional, Set

import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig, get_default_config
from research_pipelines.supervised_label.io_utils import get_ticker_to_path_map, load_market_dataframe, make_relative_to_repo
from research_pipelines.supervised_label.schemas import ChunkSample
from research_pipelines.supervised_label.split_utils import create_or_load_splits, get_split_tickers


def build_chunk_id(ticker: str, chunk_start: str, chunk_end: str, chunk_length: int) -> str:
    return f"{ticker}_{chunk_start}_{chunk_end}_len{chunk_length}"


class ChunkSampler:
    """Random chart chunk sampler restricted to a specific ticker split."""

    def __init__(
        self,
        config: Optional[SupervisedLabelConfig] = None,
        split_name: str = "train",
        seed: Optional[int] = None,
    ) -> None:
        self.config = config or get_default_config()
        self.split_name = split_name
        self.random = random.Random(self.config.random_seed if seed is None else seed)
        create_or_load_splits(config=self.config, overwrite=False)
        self._ticker_paths = get_ticker_to_path_map(config=self.config, timeframe=self.config.timeframe)
        self._data_cache: Dict[str, pd.DataFrame] = {}

    def _load_split_tickers(self) -> List[str]:
        tickers = get_split_tickers(self.split_name, config=self.config)
        if not tickers:
            raise ValueError(f"No tickers found for split '{self.split_name}'. Create split files first.")
        return tickers

    def _load_dataframe(self, ticker: str) -> pd.DataFrame:
        if ticker not in self._data_cache:
            if ticker not in self._ticker_paths:
                raise FileNotFoundError(f"Ticker {ticker} is not present in {self.config.raw_data_dir}")
            self._data_cache[ticker] = load_market_dataframe(self._ticker_paths[ticker])
        return self._data_cache[ticker]

    def _eligible_tickers(self) -> List[str]:
        eligible: List[str] = []
        for ticker in self._load_split_tickers():
            frame = self._load_dataframe(ticker)
            if len(frame) >= max(self.config.min_bars_required, self.config.chunk_length_min):
                eligible.append(ticker)
        if not eligible:
            raise ValueError(
                "No eligible tickers found for chunk sampling. Increase available history or reduce min bars."
            )
        return eligible

    def sample_chunk(
        self,
        skip_labeled_chunk_ids: Optional[Set[str]] = None,
        max_attempts: int = 500,
    ) -> ChunkSample:
        skip_labeled_chunk_ids = skip_labeled_chunk_ids or set()
        eligible_tickers = self._eligible_tickers()

        for _ in range(max_attempts):
            ticker = self.random.choice(eligible_tickers)
            frame = self._load_dataframe(ticker)
            max_length = min(self.config.chunk_length_max, len(frame))
            min_length = min(self.config.chunk_length_min, max_length)
            if max_length < min_length:
                continue
            chunk_length = self.random.randint(min_length, max_length)
            max_start = len(frame) - chunk_length
            if max_start < 0:
                continue
            start_idx = self.random.randint(0, max_start)
            end_idx = start_idx + chunk_length - 1
            chunk_df = frame.iloc[start_idx : end_idx + 1].copy().reset_index(drop=True)
            chunk_start = pd.Timestamp(chunk_df.iloc[0]["time"]).strftime("%Y-%m-%d")
            chunk_end = pd.Timestamp(chunk_df.iloc[-1]["time"]).strftime("%Y-%m-%d")
            chunk_id = build_chunk_id(
                ticker=ticker,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                chunk_length=len(chunk_df),
            )
            if chunk_id in skip_labeled_chunk_ids:
                continue
            return ChunkSample(
                ticker=ticker,
                chunk_id=chunk_id,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                source_file=make_relative_to_repo(self._ticker_paths[ticker], config=self.config),
                chunk_length=len(chunk_df),
                dataframe=chunk_df,
            )

        raise RuntimeError("Unable to sample an unlabeled chunk within the maximum number of attempts.")

    @staticmethod
    def serialize_chunk_sample(chunk: ChunkSample) -> Dict[str, object]:
        payload = asdict(chunk)
        if isinstance(payload.get("dataframe"), pd.DataFrame):
            payload["dataframe"] = payload["dataframe"].to_dict(orient="records")
        return payload
