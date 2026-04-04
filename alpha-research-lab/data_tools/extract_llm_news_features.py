"""
Extract structured LLM features from CafeF daily news JSONL files.

Input:
- data/news/cafef/raw/YYYY-MM-DD.jsonl

Output:
- data/llm_cache/YYYY-MM-DD.jsonl (one JSON object per filtered article)

Providers:
- ollama  : local Ollama server (default model: qwen3.5:4b)
- google  : Google AI Studio / Gemini API (default model: gemini-2.5-flash-lite)
            Set GOOGLE_API_KEY env var or pass --api-key.
            Uses JSON mode for zero-parse-fail guarantee.
- nvidia  : NVIDIA hosted LLM API (default pool: curated text-only chat models)
            Set NVIDIA_API_KEY env var or pass --api-key.
            Uses OpenAI-compatible chat completions.

Schema (all LLM-unique fields):
- id                 : article id
- tickers            : directly mentioned stock tickers (catches implicit refs)
- related_tickers    : other tickers implicitly affected by this news
- sentiment          : -1/0/1 — semantic sentiment for named stocks
- confidence         : 0/1/2 — how confident/clear is the sentiment signal
- event_type         : one of EVENT_TYPES taxonomy
- magnitude          : 0/1/2 — how significant is the event
- is_forward_looking : bool — discusses future events/guidance vs current/past
- market_tone        : -1/0/1 — broader market sentiment beyond named stocks
- is_rumor           : bool — speculation/rumor vs official/confirmed disclosure
- surprise_direction : -1/0/1 — negative/neutral/positive surprise vs expectations
- impact_scope       : "stock"/"sector"/"market" — breadth of impact
- named_persons      : key people mentioned (CEO, CFO, major shareholders)

Design:
- Resume-safe: skip existing day outputs unless --overwrite
- Atomic writes: write .tmp then rename
- Robust parse: salvage partial JSON where possible (Ollama); JSON mode for Google
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import os
import re
import threading
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path
from path_utils import data_path, workspace_path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = data_path("news/cafef/raw")
CACHE_DIR = data_path("llm_cache")
NVIDIA_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

EVENT_TYPES = {
    "earnings_beat", "earnings_miss", "earnings_neutral", "revenue_growth",
    "revenue_decline", "guidance_raise", "guidance_cut", "dividend_announce",
    "debt_issue", "debt_concern", "rights_issue", "buyback", "merger_acquisition",
    "divestiture", "ipo_listing", "management_change", "insider_buy", "insider_sell",
    "contract_win", "contract_loss", "partnership", "expansion", "legal_issue",
    "regulatory_approval", "regulatory_block", "policy_positive", "policy_negative",
    "rate_change", "fx_move", "commodity_price", "macro_indicator",
    "index_inclusion", "index_exclusion", "other", "no_event",
}

PROMPT_TAXONOMY = (
    "earnings_beat, earnings_miss, earnings_neutral, revenue_growth, revenue_decline, "
    "guidance_raise, guidance_cut, dividend_announce, debt_issue, debt_concern, "
    "rights_issue, buyback, merger_acquisition, divestiture, ipo_listing, "
    "management_change, insider_buy, insider_sell, contract_win, contract_loss, "
    "partnership, expansion, legal_issue, regulatory_approval, regulatory_block, "
    "policy_positive, policy_negative, rate_change, fx_move, commodity_price, "
    "macro_indicator, index_inclusion, index_exclusion, other, no_event"
)

# Archive files do not include section/category; filter using URL/title/summary/body text.
FIN_KEYWORDS = [
    "chung khoan", "co phieu", "doanh nghiep", "tai chinh", "ngan hang",
    "bat dong san", "dau tu", "ipo", "co tuc", "loi nhuan", "doanh thu",
    "phat hanh", "mua lai", "sap nhap", "trai phieu", "tin dung", "vn-index",
]

_LOG_LOCK = threading.Lock()


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _LOG_LOCK:
        print(f"[{ts}] {msg}", flush=True)


def _strip_vi(s: str) -> str:
    s = str(s).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()


def _iter_dates(date_from: str, date_to: str) -> list[Path]:
    files = sorted(p for p in RAW_DIR.glob("*.jsonl") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem))
    if date_from:
        files = [p for p in files if p.stem >= date_from]
    if date_to:
        files = [p for p in files if p.stem <= date_to]
    return files


def _load_articles(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue
                if value and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                values[key] = value
    except OSError:
        return {}
    return values


def _resolve_api_key(cli_value: str, env_var_names: list[str]) -> str:
    if cli_value:
        return cli_value
    for env_var_name in env_var_names:
        env_value = os.environ.get(env_var_name, "").strip()
        if env_value:
            return env_value
    candidates = [
        Path.cwd() / ".env",
        REPO_ROOT / ".env",
        workspace_path(".env"),
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        env_map = _load_env_file(candidate)
        for env_var_name in env_var_names:
            value = env_map.get(env_var_name, "").strip()
            if value:
                os.environ[env_var_name] = value
                return value
    return ""


def _resolve_google_api_key(cli_value: str) -> str:
    return _resolve_api_key(cli_value, ["GOOGLE_API_KEY"])


def _resolve_nvidia_api_key(cli_value: str) -> str:
    return _resolve_api_key(cli_value, ["NVIDIA_API_KEY", "NGC_API_KEY"])


def _cache_has_successful_rows(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("llm_error") in {None, ""}:
                    return True
    except OSError:
        return False
    return False


def _is_financial_article(article: dict) -> bool:
    text = " ".join(
        [
            str(article.get("url", "") or ""),
            str(article.get("title", "") or ""),
            str(article.get("summary", "") or ""),
            str(article.get("body_text", "") or ""),
            " ".join(article.get("tags") or []),
            str(article.get("section", "") or ""),
            str(article.get("category", "") or ""),
        ]
    )
    norm = _strip_vi(text)
    return any(k in norm for k in FIN_KEYWORDS)


def _chunk(seq: list[dict], n: int) -> Iterable[list[dict]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


IMPACT_SCOPES = {"stock", "sector", "market"}


def _build_prompt(batch: list[dict], max_summary_chars: int) -> str:
    lines = [
        "You are a Vietnamese financial news analyzer.",
        "For each numbered article, output a JSON object with ALL of these fields:",
        "",
        "  id              : the article id string (copy exactly)",
        "  tickers         : list of stock ticker symbols directly mentioned (uppercase, 2-6 chars)",
        "  related_tickers : list of other tickers implicitly affected by this news (upstream/downstream/peers)",
        "  sentiment       : -1 (negative for named stocks) / 0 (neutral) / 1 (positive)",
        "  confidence      : 0 (unclear/mixed) / 1 (fairly clear) / 2 (very clear signal)",
        "  event_type      : one of: " + PROMPT_TAXONOMY,
        "  magnitude       : 0 (minor) / 1 (moderate) / 2 (major event)",
        "  is_forward_looking : true if article discusses future events or guidance, false if reporting past/current",
        "  market_tone     : -1 / 0 / 1 — broader market sentiment beyond named stocks",
        "  is_rumor        : true if based on speculation/unconfirmed rumor, false if official/confirmed",
        "  surprise_direction : -1 (worse than expected) / 0 (as expected or no comparison) / 1 (better than expected)",
        "  impact_scope    : 'stock' (affects one company) / 'sector' (affects an industry) / 'market' (market-wide)",
        "  named_persons   : list of key people mentioned (CEO, CFO, major shareholders, analysts)",
        "",
        "Output ONLY a JSON array of objects, one per article. No explanation, no markdown.",
        "",
    ]
    for i, a in enumerate(batch, start=1):
        title = str(a.get("title", "") or "").strip()
        summary = str(a.get("summary", "") or "").strip()
        if max_summary_chars > 0:
            summary = summary[:max_summary_chars]
        aid = a["id"]
        lines.extend(
            [
                f"[{i}] id={aid}",
                f"Tieu de: {title}",
                f"Tom tat: {summary}",
                "",
            ]
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Model pool & rate limiter (multi-model Google provider)
# ---------------------------------------------------------------------------

# Free-tier limits (Google AI Studio).
# Models are tried in order — Gemini first (better quality), Gemma as bulk fallback.
GOOGLE_MODEL_POOL = [
    {"name": "gemini-3-flash-preview",       "rpm": 5,  "rpd": 20},
    {"name": "gemini-3.1-flash-lite-preview", "rpm": 15, "rpd": 500},
    {"name": "gemini-2.5-flash",             "rpm": 5,  "rpd": 20},
    {"name": "gemini-2.5-flash-lite",        "rpm": 10, "rpd": 20},
    {"name": "gemma-3-27b-it",               "rpm": 30, "rpd": 14400},
    {"name": "gemma-3-12b-it",               "rpm": 30, "rpd": 14400},
]

# Supported NVIDIA provider models are any text-chat model ids accepted by the
# hosted catalog. This curated pool is the default order used when --provider
# nvidia is selected without an explicit --model override.
NVIDIA_MODEL_POOL = [
    {"name": "deepseek-ai/deepseek-v3.2"},
    {"name": "moonshotai/kimi-k2-instruct-0905"},
    {"name": "moonshotai/kimi-k2-instruct"},
    {"name": "z-ai/glm-4.7"},
    {"name": "deepseek-ai/deepseek-v3.1"},
    {"name": "deepseek-ai/deepseek-v3.1-terminus"},
    {"name": "stepfun-ai/step-3.5-flash"},
    {"name": "meta/llama-4-maverick-17b-128e-instruct"},
    {"name": "mistralai/mistral-large-3-675b-instruct-2512"},
    {"name": "mistralai/mistral-medium-3-instruct"},
    {"name": "google/gemma-3-27b-it"},
    {"name": "microsoft/phi-3.5-mini-instruct"},
    {"name": "nvidia/nemotron-mini-4b-instruct"},
]

NVIDIA_MODEL_ALIASES = {cfg["name"].split("/", 1)[1]: cfg["name"] for cfg in NVIDIA_MODEL_POOL}
PROVIDER_MODEL_POOLS = {
    "google": GOOGLE_MODEL_POOL,
    "nvidia": NVIDIA_MODEL_POOL,
}
DEFAULT_MODELS = {
    "google": "gemini-2.5-flash-lite",
    "nvidia": NVIDIA_MODEL_POOL[0]["name"],
    "ollama": "qwen3.5:4b",
}

# Backward-compatible alias used by the smoke test.
MODEL_POOL = GOOGLE_MODEL_POOL


class ModelRateLimiter:
    """Thread-safe per-model rate limiter (RPM + RPD).

    Iterates models in order and returns the first one with available capacity.
    Blocks (sleeping 1 s between checks) until a slot opens or acquire_timeout
    is exceeded.  Day counters reset automatically at midnight.
    """

    def __init__(self, models: list[dict]) -> None:
        self._lock = threading.Lock()
        self._models = models
        self._rpm_windows: dict[str, list[float]] = {m["name"]: [] for m in models}
        self._rpd_counts: dict[str, int] = {m["name"]: 0 for m in models}
        self._cooldown_until: dict[str, float] = {m["name"]: 0.0 for m in models}
        self._current_day: int = datetime.now().toordinal()

    def _maybe_reset_day(self) -> None:
        today = datetime.now().toordinal()
        if today != self._current_day:
            self._current_day = today
            for m in self._models:
                self._rpd_counts[m["name"]] = 0

    def acquire(self, acquire_timeout: float = 300.0) -> str | None:
        """Return the first model with capacity, blocking until one is free.

        Returns None immediately if every model has hit its daily limit (RPD).
        Returns None after acquire_timeout if all models are only RPM-throttled.
        """
        deadline = time.time() + acquire_timeout
        while True:
            with self._lock:
                self._maybe_reset_day()
                now = time.time()
                any_rpd_left = False
                for m in self._models:
                    name = m["name"]
                    rpm_limit = m.get("rpm")
                    rpd_limit = m.get("rpd")
                    self._rpm_windows[name] = [t for t in self._rpm_windows[name] if now - t < 60.0]
                    if rpd_limit is None or self._rpd_counts[name] < rpd_limit:
                        any_rpd_left = True
                    if now < self._cooldown_until[name]:
                        continue
                    if rpd_limit is None or self._rpd_counts[name] < rpd_limit:
                        if rpm_limit is None or len(self._rpm_windows[name]) < rpm_limit:
                            self._rpm_windows[name].append(now)
                            self._rpd_counts[name] += 1
                            return name
                if not any_rpd_left:
                    return None  # All daily limits exhausted — no point waiting
            if time.time() >= deadline:
                return None
            time.sleep(1.0)

    def all_daily_exhausted(self) -> bool:
        with self._lock:
            self._maybe_reset_day()
            return all(
                m.get("rpd") is not None and self._rpd_counts[m["name"]] >= m["rpd"]
                for m in self._models
            )

    def cooldown(self, model_name: str, seconds: float) -> None:
        if seconds <= 0:
            return
        with self._lock:
            until = time.time() + seconds
            current = self._cooldown_until.get(model_name, 0.0)
            if until > current:
                self._cooldown_until[model_name] = until

    def status(self) -> str:
        with self._lock:
            now = time.time()
            parts = []
            for m in self._models:
                name = m["name"]
                rpm_limit = m.get("rpm")
                rpd_limit = m.get("rpd")
                rpm_used = sum(1 for t in self._rpm_windows[name] if now - t < 60.0)
                cooldown_left = max(0.0, self._cooldown_until[name] - now)
                cooldown_label = f" cooldown={cooldown_left:.0f}s" if cooldown_left > 0 else ""
                parts.append(
                    f"{name}(rpm={rpm_used}/{rpm_limit if rpm_limit is not None else '-'} "
                    f"rpd={self._rpd_counts[name]}/{rpd_limit if rpd_limit is not None else '-'}{cooldown_label})"
                )
            return " | ".join(parts)


def _remote_cooldown_seconds(exc: Exception) -> float:
    if isinstance(exc, TimeoutError):
        return 180.0
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in {500, 502, 503, 504}:
            return 180.0
        return 60.0
    if isinstance(exc, urllib.error.URLError):
        return 180.0
    return 60.0


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str, model: str, timeout: int, num_predict: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": num_predict},
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
    return str(body.get("response", "") or "")


def _extract_json_array(text: str) -> list[dict] | None:
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    text = re.sub(r"```[a-zA-Z]*\n?", "", text).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    chunk = text[start : end + 1]
    try:
        arr = json.loads(chunk)
        if isinstance(arr, list):
            return [x for x in arr if isinstance(x, dict)]
    except Exception:
        pass

    # salvage: split top-level object slices by brace depth
    objs: list[dict] = []
    depth = 0
    obj_start = -1
    for i, ch in enumerate(chunk):
        if ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and obj_start != -1:
                cand = chunk[obj_start : i + 1]
                try:
                    parsed = json.loads(cand)
                    if isinstance(parsed, dict):
                        objs.append(parsed)
                except Exception:
                    continue
    return objs or None


# ---------------------------------------------------------------------------
# Google AI Studio backend
# ---------------------------------------------------------------------------

def _extract_google_text(body: dict) -> str:
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("google_response_missing_candidates")
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        raise ValueError("google_response_missing_content")
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("google_response_missing_parts")
    text_parts = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    if not text_parts:
        raise ValueError("google_response_missing_text")
    return "".join(text_parts)


def _parse_google_array(body: dict, use_json_mode: bool) -> list[dict]:
    text = _extract_google_text(body)
    if use_json_mode:
        try:
            arr = json.loads(text)
        except json.JSONDecodeError:
            arr = _extract_json_array(text)
    else:
        arr = _extract_json_array(text)
    if isinstance(arr, list):
        return [x for x in arr if isinstance(x, dict)]
    return []


def _call_google(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    """Call Gemini/Gemma API. Returns parsed list of dicts.

    Gemini models (gemini-*): use JSON mode for zero-parse-fail guarantee.
    Gemma models (gemma-*): use plain text + JSON extraction fallback.
    Retries on 429 with exponential backoff (up to 3 attempts).
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    use_json_mode = model.startswith("gemini-")
    gen_cfg: dict = {"temperature": 0, "maxOutputTokens": max_output_tokens}
    if use_json_mode:
        gen_cfg["response_mime_type"] = "application/json"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(3):
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 30 * (2 ** attempt)  # 30s, 60s
                _log(f"[google] 429 rate limit, waiting {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)
            else:
                raise

    return _parse_google_array(body, use_json_mode=use_json_mode)


# ---------------------------------------------------------------------------
# NVIDIA hosted LLM backend
# ---------------------------------------------------------------------------

def _normalize_nvidia_model_name(model: str) -> str:
    model = model.strip()
    if not model:
        return model
    if "/" in model:
        return model
    return NVIDIA_MODEL_ALIASES.get(model, model)


def _extract_openai_chat_text(body: dict) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("openai_chat_missing_choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("openai_chat_missing_message")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
        if text_parts:
            return "".join(text_parts)
    raise ValueError("openai_chat_missing_content")


def _parse_openai_chat_array(body: dict) -> list[dict]:
    return _extract_json_array(_extract_openai_chat_text(body)) or []


def _call_nvidia(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    payload = {
        "model": _normalize_nvidia_model_name(model),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_output_tokens,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(3):
        req = urllib.request.Request(
            NVIDIA_CHAT_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 30 * (2 ** attempt)
                _log(f"[nvidia] 429 rate limit, waiting {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)
            else:
                raise

    return _parse_openai_chat_array(body)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _norm_tickers(v: object) -> list[str]:
    if not isinstance(v, list):
        return []
    out = []
    for t in v:
        s = str(t).strip().upper()
        if re.fullmatch(r"[A-Z0-9]{2,6}", s):
            out.append(s)
    return sorted(set(out))


def _norm_small_int(v: object, allowed: set[int]) -> int | None:
    try:
        x = int(v)
    except Exception:
        return None
    return x if x in allowed else None


def _norm_bool(v: object) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes"}:
            return True
        if s in {"false", "0", "no"}:
            return False
    if isinstance(v, (int, float)):
        if v == 1:
            return True
        if v == 0:
            return False
    return None


def _norm_impact_scope(v: object) -> str | None:
    if isinstance(v, str) and v.strip().lower() in IMPACT_SCOPES:
        return v.strip().lower()
    return None


def _norm_str_list(v: object) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()]


def _normalize_record(raw: dict, fallback_id: str) -> dict:
    ev = str(raw.get("event_type", "") or "").strip().lower()
    if ev not in EVENT_TYPES:
        ev = None
    rid = str(raw.get("id", "") or fallback_id).strip() or fallback_id
    return {
        "id": rid,
        "tickers": _norm_tickers(raw.get("tickers")),
        "related_tickers": _norm_tickers(raw.get("related_tickers")),
        "sentiment": _norm_small_int(raw.get("sentiment"), {-1, 0, 1}),
        "confidence": _norm_small_int(raw.get("confidence"), {0, 1, 2}),
        "event_type": ev,
        "magnitude": _norm_small_int(raw.get("magnitude"), {0, 1, 2}),
        "is_forward_looking": _norm_bool(raw.get("is_forward_looking")),
        "market_tone": _norm_small_int(raw.get("market_tone"), {-1, 0, 1}),
        "is_rumor": _norm_bool(raw.get("is_rumor")),
        "surprise_direction": _norm_small_int(raw.get("surprise_direction"), {-1, 0, 1}),
        "impact_scope": _norm_impact_scope(raw.get("impact_scope")),
        "named_persons": _norm_str_list(raw.get("named_persons")),
    }


def _blank_record(article: dict, err: str) -> dict:
    return {
        "id": article["id"],
        "tickers": [],
        "related_tickers": [],
        "sentiment": None,
        "confidence": None,
        "event_type": None,
        "magnitude": None,
        "is_forward_looking": None,
        "market_tone": None,
        "is_rumor": None,
        "surprise_direction": None,
        "impact_scope": None,
        "named_persons": [],
        "llm_error": err,
    }


# ---------------------------------------------------------------------------
# Per-day processing
# ---------------------------------------------------------------------------

def process_day(
    path: Path,
    batch_size: int,
    provider: str,
    model: str,
    api_key: str,
    timeout: int,
    num_predict: int,
    max_summary_chars: int,
    log_every_batches: int,
    rate_limiter: "ModelRateLimiter | None" = None,
) -> dict:
    date = path.stem
    day_t0 = time.time()
    _log(f"[{date}] start")
    articles = _load_articles(path)
    filtered = [a for a in articles if _is_financial_article(a)]
    for i, a in enumerate(filtered, start=1):
        a["id"] = f"{date}_{i:04d}"
    _log(f"[{date}] loaded total={len(articles):,} filtered={len(filtered):,}")

    parsed_ok = 0
    parse_fail = 0
    timeout_fail = 0
    pool_exhausted = False
    rows: list[dict] = []
    n_batches = max(1, math.ceil(len(filtered) / batch_size)) if filtered else 0
    done_batches = 0

    def _run_batch(batch: list[dict], depth: int = 0) -> tuple[list[dict], int, int, int, bool]:
        prompt = _build_prompt(batch, max_summary_chars=max_summary_chars)
        by_id = {a["id"]: a for a in batch}
        model_used = model

        try:
            if provider == "google":
                if rate_limiter is not None:
                    model_used = rate_limiter.acquire(acquire_timeout=300.0)
                    if model_used is None:
                        return ([_blank_record(a, "pool_exhausted") for a in batch], 0, 0, 0, True)
                arr = _call_google(
                    prompt,
                    model=model_used,
                    api_key=api_key,
                    timeout=timeout,
                    max_output_tokens=num_predict,
                )
            elif provider == "nvidia":
                if rate_limiter is not None:
                    model_used = rate_limiter.acquire(acquire_timeout=300.0)
                    if model_used is None:
                        return ([_blank_record(a, "pool_exhausted") for a in batch], 0, 0, 0, True)
                arr = _call_nvidia(
                    prompt,
                    model=model_used,
                    api_key=api_key,
                    timeout=timeout,
                    max_output_tokens=num_predict,
                )
            else:
                resp = _call_ollama(prompt, model=model, timeout=timeout, num_predict=num_predict)
                arr = _extract_json_array(resp) or []
        except Exception as e:
            if provider in {"google", "nvidia"} and rate_limiter is not None:
                rate_limiter.cooldown(model_used, _remote_cooldown_seconds(e))
            if len(batch) > 1:
                split_at = max(1, len(batch) // 2)
                _log(
                    f"[{date}] batch error provider={provider} model={model_used} size={len(batch)} "
                    f"depth={depth} err={type(e).__name__}: {e} | retrying smaller slices"
                )
                left_rows, left_ok, left_pf, left_tf, left_pool = _run_batch(batch[:split_at], depth=depth + 1)
                if left_pool:
                    remaining = [_blank_record(a, "pool_exhausted") for a in batch[split_at:]]
                    return (left_rows + remaining, left_ok, left_pf, left_tf, True)
                right_rows, right_ok, right_pf, right_tf, right_pool = _run_batch(batch[split_at:], depth=depth + 1)
                return (
                    left_rows + right_rows,
                    left_ok + right_ok,
                    left_pf + right_pf,
                    left_tf + right_tf,
                    right_pool,
                )
            if provider == "google":
                err_prefix = "google_error"
            elif provider == "nvidia":
                err_prefix = "nvidia_error"
            else:
                err_prefix = "ollama_error"
            return ([_blank_record(batch[0], f"{err_prefix}:{e}")], 0, 0, 1, False)

        if not arr:
            if provider in {"google", "nvidia"} and rate_limiter is not None:
                rate_limiter.cooldown(model_used, 60.0)
            if len(batch) > 1:
                split_at = max(1, len(batch) // 2)
                _log(
                    f"[{date}] empty/invalid JSON provider={provider} model={model_used} size={len(batch)} "
                    f"depth={depth} | retrying smaller slices"
                )
                left_rows, left_ok, left_pf, left_tf, left_pool = _run_batch(batch[:split_at], depth=depth + 1)
                if left_pool:
                    remaining = [_blank_record(a, "pool_exhausted") for a in batch[split_at:]]
                    return (left_rows + remaining, left_ok, left_pf, left_tf, True)
                right_rows, right_ok, right_pf, right_tf, right_pool = _run_batch(batch[split_at:], depth=depth + 1)
                return (
                    left_rows + right_rows,
                    left_ok + right_ok,
                    left_pf + right_pf,
                    left_tf + right_tf,
                    right_pool,
                )
            return ([_blank_record(batch[0], "json_parse_fail")], 0, 1, 0, False)

        batch_rows: list[dict] = []
        seen: set[str] = set()
        batch_ok = 0
        for obj in arr:
            rid = str(obj.get("id", "") or "").strip()
            if rid in by_id and rid not in seen:
                norm = _normalize_record(obj, rid)
                norm["llm_error"] = None
                batch_rows.append(norm)
                seen.add(rid)
                batch_ok += 1

        missing = [a for a in batch if a["id"] not in seen]
        if missing and len(batch) > 1:
            _log(
                f"[{date}] partial batch response provider={provider} model={model_used} size={len(batch)} "
                f"matched={len(seen)} missing={len(missing)} depth={depth} | retrying missing subset"
            )
            retry_rows, retry_ok, retry_pf, retry_tf, retry_pool = _run_batch(missing, depth=depth + 1)
            return (
                batch_rows + retry_rows,
                batch_ok + retry_ok,
                retry_pf,
                retry_tf,
                retry_pool,
            )

        for article in missing:
            batch_rows.append(_blank_record(article, "missing_object_in_batch"))

        return (batch_rows, batch_ok, len(missing), 0, False)

    for batch in _chunk(filtered, batch_size):
        b_t0 = time.time()
        batch_rows, batch_ok, batch_pf, batch_tf, batch_pool_exhausted = _run_batch(batch)
        rows.extend(batch_rows)
        parsed_ok += batch_ok
        parse_fail += batch_pf
        timeout_fail += batch_tf
        done_batches += 1
        if batch_pool_exhausted:
            pool_exhausted = True
            if rate_limiter is not None:
                _log(f"[{date}] all model daily limits exhausted — stopping | {rate_limiter.status()}")
            break
        if log_every_batches > 0 and (
            done_batches == 1
            or done_batches % log_every_batches == 0
            or done_batches == n_batches
        ):
            elapsed = time.time() - day_t0
            b_elapsed = time.time() - b_t0
            done_items = parsed_ok + parse_fail + timeout_fail
            rate = done_items / elapsed if elapsed > 0 else 0.0
            rem = max(0, len(filtered) - done_items)
            eta = rem / rate if rate > 0 else float("inf")
            eta_s = "inf" if not math.isfinite(eta) else f"{eta:.1f}s"
            _log(
                f"[{date}] batch {done_batches}/{n_batches} "
                f"batch_sec={b_elapsed:.2f} elapsed={elapsed:.1f}s "
                f"done={done_items:,}/{len(filtered):,} rate={rate:.2f} art/s eta={eta_s} "
                f"ok={parsed_ok:,} parse_fail={parse_fail:,} timeout={timeout_fail:,}"
            )

    # Keep deterministic order.
    order = {a["id"]: i for i, a in enumerate(filtered)}
    rows.sort(key=lambda x: order.get(x["id"], 10**9))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_DIR / f"{date}.jsonl.tmp"
    out = CACHE_DIR / f"{date}.jsonl"
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(out)
    day_elapsed = time.time() - day_t0
    done_items = parsed_ok + parse_fail + timeout_fail
    rate = done_items / day_elapsed if day_elapsed > 0 else 0.0
    _log(
        f"[{date}] done sec={day_elapsed:.1f} total={len(articles):,} filtered={len(filtered):,} "
        f"ok={parsed_ok:,} parse_fail={parse_fail:,} timeout={timeout_fail:,} "
        f"rate={rate:.2f} art/s out={out}"
    )

    return {
        "date": date,
        "articles_total": len(articles),
        "articles_filtered": len(filtered),
        "parsed_ok": parsed_ok,
        "parse_fail": parse_fail,
        "timeout_fail": timeout_fail,
        "pool_exhausted": pool_exhausted,
        "out_path": str(out),
        "elapsed_sec": day_elapsed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", type=str, default="")
    ap.add_argument("--date-to", type=str, default="")
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--provider", type=str, default="google", choices=["ollama", "google", "nvidia"],
                    help="LLM provider: 'google' (AI Studio), 'nvidia' (hosted chat LLMs), or 'ollama' (local).")
    ap.add_argument("--model", type=str, default="",
                    help="Model name. For nvidia, bare short names from the curated pool are accepted and comma-separated lists are allowed.")
    ap.add_argument("--api-key", type=str, default="",
                    help="Provider API key. For google/nvidia this also resolves from the matching .env variable.")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--num-predict", type=int, default=8192,
                    help="Max output tokens per batch (8192 needed for batch-size=20 with full schema).")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--workers", type=int, default=1,
                    help="Number of parallel day workers (default 1).")
    ap.add_argument("--max-summary-chars", type=int, default=400,
                    help="Truncate article summary in prompt to this many chars (0 = no truncation).")
    ap.add_argument("--log-every-batches", type=int, default=5,
                    help="Log progress every N batches within each day (default 5).")
    args = ap.parse_args()
    model_arg_supplied = bool(args.model.strip())

    # Resolve model default per provider
    if not args.model:
        args.model = DEFAULT_MODELS[args.provider]

    # Resolve API key
    if args.provider == "google":
        api_key = _resolve_google_api_key(args.api_key)
    elif args.provider == "nvidia":
        api_key = _resolve_nvidia_api_key(args.api_key)
    else:
        api_key = ""
    if args.provider == "google" and not api_key:
        raise SystemExit("ERROR: --api-key or GOOGLE_API_KEY required for google provider (shell env or .env).")
    if args.provider == "nvidia" and not api_key:
        raise SystemExit("ERROR: --api-key or NVIDIA_API_KEY required for nvidia provider (shell env or .env).")

    # Use provider pools for hosted backends.
    rate_limiter: ModelRateLimiter | None = None
    if args.provider in PROVIDER_MODEL_POOLS:
        if args.provider == "google":
            model_pool = GOOGLE_MODEL_POOL
        elif model_arg_supplied:
            model_pool = [{"name": _normalize_nvidia_model_name(name)} for name in args.model.split(",") if name.strip()]
        else:
            model_pool = NVIDIA_MODEL_POOL
        rate_limiter = ModelRateLimiter(model_pool)
        _log(f"Model pool: {[m['name'] for m in model_pool]}")

    files = _iter_dates(args.date_from, args.date_to)
    if not files:
        print("No input files matched date filters.")
        return

    _log(
        f"Run config: files={len(files)} from={args.date_from or '-'} to={args.date_to or '-'} "
        f"provider={args.provider} model={args.model} batch_size={args.batch_size} workers={args.workers} "
        f"timeout={args.timeout}s num_predict={args.num_predict} "
        f"max_summary_chars={args.max_summary_chars} overwrite={args.overwrite}"
    )

    total_days = 0
    total_filtered = 0
    total_ok = 0
    total_fail = 0
    total_timeout = 0
    total_elapsed = 0.0
    skipped = 0
    retry_error_only = 0
    pending: list[Path] = []
    for p in files:
        out = CACHE_DIR / f"{p.stem}.jsonl"
        if out.exists() and not args.overwrite:
            if _cache_has_successful_rows(out):
                skipped += 1
            else:
                retry_error_only += 1
                pending.append(p)
        else:
            pending.append(p)

    _log(
        f"Days pending={len(pending)} skipped_existing={skipped} "
        f"retry_error_only={retry_error_only}"
    )

    start = time.time()
    if args.workers <= 1:
        for i, p in enumerate(pending, start=1):
            stats = process_day(
                p,
                batch_size=args.batch_size,
                provider=args.provider,
                model=args.model,
                api_key=api_key,
                timeout=args.timeout,
                num_predict=args.num_predict,
                max_summary_chars=args.max_summary_chars,
                log_every_batches=args.log_every_batches,
                rate_limiter=rate_limiter,
            )
            total_days += 1
            total_filtered += stats["articles_filtered"]
            total_ok += stats["parsed_ok"]
            total_fail += stats["parse_fail"]
            total_timeout += stats["timeout_fail"]
            total_elapsed += stats["elapsed_sec"]
            wall = time.time() - start
            day_rate = total_days / wall if wall > 0 else 0.0
            rem_days = len(pending) - total_days
            eta_days = rem_days / day_rate if day_rate > 0 else float("inf")
            eta_s = "inf" if not math.isfinite(eta_days) else f"{eta_days/60:.1f}m"
            _log(
                f"[progress] {i}/{len(pending)} days done | "
                f"filtered={total_filtered:,} ok={total_ok:,} parse_fail={total_fail:,} timeout={total_timeout:,} "
                f"day_rate={day_rate:.3f} days/s eta={eta_s}"
            )
            if stats.get("pool_exhausted"):
                _log(f"All model daily limits exhausted after {total_days} days — stopping early.")
                break
    else:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {
                ex.submit(
                    process_day,
                    p,
                    args.batch_size,
                    args.provider,
                    args.model,
                    api_key,
                    args.timeout,
                    args.num_predict,
                    args.max_summary_chars,
                    args.log_every_batches,
                    rate_limiter,
                ): p.stem
                for p in pending
            }
            for i, fut in enumerate(cf.as_completed(futs), start=1):
                try:
                    stats = fut.result()
                except Exception as e:
                    _log(f"[{futs[fut]}] worker_error: {e}")
                    continue
                total_days += 1
                total_filtered += stats["articles_filtered"]
                total_ok += stats["parsed_ok"]
                total_fail += stats["parse_fail"]
                total_timeout += stats["timeout_fail"]
                total_elapsed += stats["elapsed_sec"]
                wall = time.time() - start
                day_rate = total_days / wall if wall > 0 else 0.0
                rem_days = len(pending) - total_days
                eta_days = rem_days / day_rate if day_rate > 0 else float("inf")
                eta_s = "inf" if not math.isfinite(eta_days) else f"{eta_days/60:.1f}m"
                _log(
                    f"[progress] {i}/{len(pending)} days done | "
                    f"filtered={total_filtered:,} ok={total_ok:,} parse_fail={total_fail:,} timeout={total_timeout:,} "
                    f"day_rate={day_rate:.3f} days/s eta={eta_s}"
                )
                if stats.get("pool_exhausted"):
                    _log(f"All model daily limits exhausted after {total_days} days — stopping early.")
                    ex.shutdown(wait=False, cancel_futures=True)
                    break

    wall_total = time.time() - start
    art_rate_wall = total_filtered / wall_total if wall_total > 0 else 0.0
    _log("Done.")
    _log(f"Processed days: {total_days} | skipped existing: {skipped}")
    _log(f"Filtered articles: {total_filtered:,}")
    _log(f"Parsed ok: {total_ok:,} | parse_fail: {total_fail:,} | timeout_fail: {total_timeout:,}")
    _log(
        f"Wall time: {wall_total:.1f}s | sum(day elapsed): {total_elapsed:.1f}s | "
        f"wall throughput: {art_rate_wall:.2f} filtered art/s"
    )


if __name__ == "__main__":
    main()
