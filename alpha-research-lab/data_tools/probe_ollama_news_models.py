"""
Probe local Ollama models on real CafeF news articles, one article at a time.

This script is for durable local-model comparisons on constrained hardware. It
reuses the existing news-extraction normalizer, loads real raw CafeF articles by
id, supports plain JSON vs XML-anchored prompt styles, samples RAM/VRAM during
each call, and writes a timestamped artifact under `artifacts/ollama_probes/`.

Examples:
    cd alpha-research-lab
    python data_tools/probe_ollama_news_models.py \
        --models qwen2.5-coder:3b,llama3.2:3b,phi4-mini \
        --preset core

    cd alpha-research-lab
    python data_tools/probe_ollama_news_models.py \
        --models granite3-moe:3b,smollm2:1.7b,deepseek-coder:1.3b \
        --preset all \
        --prompt-style plain_json \
        --prompt-style xml_anchor

    cd alpha-research-lab
    python data_tools/probe_ollama_news_models.py \
        --models-file notes/local_ollama_candidates.txt \
        --article '2026-01-01|8002e4554e3b25a6|A1' \
        --article '2026-01-06|899a7c579aaf8b49|A3' \
        --expectations-file notes/ollama_probe_expectations.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from data_tools import extract_llm_news_features_legacy as legacy
from src.repo_paths import artifact_path, data_path, lab_relative_path


RAW_DIR = data_path("news/cafef/raw")
ARTIFACT_DIR = artifact_path("ollama_probes")

DEFAULT_TIMEOUT = 180
DEFAULT_NUM_PREDICT = 512
DEFAULT_NUM_CTX = 2048
DEFAULT_KEEP_ALIVE = "0s"
DEFAULT_SAMPLE_INTERVAL = 0.5
DEFAULT_MODELS = ["qwen2.5-coder:3b", "llama3.2:3b", "phi4-mini"]

PROMPT_STYLES = ("plain_json", "xml_anchor")
API_MODES = ("chat", "generate")


@dataclass(frozen=True)
class ArticleExpectation:
    tickers: tuple[str, ...] = field(default_factory=tuple)
    event_type: str | None = None
    impact_scope: str | None = None
    source_authority: str | None = None
    is_forward_looking: bool | None = None
    is_rumor: bool | None = None


@dataclass(frozen=True)
class ArticlePreset:
    label: str
    date: str
    article_id: str
    note: str
    expectation: ArticleExpectation | None = None


@dataclass(frozen=True)
class LoadedArticle:
    label: str
    date: str
    path: Path
    article_id: str
    title: str
    summary: str
    body_text: str
    published_at: str | None
    url: str | None
    is_financial_article: bool
    expectation: ArticleExpectation | None = None


PRESET_ARTICLES: dict[str, ArticlePreset] = {
    "A1": ArticlePreset(
        label="A1",
        date="2026-01-01",
        article_id="8002e4554e3b25a6",
        note="IPA debt issue",
        expectation=ArticleExpectation(
            tickers=("IPA",),
            event_type="debt_issue",
            impact_scope="stock",
            source_authority="official",
            is_forward_looking=True,
            is_rumor=False,
        ),
    ),
    "A2": ArticlePreset(
        label="A2",
        date="2026-01-09",
        article_id="140b663d010812f9",
        note="bank-policy multi-ticker stress article",
        expectation=None,
    ),
    "A3": ArticlePreset(
        label="A3",
        date="2026-01-06",
        article_id="899a7c579aaf8b49",
        note="IDP dividend",
        expectation=ArticleExpectation(
            tickers=("IDP",),
            event_type="dividend_announce",
            impact_scope="stock",
            source_authority="official",
            is_forward_looking=True,
            is_rumor=False,
        ),
    ),
    "A4": ArticlePreset(
        label="A4",
        date="2026-01-01",
        article_id="775ab17877b04e18",
        note="VGC 2026 guidance",
        expectation=ArticleExpectation(
            tickers=("VGC",),
            event_type="guidance_raise",
            impact_scope="stock",
            source_authority="official",
            is_forward_looking=True,
            is_rumor=False,
        ),
    ),
}

PRESET_GROUPS: dict[str, list[str]] = {
    "core": ["A1", "A3", "A4"],
    "stress": ["A2"],
    "all": ["A1", "A2", "A3", "A4"],
}


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _clean_text(value: object) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", text).strip()


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip(), True


def _mib_from_proc_meminfo() -> float | None:
    try:
        total_kib: int | None = None
        available_kib: int | None = None
        with Path("/proc/meminfo").open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                parts = raw_line.split()
                if len(parts) < 2:
                    continue
                key = parts[0].rstrip(":")
                if key == "MemTotal":
                    total_kib = int(parts[1])
                elif key == "MemAvailable":
                    available_kib = int(parts[1])
                if total_kib is not None and available_kib is not None:
                    break
        if total_kib is None or available_kib is None:
            return None
        return (total_kib - available_kib) / 1024.0
    except Exception:
        return None


def _vram_used_mib() -> float | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            check=False,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    values: list[float] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            values.append(float(line))
        except ValueError:
            continue
    if not values:
        return None
    return max(values)


class _PeakSampler:
    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = max(0.1, interval_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.baseline_ram_mib = _mib_from_proc_meminfo()
        self.baseline_vram_mib = _vram_used_mib()
        self.peak_ram_mib = self.baseline_ram_mib
        self.peak_vram_mib = self.baseline_vram_mib

    def _sample_once(self) -> None:
        ram = _mib_from_proc_meminfo()
        if ram is not None:
            if self.peak_ram_mib is None or ram > self.peak_ram_mib:
                self.peak_ram_mib = ram
        vram = _vram_used_mib()
        if vram is not None:
            if self.peak_vram_mib is None or vram > self.peak_vram_mib:
                self.peak_vram_mib = vram

    def _run(self) -> None:
        while not self._stop.is_set():
            self._sample_once()
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, float | None]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._sample_once()
        baseline_ram = self.baseline_ram_mib
        baseline_vram = self.baseline_vram_mib
        peak_ram = self.peak_ram_mib
        peak_vram = self.peak_vram_mib
        return {
            "baseline_ram_mib": baseline_ram,
            "peak_ram_mib": peak_ram,
            "delta_ram_mib": None if baseline_ram is None or peak_ram is None else peak_ram - baseline_ram,
            "baseline_vram_mib": baseline_vram,
            "peak_vram_mib": peak_vram,
            "delta_vram_mib": None if baseline_vram is None or peak_vram is None else peak_vram - baseline_vram,
        }


def _round_metric(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _parse_csv_tokens(raw: str) -> list[str]:
    return [token.strip() for token in re.split(r"[\s,]+", str(raw or "")) if token.strip()]


def _resolve_models(model_arg: str, models_file: str | None) -> list[str]:
    models: list[str] = []
    models.extend(_parse_csv_tokens(model_arg))
    if models_file:
        lines = Path(models_file).read_text(encoding="utf-8").splitlines()
        for line in lines:
            token = line.strip()
            if not token or token.startswith("#"):
                continue
            models.extend(_parse_csv_tokens(token))
    deduped: list[str] = []
    seen: set[str] = set()
    for model in models or DEFAULT_MODELS:
        if model not in seen:
            deduped.append(model)
            seen.add(model)
    return deduped


def _parse_article_arg(raw: str) -> tuple[str, str, str | None]:
    parts = [part.strip() for part in str(raw or "").split("|")]
    if len(parts) not in {2, 3} or not parts[0] or not parts[1]:
        raise ValueError(
            f"invalid --article '{raw}'; expected DATE|ARTICLE_ID or DATE|ARTICLE_ID|LABEL"
        )
    date = parts[0]
    article_id = parts[1]
    label = parts[2] if len(parts) == 3 and parts[2] else None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError(f"invalid article date '{date}'; expected YYYY-MM-DD")
    return date, article_id, label


def _expectation_from_dict(raw: dict[str, object] | None) -> ArticleExpectation | None:
    if not raw:
        return None
    tickers = raw.get("tickers")
    if isinstance(tickers, str):
        tickers = [tickers]
    parsed_tickers = tuple(str(token).strip().upper() for token in tickers or [] if str(token).strip())
    return ArticleExpectation(
        tickers=parsed_tickers,
        event_type=str(raw.get("event_type")).strip() or None if raw.get("event_type") is not None else None,
        impact_scope=str(raw.get("impact_scope")).strip() or None if raw.get("impact_scope") is not None else None,
        source_authority=(
            str(raw.get("source_authority")).strip() or None if raw.get("source_authority") is not None else None
        ),
        is_forward_looking=raw.get("is_forward_looking") if isinstance(raw.get("is_forward_looking"), bool) else None,
        is_rumor=raw.get("is_rumor") if isinstance(raw.get("is_rumor"), bool) else None,
    )


def _load_expectations_file(path: str | None) -> dict[str, ArticleExpectation]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("--expectations-file must contain a JSON object keyed by article id")
    out: dict[str, ArticleExpectation] = {}
    for article_id, raw in payload.items():
        if not isinstance(article_id, str) or not isinstance(raw, dict):
            continue
        expectation = _expectation_from_dict(raw)
        if expectation is not None:
            out[article_id] = expectation
    return out


def _load_article_from_raw_file(path: Path, article_id: str) -> dict:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidate_id = str(row.get("article_id") or row.get("id") or "").strip()
            if candidate_id == article_id:
                row = dict(row)
                row["id"] = article_id
                row["article_id"] = article_id
                return row
    raise FileNotFoundError(f"article_id '{article_id}' not found in {path}")


def _article_case_from_row(
    *,
    label: str,
    date: str,
    path: Path,
    row: dict,
    expectation: ArticleExpectation | None,
) -> LoadedArticle:
    return LoadedArticle(
        label=label,
        date=date,
        path=path,
        article_id=str(row["article_id"]),
        title=_clean_text(row.get("title")),
        summary=_clean_text(row.get("summary")),
        body_text=_clean_text(row.get("body_text")),
        published_at=_clean_text(row.get("published_at")) or None,
        url=_clean_text(row.get("url")) or None,
        is_financial_article=legacy._is_financial_article(row),
        expectation=expectation,
    )


def _resolve_articles(
    *,
    preset: str,
    custom_articles: list[str],
    expectations_file: str | None,
) -> list[LoadedArticle]:
    expectation_overrides = _load_expectations_file(expectations_file)
    loaded: list[LoadedArticle] = []
    if custom_articles:
        for index, raw in enumerate(custom_articles, start=1):
            date, article_id, label = _parse_article_arg(raw)
            path = RAW_DIR / f"{date}.jsonl"
            row = _load_article_from_raw_file(path, article_id)
            expectation = expectation_overrides.get(article_id)
            loaded.append(
                _article_case_from_row(
                    label=label or f"C{index}",
                    date=date,
                    path=path,
                    row=row,
                    expectation=expectation,
                )
            )
        return loaded

    keys = PRESET_GROUPS[preset]
    for key in keys:
        preset_case = PRESET_ARTICLES[key]
        path = RAW_DIR / f"{preset_case.date}.jsonl"
        row = _load_article_from_raw_file(path, preset_case.article_id)
        expectation = expectation_overrides.get(preset_case.article_id, preset_case.expectation)
        loaded.append(
            _article_case_from_row(
                label=preset_case.label,
                date=preset_case.date,
                path=path,
                row=row,
                expectation=expectation,
            )
        )
    return loaded


def _render_allowed_values() -> list[str]:
    return [
        f"event_type: {legacy.PROMPT_TAXONOMY}",
        "impact_scope: stock, sector, market",
        "expectation_alignment: beats, meets, misses, not_applicable",
        "information_novelty: new, follow_up, recycled, unclear",
        "macro_theme: rates, fx, liquidity, credit, real_estate, banking, exports, commodities, energy, public_investment, regulation, geopolitics, consumption, technology, industrials, none",
        "source_authority: official, management, media_report, analyst, rumor_source, unclear",
        "causal_impact_label: revenue_positive, revenue_negative, cost_positive, cost_negative, financing_positive, financing_negative, regulatory_positive, regulatory_negative, sentiment_only, mixed, none",
    ]


def _build_probe_prompt(article: LoadedArticle, prompt_style: str, max_body_chars: int) -> tuple[str, dict[str, object]]:
    body_text, body_truncated = _truncate_text(article.body_text, max_body_chars)
    meta = {
        "title_chars": len(article.title),
        "summary_chars": len(article.summary),
        "body_chars_total": len(article.body_text),
        "body_chars_in_prompt": len(body_text),
        "body_truncated": body_truncated,
    }
    lines = [
        "You are reading one Vietnamese CafeF financial news article.",
        "Extract the article into one strict JSON object using only the article text.",
        "Do not invent tickers, event labels, related entities, or hidden expectations.",
        "If a field is unclear, use null or [].",
        "Return JSON object only. No markdown. No prose. No reasoning.",
        "Put the primary company ticker first in tickers when one name is clearly dominant.",
        "",
        "Output fields:",
        "- id",
        "- tickers",
        "- related_tickers",
        "- sentiment: -1 | 0 | 1 | null",
        "- confidence: 0 | 1 | 2 | null",
        "- event_type",
        "- magnitude: 0 | 1 | 2 | null",
        "- is_forward_looking: true | false | null",
        "- market_tone: -1 | 0 | 1 | null",
        "- is_rumor: true | false | null",
        "- surprise_direction: -1 | 0 | 1 | null",
        "- impact_scope",
        "- named_persons",
        "- expectation_alignment",
        "- information_novelty",
        "- macro_theme",
        "- source_authority",
        "- causal_impact_label",
        "",
        "Allowed codes:",
        *[f"- {line}" for line in _render_allowed_values()],
        "",
    ]
    if prompt_style == "xml_anchor":
        lines.extend(
            [
                "Use this internal XML scaffold to keep the fields consistent before you emit the final JSON object:",
                "<article_extraction>",
                "  <id></id>",
                "  <tickers></tickers>",
                "  <related_tickers></related_tickers>",
                "  <sentiment></sentiment>",
                "  <confidence></confidence>",
                "  <event_type></event_type>",
                "  <magnitude></magnitude>",
                "  <is_forward_looking></is_forward_looking>",
                "  <market_tone></market_tone>",
                "  <is_rumor></is_rumor>",
                "  <surprise_direction></surprise_direction>",
                "  <impact_scope></impact_scope>",
                "  <named_persons></named_persons>",
                "  <expectation_alignment></expectation_alignment>",
                "  <information_novelty></information_novelty>",
                "  <macro_theme></macro_theme>",
                "  <source_authority></source_authority>",
                "  <causal_impact_label></causal_impact_label>",
                "</article_extraction>",
                "Do not output the XML scaffold. Output only the final JSON object.",
                "",
            ]
        )
    lines.extend(
        [
            f"Article id: {article.article_id}",
            f"Title: {article.title}",
            f"Summary: {article.summary}",
            f"Body: {body_text}",
        ]
    )
    return "\n".join(lines), meta


def _nullable_schema(*types: str) -> dict[str, object]:
    return {"type": list(types) + ["null"]}


def _probe_json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "tickers": {"type": "array", "items": {"type": "string"}},
            "related_tickers": {"type": "array", "items": {"type": "string"}},
            "sentiment": _nullable_schema("integer"),
            "confidence": _nullable_schema("integer"),
            "event_type": _nullable_schema("string"),
            "magnitude": _nullable_schema("integer"),
            "is_forward_looking": _nullable_schema("boolean"),
            "market_tone": _nullable_schema("integer"),
            "is_rumor": _nullable_schema("boolean"),
            "surprise_direction": _nullable_schema("integer"),
            "impact_scope": _nullable_schema("string"),
            "named_persons": {"type": "array", "items": {"type": "string"}},
            "expectation_alignment": _nullable_schema("string"),
            "information_novelty": _nullable_schema("string"),
            "macro_theme": _nullable_schema("string"),
            "source_authority": _nullable_schema("string"),
            "causal_impact_label": _nullable_schema("string"),
        },
        "required": [
            "id",
            "tickers",
            "related_tickers",
            "sentiment",
            "confidence",
            "event_type",
            "magnitude",
            "is_forward_looking",
            "market_tone",
            "is_rumor",
            "surprise_direction",
            "impact_scope",
            "named_persons",
            "expectation_alignment",
            "information_novelty",
            "macro_theme",
            "source_authority",
            "causal_impact_label",
        ],
        "additionalProperties": True,
    }


def _post_json(url: str, payload: dict[str, object], timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _call_ollama_generate(
    *,
    prompt: str,
    model: str,
    timeout: int,
    num_predict: int,
    num_ctx: int,
    keep_alive: str,
) -> str:
    body = _post_json(
        "http://localhost:11434/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": keep_alive,
            "options": {
                "temperature": 0,
                "num_predict": num_predict,
                "num_ctx": num_ctx,
            },
        },
        timeout=timeout,
    )
    return str(body.get("response", "") or "")


def _extract_chat_content(body: dict) -> str:
    message = body.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        return "".join(parts)
    return ""


def _call_ollama_chat(
    *,
    prompt: str,
    model: str,
    timeout: int,
    num_predict: int,
    num_ctx: int,
    keep_alive: str,
    use_schema: bool,
) -> str:
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
        },
    }
    if use_schema:
        payload["format"] = _probe_json_schema()
    body = _post_json("http://localhost:11434/api/chat", payload, timeout=timeout)
    return _extract_chat_content(body)


def _stop_ollama_model(model: str) -> None:
    try:
        subprocess.run(
            ["ollama", "stop", model],
            capture_output=True,
            check=False,
            text=True,
        )
    except Exception:
        return


def _parse_and_normalize_response(article_id: str, raw_text: str) -> tuple[dict | None, dict[str, object]]:
    arr = legacy._extract_json_array(raw_text) or []
    if not arr:
        return None, {"parse_error": "json_parse_fail", "raw_id": None, "raw_object": None}
    raw_obj: dict | None = None
    for obj in arr:
        if isinstance(obj, dict) and str(obj.get("id", "") or "").strip() == article_id:
            raw_obj = obj
            break
    if raw_obj is None:
        raw_obj = arr[0] if isinstance(arr[0], dict) else None
    if raw_obj is None:
        return None, {"parse_error": "json_parse_fail", "raw_id": None, "raw_object": None}
    raw_id = str(raw_obj.get("id", "") or "").strip() or None
    normalized = legacy._normalize_record(raw_obj, article_id)
    return normalized, {"parse_error": None, "raw_id": raw_id, "raw_object": raw_obj}


def _score_article_result(normalized: dict | None, expectation: ArticleExpectation | None) -> dict[str, int | None]:
    if normalized is None or expectation is None:
        return {
            "ticker_exact": None,
            "event_match": None,
            "core_trust_hits": None,
            "core_trust_total": None,
        }
    ticker_exact = None
    if expectation.tickers:
        ticker_exact = int(tuple(normalized.get("tickers") or []) == expectation.tickers)
    event_match = None if expectation.event_type is None else int(normalized.get("event_type") == expectation.event_type)
    core_hits = 0
    core_total = 0
    core_fields = {
        "impact_scope": expectation.impact_scope,
        "source_authority": expectation.source_authority,
        "is_forward_looking": expectation.is_forward_looking,
        "is_rumor": expectation.is_rumor,
    }
    for field_name, expected in core_fields.items():
        if expected is None:
            continue
        core_total += 1
        if normalized.get(field_name) == expected:
            core_hits += 1
    return {
        "ticker_exact": ticker_exact,
        "event_match": event_match,
        "core_trust_hits": core_hits if core_total else None,
        "core_trust_total": core_total if core_total else None,
    }


def _run_single_probe(
    *,
    article: LoadedArticle,
    model: str,
    prompt_style: str,
    api_mode: str,
    use_schema: bool,
    timeout: int,
    num_predict: int,
    num_ctx: int,
    keep_alive: str,
    sample_interval: float,
    max_body_chars: int,
) -> dict[str, object]:
    prompt, prompt_meta = _build_probe_prompt(article, prompt_style=prompt_style, max_body_chars=max_body_chars)
    sampler = _PeakSampler(interval_seconds=sample_interval)
    raw_response_text = ""
    normalized: dict | None = None
    parse_meta: dict[str, object] = {"parse_error": None, "raw_id": None, "raw_object": None}
    call_error: str | None = None
    t0 = time.perf_counter()
    try:
        sampler.start()
        if api_mode == "chat":
            raw_response_text = _call_ollama_chat(
                prompt=prompt,
                model=model,
                timeout=timeout,
                num_predict=num_predict,
                num_ctx=num_ctx,
                keep_alive=keep_alive,
                use_schema=use_schema,
            )
        else:
            raw_response_text = _call_ollama_generate(
                prompt=prompt,
                model=model,
                timeout=timeout,
                num_predict=num_predict,
                num_ctx=num_ctx,
                keep_alive=keep_alive,
            )
        normalized, parse_meta = _parse_and_normalize_response(article.article_id, raw_response_text)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        call_error = f"HTTPError {exc.code}: {body[:500]}"
    except urllib.error.URLError as exc:
        call_error = f"URLError: {exc}"
    except TimeoutError:
        call_error = "timeout"
    except Exception as exc:
        call_error = f"{type(exc).__name__}: {exc}"
    finally:
        elapsed_sec = time.perf_counter() - t0
        memory = sampler.stop()
        _stop_ollama_model(model)

    score = _score_article_result(normalized, article.expectation)
    return {
        "model": model,
        "prompt_style": prompt_style,
        "api_mode": api_mode,
        "format_schema": bool(use_schema),
        "article_label": article.label,
        "article_id": article.article_id,
        "article_date": article.date,
        "article_path": lab_relative_path(article.path),
        "title": article.title,
        "is_financial_article": article.is_financial_article,
        "elapsed_sec": _round_metric(elapsed_sec),
        "prompt_text": prompt,
        "prompt_meta": prompt_meta,
        "raw_response_text": raw_response_text,
        "call_error": call_error,
        "parse_error": parse_meta["parse_error"],
        "raw_response_id": parse_meta["raw_id"],
        "normalized": normalized,
        "expectation": asdict(article.expectation) if article.expectation is not None else None,
        "score": score,
        **{key: _round_metric(value) for key, value in memory.items()},
    }


def _sum_ints(values: Iterable[int | None]) -> int | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return sum(filtered)


def _count_not_none(values: Iterable[object]) -> int:
    return sum(1 for value in values if value is not None)


def _max_metric(values: Iterable[float | None]) -> float | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return max(filtered)


def _summarize_probe_runs(results: list[dict[str, object]]) -> dict[str, object]:
    elapsed_values = [float(result["elapsed_sec"]) for result in results if result.get("elapsed_sec") is not None]
    ticker_values = [result["score"]["ticker_exact"] for result in results if isinstance(result.get("score"), dict)]
    event_values = [result["score"]["event_match"] for result in results if isinstance(result.get("score"), dict)]
    core_hit_values = [result["score"]["core_trust_hits"] for result in results if isinstance(result.get("score"), dict)]
    core_total_values = [result["score"]["core_trust_total"] for result in results if isinstance(result.get("score"), dict)]
    return {
        "articles": len(results),
        "avg_elapsed_sec": _round_metric(statistics.mean(elapsed_values)) if elapsed_values else None,
        "parse_failures": sum(
            1
            for result in results
            if result.get("call_error") is not None or result.get("parse_error") is not None or result.get("normalized") is None
        ),
        "peak_ram_mib": _round_metric(_max_metric(result.get("peak_ram_mib") for result in results)),
        "peak_ram_delta_mib": _round_metric(_max_metric(result.get("delta_ram_mib") for result in results)),
        "peak_vram_mib": _round_metric(_max_metric(result.get("peak_vram_mib") for result in results)),
        "peak_vram_delta_mib": _round_metric(_max_metric(result.get("delta_vram_mib") for result in results)),
        "ticker_exact_hits": _sum_ints(ticker_values),
        "ticker_exact_total": _count_not_none(ticker_values),
        "event_match_hits": _sum_ints(event_values),
        "event_match_total": _count_not_none(event_values),
        "core_trust_hits": _sum_ints(core_hit_values),
        "core_trust_total": _sum_ints(core_total_values),
    }


def _format_fraction(hit_key: str, total_key: str, summary: dict[str, object]) -> str:
    hits = summary.get(hit_key)
    total = summary.get(total_key)
    if hits is None or total in {None, 0}:
        return "-"
    return f"{hits}/{total}"


def _print_summary_table(groups: list[dict[str, object]]) -> None:
    by_style: dict[str, list[dict[str, object]]] = {}
    for group in groups:
        by_style.setdefault(str(group["prompt_style"]), []).append(group)
    for prompt_style, rows in by_style.items():
        print("")
        print(
            f"Prompt style: {prompt_style} | api_mode={rows[0]['api_mode']} | "
            f"format_schema={rows[0]['format_schema']}"
        )
        print("| Model | Avg sec | Peak RAM | Peak VRAM | Parse failures | Ticker exact | Event exact | Core trust hits |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|")
        for row in rows:
            summary = row["summary"]
            assert isinstance(summary, dict)
            print(
                "| {model} | {avg} | {ram} | {vram} | {parse_failures} | {ticker} | {event} | {core} |".format(
                    model=row["model"],
                    avg=summary.get("avg_elapsed_sec") if summary.get("avg_elapsed_sec") is not None else "-",
                    ram=summary.get("peak_ram_mib") if summary.get("peak_ram_mib") is not None else "-",
                    vram=summary.get("peak_vram_mib") if summary.get("peak_vram_mib") is not None else "-",
                    parse_failures=summary.get("parse_failures", "-"),
                    ticker=_format_fraction("ticker_exact_hits", "ticker_exact_total", summary),
                    event=_format_fraction("event_match_hits", "event_match_total", summary),
                    core=_format_fraction("core_trust_hits", "core_trust_total", summary),
                )
            )


def _default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ARTIFACT_DIR / f"{timestamp}_ollama_news_probe.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="", help="Comma or whitespace separated model list.")
    parser.add_argument("--models-file", default=None, help="Optional text file with one model per line.")
    parser.add_argument(
        "--preset",
        choices=sorted(PRESET_GROUPS),
        default="core",
        help="Built-in article set to probe when --article is not supplied.",
    )
    parser.add_argument(
        "--article",
        action="append",
        default=[],
        help="Custom article in DATE|ARTICLE_ID or DATE|ARTICLE_ID|LABEL format. May be repeated.",
    )
    parser.add_argument(
        "--expectations-file",
        default=None,
        help="Optional JSON mapping article_id to expected fields for scoring custom articles.",
    )
    parser.add_argument(
        "--prompt-style",
        action="append",
        choices=PROMPT_STYLES,
        default=[],
        help="Prompt style to evaluate. Repeat to compare multiple styles. Defaults to plain_json.",
    )
    parser.add_argument("--api-mode", choices=API_MODES, default="chat")
    parser.add_argument(
        "--no-format-schema",
        action="store_true",
        help="Disable Ollama chat JSON schema enforcement. Ignored in generate mode.",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--num-predict", type=int, default=DEFAULT_NUM_PREDICT)
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    parser.add_argument("--keep-alive", default=DEFAULT_KEEP_ALIVE)
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=DEFAULT_SAMPLE_INTERVAL,
        help="Memory sampling interval in seconds.",
    )
    parser.add_argument(
        "--max-body-chars",
        type=int,
        default=0,
        help="Truncate body_text to this many chars before prompting. 0 means full body.",
    )
    parser.add_argument(
        "--output",
        default=str(_default_output_path()),
        help="JSON artifact path. Defaults to artifacts/ollama_probes/<timestamp>_ollama_news_probe.json",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List the built-in article presets and exit.",
    )
    return parser


def _print_presets() -> None:
    print("Built-in article presets:")
    for key in sorted(PRESET_ARTICLES):
        preset = PRESET_ARTICLES[key]
        print(f"- {preset.label}: {preset.date} | {preset.article_id} | {preset.note}")
    print("")
    print("Preset groups:")
    for key, labels in sorted(PRESET_GROUPS.items()):
        print(f"- {key}: {', '.join(labels)}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if args.list_presets:
        _print_presets()
        return 0

    prompt_styles = args.prompt_style or ["plain_json"]
    models = _resolve_models(args.models, args.models_file)
    articles = _resolve_articles(
        preset=args.preset,
        custom_articles=args.article,
        expectations_file=args.expectations_file,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Models: {', '.join(models)}")
    print(
        "Articles: "
        + ", ".join(f"{article.label}({article.date}|{article.article_id})" for article in articles)
    )

    groups: list[dict[str, object]] = []
    for prompt_style in prompt_styles:
        for model in models:
            print(f"[probe] prompt_style={prompt_style} api_mode={args.api_mode} model={model}")
            result_rows: list[dict[str, object]] = []
            for article in articles:
                print(f"  - article={article.label} id={article.article_id}")
                result_rows.append(
                    _run_single_probe(
                        article=article,
                        model=model,
                        prompt_style=prompt_style,
                        api_mode=args.api_mode,
                        use_schema=(args.api_mode == "chat" and not args.no_format_schema),
                        timeout=args.timeout,
                        num_predict=args.num_predict,
                        num_ctx=args.num_ctx,
                        keep_alive=args.keep_alive,
                        sample_interval=args.sample_interval,
                        max_body_chars=args.max_body_chars,
                    )
                )
            groups.append(
                {
                    "model": model,
                    "prompt_style": prompt_style,
                    "api_mode": args.api_mode,
                    "format_schema": bool(args.api_mode == "chat" and not args.no_format_schema),
                    "summary": _summarize_probe_runs(result_rows),
                    "articles": result_rows,
                }
            )

    artifact = {
        "version": 1,
        "created_at": _utc_now_iso_z(),
        "script": "data_tools/probe_ollama_news_models.py",
        "config": {
            "models": models,
            "prompt_styles": prompt_styles,
            "api_mode": args.api_mode,
            "format_schema": bool(args.api_mode == "chat" and not args.no_format_schema),
            "timeout": args.timeout,
            "num_predict": args.num_predict,
            "num_ctx": args.num_ctx,
            "keep_alive": args.keep_alive,
            "sample_interval": args.sample_interval,
            "max_body_chars": args.max_body_chars,
        },
        "article_set": [
            {
                "label": article.label,
                "date": article.date,
                "article_id": article.article_id,
                "path": lab_relative_path(article.path),
                "title": article.title,
                "published_at": article.published_at,
                "url": article.url,
                "is_financial_article": article.is_financial_article,
                "expectation": asdict(article.expectation) if article.expectation is not None else None,
            }
            for article in articles
        ],
        "results": groups,
    }
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _print_summary_table(groups)
    print("")
    print(f"Artifact written: {lab_relative_path(output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
