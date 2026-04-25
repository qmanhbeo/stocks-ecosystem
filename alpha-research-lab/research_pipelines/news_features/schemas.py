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


@dataclass(slots=True)
class OllamaGuardedArticleFeatureRow:
    article_id: str
    ticker: str
    date: str
    published_at: Optional[str]
    url: str
    source: str
    match_source: str
    title_hit: int
    body_hit: int
    local_model_name: str
    ollama_guarded_input_text_length: float
    ollama_guarded_confidence: Optional[float]
    ollama_guarded_event_family: Optional[str]
    ollama_guarded_impact_scope: Optional[str]
    ollama_guarded_source_authority: Optional[str]
    ollama_guarded_is_rumor: Optional[bool]
    local_parse_ok: bool
    local_abstained: bool
    local_error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class OllamaGuardedDailyFeatureRow:
    ticker: str
    date: str
    ollama_guarded_article_count_1d: float
    ollama_guarded_article_count_5d: float
    ollama_guarded_article_count_30d: float
    ollama_guarded_confidence_mean: float
    ollama_guarded_rumor_share: float
    ollama_guarded_event_family_unknown_share: float
    ollama_guarded_event_family_earnings_share: float
    ollama_guarded_event_family_dividend_share: float
    ollama_guarded_event_family_guidance_share: float
    ollama_guarded_event_family_capital_raise_or_debt_share: float
    ollama_guarded_event_family_mna_or_asset_share: float
    ollama_guarded_event_family_regulatory_or_legal_share: float
    ollama_guarded_event_family_other_company_event_share: float
    ollama_guarded_event_family_macro_or_sector_share: float
    ollama_guarded_impact_scope_unknown_share: float
    ollama_guarded_impact_scope_stock_share: float
    ollama_guarded_impact_scope_sector_share: float
    ollama_guarded_impact_scope_market_share: float
    ollama_guarded_impact_scope_macro_share: float
    ollama_guarded_source_authority_unknown_share: float
    ollama_guarded_source_authority_official_share: float
    ollama_guarded_source_authority_media_report_share: float
    ollama_guarded_source_authority_rumor_or_unsourced_share: float
    ollama_guarded_abstain_share: float
    ollama_guarded_parse_fail_share: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
