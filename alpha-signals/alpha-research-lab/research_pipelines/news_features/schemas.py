"""Typed records for the news feature pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass(slots=True)
class RawArticleRecord:
    article_id: str
    source: str
    url: str
    title: str
    summary: str
    body_text: str
    published_at: Optional[str]
    published_at_source: str
    fetched_at: str
    author: Optional[str] = None
    section_name: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedArticleRecord:
    article_id: str
    source: str
    url: str
    title: str
    summary: str
    body_text: str
    clean_title: str
    clean_summary: str
    clean_body_text: str
    published_at: str
    date: str
    author: Optional[str] = None
    section_name: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class TaggedArticleRecord:
    article_id: str
    ticker: str
    date: str
    url: str
    source: str
    match_source: str
    title_hit: int
    body_hit: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class DailyTabularFeatureRow:
    ticker: str
    date: str
    news_article_count_1d: float
    news_title_len_mean: float
    news_body_len_mean: float
    news_articles_with_title_hit: float
    news_articles_with_body_hit: float
    news_unique_urls_1d: float
    news_sentiment_keyword_score_sum: float
    news_sentiment_keyword_score_mean: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class DailyEmbeddingFeatureRow:
    ticker: str
    date: str
    embedding_values: List[float]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
