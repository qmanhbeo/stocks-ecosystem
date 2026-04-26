"""Low-resource prompt probes for the residual Ollama guarded lane."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess
import tempfile
from time import perf_counter
from typing import Optional
import urllib.request

import pandas as pd

from data_tools import extract_llm_news_features_legacy as legacy
from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.core.build_ollama_guarded_features import (
    OLLAMA_GUARDED_FIELD_SETS,
    EVENT_TYPE_TO_FAMILY,
    _prepare_ollama_guarded_input_articles_cache,
    _extract_chat_content,
    _norm_guarded_event_family,
    _norm_guarded_impact_scope,
    _norm_guarded_source_authority,
    _normalize_guarded_response,
    _ollama_guarded_json_schema,
    _stop_ollama_model,
    _truncate_words,
)


@dataclass(frozen=True)
class PromptVariant:
    name: str
    header: str
    output_format: str
    field_set: str
    num_ctx: int
    body_words: int
    schema_position: str
    negative_constraint: str
    anchor: str
    few_shot: bool
    prefill: bool
    temperature: float
    use_schema: bool


CORE_FIELDS = ["event_family", "impact_scope", "source_authority", "is_rumor"]
FULL_FIELDS = ["confidence", *CORE_FIELDS]
CURATED_SAMPLE_GOLD = {
    "8002e4554e3b25a6": {
        "article_id": "8002e4554e3b25a6",
        "confidence": 2,
        "event_family": "capital_raise_or_debt",
        "impact_scope": "stock",
        "source_authority": "official",
        "is_rumor": False,
    },
    "140b663d010812f9": {
        "article_id": "140b663d010812f9",
        "confidence": 1,
        "event_family": "macro_or_sector",
        "impact_scope": "sector",
        "source_authority": "media_report",
        "is_rumor": False,
    },
    "899a7c579aaf8b49": {
        "article_id": "899a7c579aaf8b49",
        "confidence": 2,
        "event_family": "dividend",
        "impact_scope": "stock",
        "source_authority": "official",
        "is_rumor": False,
    },
    "775ab17877b04e18": {
        "article_id": "775ab17877b04e18",
        "confidence": 2,
        "event_family": "guidance",
        "impact_scope": "stock",
        "source_authority": "official",
        "is_rumor": False,
    },
}
CURATED_SAMPLE_RAW_DATES = {
    "8002e4554e3b25a6": "2026-01-01",
    "140b663d010812f9": "2026-01-09",
    "899a7c579aaf8b49": "2026-01-06",
    "775ab17877b04e18": "2026-01-01",
}


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


def _field_list(field_set: str) -> list[str]:
    return list(OLLAMA_GUARDED_FIELD_SETS.get(field_set, OLLAMA_GUARDED_FIELD_SETS["full5"]))


def _json_schema_for_fields(fields: list[str]) -> dict[str, object]:
    schema = _ollama_guarded_json_schema()
    schema["required"] = ["id", *fields]
    schema["properties"] = {
        key: value
        for key, value in dict(schema["properties"]).items()
        if key in {"id", *fields}
    }
    return schema


def _schema_text(fields: list[str], output_format: str) -> str:
    if output_format == "csv":
        return "CSV columns: id," + ",".join(fields)
    if output_format == "xml":
        return "XML tags: <id>, " + ", ".join(f"<{field}>" for field in fields)
    lines = [
        "JSON keys: id," + ",".join(fields),
        "confidence: 0,1,2,null",
        "event_family: earnings(kqkd/loi_nhuan),dividend(co_tuc),guidance(ke_hoach/du_bao),capital_raise_or_debt(trai_phieu/phat_hanh/tang_von),mna_or_asset(mua_ban/sap_nhap/tai_san/co_phan),regulatory_or_legal(phap_ly/kien/to_cao/xu_phat),other_company_event,macro_or_sector,unknown,null",
        "impact_scope: stock,sector,market,macro,unknown,null",
        "source_authority: official,media_report,rumor_or_unsourced,unknown,null",
        "is_rumor: true,false,null",
    ]
    return "\n".join(line for line in lines if any(field in line or line.startswith("JSON") for field in fields))


def _one_shot_text(output_format: str, fields: list[str]) -> str:
    values = {
        "id": "example",
        "confidence": 2,
        "event_family": "dividend",
        "impact_scope": "stock",
        "source_authority": "official",
        "is_rumor": False,
    }
    if output_format == "csv":
        return "Example output:\n" + ",".join(str(values.get(field, "")) for field in ["id", *fields])
    if output_format == "xml":
        return "Example output:\n<result>" + "".join(
            f"<{field}>{str(values.get(field, '')).lower()}</{field}>" for field in ["id", *fields]
        ) + "</result>"
    return "Example output:\n" + json.dumps({field: values[field] for field in ["id", *fields]}, ensure_ascii=False)


def _variant_prompt(article: dict[str, object], variant: PromptVariant) -> str:
    fields = _field_list(variant.field_set)
    title = str(article.get("clean_title") or "")
    summary = str(article.get("clean_summary") or "")
    body = str(article.get("clean_body_text") or "")
    if variant.body_words > 0:
        body = _truncate_words(body, variant.body_words)
    article_block = "\n".join(
        [
            f"ID: {article['article_id']}",
            f"TITLE: {title}",
            f"SUMMARY: {summary}",
            f"BODY: {body}",
        ]
    )
    header = []
    if variant.header == "expert":
        header.append("You are an expert Vietnamese equity-news analyst.")
    if variant.negative_constraint == "no_chat":
        header.append("Return data only. No prose or markdown.")
    elif variant.negative_constraint == "stay_silent":
        header.append("If unsure, use null fields.")

    schema = _schema_text(fields, variant.output_format)
    parts: list[str] = []
    parts.extend(header)
    if variant.schema_position == "top":
        parts.append(schema)
    if variant.few_shot:
        parts.append(_one_shot_text(variant.output_format, fields))
    parts.append("Article:")
    parts.append(article_block)
    if variant.schema_position == "bottom":
        parts.append(schema)
    if variant.anchor == "result":
        parts.append("Start response with RESULT:")
    elif variant.anchor == "json_start":
        parts.append("---JSON START---")
    if variant.prefill and variant.output_format == "json":
        parts.append('Begin exactly with: {"id":')
    return "\n\n".join(part for part in parts if part)


def _call_ollama(prompt: str, config: NewsFeaturesConfig, variant: PromptVariant) -> tuple[str, dict[str, object]]:
    payload: dict[str, object] = {
        "model": config.ollama_guarded_model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "keep_alive": config.ollama_guarded_keep_alive,
        "options": {
            "temperature": float(variant.temperature),
            "num_predict": int(config.ollama_guarded_num_predict),
            "num_ctx": int(variant.num_ctx),
        },
    }
    if variant.output_format == "json" and variant.use_schema:
        payload["format"] = _json_schema_for_fields(_field_list(variant.field_set))
    request = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = perf_counter()
    with urllib.request.urlopen(request, timeout=int(config.ollama_guarded_timeout_seconds)) as response:
        body = json.loads(response.read().decode("utf-8", errors="replace"))
    elapsed = perf_counter() - started
    body["wall_seconds"] = elapsed
    return _extract_chat_content(body), body


def _parse_xml(raw_text: str) -> dict[str, object] | None:
    values: dict[str, object] = {}
    for field in ["id", *FULL_FIELDS]:
        match = re.search(rf"<{field}>\s*(.*?)\s*</{field}>", raw_text, flags=re.I | re.S)
        if match:
            values[field] = match.group(1).strip()
    return values or None


def _parse_csv(raw_text: str, fields: list[str]) -> dict[str, object] | None:
    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    if not lines:
        return None
    line = lines[-1]
    if line.lower().startswith("result:"):
        line = line.split(":", 1)[1].strip()
    values = [part.strip().strip('"') for part in line.split(",")]
    expected = ["id", *fields]
    if len(values) < len(expected):
        return None
    return dict(zip(expected, values))


def _normalize_probe_response(
    *,
    article_id: str,
    raw_text: str,
    config: NewsFeaturesConfig,
    input_text_length: int,
    variant: PromptVariant,
) -> dict[str, object]:
    if variant.output_format == "json":
        text = raw_text.strip()
        if text.lower().startswith("result:"):
            text = text.split(":", 1)[1].strip()
        text = text.replace("---JSON START---", "").strip()
        return _normalize_guarded_response(
            article_id=article_id,
            raw_text=text,
            config=config,
            input_text_length=input_text_length,
        )

    fields = _field_list(variant.field_set)
    raw_obj = _parse_xml(raw_text) if variant.output_format == "xml" else _parse_csv(raw_text, fields)
    if not raw_obj:
        return {
            "local_parse_ok": False,
            "local_abstained": True,
            "local_error": "parse_fail",
            "ollama_guarded_confidence": None,
            "ollama_guarded_event_family": None,
            "ollama_guarded_impact_scope": None,
            "ollama_guarded_source_authority": None,
            "ollama_guarded_is_rumor": None,
        }
    return {
        "local_parse_ok": True,
        "local_abstained": False,
        "local_error": None,
        "ollama_guarded_confidence": float(raw_obj["confidence"]) if str(raw_obj.get("confidence", "")).isdigit() else None,
        "ollama_guarded_event_family": _norm_guarded_event_family(raw_obj.get("event_family")),
        "ollama_guarded_impact_scope": _norm_guarded_impact_scope(raw_obj.get("impact_scope")),
        "ollama_guarded_source_authority": _norm_guarded_source_authority(raw_obj.get("source_authority")),
        "ollama_guarded_is_rumor": str(raw_obj.get("is_rumor", "")).strip().lower() in {"true", "1", "yes"},
    }


def _gold_from_cache(record: dict[str, object]) -> dict[str, object]:
    event_family = _norm_guarded_event_family(record.get("event_family"))
    if event_family is None:
        event_family = EVENT_TYPE_TO_FAMILY.get(str(record.get("event_type") or ""), None)
        event_family = _norm_guarded_event_family(event_family)
    return {
        "article_id": str(record.get("id") or ""),
        "confidence": record.get("confidence"),
        "event_family": event_family,
        "impact_scope": _norm_guarded_impact_scope(record.get("impact_scope")),
        "source_authority": _norm_guarded_source_authority(record.get("source_authority")),
        "is_rumor": record.get("is_rumor") if record.get("is_rumor") is not None else None,
    }


def _cache_records(config: NewsFeaturesConfig, max_records: int) -> list[dict[str, object]]:
    cache_dir = config.data_root / "llm_cache"
    records: list[dict[str, object]] = []
    for path in sorted(cache_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if len(records) >= max_records:
                    return records
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                gold = _gold_from_cache(record)
                if any(gold.get(field) is not None for field in CORE_FIELDS):
                    records.append(record)
    return records


def _article_from_raw_record(
    article_id: str,
    raw: dict[str, object],
    gold: dict[str, object],
    sample_source: str,
) -> dict[str, object]:
    return {
        "article_id": str(article_id),
        "clean_title": " ".join(str(raw.get("title", "") or "").split()).strip(),
        "clean_summary": " ".join(str(raw.get("summary", "") or "").split()).strip(),
        "clean_body_text": " ".join(str(raw.get("body_text", "") or "").split()).strip(),
        "gold": gold,
        "sample_source": sample_source,
    }


def _load_raw_article_by_id(config: NewsFeaturesConfig, date: str, article_id: str) -> dict[str, object] | None:
    raw_path = config.source_raw_dir("cafef") / f"{date}.jsonl"
    if not raw_path.exists():
        return None
    for raw in legacy._load_articles(raw_path):
        if str(raw.get("article_id") or "") == article_id:
            return raw
    return None


def _article_from_cache_record(config: NewsFeaturesConfig, record: dict[str, object]) -> dict[str, object] | None:
    record_id = str(record.get("id") or "")
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})_(\d{4})", record_id)
    if not match:
        return None
    date, ordinal_text = match.groups()
    raw_path = config.source_raw_dir("cafef") / f"{date}.jsonl"
    if not raw_path.exists():
        return None
    raw_articles = legacy._load_articles(raw_path)
    filtered = [article for article in raw_articles if legacy._is_financial_article(article)]
    ordinal = int(ordinal_text)
    if ordinal <= 0 or ordinal > len(filtered):
        return None
    gold = _gold_from_cache(record)
    if gold.get("event_family") is None:
        return None
    if sum(1 for field in CORE_FIELDS if gold.get(field) is not None) < 2:
        return None
    return _article_from_raw_record(record_id, filtered[ordinal - 1], gold, "legacy_llm_cache_raw_map")


def _load_sample_articles(config: NewsFeaturesConfig, sample_size: int, max_cache_records: int) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for article_id, gold in CURATED_SAMPLE_GOLD.items():
        raw = _load_raw_article_by_id(config, CURATED_SAMPLE_RAW_DATES[article_id], article_id)
        if raw is None:
            continue
        selected.append(_article_from_raw_record(article_id, raw, gold, "curated_current_raw"))
        seen_ids.add(article_id)
        if len(selected) >= sample_size:
            return selected

    for record in _cache_records(config, max_records=max_cache_records):
        article = _article_from_cache_record(config, record)
        if article is None:
            continue
        article_id = str(article["article_id"])
        if article_id in seen_ids:
            continue
        selected.append(article)
        seen_ids.add(article_id)
        if len(selected) >= sample_size:
            return selected
    return selected


def _variants() -> list[PromptVariant]:
    return [
        PromptVariant("baseline_full_json_2048_raw", "expert", "json", "full5", 2048, 0, "top", "no_chat", "none", False, False, 0.0, True),
        PromptVariant("lean_full5_json_512_300_top", "none", "json", "full5", 512, 300, "top", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_full5_json_512_300_bottom", "none", "json", "full5", 512, 300, "bottom", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_full5_json_1024_300_bottom", "none", "json", "full5", 1024, 300, "bottom", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_full5_json_2048_300_bottom", "none", "json", "full5", 2048, 300, "bottom", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_full5_json_512_raw_top", "none", "json", "full5", 512, 0, "top", "none", "none", False, False, 0.0, True),
        PromptVariant("robust_full5_json_512_300_top", "expert", "json", "full5", 512, 300, "top", "no_chat", "none", False, False, 0.0, True),
        PromptVariant("lean_event_rumor_json_512_300_top", "none", "json", "event_rumor", 512, 300, "top", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_event_rumor_json_512_300_bottom", "none", "json", "event_rumor", 512, 300, "bottom", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_event_rumor_json_1024_300_bottom", "none", "json", "event_rumor", 1024, 300, "bottom", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_event_rumor_json_2048_300_bottom", "none", "json", "event_rumor", 2048, 300, "bottom", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_event_only_json_512_300_bottom", "none", "json", "event_only", 512, 300, "bottom", "none", "none", False, False, 0.0, True),
        PromptVariant("lean_event_rumor_json_512_300_1shot", "none", "json", "event_rumor", 512, 300, "bottom", "none", "none", True, False, 0.0, True),
        PromptVariant("lean_event_rumor_json_512_300_result_anchor", "none", "json", "event_rumor", 512, 300, "bottom", "none", "result", False, False, 0.0, True),
        PromptVariant("lean_event_rumor_json_512_300_prefill", "none", "json", "event_rumor", 512, 300, "bottom", "none", "none", False, True, 0.0, True),
        PromptVariant("lean_event_rumor_json_512_300_temp01", "none", "json", "event_rumor", 512, 300, "bottom", "none", "none", False, False, 0.1, True),
        PromptVariant("lean_event_rumor_xml_512_300", "none", "xml", "event_rumor", 512, 300, "bottom", "none", "none", False, False, 0.0, False),
        PromptVariant("lean_event_rumor_csv_512_300", "none", "csv", "event_rumor", 512, 300, "bottom", "none", "none", False, False, 0.0, False),
    ]


def _score_rows(rows: list[dict[str, object]], variant: PromptVariant) -> dict[str, object]:
    parse_ok = sum(1 for row in rows if row["parse_ok"])
    scored_fields = [field for field in CORE_FIELDS if field in _field_list(variant.field_set)]
    field_matches = 0
    field_total = 0
    core_exact = 0
    core_total = 0
    for row in rows:
        gold = row["gold"]
        pred = row["prediction"]
        core_row_total = 0
        core_row_matches = 0
        for field in scored_fields:
            gold_value = gold.get(field)
            if gold_value is None:
                continue
            pred_value = pred.get(f"ollama_guarded_{field}") if field != "is_rumor" else pred.get("ollama_guarded_is_rumor")
            match = pred_value == gold_value
            field_total += 1
            field_matches += int(match)
            core_row_total += 1
            core_row_matches += int(match)
        if core_row_total:
            core_total += 1
            core_exact += int(core_row_matches == core_row_total)
    seconds = [float(row["seconds"]) for row in rows]
    eval_tokens = [int(row.get("eval_count") or 0) for row in rows]
    eval_seconds = [float(row.get("eval_duration_ns") or 0) / 1_000_000_000.0 for row in rows]
    total_eval_tokens = sum(eval_tokens)
    total_eval_seconds = sum(eval_seconds)
    field_accuracy = field_matches / field_total if field_total else 0.0
    parse_ok_rate = parse_ok / len(rows) if rows else 0.0
    core_exact_rate = core_exact / core_total if core_total else 0.0
    avg_seconds = sum(seconds) / len(seconds) if seconds else 0.0
    exact_factor = core_exact_rate if core_total else field_accuracy
    return {
        "variant": variant.name,
        "settings": asdict(variant),
        "scored_fields": scored_fields,
        "sample_size": len(rows),
        "parse_ok_rate": parse_ok_rate,
        "field_accuracy": field_accuracy,
        "core_exact_rate": core_exact_rate,
        "avg_seconds_per_article": avg_seconds,
        "articles_per_second": (1.0 / avg_seconds) if avg_seconds > 0 else 0.0,
        "eval_tokens_per_second": (total_eval_tokens / total_eval_seconds) if total_eval_seconds > 0 else None,
        "avg_prompt_tokens": sum(int(row.get("prompt_eval_count") or 0) for row in rows) / len(rows) if rows else None,
        "avg_eval_tokens": sum(eval_tokens) / len(rows) if rows else None,
        "score": (parse_ok_rate * field_accuracy * exact_factor) / max(avg_seconds, 0.001),
    }


def run_probe(
    *,
    config: NewsFeaturesConfig,
    sample_size: int,
    max_cache_records: int,
    output_path: Optional[Path],
) -> dict[str, object]:
    articles = _load_sample_articles(config, sample_size=sample_size, max_cache_records=max_cache_records)
    if not articles:
        raise RuntimeError("No labelled sample articles found for Ollama prompt probe.")
    result_rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    try:
        for variant in _variants():
            variant_rows: list[dict[str, object]] = []
            for article in articles:
                prompt = _variant_prompt(article, variant)
                raw, response = _call_ollama(prompt, config, variant)
                prediction = _normalize_probe_response(
                    article_id=str(article["article_id"]),
                    raw_text=raw,
                    config=config,
                    input_text_length=len(prompt),
                    variant=variant,
                )
                row = {
                    "variant": variant.name,
                    "article_id": str(article["article_id"]),
                    "gold": article["gold"],
                    "prediction": prediction,
                    "parse_ok": bool(prediction.get("local_parse_ok")),
                    "seconds": float(response.get("wall_seconds") or 0.0),
                    "prompt_eval_count": response.get("prompt_eval_count"),
                    "eval_count": response.get("eval_count"),
                    "eval_duration_ns": response.get("eval_duration"),
                    "raw_response_preview": str(raw or "")[:500],
                }
                variant_rows.append(row)
                result_rows.append(row)
            summaries.append(_score_rows(variant_rows, variant))
            best_so_far = max(summaries, key=lambda item: float(item["score"]))
            print(
                f"[ollama_prompt_probe] variant={variant.name} "
                f"parse={summaries[-1]['parse_ok_rate']:.2f} "
                f"field_acc={summaries[-1]['field_accuracy']:.2f} "
                f"core_exact={summaries[-1]['core_exact_rate']:.2f} "
                f"sec={summaries[-1]['avg_seconds_per_article']:.2f} "
                f"best={best_so_far['variant']}",
                flush=True,
            )
    finally:
        _stop_ollama_model(config.ollama_guarded_model_name)

    winner = max(summaries, key=lambda item: float(item["score"]))
    payload = {
        "status": "complete",
        "model_name": config.ollama_guarded_model_name,
        "sample_size": len(articles),
        "sample_article_ids": [str(article["article_id"]) for article in articles],
        "sample_sources": {
            str(article["article_id"]): str(article.get("sample_source", "unknown"))
            for article in articles
        },
        "summaries": sorted(summaries, key=lambda item: float(item["score"]), reverse=True),
        "winner": winner,
        "rows": result_rows,
        "notes": {
            "quality_reference": "Hosted cache weak labels; use for prompt selection, not final truth.",
            "quantization": "No local Q8/FP16 tag was available in ollama list; quantization was not varied.",
        },
    }
    if output_path is None:
        stamp = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = config.repo_root / "artifacts" / "run_summaries" / f"{stamp}_ollama_guarded_prompt_probe.json"
    _write_json_atomic(output_path, payload)
    _write_json_atomic(config.repo_root / "artifacts" / "run_summaries" / "latest_ollama_guarded_prompt_probe.json", payload)
    print(f"[ollama_prompt_probe] winner={winner['variant']} output={output_path}", flush=True)
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Low-resource grid probe for Ollama guarded prompts.")
    parser.add_argument("--sample-size", type=int, default=6)
    parser.add_argument("--max-cache-records", type=int, default=20000)
    parser.add_argument("--output-path", default="")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = get_default_config()
    run_probe(
        config=config,
        sample_size=max(int(args.sample_size), 1),
        max_cache_records=max(int(args.max_cache_records), 1),
        output_path=Path(args.output_path).expanduser() if args.output_path else None,
    )


if __name__ == "__main__":
    main()
