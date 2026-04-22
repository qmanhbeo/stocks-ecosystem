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


@dataclass(slots=True)
class PhoBertArticleSentimentRow:
    article_id: str
    ticker: str
    date: str
    published_at: Optional[str]
    url: str
    source: str
    match_source: str
    title_hit: int
    body_hit: int
    phobert_model_id: str
    phobert_input_text_length: float
    phobert_segmented_text_length: float
    phobert_predicted_label: str
    phobert_confidence: float
    phobert_prob_neg: float
    phobert_prob_neu: float
    phobert_prob_pos: float
    phobert_sentiment_score: float
    phobert_sentiment_conf_weighted: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class PhoBertDailyFeatureRow:
    ticker: str
    date: str
    phobert_article_count_1d: float
    phobert_sentiment_score_mean: float
    phobert_sentiment_score_sum: float
    phobert_sentiment_conf_weighted_mean: float
    phobert_sentiment_conf_weighted_sum: float
    phobert_prob_pos_mean: float
    phobert_prob_neu_mean: float
    phobert_prob_neg_mean: float
    phobert_pos_share: float
    phobert_neu_share: float
    phobert_neg_share: float
    phobert_article_count_5d: float
    phobert_article_count_30d: float
    phobert_sentiment_5d: float
    phobert_sentiment_30d: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
