"""Build additive guarded local Ollama news datasets from tagged articles only.

Preferred operator alias: `build_ollama_probe_features.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from time import perf_counter
from typing import Callable, Optional
import urllib.request

import pandas as pd

from data_tools import extract_llm_news_features_legacy as legacy
from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


OllamaGuardedRawResponseFn = Callable[[dict[str, object]], str]

OLLAMA_GUARDED_INPUT_COLUMNS = [
    "article_id",
    "published_at",
    "clean_title",
    "clean_summary",
    "clean_body_text",
]

ARTICLE_COLUMNS = [
    "article_id",
    "ticker",
    "date",
    "published_at",
    "url",
    "source",
    "match_source",
    "title_hit",
    "body_hit",
    "local_model_name",
    "ollama_guarded_input_text_length",
    "ollama_guarded_confidence",
    "ollama_guarded_event_family",
    "ollama_guarded_impact_scope",
    "ollama_guarded_source_authority",
    "ollama_guarded_is_rumor",
    "local_parse_ok",
    "local_abstained",
    "local_error",
]

EVENT_FAMILY_VALUES = (
    "unknown",
    "earnings",
    "dividend",
    "guidance",
    "capital_raise_or_debt",
    "mna_or_asset",
    "regulatory_or_legal",
    "other_company_event",
    "macro_or_sector",
)
IMPACT_SCOPE_VALUES = ("unknown", "stock", "sector", "market", "macro")
SOURCE_AUTHORITY_VALUES = ("unknown", "official", "media_report", "rumor_or_unsourced")
OLLAMA_GUARDED_FIELD_SETS = {
    "full5": ("confidence", "event_family", "impact_scope", "source_authority", "is_rumor"),
    "core3": ("event_family", "impact_scope", "source_authority"),
    "event_rumor": ("confidence", "event_family", "is_rumor"),
    "event_only": ("confidence", "event_family"),
}

EVENT_TYPE_TO_FAMILY = {
    "earnings_beat": "earnings",
    "earnings_miss": "earnings",
    "earnings_preview": "earnings",
    "dividend_announce": "dividend",
    "guidance_raise": "guidance",
    "guidance_cut": "guidance",
    "capital_raise": "capital_raise_or_debt",
    "debt_issue": "capital_raise_or_debt",
    "share_buyback": "capital_raise_or_debt",
    "ipo_listing": "capital_raise_or_debt",
    "merger_acquisition": "mna_or_asset",
    "asset_sale": "mna_or_asset",
    "legal_issue": "regulatory_or_legal",
    "regulatory_approval": "regulatory_or_legal",
    "leadership_change": "other_company_event",
    "partnership": "other_company_event",
    "sector_news": "macro_or_sector",
    "macro_policy": "macro_or_sector",
}

OLLAMA_GUARDED_INPUT_CACHE_VERSION = 1
OLLAMA_GUARDED_CHECKPOINT_VERSION = 1
OLLAMA_GUARDED_SCORE_CACHE_VERSION = 1
OLLAMA_GUARDED_PROMPT_VERSION = 4

SCORE_CACHE_COLUMNS = [
    "article_id",
    "published_at",
    "ollama_guarded_score_key",
    "ollama_guarded_score_signature_hash",
    "local_model_name",
    "ollama_guarded_input_text_length",
    "ollama_guarded_confidence",
    "ollama_guarded_event_family",
    "ollama_guarded_impact_scope",
    "ollama_guarded_source_authority",
    "ollama_guarded_is_rumor",
    "local_parse_ok",
    "local_abstained",
    "local_error",
    "cached_at_utc",
]

SCORE_VALUE_COLUMNS = [
    column
    for column in SCORE_CACHE_COLUMNS
    if column not in {"ollama_guarded_score_key", "ollama_guarded_score_signature_hash", "cached_at_utc"}
]


def _empty_article_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=ARTICLE_COLUMNS)


def _empty_daily_dataframe(config: NewsFeaturesConfig) -> pd.DataFrame:
    return pd.DataFrame(columns=["ticker", "date", *config.ollama_guarded_daily_columns()])


def _nullable_schema(*types: str) -> dict[str, object]:
    return {"type": list(types) + ["null"]}


def _ollama_guarded_fields(config: NewsFeaturesConfig) -> tuple[str, ...]:
    raw = str(getattr(config, "ollama_guarded_field_set", "full5") or "full5").strip()
    return OLLAMA_GUARDED_FIELD_SETS.get(raw, OLLAMA_GUARDED_FIELD_SETS["full5"])


def _ollama_guarded_json_schema(fields: tuple[str, ...] | list[str] | None = None) -> dict[str, object]:
    active_fields = tuple(fields or OLLAMA_GUARDED_FIELD_SETS["full5"])
    properties = {
        "id": {"type": "string"},
        "confidence": _nullable_schema("integer"),
        "event_family": _nullable_schema("string"),
        "impact_scope": _nullable_schema("string"),
        "source_authority": _nullable_schema("string"),
        "is_rumor": _nullable_schema("boolean"),
    }
    return {
        "type": "object",
        "properties": {key: properties[key] for key in ("id", *active_fields)},
        "required": ["id", *active_fields],
        "additionalProperties": True,
    }


def _extract_chat_content(body: dict[str, object]) -> str:
    message = body.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        return "".join(parts)
    return ""


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _truncate_words(text: str, max_words: int) -> str:
    if max_words <= 0:
        return text
    words = str(text or "").split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).strip()


def _compose_input_text(row: pd.Series, max_body_chars: int) -> str:
    title = _clean_text(row.get("clean_title", ""))
    summary = _clean_text(row.get("clean_summary", ""))
    body = _clean_text(row.get("clean_body_text", ""))
    if max_body_chars > 0 and len(body) > max_body_chars:
        body = body[:max_body_chars].rstrip()
    parts = [part for part in [title, summary, body] if part]
    return " ".join(parts).strip()


def _prepare_prompt_text_parts(row: pd.Series, config: NewsFeaturesConfig) -> dict[str, str]:
    title = _clean_text(row.get("clean_title", ""))
    summary = _clean_text(row.get("clean_summary", ""))
    body = _clean_text(row.get("clean_body_text", ""))
    if int(config.ollama_guarded_max_body_words) > 0:
        body = _truncate_words(body, int(config.ollama_guarded_max_body_words))
    if int(config.ollama_guarded_max_body_chars) > 0 and len(body) > int(config.ollama_guarded_max_body_chars):
        body = body[: int(config.ollama_guarded_max_body_chars)].rstrip()
    return {"title": title, "summary": summary, "body": body}


def _article_payload_from_row(row: pd.Series, config: NewsFeaturesConfig) -> dict[str, object]:
    parts = _prepare_prompt_text_parts(row, config)
    input_text = " ".join(part for part in [parts["title"], parts["summary"], parts["body"]] if part).strip()
    return {
        "article_id": str(row.get("article_id", "") or ""),
        "published_at": row.get("published_at"),
        "clean_title": parts["title"],
        "clean_summary": parts["summary"],
        "clean_body_text": parts["body"],
        "input_text": input_text,
        "input_text_length": int(len(input_text)),
    }


def _ollama_guarded_schema_lines(fields: tuple[str, ...] | list[str]) -> list[str]:
    active_fields = tuple(fields)
    lines = ['Keys: "id",' + ",".join(f'"{field}"' for field in active_fields) + "."]
    if "confidence" in active_fields:
        lines.append("confidence: 0,1,2,null.")
    if "event_family" in active_fields:
        lines.append(
            "event_family: earnings(kqkd/loi_nhuan),dividend(co_tuc),guidance(ke_hoach/du_bao),"
            "capital_raise_or_debt(trai_phieu/phat_hanh/tang_von),mna_or_asset(mua_ban/sap_nhap/tai_san/co_phan),"
            "regulatory_or_legal(phap_ly/kien/to_cao/xu_phat),other_company_event,macro_or_sector,unknown,null."
        )
    if "impact_scope" in active_fields:
        lines.append("impact_scope: stock,sector,market,macro,unknown,null.")
    if "source_authority" in active_fields:
        lines.append("source_authority: official,media_report,rumor_or_unsourced,unknown,null.")
    if "is_rumor" in active_fields:
        lines.append("is_rumor: true,false,null.")
    return lines


def _build_ollama_guarded_prompt(article: dict[str, object], config: NewsFeaturesConfig) -> str:
    prompt_variant = str(config.ollama_guarded_prompt_variant)
    prompt_variant = {
        "lean_json_v1": "lean_json_bottom_v1",
        "robust_json_v1": "robust_json_top_v1",
    }.get(prompt_variant, prompt_variant)
    if prompt_variant not in {"lean_json_bottom_v1", "lean_json_top_v1", "robust_json_top_v1"}:
        prompt_variant = "lean_json_bottom_v1"
    fields = _ollama_guarded_fields(config)
    header = (
        ["You are an expert Vietnamese equity-news analyst."]
        if prompt_variant == "robust_json_top_v1"
        else []
    )
    instruction_lines = [
        "Return one compact JSON object for this Vietnamese financial news article.",
        *_ollama_guarded_schema_lines(fields),
    ]
    article_lines = [
        f"ID: {article['article_id']}",
        f"TITLE: {article['clean_title']}",
        f"SUMMARY: {article['clean_summary']}",
        f"BODY: {article['clean_body_text']}",
    ]
    if prompt_variant.endswith("top_v1"):
        return "\n".join([*header, *instruction_lines, "", *article_lines])
    return "\n".join([*header, *article_lines, "", *instruction_lines])


def _call_ollama_chat(prompt: str, config: NewsFeaturesConfig) -> str:
    payload: dict[str, object] = {
        "model": config.ollama_guarded_model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "keep_alive": config.ollama_guarded_keep_alive,
        "options": {
            "temperature": float(config.ollama_guarded_temperature),
            "num_predict": int(config.ollama_guarded_num_predict),
            "num_ctx": int(config.ollama_guarded_num_ctx),
        },
    }
    if config.ollama_guarded_use_schema:
        payload["format"] = _ollama_guarded_json_schema(_ollama_guarded_fields(config))
    request = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(config.ollama_guarded_timeout_seconds)) as response:
        body = json.loads(response.read().decode("utf-8", errors="replace"))
    return _extract_chat_content(body)


def _stop_ollama_model(model_name: str) -> None:
    try:
        subprocess.run(
            ["ollama", "stop", model_name],
            capture_output=True,
            check=False,
            text=True,
        )
    except Exception:
        return


def _blank_inference_result(
    *,
    config: NewsFeaturesConfig,
    input_text_length: int,
    error: Optional[str],
    parse_ok: bool = False,
) -> dict[str, object]:
    return {
        "local_model_name": config.ollama_guarded_model_name,
        "ollama_guarded_input_text_length": int(input_text_length),
        "ollama_guarded_confidence": None,
        "ollama_guarded_event_family": None,
        "ollama_guarded_impact_scope": None,
        "ollama_guarded_source_authority": None,
        "ollama_guarded_is_rumor": None,
        "local_parse_ok": bool(parse_ok),
        "local_abstained": True,
        "local_error": error,
    }


def _norm_guarded_event_family(value: object) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw in EVENT_FAMILY_VALUES:
        return raw
    if raw in EVENT_TYPE_TO_FAMILY:
        return EVENT_TYPE_TO_FAMILY[raw]
    normalized = raw.replace("-", "_").replace("/", "_").replace(" ", "_")
    if normalized in EVENT_FAMILY_VALUES:
        return normalized
    if normalized in EVENT_TYPE_TO_FAMILY:
        return EVENT_TYPE_TO_FAMILY[normalized]
    if "earning" in normalized or "profit" in normalized or "result" in normalized:
        return "earnings"
    if "dividend" in normalized or "co_tuc" in normalized:
        return "dividend"
    if "guidance" in normalized or "plan" in normalized or "forecast" in normalized:
        return "guidance"
    if "debt" in normalized or "bond" in normalized or "raise" in normalized or "issue" in normalized:
        return "capital_raise_or_debt"
    if "merger" in normalized or "acquisition" in normalized or "asset" in normalized or "mna" in normalized:
        return "mna_or_asset"
    if "legal" in normalized or "regulatory" in normalized or "approval" in normalized:
        return "regulatory_or_legal"
    if "macro" in normalized or "sector" in normalized or "policy" in normalized:
        return "macro_or_sector"
    return "other_company_event"


def _norm_guarded_impact_scope(value: object) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    normalized = legacy._norm_impact_scope(value)
    if normalized in {"stock", "sector", "market"}:
        return normalized
    normalized = raw.replace("-", "_").replace("/", "_").replace(" ", "_")
    if normalized in IMPACT_SCOPE_VALUES:
        return normalized
    if "macro" in normalized:
        return "macro"
    if "stock" in normalized or "company" in normalized:
        return "stock"
    if "sector" in normalized or "industry" in normalized:
        return "sector"
    if "market" in normalized or "index" in normalized:
        return "market"
    return "unknown"


def _norm_guarded_source_authority(value: object) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    normalized = legacy._norm_enum(value, legacy.SOURCE_AUTHORITIES)
    if normalized in {"official", "management"}:
        return "official"
    if normalized in {"media_report", "analyst"}:
        return "media_report"
    if normalized == "rumor_source":
        return "rumor_or_unsourced"
    if normalized == "unclear":
        return "unknown"
    normalized = raw.replace("-", "_").replace("/", "_").replace(" ", "_")
    if normalized in SOURCE_AUTHORITY_VALUES:
        return normalized
    if "official" in normalized or "management" in normalized or "regulatory" in normalized:
        return "official"
    if "media" in normalized or "report" in normalized or "analyst" in normalized:
        return "media_report"
    if "rumor" in normalized or "unsourced" in normalized:
        return "rumor_or_unsourced"
    return "unknown"


def _normalize_guarded_response(
    *,
    article_id: str,
    raw_text: str,
    config: NewsFeaturesConfig,
    input_text_length: int,
) -> dict[str, object]:
    parsed = legacy._extract_json_array(str(raw_text or "")) or []
    if not parsed:
        return _blank_inference_result(
            config=config,
            input_text_length=input_text_length,
            error="json_parse_fail",
        )

    raw_obj: Optional[dict[str, object]] = None
    for item in parsed:
        if isinstance(item, dict) and str(item.get("id", "") or "").strip() == article_id:
            raw_obj = item
            break
    if raw_obj is None:
        first = parsed[0]
        raw_obj = first if isinstance(first, dict) else None
    if raw_obj is None:
        return _blank_inference_result(
            config=config,
            input_text_length=input_text_length,
            error="json_parse_fail",
        )

    normalized = legacy._normalize_record(raw_obj, article_id)
    confidence = normalized.get("confidence")
    event_family = _norm_guarded_event_family(raw_obj.get("event_family"))
    if event_family is None:
        event_family = _norm_guarded_event_family(normalized.get("event_type"))
    impact_scope = _norm_guarded_impact_scope(raw_obj.get("impact_scope"))
    if impact_scope is None:
        impact_scope = _norm_guarded_impact_scope(normalized.get("impact_scope"))
    source_authority = _norm_guarded_source_authority(raw_obj.get("source_authority"))
    if source_authority is None:
        source_authority = _norm_guarded_source_authority(normalized.get("source_authority"))
    is_rumor = normalized.get("is_rumor")
    has_signal = any(value is not None for value in [confidence, event_family, impact_scope, source_authority, is_rumor])
    return {
        "local_model_name": config.ollama_guarded_model_name,
        "ollama_guarded_input_text_length": int(input_text_length),
        "ollama_guarded_confidence": float(confidence) if confidence is not None else None,
        "ollama_guarded_event_family": event_family,
        "ollama_guarded_impact_scope": impact_scope,
        "ollama_guarded_source_authority": source_authority,
        "ollama_guarded_is_rumor": is_rumor,
        "local_parse_ok": True,
        "local_abstained": not has_signal,
        "local_error": None,
    }


def _infer_single_article(
    article: dict[str, object],
    *,
    config: NewsFeaturesConfig,
    raw_response_fn: Optional[OllamaGuardedRawResponseFn] = None,
) -> dict[str, object]:
    input_text_length = int(article.get("input_text_length", 0) or 0)
    if input_text_length <= 0:
        return _blank_inference_result(
            config=config,
            input_text_length=0,
            error="empty_article_text",
        )

    try:
        if raw_response_fn is not None:
            raw_text = raw_response_fn(article)
        else:
            prompt = _build_ollama_guarded_prompt(article, config)
            raw_text = _call_ollama_chat(prompt, config)
        return _normalize_guarded_response(
            article_id=str(article.get("article_id", "") or ""),
            raw_text=str(raw_text or ""),
            config=config,
            input_text_length=input_text_length,
        )
    except Exception:
        return _blank_inference_result(
            config=config,
            input_text_length=input_text_length,
            error="ollama_call_error",
        )
    finally:
        if raw_response_fn is None and bool(config.ollama_guarded_stop_after_each_call):
            _stop_ollama_model(config.ollama_guarded_model_name)


def _infer_article_frame(
    article_frame: pd.DataFrame,
    *,
    config: NewsFeaturesConfig,
    raw_response_fn: Optional[OllamaGuardedRawResponseFn] = None,
    log_progress: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_articles = int(len(article_frame))
    progress_interval = 1 if total_articles <= 10 else 100
    for article_index, article_row in enumerate(article_frame.to_dict(orient="records"), start=1):
        article = _article_payload_from_row(pd.Series(article_row), config)
        result = _infer_single_article(article, config=config, raw_response_fn=raw_response_fn)
        rows.append(
            {
                "article_id": str(article["article_id"]),
                "published_at": article.get("published_at"),
                **result,
            }
        )
        if log_progress and (
            article_index == 1
            or article_index % progress_interval == 0
            or article_index == total_articles
        ):
            print(
                f"Ollama guarded scoring {article_index}/{total_articles}; "
                f"abstained_rows={sum(1 for row in rows if row['local_abstained'])}",
                flush=True,
            )
    return pd.DataFrame(rows)


def _prepare_direct_article_inputs(
    normalized_df: pd.DataFrame,
    tagged_df: pd.DataFrame,
    *,
    config: NewsFeaturesConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    normalized = normalized_df.copy()
    for column, default_value in (
        ("published_at", None),
        ("clean_title", ""),
        ("clean_summary", ""),
        ("clean_body_text", ""),
    ):
        if column not in normalized.columns:
            normalized[column] = default_value

    merged = tagged_df.merge(
        normalized[
            [
                "article_id",
                "url",
                "date",
                "source",
                "published_at",
                "clean_title",
                "clean_summary",
                "clean_body_text",
            ]
        ],
        on=["article_id", "url", "date", "source"],
        how="left",
        validate="many_to_one",
    )
    unique_articles = (
        merged[
            [
                "article_id",
                "published_at",
                "clean_title",
                "clean_summary",
                "clean_body_text",
            ]
        ]
        .drop_duplicates(subset=["article_id"])
        .reset_index(drop=True)
    )
    return merged, unique_articles


def build_ollama_guarded_article_feature_dataframe(
    normalized_df: pd.DataFrame,
    tagged_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    raw_response_fn: Optional[OllamaGuardedRawResponseFn] = None,
    log_progress: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    config = config or get_default_config()
    if normalized_df.empty or tagged_df.empty:
        metadata = {
            "local_model_name": config.ollama_guarded_model_name,
            "article_score_rows": 0,
            "unique_article_count": 0,
        }
        return _empty_article_dataframe(), metadata

    merged, unique_articles = _prepare_direct_article_inputs(normalized_df, tagged_df, config=config)
    if unique_articles.empty:
        metadata = {
            "local_model_name": config.ollama_guarded_model_name,
            "article_score_rows": 0,
            "unique_article_count": 0,
        }
        return _empty_article_dataframe(), metadata

    if log_progress:
        print(
            f"Ollama guarded stage 1/2: scoring {len(unique_articles)} tagged unique articles",
            flush=True,
        )
    article_scores = _infer_article_frame(
        unique_articles,
        config=config,
        raw_response_fn=raw_response_fn,
        log_progress=log_progress,
    )
    if article_scores.empty:
        metadata = {
            "local_model_name": config.ollama_guarded_model_name,
            "article_score_rows": 0,
            "unique_article_count": int(len(unique_articles)),
        }
        return _empty_article_dataframe(), metadata

    article_rows = merged[
        [
            "article_id",
            "ticker",
            "date",
            "url",
            "source",
            "match_source",
            "title_hit",
            "body_hit",
        ]
    ].merge(
        article_scores,
        on="article_id",
        how="inner",
        validate="many_to_one",
    )
    article_rows = article_rows[ARTICLE_COLUMNS].sort_values(["ticker", "date", "article_id"]).reset_index(drop=True)
    metadata = {
        "local_model_name": config.ollama_guarded_model_name,
        "article_score_rows": int(len(article_rows)),
        "unique_article_count": int(len(unique_articles)),
    }
    return article_rows, metadata


def build_ollama_guarded_daily_feature_dataframe(
    article_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    *,
    log_progress: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    if article_df.empty:
        return _empty_daily_dataframe(config)

    working = article_df.copy()
    rumor_flags = working["ollama_guarded_is_rumor"].astype("boolean")
    working["_confidence_valid"] = working["ollama_guarded_confidence"].notna().astype(float)
    working["_rumor_valid"] = rumor_flags.notna().astype(float)
    working["_rumor_true"] = rumor_flags.fillna(False).astype(float)
    working["_abstained"] = working["local_abstained"].astype(float)
    working["_parse_fail"] = (~working["local_parse_ok"]).astype(float)
    for event_family in EVENT_FAMILY_VALUES:
        working[f"_event_family__{event_family}"] = (
            working["ollama_guarded_event_family"].fillna("unknown").eq(event_family).astype(float)
        )
    for impact_scope in IMPACT_SCOPE_VALUES:
        working[f"_impact_scope__{impact_scope}"] = (
            working["ollama_guarded_impact_scope"].fillna("unknown").eq(impact_scope).astype(float)
        )
    for authority in SOURCE_AUTHORITY_VALUES:
        working[f"_source_authority__{authority}"] = (
            working["ollama_guarded_source_authority"].fillna("unknown").eq(authority).astype(float)
        )

    if log_progress:
        print(
            f"Ollama guarded daily aggregation: grouping {len(working)} article-ticker rows",
            flush=True,
        )
    aggregate_spec: dict[str, tuple[str, str]] = {
        "ollama_guarded_article_count_1d": ("article_id", "size"),
        "_confidence_sum": ("ollama_guarded_confidence", "sum"),
        "_confidence_count": ("_confidence_valid", "sum"),
        "_rumor_true_sum": ("_rumor_true", "sum"),
        "_rumor_valid_count": ("_rumor_valid", "sum"),
        "_abstain_count": ("_abstained", "sum"),
        "_parse_fail_count": ("_parse_fail", "sum"),
    }
    for event_family in EVENT_FAMILY_VALUES:
        aggregate_spec[f"_event_family__{event_family}__sum"] = (f"_event_family__{event_family}", "sum")
    for impact_scope in IMPACT_SCOPE_VALUES:
        aggregate_spec[f"_impact_scope__{impact_scope}__sum"] = (f"_impact_scope__{impact_scope}", "sum")
    for authority in SOURCE_AUTHORITY_VALUES:
        aggregate_spec[f"_source_authority__{authority}__sum"] = (f"_source_authority__{authority}", "sum")
    daily = working.groupby(["ticker", "date"], as_index=False).agg(**aggregate_spec).sort_values(
        ["ticker", "date"]
    ).reset_index(drop=True)
    daily["ollama_guarded_confidence_mean"] = daily["_confidence_sum"] / daily["_confidence_count"].replace(
        0.0,
        pd.NA,
    )
    daily["ollama_guarded_rumor_share"] = daily["_rumor_true_sum"] / daily["_rumor_valid_count"].replace(
        0.0,
        pd.NA,
    )
    for event_family in EVENT_FAMILY_VALUES:
        daily[f"ollama_guarded_event_family_{event_family}_share"] = (
            daily[f"_event_family__{event_family}__sum"] / daily["ollama_guarded_article_count_1d"]
        )
    for impact_scope in IMPACT_SCOPE_VALUES:
        daily[f"ollama_guarded_impact_scope_{impact_scope}_share"] = (
            daily[f"_impact_scope__{impact_scope}__sum"] / daily["ollama_guarded_article_count_1d"]
        )
    for authority in SOURCE_AUTHORITY_VALUES:
        daily[f"ollama_guarded_source_authority_{authority}_share"] = (
            daily[f"_source_authority__{authority}__sum"] / daily["ollama_guarded_article_count_1d"]
        )
    daily["ollama_guarded_abstain_share"] = daily["_abstain_count"] / daily["ollama_guarded_article_count_1d"]
    daily["ollama_guarded_parse_fail_share"] = daily["_parse_fail_count"] / daily["ollama_guarded_article_count_1d"]
    daily["date"] = pd.to_datetime(daily["date"])

    frames: list[pd.DataFrame] = []
    ticker_groups = list(daily.groupby("ticker", sort=True))
    total_tickers = len(ticker_groups)
    progress_interval = 1 if total_tickers <= 10 else 10
    value_columns = [
        "ollama_guarded_article_count_1d",
        "ollama_guarded_confidence_mean",
        "ollama_guarded_rumor_share",
        "ollama_guarded_abstain_share",
        "ollama_guarded_parse_fail_share",
        *(f"ollama_guarded_event_family_{event_family}_share" for event_family in EVENT_FAMILY_VALUES),
        *(f"ollama_guarded_impact_scope_{impact_scope}_share" for impact_scope in IMPACT_SCOPE_VALUES),
        *(f"ollama_guarded_source_authority_{authority}_share" for authority in SOURCE_AUTHORITY_VALUES),
    ]
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        for column in value_columns:
            group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)
        group["ollama_guarded_article_count_5d"] = (
            group["ollama_guarded_article_count_1d"].rolling(window=5, min_periods=1).sum()
        )
        group["ollama_guarded_article_count_30d"] = (
            group["ollama_guarded_article_count_1d"].rolling(window=30, min_periods=1).sum()
        )
        group = group.reset_index().rename(columns={"index": "date"})
        frames.append(group[["ticker", "date", *config.ollama_guarded_daily_columns()]])
        if log_progress and (
            ticker_index == 1
            or ticker_index % progress_interval == 0
            or ticker_index == total_tickers
        ):
            print(
                f"Ollama guarded daily aggregation progress: processed {ticker_index}/{total_tickers} tickers",
                flush=True,
            )

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def _path_checkpoint_signature(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _stable_hash_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _ollama_guarded_score_signature(config: NewsFeaturesConfig) -> dict[str, object]:
    return {
        "score_cache_version": OLLAMA_GUARDED_SCORE_CACHE_VERSION,
        "prompt_version": OLLAMA_GUARDED_PROMPT_VERSION,
        "ollama_guarded_model_name": config.ollama_guarded_model_name,
        "ollama_guarded_timeout_seconds": int(config.ollama_guarded_timeout_seconds),
        "ollama_guarded_num_predict": int(config.ollama_guarded_num_predict),
        "ollama_guarded_num_ctx": int(config.ollama_guarded_num_ctx),
        "ollama_guarded_temperature": float(config.ollama_guarded_temperature),
        "ollama_guarded_use_schema": bool(config.ollama_guarded_use_schema),
        "ollama_guarded_prompt_variant": str(config.ollama_guarded_prompt_variant),
        "ollama_guarded_field_set": str(config.ollama_guarded_field_set),
        "ollama_guarded_max_body_chars": int(config.ollama_guarded_max_body_chars),
        "ollama_guarded_max_body_words": int(config.ollama_guarded_max_body_words),
    }


def _ollama_guarded_score_signature_hash(score_signature: dict[str, object]) -> str:
    return _stable_hash_payload(score_signature)[:16]


def _ollama_guarded_score_key(article: dict[str, object], score_signature: dict[str, object]) -> str:
    return _stable_hash_payload(
        {
            "score_signature": score_signature,
            "article": {
                "article_id": str(article.get("article_id", "") or ""),
                "published_at": str(article.get("published_at", "") or ""),
                "clean_title": str(article.get("clean_title", "") or ""),
                "clean_summary": str(article.get("clean_summary", "") or ""),
                "clean_body_text": str(article.get("clean_body_text", "") or ""),
            },
        }
    )


def _attach_ollama_guarded_score_keys(
    article_frame: pd.DataFrame,
    *,
    config: NewsFeaturesConfig,
    score_signature: dict[str, object],
    score_signature_hash: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for article_row in article_frame.to_dict(orient="records"):
        article = _article_payload_from_row(pd.Series(article_row), config)
        rows.append(
            {
                **article_row,
                "ollama_guarded_score_key": _ollama_guarded_score_key(article, score_signature),
                "ollama_guarded_score_signature_hash": score_signature_hash,
            }
        )
    return pd.DataFrame(rows)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".json", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _load_json_payload(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _current_utc_timestamp() -> str:
    return pd.Timestamp.utcnow().isoformat()


def _write_ollama_guarded_job_status(
    config: NewsFeaturesConfig,
    *,
    status: str,
    phase: str,
    progress_updates: Optional[dict[str, object]] = None,
    throughput_updates: Optional[dict[str, object]] = None,
    error: Optional[str] = None,
    started_at: Optional[str] = None,
) -> dict[str, object]:
    status_path = config.ollama_guarded_job_status_path()
    existing = _load_json_payload(status_path)
    now = _current_utc_timestamp()
    existing_started_at = str(existing.get("started_at") or "")
    new_started_at = str(started_at or existing_started_at or now)
    reset_existing = bool(started_at is not None and existing_started_at and existing_started_at != new_started_at)
    progress = {} if reset_existing else dict(existing.get("progress") or {})
    progress.update(progress_updates or {})
    throughput = {} if reset_existing else dict(existing.get("throughput") or {})
    throughput.update(throughput_updates or {})
    payload = {
        "job": "ollama_guarded_publish",
        "status": str(status),
        "started_at": new_started_at,
        "updated_at": now,
        "last_heartbeat": now,
        "phase": str(phase),
        "progress": progress,
        "throughput": throughput,
        "artifacts": {
            "status_file": str(status_path),
            "input_articles": str(config.ollama_guarded_input_articles_path()),
            "checkpoint_manifest": str(config.ollama_guarded_checkpoint_manifest_path()),
            "score_cache_root": str(config.ollama_guarded_score_cache_root_dir()),
            "article_dataset": str(config.ollama_guarded_article_features_path()),
            "ticker_day_dataset": str(config.ollama_guarded_ticker_day_features_path()),
        },
    }
    if error is not None:
        payload["error"] = str(error)
    _write_json_atomic(status_path, payload)
    return payload


def _load_ollama_guarded_input_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    return _load_json_payload(config.ollama_guarded_input_manifest_path())


def _write_ollama_guarded_input_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.ollama_guarded_input_manifest_path(), payload)


def _load_ollama_guarded_checkpoint_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    return _load_json_payload(config.ollama_guarded_checkpoint_manifest_path())


def _write_ollama_guarded_checkpoint_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.ollama_guarded_checkpoint_manifest_path(), payload)


def _load_ollama_guarded_score_cache_manifest(
    config: NewsFeaturesConfig,
    score_signature_hash: str,
) -> dict[str, object]:
    return _load_json_payload(config.ollama_guarded_score_cache_manifest_path(score_signature_hash))


def _write_ollama_guarded_score_cache_manifest(
    config: NewsFeaturesConfig,
    score_signature_hash: str,
    payload: dict[str, object],
) -> None:
    _write_json_atomic(config.ollama_guarded_score_cache_manifest_path(score_signature_hash), payload)


def _load_ollama_guarded_score_cache_lookup(
    config: NewsFeaturesConfig,
    *,
    score_signature_hash: str,
) -> dict[str, dict[str, object]]:
    cache_dir = config.ollama_guarded_score_cache_dir(score_signature_hash)
    if not cache_dir.exists():
        return {}
    frames: list[pd.DataFrame] = []
    for shard_path in sorted(cache_dir.glob("score_shard_*.parquet")):
        shard = pd.read_parquet(shard_path)
        if shard.empty:
            continue
        if "ollama_guarded_score_key" not in shard.columns:
            continue
        shard = shard.copy()
        shard["ollama_guarded_score_key"] = shard["ollama_guarded_score_key"].astype(str)
        if "ollama_guarded_score_signature_hash" in shard.columns:
            shard = shard[shard["ollama_guarded_score_signature_hash"].astype(str) == score_signature_hash]
        frames.append(shard)
    if not frames:
        return {}
    cache = pd.concat(frames, ignore_index=True)
    cache = cache.drop_duplicates(subset=["ollama_guarded_score_key"], keep="last")
    return {
        str(row["ollama_guarded_score_key"]): {
            column: row.get(column)
            for column in SCORE_VALUE_COLUMNS
            if column in cache.columns
        }
        for row in cache.to_dict(orient="records")
    }


def _append_ollama_guarded_score_cache_rows(
    config: NewsFeaturesConfig,
    *,
    score_signature_hash: str,
    score_signature: dict[str, object],
    rows: pd.DataFrame,
) -> int:
    if rows.empty:
        return 0
    cache_dir = config.ollama_guarded_score_cache_dir(score_signature_hash)
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_ollama_guarded_score_cache_manifest(config, score_signature_hash)
    existing_shards = sorted(cache_dir.glob("score_shard_*.parquet"))
    shard_count = max(int(manifest.get("shard_count", 0)), len(existing_shards))
    shard_index = shard_count + 1
    cache_rows = rows.copy()
    for column in SCORE_CACHE_COLUMNS:
        if column not in cache_rows.columns:
            cache_rows[column] = None
    cache_rows["article_id"] = cache_rows["article_id"].astype(str)
    cache_rows["ollama_guarded_score_key"] = cache_rows["ollama_guarded_score_key"].astype(str)
    cache_rows["ollama_guarded_score_signature_hash"] = score_signature_hash
    cache_rows["cached_at_utc"] = _current_utc_timestamp()
    cache_rows = cache_rows[SCORE_CACHE_COLUMNS]
    cache_rows = cache_rows.drop_duplicates(subset=["ollama_guarded_score_key"], keep="last").reset_index(drop=True)
    write_parquet_atomic(
        cache_rows,
        config.ollama_guarded_score_cache_shard_path(score_signature_hash, shard_index),
        index=False,
    )
    prior_rows = int(manifest.get("cached_score_rows", 0))
    manifest.update(
        {
            "score_cache_version": OLLAMA_GUARDED_SCORE_CACHE_VERSION,
            "score_signature": score_signature,
            "score_signature_hash": score_signature_hash,
            "shard_count": int(shard_index),
            "cached_score_rows": int(prior_rows + len(cache_rows)),
            "updated_at_utc": _current_utc_timestamp(),
        }
    )
    if "created_at_utc" not in manifest:
        manifest["created_at_utc"] = _current_utc_timestamp()
    _write_ollama_guarded_score_cache_manifest(config, score_signature_hash, manifest)
    return int(len(cache_rows))


def _clear_ollama_guarded_checkpoint_state(config: NewsFeaturesConfig) -> None:
    checkpoint_dir = config.ollama_guarded_checkpoint_dir()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for path in checkpoint_dir.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)


def _ollama_guarded_input_source_signature(
    config: NewsFeaturesConfig,
    *,
    normalized_rows: int,
    tagged_rows: int,
) -> dict[str, object]:
    return {
        "input_cache_version": OLLAMA_GUARDED_INPUT_CACHE_VERSION,
        "normalized_rows": int(normalized_rows),
        "tagged_rows": int(tagged_rows),
        "normalized_input": _path_checkpoint_signature(config.normalized_path()),
        "tagged_input": _path_checkpoint_signature(config.tagged_path()),
        "ollama_guarded_min_article_scope_prob": float(config.ollama_guarded_min_article_scope_prob),
        "ollama_guarded_min_source_type_prob": float(config.ollama_guarded_min_source_type_prob),
        "article_scope_input": _path_checkpoint_signature(config.phobert_article_scope_article_features_path()),
        "source_type_input": _path_checkpoint_signature(config.phobert_source_type_article_features_path()),
    }


def _apply_ollama_guarded_input_gates(config: NewsFeaturesConfig, article_ids: set[str]) -> set[str]:
    kept = set(article_ids)
    min_scope_prob = float(config.ollama_guarded_min_article_scope_prob)
    min_source_prob = float(config.ollama_guarded_min_source_type_prob)
    if min_scope_prob > 0:
        scope_path = config.phobert_article_scope_article_features_path()
        if not scope_path.exists():
            raise FileNotFoundError(f"Missing article-scope gate input: {scope_path}")
        scope = pd.read_parquet(
            scope_path,
            columns=["article_id", "phobert_article_scope_prob_positive"],
        ).drop_duplicates(subset=["article_id"])
        scope["article_id"] = scope["article_id"].astype(str)
        scope_ids = set(
            scope.loc[
                pd.to_numeric(scope["phobert_article_scope_prob_positive"], errors="coerce").fillna(0.0)
                >= min_scope_prob,
                "article_id",
            ].tolist()
        )
        kept.intersection_update(scope_ids)
        print(
            f"Ollama guarded article-scope gate: threshold={min_scope_prob:.3f}, kept={len(kept)}/{len(article_ids)}",
            flush=True,
        )
    if min_source_prob > 0:
        source_path = config.phobert_source_type_article_features_path()
        if not source_path.exists():
            raise FileNotFoundError(f"Missing source-type gate input: {source_path}")
        source = pd.read_parquet(
            source_path,
            columns=["article_id", "phobert_source_type_prob_positive"],
        ).drop_duplicates(subset=["article_id"])
        source["article_id"] = source["article_id"].astype(str)
        source_ids = set(
            source.loc[
                pd.to_numeric(source["phobert_source_type_prob_positive"], errors="coerce").fillna(0.0)
                >= min_source_prob,
                "article_id",
            ].tolist()
        )
        before = len(kept)
        kept.intersection_update(source_ids)
        print(
            f"Ollama guarded source-type gate: threshold={min_source_prob:.3f}, kept={len(kept)}/{before}",
            flush=True,
        )
    return kept


def _ollama_guarded_run_signature(
    config: NewsFeaturesConfig,
    *,
    input_rows: int,
    input_source_signature: dict[str, object],
) -> dict[str, object]:
    score_signature = _ollama_guarded_score_signature(config)
    score_signature_hash = _ollama_guarded_score_signature_hash(score_signature)
    return {
        "checkpoint_version": OLLAMA_GUARDED_CHECKPOINT_VERSION,
        "score_cache_version": OLLAMA_GUARDED_SCORE_CACHE_VERSION,
        "score_signature": score_signature,
        "score_signature_hash": score_signature_hash,
        "ollama_guarded_checkpoint_rows": int(config.ollama_guarded_checkpoint_rows),
        "ollama_guarded_input_rows": int(input_rows),
        "ollama_guarded_input": _path_checkpoint_signature(config.ollama_guarded_input_articles_path()),
        "ollama_guarded_input_source_signature": input_source_signature,
    }


def _legacy_ollama_guarded_run_signature_without_checkpoint_rows(
    config: NewsFeaturesConfig,
    *,
    input_rows: int,
    input_source_signature: dict[str, object],
) -> dict[str, object]:
    return {
        "checkpoint_version": OLLAMA_GUARDED_CHECKPOINT_VERSION,
        "prompt_version": OLLAMA_GUARDED_PROMPT_VERSION,
        "ollama_guarded_model_name": config.ollama_guarded_model_name,
        "ollama_guarded_timeout_seconds": int(config.ollama_guarded_timeout_seconds),
        "ollama_guarded_num_predict": int(config.ollama_guarded_num_predict),
        "ollama_guarded_num_ctx": int(config.ollama_guarded_num_ctx),
        "ollama_guarded_temperature": float(config.ollama_guarded_temperature),
        "ollama_guarded_keep_alive": str(config.ollama_guarded_keep_alive),
        "ollama_guarded_use_schema": bool(config.ollama_guarded_use_schema),
        "ollama_guarded_prompt_variant": str(config.ollama_guarded_prompt_variant),
        "ollama_guarded_field_set": str(config.ollama_guarded_field_set),
        "ollama_guarded_max_body_chars": int(config.ollama_guarded_max_body_chars),
        "ollama_guarded_max_body_words": int(config.ollama_guarded_max_body_words),
        "ollama_guarded_stop_after_each_call": bool(config.ollama_guarded_stop_after_each_call),
        "ollama_guarded_min_article_scope_prob": float(config.ollama_guarded_min_article_scope_prob),
        "ollama_guarded_min_source_type_prob": float(config.ollama_guarded_min_source_type_prob),
        "ollama_guarded_input_rows": int(input_rows),
        "ollama_guarded_input": _path_checkpoint_signature(config.ollama_guarded_input_articles_path()),
        "ollama_guarded_input_source_signature": input_source_signature,
    }


def _checkpoint_score_signature_compatible(
    *,
    checkpoint_manifest: dict[str, object],
    score_signature_hash: str,
    legacy_signature_without_checkpoint_rows: dict[str, object],
) -> bool:
    if not checkpoint_manifest:
        return False
    if str(checkpoint_manifest.get("score_signature_hash") or "") == score_signature_hash:
        return True
    run_signature = checkpoint_manifest.get("run_signature")
    if not isinstance(run_signature, dict):
        return False
    if str(run_signature.get("score_signature_hash") or "") == score_signature_hash:
        return True
    legacy = dict(run_signature)
    legacy.pop("ollama_guarded_checkpoint_rows", None)
    return legacy == legacy_signature_without_checkpoint_rows


def _checkpoint_input_signature_compatible(
    *,
    checkpoint_manifest: dict[str, object],
    run_signature: dict[str, object],
    legacy_signature_without_checkpoint_rows: dict[str, object],
) -> bool:
    existing_run_signature = checkpoint_manifest.get("run_signature")
    if not isinstance(existing_run_signature, dict):
        return False
    if "score_signature_hash" in existing_run_signature:
        return (
            existing_run_signature.get("ollama_guarded_input_rows") == run_signature.get("ollama_guarded_input_rows")
            and existing_run_signature.get("ollama_guarded_input") == run_signature.get("ollama_guarded_input")
            and existing_run_signature.get("ollama_guarded_input_source_signature")
            == run_signature.get("ollama_guarded_input_source_signature")
        )
    legacy = dict(existing_run_signature)
    legacy.pop("ollama_guarded_checkpoint_rows", None)
    return legacy == legacy_signature_without_checkpoint_rows


def _load_checkpoint_score_rows_for_migration(
    *,
    checkpoint_manifest: dict[str, object],
) -> dict[str, dict[str, object]]:
    completed_batches = checkpoint_manifest.get("completed_batches") or {}
    if not isinstance(completed_batches, dict):
        return {}
    frames: list[pd.DataFrame] = []
    for batch_meta in completed_batches.values():
        if not isinstance(batch_meta, dict):
            continue
        shard_path_value = batch_meta.get("shard_path")
        if not shard_path_value or int(batch_meta.get("article_rows", 0)) == 0:
            continue
        shard_path = Path(str(shard_path_value))
        if not shard_path.exists():
            continue
        shard = pd.read_parquet(shard_path)
        if not shard.empty:
            frames.append(shard)
    if not frames:
        return {}
    scores = pd.concat(frames, ignore_index=True)
    scores["article_id"] = scores["article_id"].astype(str)
    scores = scores.drop_duplicates(subset=["article_id"], keep="last")
    return {
        str(row["article_id"]): {
            column: row.get(column)
            for column in SCORE_VALUE_COLUMNS
            if column in scores.columns
        }
        for row in scores.to_dict(orient="records")
    }


def _prepare_ollama_guarded_input_articles_cache(
    *,
    config: NewsFeaturesConfig,
    normalized_file,
    normalized_rows: int,
    tagged: pd.DataFrame,
) -> dict[str, object]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Preparing Ollama guarded input cache requires pyarrow.") from exc

    all_tagged_article_ids = {str(article_id) for article_id in tagged["article_id"].astype(str).tolist()}
    tagged_article_ids = _apply_ollama_guarded_input_gates(config, all_tagged_article_ids)
    source_signature = _ollama_guarded_input_source_signature(
        config,
        normalized_rows=int(normalized_rows),
        tagged_rows=int(len(tagged)),
    )
    input_manifest = _load_ollama_guarded_input_manifest(config)
    input_path = config.ollama_guarded_input_articles_path()
    if input_path.exists() and input_manifest.get("source_signature") == source_signature:
        cached_rows = int(input_manifest.get("input_rows", 0))
        print(
            f"Ollama guarded input cache reuse: input_rows={cached_rows}, "
            f"unique_tagged_articles={len(all_tagged_article_ids)}, gated_articles={len(tagged_article_ids)}",
            flush=True,
        )
        return input_manifest

    print(
        f"Ollama guarded input cache rebuild: scanning normalized_rows={normalized_rows} for "
        f"{len(tagged_article_ids)} gated articles from {len(all_tagged_article_ids)} unique tagged articles",
        flush=True,
    )
    input_schema = pa.schema([(column, pa.string()) for column in OLLAMA_GUARDED_INPUT_COLUMNS])
    writer = None
    temp_input_path: Optional[Path] = None
    input_rows = 0
    scanned_rows = 0
    seen_article_ids: set[str] = set()
    missing_article_ids = set(tagged_article_ids)
    batch_size = max(int(config.ollama_guarded_checkpoint_rows) * 10, 20000)
    progress_interval = 50000
    try:
        with tempfile.NamedTemporaryFile(dir=input_path.parent, suffix=".parquet", delete=False) as handle:
            temp_input_path = Path(handle.name)

        for batch_index, batch in enumerate(
            normalized_file.iter_batches(batch_size=batch_size, columns=OLLAMA_GUARDED_INPUT_COLUMNS),
            start=1,
        ):
            batch_df = batch.to_pandas()
            batch_row_count = int(len(batch_df))
            scanned_rows += batch_row_count
            batch_df["article_id"] = batch_df["article_id"].astype(str)
            batch_df = batch_df[batch_df["article_id"].isin(tagged_article_ids)].copy()
            if not batch_df.empty:
                batch_df = batch_df[~batch_df["article_id"].isin(seen_article_ids)].copy()
                if not batch_df.empty:
                    for column in OLLAMA_GUARDED_INPUT_COLUMNS:
                        batch_df[column] = batch_df[column].where(batch_df[column].notna(), "")
                        batch_df[column] = batch_df[column].astype(str)
                    batch_df = batch_df.drop_duplicates(subset=["article_id"], keep="first").reset_index(drop=True)
                    if not batch_df.empty:
                        table = pa.Table.from_pandas(
                            batch_df[OLLAMA_GUARDED_INPUT_COLUMNS],
                            preserve_index=False,
                            schema=input_schema,
                        )
                        if writer is None:
                            writer = pq.ParquetWriter(temp_input_path, schema=table.schema)
                        writer.write_table(table)
                        written_ids = set(batch_df["article_id"].tolist())
                        seen_article_ids.update(written_ids)
                        missing_article_ids.difference_update(written_ids)
                        input_rows += int(len(batch_df))
            if (
                scanned_rows == batch_row_count
                or scanned_rows % progress_interval == 0
                or scanned_rows >= normalized_rows
            ):
                print(
                    f"Ollama guarded input cache scan {scanned_rows}/{normalized_rows}; "
                    f"matched_input_rows={input_rows}, remaining_missing_articles={len(missing_article_ids)}, "
                    f"batch_index={batch_index}",
                    flush=True,
                )

        if missing_article_ids:
            missing_df = pd.DataFrame(
                [
                    {
                        "article_id": article_id,
                        "published_at": "",
                        "clean_title": "",
                        "clean_summary": "",
                        "clean_body_text": "",
                    }
                    for article_id in sorted(missing_article_ids)
                ],
                columns=OLLAMA_GUARDED_INPUT_COLUMNS,
            )
            table = pa.Table.from_pandas(missing_df, preserve_index=False, schema=input_schema)
            if writer is None:
                writer = pq.ParquetWriter(temp_input_path, schema=table.schema)
            writer.write_table(table)
            input_rows += int(len(missing_df))

        if writer is not None and temp_input_path is not None:
            writer.close()
            writer = None
            temp_input_path.replace(input_path)
        else:
            write_parquet_atomic(pd.DataFrame(columns=OLLAMA_GUARDED_INPUT_COLUMNS), input_path, index=False)
    finally:
        if writer is not None:
            writer.close()
        if temp_input_path is not None and temp_input_path.exists():
            temp_input_path.unlink(missing_ok=True)

    input_manifest = {
        "input_cache_version": OLLAMA_GUARDED_INPUT_CACHE_VERSION,
        "source_signature": source_signature,
        "input_rows": int(input_rows),
        "tagged_unique_article_count": int(len(all_tagged_article_ids)),
        "gated_article_count": int(len(tagged_article_ids)),
        "missing_normalized_article_count": int(len(missing_article_ids)),
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
    }
    _write_ollama_guarded_input_manifest(config, input_manifest)
    print(
        f"Ollama guarded input cache ready: input_rows={input_rows} -> {input_path}",
        flush=True,
    )
    return input_manifest


def _daily_feature_frame_from_state(
    daily_state: dict[tuple[str, str], dict[str, float]],
    config: NewsFeaturesConfig,
    *,
    log_progress: bool = False,
) -> pd.DataFrame:
    if not daily_state:
        return _empty_daily_dataframe(config)

    daily = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "date": date,
                "ollama_guarded_article_count_1d": state["article_count"],
                "ollama_guarded_confidence_mean": (
                    state["confidence_sum"] / state["confidence_count"]
                    if state["confidence_count"] > 0
                    else float("nan")
                ),
                "ollama_guarded_rumor_share": (
                    state["rumor_true_sum"] / state["rumor_valid_count"]
                    if state["rumor_valid_count"] > 0
                    else float("nan")
                ),
                **{
                    f"ollama_guarded_event_family_{event_family}_share": (
                        state.get(f"event_family__{event_family}", 0.0) / state["article_count"]
                    )
                    for event_family in EVENT_FAMILY_VALUES
                },
                **{
                    f"ollama_guarded_impact_scope_{impact_scope}_share": (
                        state.get(f"impact_scope__{impact_scope}", 0.0) / state["article_count"]
                    )
                    for impact_scope in IMPACT_SCOPE_VALUES
                },
                **{
                    f"ollama_guarded_source_authority_{authority}_share": (
                        state.get(f"source_authority__{authority}", 0.0) / state["article_count"]
                    )
                    for authority in SOURCE_AUTHORITY_VALUES
                },
                "ollama_guarded_abstain_share": state["abstain_count"] / state["article_count"],
                "ollama_guarded_parse_fail_share": state["parse_fail_count"] / state["article_count"],
            }
            for (ticker, date), state in daily_state.items()
            if state["article_count"] > 0
        ]
    )
    daily["date"] = pd.to_datetime(daily["date"])
    frames: list[pd.DataFrame] = []
    ticker_groups = list(daily.groupby("ticker", sort=True))
    total_tickers = len(ticker_groups)
    progress_interval = 1 if total_tickers <= 10 else 10
    fill_columns = [
        "ollama_guarded_article_count_1d",
        "ollama_guarded_confidence_mean",
        "ollama_guarded_rumor_share",
        "ollama_guarded_abstain_share",
        "ollama_guarded_parse_fail_share",
        *(f"ollama_guarded_event_family_{event_family}_share" for event_family in EVENT_FAMILY_VALUES),
        *(f"ollama_guarded_impact_scope_{impact_scope}_share" for impact_scope in IMPACT_SCOPE_VALUES),
        *(f"ollama_guarded_source_authority_{authority}_share" for authority in SOURCE_AUTHORITY_VALUES),
    ]
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        for column in fill_columns:
            group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)
        group["ollama_guarded_article_count_5d"] = (
            group["ollama_guarded_article_count_1d"].rolling(window=5, min_periods=1).sum()
        )
        group["ollama_guarded_article_count_30d"] = (
            group["ollama_guarded_article_count_1d"].rolling(window=30, min_periods=1).sum()
        )
        group = group.reset_index().rename(columns={"index": "date"})
        frames.append(group[["ticker", "date", *config.ollama_guarded_daily_columns()]])
        if log_progress and (
            ticker_index == 1
            or ticker_index % progress_interval == 0
            or ticker_index == total_tickers
        ):
            print(
                f"Ollama guarded daily aggregation progress: processed {ticker_index}/{total_tickers} tickers",
                flush=True,
            )
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def _finalize_ollama_guarded_from_checkpoints(
    *,
    config: NewsFeaturesConfig,
    checkpoint_manifest: dict[str, object],
) -> tuple[pd.DataFrame, dict[str, object]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Ollama guarded checkpoint finalization requires pyarrow.") from exc

    article_schema = pa.schema(
        [
            ("article_id", pa.string()),
            ("ticker", pa.string()),
            ("date", pa.string()),
            ("published_at", pa.string()),
            ("url", pa.string()),
            ("source", pa.string()),
            ("match_source", pa.string()),
            ("title_hit", pa.int64()),
            ("body_hit", pa.int64()),
            ("local_model_name", pa.string()),
            ("ollama_guarded_input_text_length", pa.int64()),
            ("ollama_guarded_confidence", pa.float64()),
            ("ollama_guarded_event_family", pa.string()),
            ("ollama_guarded_impact_scope", pa.string()),
            ("ollama_guarded_source_authority", pa.string()),
            ("ollama_guarded_is_rumor", pa.bool_()),
            ("local_parse_ok", pa.bool_()),
            ("local_abstained", pa.bool_()),
            ("local_error", pa.string()),
        ]
    )
    completed_batches = checkpoint_manifest.get("completed_batches") or {}
    batch_items = sorted(completed_batches.items(), key=lambda item: int(item[0]))
    total_batches = len(batch_items)
    progress_interval = 1 if total_batches <= 10 else 25
    daily_state: dict[tuple[str, str], dict[str, float]] = {}
    writer = None
    temp_article_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=config.ollama_guarded_article_features_path().parent,
            suffix=".parquet",
            delete=False,
        ) as handle:
            temp_article_path = Path(handle.name)

        for batch_index, (batch_key, batch_meta) in enumerate(batch_items, start=1):
            shard_path_value = batch_meta.get("shard_path")
            if not shard_path_value or int(batch_meta.get("article_rows", 0)) == 0:
                if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                    print(
                        f"Ollama guarded finalize shard {batch_index}/{total_batches}",
                        flush=True,
                    )
                continue

            shard_path = Path(str(shard_path_value))
            if not shard_path.exists():
                raise FileNotFoundError(f"Missing Ollama guarded checkpoint shard: {shard_path}")
            shard_df = pd.read_parquet(shard_path)
            if not shard_df.empty:
                table = pa.Table.from_pandas(shard_df[ARTICLE_COLUMNS], preserve_index=False, schema=article_schema)
                if writer is None:
                    writer = pq.ParquetWriter(temp_article_path, schema=article_schema)
                writer.write_table(table)

                rumor_flags = shard_df["ollama_guarded_is_rumor"].astype("boolean")
                for event_family in EVENT_FAMILY_VALUES:
                    shard_df[f"_event_family__{event_family}"] = (
                        shard_df["ollama_guarded_event_family"].fillna("unknown").eq(event_family).astype(float)
                    )
                for impact_scope in IMPACT_SCOPE_VALUES:
                    shard_df[f"_impact_scope__{impact_scope}"] = (
                        shard_df["ollama_guarded_impact_scope"].fillna("unknown").eq(impact_scope).astype(float)
                    )
                for authority in SOURCE_AUTHORITY_VALUES:
                    shard_df[f"_source_authority__{authority}"] = (
                        shard_df["ollama_guarded_source_authority"].fillna("unknown").eq(authority).astype(float)
                    )
                grouped = (
                    shard_df.assign(
                        _confidence_valid=shard_df["ollama_guarded_confidence"].notna().astype(float),
                        _rumor_valid=rumor_flags.notna().astype(float),
                        _rumor_true=rumor_flags.fillna(False).astype(float),
                        _abstain_count=shard_df["local_abstained"].astype(float),
                        _parse_fail_count=(~shard_df["local_parse_ok"]).astype(float),
                    )
                    .groupby(["ticker", "date"], as_index=False)
                    .agg(
                        article_count=("article_id", "size"),
                        confidence_sum=("ollama_guarded_confidence", "sum"),
                        confidence_count=("_confidence_valid", "sum"),
                        rumor_true_sum=("_rumor_true", "sum"),
                        rumor_valid_count=("_rumor_valid", "sum"),
                        abstain_count=("_abstain_count", "sum"),
                        parse_fail_count=("_parse_fail_count", "sum"),
                        **{
                            f"event_family__{event_family}": (f"_event_family__{event_family}", "sum")
                            for event_family in EVENT_FAMILY_VALUES
                        },
                        **{
                            f"impact_scope__{impact_scope}": (f"_impact_scope__{impact_scope}", "sum")
                            for impact_scope in IMPACT_SCOPE_VALUES
                        },
                        **{
                            f"source_authority__{authority}": (f"_source_authority__{authority}", "sum")
                            for authority in SOURCE_AUTHORITY_VALUES
                        },
                    )
                )
                for row in grouped.to_dict(orient="records"):
                    key = (str(row["ticker"]), str(row["date"]))
                    state = daily_state.setdefault(
                        key,
                        {
                            "article_count": 0.0,
                            "confidence_sum": 0.0,
                            "confidence_count": 0.0,
                            "rumor_true_sum": 0.0,
                            "rumor_valid_count": 0.0,
                            "abstain_count": 0.0,
                            "parse_fail_count": 0.0,
                            **{f"event_family__{event_family}": 0.0 for event_family in EVENT_FAMILY_VALUES},
                            **{f"impact_scope__{impact_scope}": 0.0 for impact_scope in IMPACT_SCOPE_VALUES},
                            **{
                                f"source_authority__{authority}": 0.0
                                for authority in SOURCE_AUTHORITY_VALUES
                            },
                        },
                    )
                    for field in state:
                        state[field] += float(row[field])

            if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                print(
                    f"Ollama guarded finalize shard {batch_index}/{total_batches}",
                    flush=True,
                )

        if writer is not None and temp_article_path is not None:
            writer.close()
            writer = None
            temp_article_path.replace(config.ollama_guarded_article_features_path())
        else:
            write_parquet_atomic(_empty_article_dataframe(), config.ollama_guarded_article_features_path(), index=False)
    finally:
        if writer is not None:
            writer.close()
        if temp_article_path is not None and temp_article_path.exists():
            temp_article_path.unlink(missing_ok=True)

    daily = _daily_feature_frame_from_state(daily_state, config, log_progress=True)
    write_parquet_atomic(daily, config.ollama_guarded_ticker_day_features_path(), index=False)

    checkpoint_manifest["status"] = "complete"
    checkpoint_manifest["daily_feature_rows"] = int(len(daily))
    checkpoint_manifest["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
    _write_ollama_guarded_checkpoint_manifest(config, checkpoint_manifest)

    for batch_meta in completed_batches.values():
        shard_path_value = batch_meta.get("shard_path")
        if shard_path_value:
            Path(str(shard_path_value)).unlink(missing_ok=True)

    metadata = {
        "local_model_name": checkpoint_manifest.get("local_model_name", config.ollama_guarded_model_name),
        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
        "daily_feature_rows": int(len(daily)),
        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
        "checkpoint_status": str(checkpoint_manifest.get("status", "unknown")),
        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
    }
    return daily, metadata


def build_ollama_guarded_feature_exports(
    config: Optional[NewsFeaturesConfig] = None,
    raw_response_fn: Optional[OllamaGuardedRawResponseFn] = None,
    *,
    checkpoint_batch_limit: Optional[int] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    job_started_at = _current_utc_timestamp()
    overall_start = perf_counter()
    load_start = perf_counter()
    guarded_input_rows = 0
    _write_ollama_guarded_job_status(
        config,
        status="running",
        phase="bootstrap",
        progress_updates={
            "local_model_name": config.ollama_guarded_model_name,
            "num_ctx": int(config.ollama_guarded_num_ctx),
            "num_predict": int(config.ollama_guarded_num_predict),
            "temperature": float(config.ollama_guarded_temperature),
            "prompt_variant": str(config.ollama_guarded_prompt_variant),
            "field_set": str(config.ollama_guarded_field_set),
            "max_body_words": int(config.ollama_guarded_max_body_words),
            "max_body_chars": int(config.ollama_guarded_max_body_chars),
            "min_article_scope_prob": float(config.ollama_guarded_min_article_scope_prob),
            "min_source_type_prob": float(config.ollama_guarded_min_source_type_prob),
            "checkpoint_rows": int(config.ollama_guarded_checkpoint_rows),
        },
        started_at=job_started_at,
    )
    if not config.normalized_path().exists() or not config.tagged_path().exists():
        article_rows = _empty_article_dataframe()
        daily = _empty_daily_dataframe(config)
        metadata = {
            "local_model_name": config.ollama_guarded_model_name,
            "article_score_rows": 0,
            "daily_feature_rows": 0,
            "unique_article_count": 0,
        }
        load_elapsed = perf_counter() - load_start
        write_start = perf_counter()
        write_parquet_atomic(article_rows, config.ollama_guarded_article_features_path(), index=False)
        write_parquet_atomic(daily, config.ollama_guarded_ticker_day_features_path(), index=False)
        write_elapsed = perf_counter() - write_start
        build_elapsed = 0.0
        _write_ollama_guarded_job_status(
            config,
            status="complete",
            phase="empty_inputs",
            progress_updates=metadata,
            started_at=job_started_at,
        )
    else:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError("Streaming Ollama guarded export requires pyarrow.") from exc

        normalized_file = pq.ParquetFile(config.normalized_path())
        normalized_rows = normalized_file.metadata.num_rows
        tagged = pd.read_parquet(config.tagged_path())
        tagged["article_id"] = tagged["article_id"].astype(str)
        tagged_rows = len(tagged)
        load_elapsed = perf_counter() - load_start
        print(
            f"Loaded normalized_rows={normalized_rows} and tagged_rows={tagged_rows} for Ollama guarded lane in {load_elapsed:.1f}s",
            flush=True,
        )
        _write_ollama_guarded_job_status(
            config,
            status="running",
            phase="input_cache",
            progress_updates={
                "normalized_rows": int(normalized_rows),
                "tagged_rows": int(tagged_rows),
            },
            throughput_updates={"phase": "load", "seconds": float(load_elapsed)},
            started_at=job_started_at,
        )

        input_manifest = _prepare_ollama_guarded_input_articles_cache(
            config=config,
            normalized_file=normalized_file,
            normalized_rows=int(normalized_rows),
            tagged=tagged,
        )
        input_file = pq.ParquetFile(config.ollama_guarded_input_articles_path())
        input_rows = int(input_file.metadata.num_rows)
        guarded_input_rows = int(input_rows)
        input_source_signature = dict(input_manifest.get("source_signature") or {})
        print(
            f"Ollama guarded scoring universe: input_rows={input_rows} from {config.ollama_guarded_input_articles_path()}",
            flush=True,
        )
        _write_ollama_guarded_job_status(
            config,
            status="running",
            phase="score",
            progress_updates={
                "ollama_guarded_input_rows": int(input_rows),
                "completed_batches": int((checkpoint_manifest := _load_ollama_guarded_checkpoint_manifest(config)).get("completed_batch_count", 0)),
                "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
            },
            started_at=job_started_at,
        )

        if input_rows == 0:
            _clear_ollama_guarded_checkpoint_state(config)
            daily = _empty_daily_dataframe(config)
            metadata = {
                "local_model_name": config.ollama_guarded_model_name,
                "ollama_guarded_input_rows": 0,
                "article_score_rows": 0,
                "daily_feature_rows": 0,
                "unique_article_count": 0,
                "checkpoint_status": "complete",
                "checkpoint_completed_batches": 0,
                "checkpoint_total_batches": 0,
            }
            build_elapsed = 0.0
            write_start = perf_counter()
            write_parquet_atomic(_empty_article_dataframe(), config.ollama_guarded_article_features_path(), index=False)
            write_parquet_atomic(daily, config.ollama_guarded_ticker_day_features_path(), index=False)
            write_elapsed = perf_counter() - write_start
            _write_ollama_guarded_job_status(
                config,
                status="complete",
                phase="empty_score_universe",
                progress_updates=metadata,
                started_at=job_started_at,
            )
        else:
            score_signature = _ollama_guarded_score_signature(config)
            score_signature_hash = _ollama_guarded_score_signature_hash(score_signature)
            run_signature = _ollama_guarded_run_signature(
                config,
                input_rows=input_rows,
                input_source_signature=input_source_signature,
            )
            legacy_signature_without_checkpoint_rows = _legacy_ollama_guarded_run_signature_without_checkpoint_rows(
                config,
                input_rows=input_rows,
                input_source_signature=input_source_signature,
            )
            checkpoint_manifest = _load_ollama_guarded_checkpoint_manifest(config)
            exact_checkpoint_signature = checkpoint_manifest.get("run_signature") == run_signature
            score_compatible_checkpoint = _checkpoint_score_signature_compatible(
                checkpoint_manifest=checkpoint_manifest,
                score_signature_hash=score_signature_hash,
                legacy_signature_without_checkpoint_rows=legacy_signature_without_checkpoint_rows,
            )
            input_compatible_checkpoint = _checkpoint_input_signature_compatible(
                checkpoint_manifest=checkpoint_manifest,
                run_signature=run_signature,
                legacy_signature_without_checkpoint_rows=legacy_signature_without_checkpoint_rows,
            )
            score_cache_lookup = _load_ollama_guarded_score_cache_lookup(
                config,
                score_signature_hash=score_signature_hash,
            )
            print(
                f"Ollama guarded score cache load: signature={score_signature_hash}, "
                f"cached_rows={len(score_cache_lookup)}",
                flush=True,
            )

            if (
                checkpoint_manifest.get("status") == "complete"
                and score_compatible_checkpoint
                and input_compatible_checkpoint
                and config.ollama_guarded_article_features_path().exists()
                and config.ollama_guarded_ticker_day_features_path().exists()
            ):
                print(
                    "Ollama guarded score output already complete; reusing published datasets",
                    flush=True,
                )
                daily = pd.read_parquet(config.ollama_guarded_ticker_day_features_path())
                metadata = {
                    "local_model_name": checkpoint_manifest.get("local_model_name", config.ollama_guarded_model_name),
                    "ollama_guarded_input_rows": int(input_rows),
                    "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                    "daily_feature_rows": int(len(daily)),
                    "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                    "checkpoint_status": "complete",
                    "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                    "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
                    "total_candidate_rows": int(input_rows),
                    "reused_cached_rows": 0,
                    "cache_miss_rows": 0,
                    "newly_scored_rows": 0,
                    "skipped_completed_rows": int(input_rows),
                    "checkpoint_files_written": 0,
                }
                build_elapsed = 0.0
                write_elapsed = 0.0
            else:
                migrated_checkpoint_scores: dict[str, dict[str, object]] = {}
                if checkpoint_manifest and not exact_checkpoint_signature:
                    if score_compatible_checkpoint and input_compatible_checkpoint:
                        migrated_checkpoint_scores = _load_checkpoint_score_rows_for_migration(
                            checkpoint_manifest=checkpoint_manifest,
                        )
                        print(
                            "Ollama guarded checkpoint cadence changed; "
                            f"migratable_scored_articles={len(migrated_checkpoint_scores)}",
                            flush=True,
                        )
                    elif score_compatible_checkpoint:
                        print(
                            "Ollama guarded input universe changed; reusing row-level score cache only",
                            flush=True,
                        )
                    else:
                        print(
                            "Ollama guarded scoring signature changed; old checkpoints cannot be reused",
                            flush=True,
                        )
                    _clear_ollama_guarded_checkpoint_state(config)
                    checkpoint_manifest = {}
                    exact_checkpoint_signature = False

                total_batches = max(
                    (int(input_rows) + int(config.ollama_guarded_checkpoint_rows) - 1)
                    // int(config.ollama_guarded_checkpoint_rows),
                    1,
                )
                if not checkpoint_manifest:
                    checkpoint_manifest = {
                        "checkpoint_version": OLLAMA_GUARDED_CHECKPOINT_VERSION,
                        "status": "in_progress",
                        "run_signature": run_signature,
                        "score_signature": score_signature,
                        "score_signature_hash": score_signature_hash,
                        "local_model_name": config.ollama_guarded_model_name,
                        "ollama_guarded_input_rows": int(input_rows),
                        "normalized_rows": int(normalized_rows),
                        "tagged_rows": int(tagged_rows),
                        "total_batches": int(total_batches),
                        "completed_batch_count": 0,
                        "article_score_rows": 0,
                        "unique_article_count": 0,
                        "completed_batches": {},
                        "created_at_utc": pd.Timestamp.utcnow().isoformat(),
                    }
                    _write_ollama_guarded_checkpoint_manifest(config, checkpoint_manifest)
                    print(
                        f"Ollama guarded checkpoint start: total_batches={total_batches}, "
                        f"checkpoint_rows={config.ollama_guarded_checkpoint_rows}",
                        flush=True,
                    )
                else:
                    print(
                        "Ollama guarded checkpoint resume: "
                        f"completed_batches={int(checkpoint_manifest.get('completed_batch_count', 0))}/{total_batches}, "
                        f"article_rows={int(checkpoint_manifest.get('article_score_rows', 0))}, "
                        f"unique_articles={int(checkpoint_manifest.get('unique_article_count', 0))}",
                        flush=True,
                    )
                _write_ollama_guarded_job_status(
                    config,
                    status="running",
                    phase="score",
                    progress_updates={
                        "total_batches": int(total_batches),
                        "completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                        "checkpoint_status": str(checkpoint_manifest.get("status", "unknown")),
                        "score_signature_hash": score_signature_hash,
                        "score_cache_rows": int(len(score_cache_lookup)),
                    },
                    started_at=job_started_at,
                )

                build_start = perf_counter()
                tagged = tagged[
                    ["article_id", "ticker", "date", "url", "source", "match_source", "title_hit", "body_hit"]
                ].copy()
                tagged_indexed = tagged.set_index("article_id", drop=False)

                completed_batches = dict(checkpoint_manifest.get("completed_batches") or {})
                article_score_rows = int(checkpoint_manifest.get("article_score_rows", 0))
                unique_article_count = int(checkpoint_manifest.get("unique_article_count", 0))
                processed_input_rows = 0
                processed_new_batches = 0
                progress_interval = max(int(config.ollama_guarded_checkpoint_rows), 1)
                reused_cached_rows = 0
                cache_miss_rows = 0
                newly_scored_rows = 0
                skipped_completed_rows = 0
                migrated_checkpoint_rows = 0
                checkpoint_files_written = 0

                for batch_index, batch in enumerate(
                    input_file.iter_batches(
                        batch_size=int(config.ollama_guarded_checkpoint_rows),
                        columns=OLLAMA_GUARDED_INPUT_COLUMNS,
                    ),
                    start=1,
                ):
                    batch_key = str(batch_index)
                    batch_row_count = int(batch.num_rows)
                    processed_input_rows += batch_row_count
                    existing_meta = completed_batches.get(batch_key)
                    if existing_meta is not None:
                        shard_path_value = existing_meta.get("shard_path")
                        if int(existing_meta.get("article_rows", 0)) == 0 or (
                            shard_path_value and Path(str(shard_path_value)).exists()
                        ):
                            skipped_completed_rows += batch_row_count
                            if (
                                processed_input_rows == batch_row_count
                                or processed_input_rows % progress_interval == 0
                                or processed_input_rows >= input_rows
                            ):
                                print(
                                    f"Ollama guarded input scan {processed_input_rows}/{input_rows}; "
                                    f"unique_articles={unique_article_count}, article_rows={article_score_rows} "
                                    f"(resume skip)",
                                    flush=True,
                                )
                            continue

                    input_batch = batch.to_pandas()
                    input_batch["article_id"] = input_batch["article_id"].astype(str)
                    input_batch = _attach_ollama_guarded_score_keys(
                        input_batch,
                        config=config,
                        score_signature=score_signature,
                        score_signature_hash=score_signature_hash,
                    )
                    batch_unique_articles = int(len(input_batch))
                    batch_article_rows = 0
                    shard_path: Optional[Path] = None

                    batch_score_rows: list[dict[str, object]] = []
                    cache_append_rows: list[dict[str, object]] = []
                    miss_rows: list[dict[str, object]] = []
                    for row in input_batch.to_dict(orient="records"):
                        score_key = str(row["ollama_guarded_score_key"])
                        cached_row = score_cache_lookup.get(score_key)
                        if cached_row is not None:
                            batch_score_rows.append(dict(cached_row))
                            reused_cached_rows += 1
                            continue
                        migrated_row = migrated_checkpoint_scores.get(str(row["article_id"]))
                        if migrated_row is not None:
                            value_row = {
                                column: migrated_row.get(column)
                                for column in SCORE_VALUE_COLUMNS
                            }
                            value_row["article_id"] = str(row["article_id"])
                            if not value_row.get("published_at"):
                                value_row["published_at"] = row.get("published_at")
                            cache_row = {
                                **value_row,
                                "ollama_guarded_score_key": score_key,
                                "ollama_guarded_score_signature_hash": score_signature_hash,
                                "cached_at_utc": _current_utc_timestamp(),
                            }
                            cache_append_rows.append(cache_row)
                            score_cache_lookup[score_key] = value_row
                            batch_score_rows.append(value_row)
                            reused_cached_rows += 1
                            migrated_checkpoint_rows += 1
                            continue
                        miss_rows.append(row)

                    cache_miss_rows += len(miss_rows)
                    if miss_rows:
                        miss_batch = pd.DataFrame(miss_rows)
                        scored_rows = _infer_article_frame(
                            miss_batch[OLLAMA_GUARDED_INPUT_COLUMNS],
                            config=config,
                            raw_response_fn=raw_response_fn,
                            log_progress=False,
                        )
                        if not scored_rows.empty:
                            scored_rows = scored_rows.merge(
                                miss_batch[
                                    [
                                        "article_id",
                                        "ollama_guarded_score_key",
                                        "ollama_guarded_score_signature_hash",
                                    ]
                                ],
                                on="article_id",
                                how="left",
                                validate="one_to_one",
                            )
                            for row in scored_rows.to_dict(orient="records"):
                                value_row = {
                                    column: row.get(column)
                                    for column in SCORE_VALUE_COLUMNS
                                }
                                cache_row = {
                                    **value_row,
                                    "ollama_guarded_score_key": str(row["ollama_guarded_score_key"]),
                                    "ollama_guarded_score_signature_hash": score_signature_hash,
                                    "cached_at_utc": _current_utc_timestamp(),
                                }
                                cache_append_rows.append(cache_row)
                                score_cache_lookup[str(row["ollama_guarded_score_key"])] = value_row
                                batch_score_rows.append(value_row)
                            newly_scored_rows += int(len(scored_rows))

                    if cache_append_rows:
                        _append_ollama_guarded_score_cache_rows(
                            config,
                            score_signature_hash=score_signature_hash,
                            score_signature=score_signature,
                            rows=pd.DataFrame(cache_append_rows),
                        )

                    inference_rows = pd.DataFrame(batch_score_rows)
                    if not inference_rows.empty:
                        for column in SCORE_VALUE_COLUMNS:
                            if column not in inference_rows.columns:
                                inference_rows[column] = None
                        inference_rows = inference_rows[SCORE_VALUE_COLUMNS]
                    if not inference_rows.empty:
                        batch_tagged = tagged_indexed.loc[inference_rows["article_id"].tolist()].reset_index(drop=True)
                        article_rows_batch = batch_tagged.merge(
                            inference_rows,
                            on="article_id",
                            how="inner",
                            validate="many_to_one",
                        )
                        article_rows_batch = article_rows_batch[ARTICLE_COLUMNS]
                        batch_article_rows = int(len(article_rows_batch))
                        if batch_article_rows > 0:
                            shard_path = config.ollama_guarded_checkpoint_shard_path(batch_index)
                            write_parquet_atomic(article_rows_batch, shard_path, index=False)
                            checkpoint_files_written += 1

                    article_score_rows += batch_article_rows
                    unique_article_count += batch_unique_articles
                    completed_batches[batch_key] = {
                        "batch_index": int(batch_index),
                        "input_batch_rows": int(batch_row_count),
                        "matched_unique_articles": int(batch_unique_articles),
                        "article_rows": int(batch_article_rows),
                        "shard_path": str(shard_path) if shard_path is not None else None,
                    }
                    checkpoint_manifest.update(
                        {
                            "status": "in_progress",
                            "run_signature": run_signature,
                            "score_signature": score_signature,
                            "score_signature_hash": score_signature_hash,
                            "local_model_name": config.ollama_guarded_model_name,
                            "completed_batches": completed_batches,
                            "completed_batch_count": int(len(completed_batches)),
                            "article_score_rows": int(article_score_rows),
                            "unique_article_count": int(unique_article_count),
                            "cache_stats": {
                                "total_candidate_rows": int(input_rows),
                                "reused_cached_rows": int(reused_cached_rows),
                                "cache_miss_rows": int(cache_miss_rows),
                                "newly_scored_rows": int(newly_scored_rows),
                                "skipped_completed_rows": int(skipped_completed_rows),
                                "migrated_checkpoint_rows": int(migrated_checkpoint_rows),
                                "checkpoint_files_written": int(checkpoint_files_written),
                            },
                            "last_completed_batch": int(batch_index),
                            "last_updated_utc": pd.Timestamp.utcnow().isoformat(),
                        }
                    )
                    _write_ollama_guarded_checkpoint_manifest(config, checkpoint_manifest)
                    processed_new_batches += 1

                    if (
                        processed_input_rows == batch_row_count
                        or processed_input_rows % progress_interval == 0
                        or processed_input_rows >= input_rows
                    ):
                        elapsed = max(perf_counter() - build_start, 1e-9)
                        print(
                            f"Ollama guarded input scan {processed_input_rows}/{input_rows}; "
                            f"unique_articles={unique_article_count}, article_rows={article_score_rows}, "
                            f"cache_hits={reused_cached_rows}, cache_misses={cache_miss_rows}, "
                            f"newly_scored={newly_scored_rows}",
                            flush=True,
                        )
                        _write_ollama_guarded_job_status(
                            config,
                            status="running",
                            phase="score",
                            progress_updates={
                                "processed_input_rows": int(processed_input_rows),
                                "ollama_guarded_input_rows": int(input_rows),
                                "completed_batches": int(len(completed_batches)),
                                "total_batches": int(total_batches),
                                "article_score_rows": int(article_score_rows),
                                "unique_article_count": int(unique_article_count),
                                "last_completed_batch": int(batch_index),
                                "checkpoint_status": "in_progress",
                                "total_candidate_rows": int(input_rows),
                                "reused_cached_rows": int(reused_cached_rows),
                                "cache_miss_rows": int(cache_miss_rows),
                                "newly_scored_rows": int(newly_scored_rows),
                                "skipped_completed_rows": int(skipped_completed_rows),
                                "migrated_checkpoint_rows": int(migrated_checkpoint_rows),
                                "checkpoint_files_written": int(checkpoint_files_written),
                            },
                            throughput_updates={
                                "phase": "score",
                                "input_rows_per_second": float(processed_input_rows / elapsed),
                                "new_batches": int(processed_new_batches),
                                "elapsed_seconds": float(elapsed),
                            },
                            started_at=job_started_at,
                        )

                    if checkpoint_batch_limit is not None and processed_new_batches >= int(checkpoint_batch_limit):
                        print(
                            f"Ollama guarded checkpoint test stop after {processed_new_batches} new batches",
                            flush=True,
                        )
                        break

                if int(checkpoint_manifest.get("completed_batch_count", 0)) == int(
                    checkpoint_manifest.get("total_batches", total_batches)
                ):
                    print("Ollama guarded checkpoint scoring complete. Finalizing published datasets...", flush=True)
                    _write_ollama_guarded_job_status(
                        config,
                        status="running",
                        phase="finalize",
                        progress_updates={
                            "completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                            "total_batches": int(checkpoint_manifest.get("total_batches", total_batches)),
                            "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                            "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                            "total_candidate_rows": int(input_rows),
                            "reused_cached_rows": int(reused_cached_rows),
                            "cache_miss_rows": int(cache_miss_rows),
                            "newly_scored_rows": int(newly_scored_rows),
                            "skipped_completed_rows": int(skipped_completed_rows),
                            "migrated_checkpoint_rows": int(migrated_checkpoint_rows),
                            "checkpoint_files_written": int(checkpoint_files_written),
                        },
                        started_at=job_started_at,
                    )
                    daily, finalized_metadata = _finalize_ollama_guarded_from_checkpoints(
                        config=config,
                        checkpoint_manifest=checkpoint_manifest,
                    )
                    metadata = dict(finalized_metadata)
                else:
                    daily = _empty_daily_dataframe(config)
                    metadata = {
                        "local_model_name": config.ollama_guarded_model_name,
                        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                        "daily_feature_rows": 0,
                        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                        "checkpoint_status": "in_progress",
                        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", total_batches)),
                    }
                metadata.update(
                    {
                        "total_candidate_rows": int(input_rows),
                        "reused_cached_rows": int(reused_cached_rows),
                        "cache_miss_rows": int(cache_miss_rows),
                        "newly_scored_rows": int(newly_scored_rows),
                        "skipped_completed_rows": int(skipped_completed_rows),
                        "migrated_checkpoint_rows": int(migrated_checkpoint_rows),
                        "checkpoint_files_written": int(checkpoint_files_written),
                        "score_signature_hash": score_signature_hash,
                        "score_cache_rows": int(len(score_cache_lookup)),
                    }
                )

                build_elapsed = perf_counter() - build_start
                write_elapsed = 0.0

    metadata.update(
        {
            "ollama_guarded_input_rows": int(guarded_input_rows),
            "article_score_rows": int(metadata.get("article_score_rows", 0)),
            "daily_feature_rows": int(len(daily)),
        }
    )
    update_manifest(
        config=config,
        ollama_guarded_model_name=str(metadata.get("local_model_name", config.ollama_guarded_model_name)),
        ollama_guarded_article_features_rows=int(metadata.get("article_score_rows", 0)),
        ollama_guarded_ticker_day_features_rows=int(len(daily)),
        ollama_guarded_checkpoint_status=str(
            metadata.get("checkpoint_status", "complete" if len(daily) > 0 else "in_progress")
        ),
        ollama_guarded_checkpoint_completed_batches=int(metadata.get("checkpoint_completed_batches", 0)),
        ollama_guarded_checkpoint_total_batches=int(metadata.get("checkpoint_total_batches", 0)),
        ollama_guarded_input_articles_rows=int(metadata.get("ollama_guarded_input_rows", 0)),
        ollama_guarded_article_features_dataset_path=describe_path(
            config.ollama_guarded_article_features_path(),
            config=config,
        ),
        ollama_guarded_ticker_day_features_dataset_path=describe_path(
            config.ollama_guarded_ticker_day_features_path(),
            config=config,
        ),
        ollama_guarded_input_articles_dataset_path=describe_path(
            config.ollama_guarded_input_articles_path(),
            config=config,
        ),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, build={build_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(
        "Ollama guarded cache summary: "
        f"total_candidate_rows={int(metadata.get('total_candidate_rows', metadata.get('ollama_guarded_input_rows', 0)))}, "
        f"reused_cached_rows={int(metadata.get('reused_cached_rows', 0))}, "
        f"newly_scored_rows={int(metadata.get('newly_scored_rows', 0))}, "
        f"skipped_completed_rows={int(metadata.get('skipped_completed_rows', 0))}, "
        f"checkpoint_files_written={int(metadata.get('checkpoint_files_written', 0))}",
        flush=True,
    )
    print(
        f"Built {int(metadata.get('article_score_rows', 0))} Ollama guarded article rows and {len(daily)} ticker-day rows -> "
        f"{config.ollama_guarded_ticker_day_features_path()}",
        flush=True,
    )
    _write_ollama_guarded_job_status(
        config,
        status=str(metadata.get("checkpoint_status", "complete" if len(daily) > 0 else "in_progress")),
        phase="complete" if str(metadata.get("checkpoint_status", "complete" if len(daily) > 0 else "in_progress")) == "complete" else "score",
        progress_updates=metadata,
        throughput_updates={"phase": "total", "elapsed_seconds": float(overall_elapsed)},
        started_at=job_started_at,
    )
    if raw_response_fn is None and not bool(config.ollama_guarded_stop_after_each_call):
        _stop_ollama_model(config.ollama_guarded_model_name)
    return daily


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build additive guarded local Ollama news datasets.")
    parser.add_argument(
        "--checkpoint-batch-limit",
        type=int,
        default=0,
        help="Stop after N new checkpoint batches for a low-resource canary; 0 means run until complete.",
    )
    parser.add_argument("--field-set", choices=sorted(OLLAMA_GUARDED_FIELD_SETS), default="")
    parser.add_argument("--prompt-variant", default="")
    parser.add_argument("--num-ctx", type=int, default=0)
    parser.add_argument("--num-predict", type=int, default=0)
    parser.add_argument("--max-body-words", type=int, default=-1)
    parser.add_argument("--min-article-scope-prob", type=float, default=-1.0)
    parser.add_argument("--min-source-type-prob", type=float, default=-1.0)
    parser.add_argument("--checkpoint-rows", type=int, default=0)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = get_default_config()
    if args.field_set:
        config.ollama_guarded_field_set = str(args.field_set)
    if args.prompt_variant:
        config.ollama_guarded_prompt_variant = str(args.prompt_variant)
    if int(args.num_ctx) > 0:
        config.ollama_guarded_num_ctx = int(args.num_ctx)
    if int(args.num_predict) > 0:
        config.ollama_guarded_num_predict = int(args.num_predict)
    if int(args.max_body_words) >= 0:
        config.ollama_guarded_max_body_words = int(args.max_body_words)
    if float(args.min_article_scope_prob) >= 0:
        config.ollama_guarded_min_article_scope_prob = float(args.min_article_scope_prob)
    if float(args.min_source_type_prob) >= 0:
        config.ollama_guarded_min_source_type_prob = float(args.min_source_type_prob)
    if int(args.checkpoint_rows) > 0:
        config.ollama_guarded_checkpoint_rows = int(args.checkpoint_rows)
    checkpoint_batch_limit = int(args.checkpoint_batch_limit)
    build_ollama_guarded_feature_exports(
        config=config,
        checkpoint_batch_limit=checkpoint_batch_limit if checkpoint_batch_limit > 0 else None,
    )


if __name__ == "__main__":
    main()
