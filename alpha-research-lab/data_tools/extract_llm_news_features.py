"""
Extract structured LLM features from CafeF daily news JSONL files.

Input:
- data/news/cafef/raw/YYYY-MM-DD.jsonl

Output:
- data/llm_cache/YYYY-MM-DD.jsonl (one JSON object per filtered article)

Providers:
- auto         : hosted auto-pool across configured providers, ranked by observed latency
- ollama       : local Ollama server (default model: qwen3.5:4b)
- google       : Google AI Studio / Gemini API
- nvidia       : NVIDIA hosted LLM API
- mistral      : Mistral chat completions API
- huggingface  : Hugging Face router chat completions API
- vercel       : Vercel AI Gateway OpenAI-compatible chat completions API

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
- expectation_alignment : beats/meets/misses/not_applicable vs plan / target / expectation / trajectory
- information_novelty   : new/follow_up/recycled/unclear
- macro_theme           : rates/fx/liquidity/credit/real_estate/banking/exports/commodities/energy/public_investment/regulation/geopolitics/consumption/technology/industrials/none
- source_authority      : official/management/media_report/analyst/rumor_source/unclear
- causal_impact_label   : revenue_positive/revenue_negative/cost_positive/cost_negative/financing_positive/financing_negative/regulatory_positive/regulatory_negative/sentiment_only/mixed/none

Design:
- Resume-safe: skip existing day outputs unless --overwrite
- Atomic writes: write .tmp then rename
- Robust parse: salvage partial JSON where possible (Ollama); JSON mode for Google
- Batch concurrency is per-day; days stay serial so a cancel stops before later days start
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import os
import re
import statistics
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
import pandas as pd
from path_utils import data_path, workspace_path
from typing import Iterable
from src.repo_paths import artifact_path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = data_path("news/cafef/raw")
CACHE_DIR = data_path("llm_cache")
HOSTED_MODEL_STATS_PATH = artifact_path("llm_runtime", "hosted_model_stats.json")
NVIDIA_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"
HUGGINGFACE_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
VERCEL_CHAT_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"
CEREBRAS_CHAT_URL = "https://api.cerebras.ai/v1/chat/completions"
FIREWORKS_CHAT_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENCODE_CHAT_URL = "https://opencode.ai/zen/v1/chat/completions"

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
    candidates = [
        Path.cwd() / ".env",
        REPO_ROOT / ".env",
        workspace_path(".env"),
    ]
    seen: set[Path] = set()
    env_maps: list[dict[str, str]] = []
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        env_maps.append(_load_env_file(candidate))
    for env_var_name in env_var_names:
        env_value = os.environ.get(env_var_name, "").strip()
        if env_value:
            return env_value
        for env_map in env_maps:
            value = env_map.get(env_var_name, "").strip()
            if value:
                os.environ[env_var_name] = value
                return value
    return ""


def _resolve_google_api_key(cli_value: str) -> str:
    return _resolve_api_key(cli_value, ["GOOGLE_API_KEY"])


def _resolve_nvidia_api_key(cli_value: str) -> str:
    return _resolve_api_key(cli_value, ["NVIDIA_API_KEY", "NGC_API_KEY"])


def _resolve_mistral_api_key(cli_value: str, model_name: str = "") -> str:
    return _resolve_api_key(cli_value, _mistral_api_env_names(model_name))


def _resolve_huggingface_api_key(cli_value: str) -> str:
    return _resolve_api_key(cli_value, ["HUGGINGFACE_FINEGRAINED", "HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN"])


def _resolve_vercel_api_key(cli_value: str) -> str:
    return _resolve_api_key(cli_value, ["VERCEL_AI_GATEWAY_API_KEY", "AI_GATEWAY_API_KEY", "VERCEL_OIDC_TOKEN"])


def _resolve_provider_api_key(provider: str, cli_value: str = "", model_name: str = "") -> str:
    if provider == "google":
        return _resolve_google_api_key(cli_value)
    if provider == "nvidia":
        return _resolve_nvidia_api_key(cli_value)
    if provider == "cerebras":
        return _resolve_api_key(cli_value, ["CEREBRAS_API_KEY"])
    if provider == "fireworks":
        return _resolve_api_key(cli_value, ["FIREWORKS_API_KEY"])
    if provider == "groq":
        return _resolve_api_key(cli_value, ["GROQ_API_KEY"])
    if provider == "mistral":
        return _resolve_mistral_api_key(cli_value, model_name=model_name)
    if provider == "huggingface":
        return _resolve_huggingface_api_key(cli_value)
    if provider == "vercel":
        return _resolve_vercel_api_key(cli_value)
    if provider == "opencode":
        return _resolve_api_key(cli_value, ["OPENCODE_ZEN_API_KEY", "OPENCODE_API_KEY"])
    return ""


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
    keep_hits = sum(1 for term in FINANCIAL_KEEP_TERMS if term in norm)
    fluff_hits = sum(1 for term in FLUFF_DROP_TERMS if term in norm)
    if keep_hits == 0:
        return False
    if fluff_hits >= 2 and keep_hits < 2:
        return False
    return True


def _chunk(seq: list[dict], n: int) -> Iterable[list[dict]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _clean_str(value: object) -> str:
    return str(value).strip()


def _text_blob(article: dict) -> str:
    return " ".join(
        [
            _clean_str(article.get("title", "") or ""),
            _clean_str(article.get("summary", "") or ""),
            _clean_str(article.get("body_text", "") or ""),
        ]
    ).strip()


def _source_domain_from_url(url: object) -> str | None:
    raw = _clean_str(url)
    if not raw:
        return None
    parsed = urlparse(raw)
    host = parsed.netloc.lower().strip()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _parse_published_at(value: object) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    if getattr(ts, "tzinfo", None) is not None:
        return ts.tz_convert("Asia/Ho_Chi_Minh")
    return ts.tz_localize("Asia/Ho_Chi_Minh")


def _event_time_type_from_published_at(value: object) -> str:
    ts = _parse_published_at(value)
    if ts is None:
        return "unknown"
    minute_of_day = ts.hour * 60 + ts.minute
    if minute_of_day < VN_MARKET_OPEN_MINUTE:
        return "pre_market"
    if minute_of_day <= VN_MARKET_CLOSE_MINUTE:
        return "intraday"
    return "post_market"


def _article_semantic_flags(article: dict) -> dict[str, object]:
    text = _strip_vi(_text_blob(article))
    return {
        "event_time_type": _event_time_type_from_published_at(article.get("published_at")),
        "source_domain": _source_domain_from_url(article.get("url")),
        "article_text_length": int(len(_text_blob(article).strip())),
        "article_has_numbers": bool(re.search(r"\d", text)),
        "article_mentions_percent": bool(
            re.search(r"%|\bpercent\b|\bphan tram\b", text)
        ),
    }


IMPACT_SCOPES = {"stock", "sector", "market"}
EXPECTATION_ALIGNMENTS = {"beats", "meets", "misses", "not_applicable"}
INFORMATION_NOVELTIES = {"new", "follow_up", "recycled", "unclear"}
MACRO_THEMES = {
    "rates", "fx", "liquidity", "credit", "real_estate", "banking",
    "exports", "commodities", "energy", "public_investment", "regulation",
    "geopolitics", "consumption", "technology", "industrials", "none",
}
SOURCE_AUTHORITIES = {"official", "management", "media_report", "analyst", "rumor_source", "unclear"}
CAUSAL_IMPACT_LABELS = {
    "revenue_positive", "revenue_negative", "cost_positive", "cost_negative",
    "financing_positive", "financing_negative", "regulatory_positive",
    "regulatory_negative", "sentiment_only", "mixed", "none",
}

FINANCIAL_KEEP_TERMS = [
    "chung khoan", "co phieu", "doanh nghiep", "tai chinh", "ngan hang",
    "bat dong san", "dau tu", "ipo", "co tuc", "loi nhuan", "doanh thu",
    "phat hanh", "mua lai", "sap nhap", "trai phieu", "tin dung", "vn-index",
    "lai suat", "ty gia", "fx", "usd", "tien te", "nha dau tu",
    "ket qua kinh doanh", "bao cao tai chinh", "ke hoach", "muc tieu",
    "san giao dich", "xuat khau", "hang hoa", "gia dau", "dien", "than",
    "khi", "thep", "ban le", "public investment",
]

FLUFF_DROP_TERMS = [
    "showbiz", "celebrity", "am thuc", "du lich", "thoi trang", "lam dep",
    "suc khoe", "doi song", "gia dinh", "the thao", "bong da", "giai tri",
    "quan ao", "xe dep", "cau chuyen", "chia se", "tam su",
]

VN_MARKET_OPEN_MINUTE = 9 * 60
VN_MARKET_CLOSE_MINUTE = 14 * 60 + 45


def _build_prompt(batch: list[dict], max_summary_chars: int) -> str:
    lines = [
        "You are reading Vietnamese CafeF financial news.",
        "Many articles are recap, rolling-update, or headline-led; do not force hidden numbers.",
        "Use only the article text for semantic judgments.",
        "Do not extract timestamps, source domains, authors, URLs, or exact numeric expectations.",
        "Return JSON array only.",
        "",
        "Fields:",
        "- id",
        "- tickers / related_tickers",
        "- sentiment: -1 | 0 | 1",
        "- confidence: 0 | 1 | 2",
        "- event_type, magnitude: 0 | 1 | 2",
        "- is_forward_looking, market_tone: -1 | 0 | 1",
        "- is_rumor, surprise_direction: bool / -1 | 0 | 1",
        "- impact_scope, named_persons",
        "- expectation_alignment: beats | meets | misses | not_applicable",
        "- information_novelty: new | follow_up | recycled | unclear",
        "- macro_theme: rates | fx | liquidity | credit | real_estate | banking | exports | commodities | energy | public_investment | regulation | geopolitics | consumption | technology | industrials | none",
        "- source_authority: official | management | media_report | analyst | rumor_source | unclear",
        "- causal_impact_label: revenue_positive | revenue_negative | cost_positive | cost_negative | financing_positive | financing_negative | regulatory_positive | regulatory_negative | sentiment_only | mixed | none",
        "",
        "Expectation alignment is relative to plan / target / expectation / prior trajectory, not only analyst consensus.",
        "Information novelty should mark recap or repeated story lines as recycled.",
        "Use the exact codes above. Do not output words like positive, negative, neutral, low, high, or company.",
        "Single dominant macro_theme and single dominant causal_impact_label only.",
        "Keep output strict JSON, no markdown, no prose.",
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
# Hosted model pools, credentials, and scheduler
# ---------------------------------------------------------------------------

HOSTED_PROVIDERS = {
    "auto",
    "google",
    "nvidia",
    "mistral",
    "huggingface",
    "vercel",
    "cerebras",
    "fireworks",
    "groq",
    "opencode",
}
HOSTED_PROVIDER_NAMES = {
    "google",
    "nvidia",
    "mistral",
    "huggingface",
    "vercel",
    "cerebras",
    "fireworks",
    "groq",
    "opencode",
}
AUTO_STABLE_PROVIDER_NAMES = {"google", "nvidia", "mistral"}

# Free-tier limits (Google AI Studio) are enforced in-process. Other providers
# run unbounded unless their APIs explicitly throttle us.
GOOGLE_MODEL_POOL = [
    {"name": "gemini-2.5-flash-lite", "rpm": 10, "rpd": 20, "seed_latency": 2.0},
    {"name": "gemini-3.1-flash-lite-preview", "rpm": 15, "rpd": 500, "seed_latency": 3.4},
    {"name": "gemini-3-flash-preview", "rpm": 5, "rpd": 20, "seed_latency": 9.6},
    {"name": "gemini-2.5-flash", "rpm": 5, "rpd": 20, "seed_latency": 12.6},
    {"name": "gemma-3-27b-it", "rpm": 30, "rpd": 14400, "seed_latency": 12.6},
    {"name": "gemma-3-12b-it", "rpm": 30, "rpd": 14400, "seed_latency": 42.0},
]

NVIDIA_MODEL_POOL = [
    {"name": "stepfun-ai/step-3.5-flash", "seed_latency": 2.8},
    {"name": "nvidia/nemotron-mini-4b-instruct", "seed_latency": 3.1},
    {"name": "microsoft/phi-3.5-mini-instruct", "seed_latency": 3.5},
    {"name": "moonshotai/kimi-k2", "seed_latency": 4.5},
    {"name": "moonshotai/kimi-k2-0905", "seed_latency": 4.8},
    {"name": "moonshotai/kimi-k2.5", "seed_latency": 5.0},
    {"name": "deepseek-ai/deepseek-v3_2", "seed_latency": 5.2},
    {"name": "z-ai/glm-4.7", "seed_latency": 5.5},
    {"name": "deepseek-ai/deepseek-v3.1", "seed_latency": 6.0},
    {"name": "deepseek-ai/deepseek-v3.1-terminus", "seed_latency": 6.2},
    {"name": "google/gemma-3-27b-it", "seed_latency": 7.0},
    {"name": "mistralai/mistral-medium-3-instruct", "seed_latency": 7.5},
    {"name": "meta/llama-4-maverick-17b-128e-instruct", "seed_latency": 8.0},
    {"name": "mistralai/mistral-large-3-675b-instruct-2512", "seed_latency": 10.0},
]

MISTRAL_MODEL_POOL = [
    {"name": "mistral-small-latest", "seed_latency": 2.5},
    {"name": "codestral-latest", "seed_latency": 3.1},
    {"name": "mistral-medium-latest", "seed_latency": 4.8},
    {"name": "mistral-large-latest", "seed_latency": 7.5},
]

HUGGINGFACE_MODEL_POOL = [
    {"name": "microsoft/Phi-4-mini-instruct", "seed_latency": 3.0},
    {"name": "meta-llama/Llama-3.3-70B-Instruct", "seed_latency": 4.8},
    {"name": "Qwen/Qwen2.5-72B-Instruct", "seed_latency": 5.0},
    {"name": "mistralai/Mistral-Small-3.1-24B-Instruct-2503", "seed_latency": 5.5},
]

VERCEL_MODEL_POOL = [
    {"name": "google/gemini-2.5-flash-lite", "seed_latency": 2.6},
    {"name": "mistral/mistral-small", "seed_latency": 3.1},
    {"name": "moonshotai/kimi-k2.5", "seed_latency": 4.8},
    {"name": "deepseek/deepseek-v3.2", "seed_latency": 5.2},
    {"name": "minimax/minimax-m2.5", "seed_latency": 4.2},
    {"name": "mistral/mistral-large-3", "seed_latency": 7.5},
]

CEREBRAS_MODEL_POOL = [
    {"name": "llama3.1-8b", "seed_latency": 2.6},
    {"name": "llama-3.3-70b", "seed_latency": 4.5},
    {"name": "gpt-oss-120b", "seed_latency": 4.8},
    {"name": "qwen-3-32b", "seed_latency": 5.0},
    {"name": "zai-glm-4.7", "seed_latency": 5.3},
]

FIREWORKS_MODEL_POOL = [
    {"name": "accounts/fireworks/models/llama-v3p1-8b-instruct", "seed_latency": 2.7},
    {"name": "accounts/fireworks/models/deepseek-v3p1", "seed_latency": 3.6},
    {"name": "accounts/fireworks/models/llama-v3p1-70b-instruct", "seed_latency": 4.8},
    {"name": "accounts/fireworks/models/qwen3-0p6b", "seed_latency": 2.9},
]

GROQ_MODEL_POOL = [
    {"name": "llama-3.1-8b-instant", "seed_latency": 2.2},
    {"name": "llama-3.3-70b-versatile", "seed_latency": 3.6},
    {"name": "openai/gpt-oss-20b", "seed_latency": 3.0},
    {"name": "openai/gpt-oss-120b", "seed_latency": 4.1},
    {"name": "deepseek-r1-distill-llama-70b", "seed_latency": 4.8},
]

OPENCODE_MODEL_POOL = [
    {"name": "opencode/gpt-5.2-codex", "seed_latency": 2.2},
    {"name": "opencode/gpt-5.2", "seed_latency": 2.6},
    {"name": "opencode/claude-opus-4-5", "seed_latency": 4.0},
    {"name": "opencode/glm-4.7", "seed_latency": 3.5},
    {"name": "opencode/kimi-k2.5", "seed_latency": 4.2},
    {"name": "opencode/minimax-m2.5", "seed_latency": 3.3},
    {"name": "opencode/nemotron-3-super-free", "seed_latency": 4.7},
]

PROVIDER_MODEL_POOLS = {
    "google": GOOGLE_MODEL_POOL,
    "nvidia": NVIDIA_MODEL_POOL,
    "mistral": MISTRAL_MODEL_POOL,
    "huggingface": HUGGINGFACE_MODEL_POOL,
    "vercel": VERCEL_MODEL_POOL,
    "cerebras": CEREBRAS_MODEL_POOL,
    "fireworks": FIREWORKS_MODEL_POOL,
    "groq": GROQ_MODEL_POOL,
    "opencode": OPENCODE_MODEL_POOL,
}
DEFAULT_MODELS = {
    "auto": "",
    "google": GOOGLE_MODEL_POOL[0]["name"],
    "nvidia": NVIDIA_MODEL_POOL[0]["name"],
    "mistral": MISTRAL_MODEL_POOL[0]["name"],
    "huggingface": HUGGINGFACE_MODEL_POOL[0]["name"],
    "vercel": VERCEL_MODEL_POOL[0]["name"],
    "ollama": "qwen3.5:4b",
}

# Backward-compatible alias used by the smoke test.
MODEL_POOL = GOOGLE_MODEL_POOL
NVIDIA_MODEL_ALIASES = {cfg["name"].split("/", 1)[1]: cfg["name"] for cfg in NVIDIA_MODEL_POOL}
NVIDIA_MODEL_ALIASES.update(
    {
        "step-3.5-flash": "stepfun-ai/step-3.5-flash",
        "kimi-k2-instruct": "moonshotai/kimi-k2",
        "kimi-k2-instruct-0905": "moonshotai/kimi-k2-0905",
        "deepseek-v3.2": "deepseek-ai/deepseek-v3_2",
    }
)


@dataclass(frozen=True)
class HostedModelSpec:
    provider: str
    name: str
    api_key_envs: tuple[str, ...]
    rpm: int | None = None
    rpd: int | None = None
    seed_latency: float = 10.0
    priority_tier: int = 0

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.name}"


def _provider_error_prefix(provider: str) -> str:
    return {
        "google": "google_error",
        "nvidia": "nvidia_error",
        "mistral": "mistral_error",
        "huggingface": "huggingface_error",
        "vercel": "vercel_error",
        "cerebras": "cerebras_error",
        "fireworks": "fireworks_error",
        "groq": "groq_error",
        "opencode": "opencode_error",
    }.get(provider, "ollama_error")


def _mistral_api_env_names(model_name: str = "") -> list[str]:
    lowered = model_name.lower()
    if "codestral" in lowered or "devstral" in lowered or "costral" in lowered:
        return ["MISTRAL_COSTRAL_API_KEY", "MISTRAL_CODESTRAL_API_KEY", "MISTRAL_API_KEY"]
    return ["MISTRAL_API_KEY", "MISTRAL_COSTRAL_API_KEY", "MISTRAL_CODESTRAL_API_KEY"]


def _api_env_names_for_provider(provider: str, model_name: str = "") -> list[str]:
    if provider == "google":
        return ["GOOGLE_API_KEY"]
    if provider == "nvidia":
        return ["NVIDIA_API_KEY", "NGC_API_KEY"]
    if provider == "cerebras":
        return ["CEREBRAS_API_KEY"]
    if provider == "fireworks":
        return ["FIREWORKS_API_KEY"]
    if provider == "groq":
        return ["GROQ_API_KEY"]
    if provider == "mistral":
        return _mistral_api_env_names(model_name)
    if provider == "huggingface":
        return ["HUGGINGFACE_FINEGRAINED", "HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN"]
    if provider == "vercel":
        return ["VERCEL_AI_GATEWAY_API_KEY", "AI_GATEWAY_API_KEY", "VERCEL_OIDC_TOKEN"]
    if provider == "opencode":
        return ["OPENCODE_ZEN_API_KEY", "OPENCODE_API_KEY"]
    return []


def _build_hosted_spec(provider: str, cfg: dict) -> HostedModelSpec:
    return HostedModelSpec(
        provider=provider,
        name=str(cfg["name"]),
        api_key_envs=tuple(_api_env_names_for_provider(provider, str(cfg["name"]))),
        rpm=cfg.get("rpm"),
        rpd=cfg.get("rpd"),
        seed_latency=float(cfg.get("seed_latency", 10.0)),
        priority_tier=int(cfg.get("priority_tier", 0) or 0),
    )


def _coerce_hosted_spec(item: HostedModelSpec | dict | str, default_provider: str = "hosted") -> HostedModelSpec:
    if isinstance(item, HostedModelSpec):
        return item
    if isinstance(item, str):
        return HostedModelSpec(
            provider=default_provider,
            name=item,
            api_key_envs=tuple(_api_env_names_for_provider(default_provider, item)),
        )
    provider = str(item.get("provider", default_provider))
    return HostedModelSpec(
        provider=provider,
        name=str(item["name"]),
        api_key_envs=tuple(item.get("api_key_envs") or _api_env_names_for_provider(provider, str(item["name"]))),
        rpm=item.get("rpm"),
        rpd=item.get("rpd"),
        seed_latency=float(item.get("seed_latency", 10.0)),
        priority_tier=int(item.get("priority_tier", 0) or 0),
    )


class HostedModelScheduler:
    """Thread-safe hosted scheduler with latency ranking, quotas, and cooldowns."""

    def __init__(self, models: list[HostedModelSpec | dict | str], stats_path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._models = [_coerce_hosted_spec(model) for model in models]
        self._models_by_key = {model.key: model for model in self._models}
        self._models_by_name = {model.name: model for model in self._models}
        self._providers = sorted({model.provider for model in self._models})
        self._rpm_windows: dict[str, list[float]] = {model.key: [] for model in self._models}
        self._rpd_counts: dict[str, int] = {model.key: 0 for model in self._models}
        self._cooldown_until: dict[str, float] = {model.key: 0.0 for model in self._models}
        self._provider_cooldown_until: dict[str, float] = {provider: 0.0 for provider in self._providers}
        self._inflight_model_counts: dict[str, int] = {model.key: 0 for model in self._models}
        self._inflight_provider_counts: dict[str, int] = {provider: 0 for provider in self._providers}
        self._current_day: int = datetime.now().toordinal()
        self._stats_path = Path(stats_path or HOSTED_MODEL_STATS_PATH)
        self._stats = self._load_stats()
        self._seed_stats()

    def _load_stats(self) -> dict[str, dict]:
        try:
            payload = json.loads(self._stats_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        models = payload.get("models", payload) if isinstance(payload, dict) else {}
        if not isinstance(models, dict):
            return {}
        out: dict[str, dict] = {}
        for key, raw in models.items():
            if not isinstance(raw, dict):
                continue
            recent_latencies = [
                float(value)
                for value in raw.get("recent_latencies", [])
                if isinstance(value, (int, float)) and float(value) > 0
            ][-20:]
            out[str(key)] = {
                "success_count": int(raw.get("success_count", 0) or 0),
                "failure_count": int(raw.get("failure_count", 0) or 0),
                "failure_streak": int(raw.get("failure_streak", 0) or 0),
                "recent_latencies": recent_latencies,
                "last_success": str(raw.get("last_success", "") or ""),
                "last_failure": str(raw.get("last_failure", "") or ""),
                "cooldown_until": float(raw.get("cooldown_until", 0.0) or 0.0),
            }
        return out

    def _seed_stats(self) -> None:
        now = time.time()
        for model in self._models:
            stats = self._stats.setdefault(
                model.key,
                {
                    "success_count": 0,
                    "failure_count": 0,
                    "failure_streak": 0,
                    "recent_latencies": [],
                    "last_success": "",
                    "last_failure": "",
                    "cooldown_until": 0.0,
                },
            )
            cooldown_until = float(stats.get("cooldown_until", 0.0) or 0.0)
            self._cooldown_until[model.key] = cooldown_until if cooldown_until > now else 0.0
        for provider in self._providers:
            self._provider_cooldown_until[provider] = 0.0

    def _save_stats_locked(self) -> None:
        self._stats_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "models": self._stats,
        }
        tmp = self._stats_path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.replace(self._stats_path)

    def _resolve_key(self, model_name_or_key: str) -> str:
        if model_name_or_key in self._models_by_key:
            return model_name_or_key
        if model_name_or_key in self._models_by_name:
            return self._models_by_name[model_name_or_key].key
        raise KeyError(model_name_or_key)

    def _maybe_reset_day_locked(self) -> None:
        today = datetime.now().toordinal()
        if today != self._current_day:
            self._current_day = today
            for model in self._models:
                self._rpd_counts[model.key] = 0

    def _provider_is_cooldown_locked(self, provider: str, now: float) -> bool:
        return self._provider_cooldown_until.get(provider, 0.0) > now

    def _model_is_available_locked(self, model: HostedModelSpec) -> bool:
        return self._inflight_model_counts.get(model.key, 0) == 0 and self._inflight_provider_counts.get(
            model.provider, 0
        ) == 0

    def _reserve_locked(self, model: HostedModelSpec, now: float) -> None:
        self._rpm_windows[model.key].append(now)
        self._rpd_counts[model.key] += 1
        self._inflight_model_counts[model.key] = self._inflight_model_counts.get(model.key, 0) + 1
        self._inflight_provider_counts[model.provider] = self._inflight_provider_counts.get(model.provider, 0) + 1

    def _release_locked(self, model: HostedModelSpec) -> None:
        model_count = self._inflight_model_counts.get(model.key, 0)
        if model_count > 0:
            self._inflight_model_counts[model.key] = model_count - 1
        provider_count = self._inflight_provider_counts.get(model.provider, 0)
        if provider_count > 0:
            self._inflight_provider_counts[model.provider] = provider_count - 1

    def _prune_rpm_locked(self, now: float) -> None:
        for key, timestamps in self._rpm_windows.items():
            self._rpm_windows[key] = [ts for ts in timestamps if now - ts < 60.0]

    def _latency_score_locked(self, model: HostedModelSpec) -> float:
        stats = self._stats.get(model.key, {})
        latencies = stats.get("recent_latencies") or []
        if latencies:
            return float(statistics.median(latencies))
        return model.seed_latency

    def _failure_penalty_locked(self, model: HostedModelSpec) -> float:
        stats = self._stats.get(model.key, {})
        streak = int(stats.get("failure_streak", 0) or 0)
        return min(60.0, streak * 10.0)

    def _score_locked(self, model: HostedModelSpec, index: int) -> float:
        return (
            self._latency_score_locked(model)
            + self._failure_penalty_locked(model)
            + (model.priority_tier * 100.0)
            + (index / 1000.0)
        )

    def acquire_spec(self, acquire_timeout: float = 300.0) -> HostedModelSpec | None:
        deadline = time.time() + acquire_timeout
        while True:
            with self._lock:
                self._maybe_reset_day_locked()
                now = time.time()
                self._prune_rpm_locked(now)
                candidates: list[tuple[float, HostedModelSpec]] = []
                any_rpd_left = False
                for index, model in enumerate(self._models):
                    key = model.key
                    rpm_limit = model.rpm
                    rpd_limit = model.rpd
                    if rpd_limit is None or self._rpd_counts[key] < rpd_limit:
                        any_rpd_left = True
                    if now < self._cooldown_until[key]:
                        continue
                    if self._provider_is_cooldown_locked(model.provider, now):
                        continue
                    if not self._model_is_available_locked(model):
                        continue
                    if rpd_limit is not None and self._rpd_counts[key] >= rpd_limit:
                        continue
                    if rpm_limit is not None and len(self._rpm_windows[key]) >= rpm_limit:
                        continue
                    candidates.append((self._score_locked(model, index), model))
                if candidates:
                    _, chosen = min(candidates, key=lambda item: item[0])
                    self._reserve_locked(chosen, now)
                    return chosen
                if not any_rpd_left:
                    return None
            if time.time() >= deadline:
                return None
            time.sleep(1.0)

    def acquire(self, acquire_timeout: float = 300.0) -> str | None:
        model = self.acquire_spec(acquire_timeout=acquire_timeout)
        return model.name if model else None

    def specs(self) -> list[HostedModelSpec]:
        return list(self._models)

    def all_daily_exhausted(self) -> bool:
        with self._lock:
            self._maybe_reset_day_locked()
            return all(
                model.rpd is not None and self._rpd_counts[model.key] >= model.rpd
                for model in self._models
            )

    def cooldown(self, model_name_or_key: str, seconds: float) -> None:
        if seconds <= 0:
            return
        with self._lock:
            key = self._resolve_key(model_name_or_key)
            until = time.time() + seconds
            current = self._cooldown_until.get(key, 0.0)
            if until > current:
                self._cooldown_until[key] = until
                self._stats.setdefault(key, {})["cooldown_until"] = until
                self._save_stats_locked()

    def provider_cooldown(self, provider: str, seconds: float) -> None:
        if seconds <= 0:
            return
        with self._lock:
            until = time.time() + seconds
            current = self._provider_cooldown_until.get(provider, 0.0)
            if until > current:
                self._provider_cooldown_until[provider] = until

    def record_success(self, model_name_or_key: str, latency_sec: float) -> None:
        with self._lock:
            key = self._resolve_key(model_name_or_key)
            model = self._models_by_key[key]
            self._release_locked(model)
            stats = self._stats.setdefault(
                key,
                {
                    "success_count": 0,
                    "failure_count": 0,
                    "failure_streak": 0,
                    "recent_latencies": [],
                    "last_success": "",
                    "last_failure": "",
                    "cooldown_until": 0.0,
                },
            )
            latencies = list(stats.get("recent_latencies") or [])
            if latency_sec > 0:
                latencies.append(float(latency_sec))
            stats["recent_latencies"] = latencies[-20:]
            stats["success_count"] = int(stats.get("success_count", 0) or 0) + 1
            stats["failure_streak"] = 0
            stats["last_success"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            stats["cooldown_until"] = 0.0
            self._cooldown_until[key] = 0.0
            self._save_stats_locked()

    def record_failure(
        self,
        model_name_or_key: str,
        cooldown_seconds: float = 0.0,
        provider_cooldown_seconds: float = 0.0,
    ) -> None:
        with self._lock:
            key = self._resolve_key(model_name_or_key)
            model = self._models_by_key[key]
            self._release_locked(model)
            stats = self._stats.setdefault(
                key,
                {
                    "success_count": 0,
                    "failure_count": 0,
                    "failure_streak": 0,
                    "recent_latencies": [],
                    "last_success": "",
                    "last_failure": "",
                    "cooldown_until": 0.0,
                },
            )
            stats["failure_count"] = int(stats.get("failure_count", 0) or 0) + 1
            stats["failure_streak"] = int(stats.get("failure_streak", 0) or 0) + 1
            stats["last_failure"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            if cooldown_seconds > 0:
                until = time.time() + cooldown_seconds
                if until > self._cooldown_until.get(key, 0.0):
                    self._cooldown_until[key] = until
                    stats["cooldown_until"] = until
            if provider_cooldown_seconds > 0:
                until = time.time() + provider_cooldown_seconds
                current = self._provider_cooldown_until.get(model.provider, 0.0)
                if until > current:
                    self._provider_cooldown_until[model.provider] = until
            self._save_stats_locked()

    def status(self) -> str:
        with self._lock:
            now = time.time()
            self._prune_rpm_locked(now)
            parts = []
            for model in self._models:
                key = model.key
                stats = self._stats.get(key, {})
                cooldown_left = max(0.0, self._cooldown_until.get(key, 0.0) - now)
                cooldown_label = f" cooldown={cooldown_left:.0f}s" if cooldown_left > 0 else ""
                provider_cooldown_left = max(0.0, self._provider_cooldown_until.get(model.provider, 0.0) - now)
                provider_cooldown_label = (
                    f" provider_cd={provider_cooldown_left:.0f}s" if provider_cooldown_left > 0 else ""
                )
                parts.append(
                    f"{key}(rpm={len(self._rpm_windows[key])}/{model.rpm if model.rpm is not None else '-'} "
                    f"rpd={self._rpd_counts[key]}/{model.rpd if model.rpd is not None else '-'} "
                    f"lat={self._latency_score_locked(model):.1f}s fail_streak={int(stats.get('failure_streak', 0) or 0)}"
                    f"{cooldown_label}{provider_cooldown_label} inflight={self._inflight_model_counts.get(key, 0)}/"
                    f"{self._inflight_provider_counts.get(model.provider, 0)})"
                )
            return " | ".join(parts)


# Backward-compatible alias kept for older tests and callers.
ModelRateLimiter = HostedModelScheduler


def _remote_cooldown_seconds(exc: Exception) -> float:
    if isinstance(exc, TimeoutError):
        return 300.0
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 429:
            return 900.0
        if exc.code in {403, 404}:
            return 21600.0
        if exc.code in {500, 502, 503, 504}:
            return 180.0
        return 60.0
    if isinstance(exc, urllib.error.URLError):
        return 180.0
    return 60.0


def _provider_cooldown_seconds(exc: Exception) -> float:
    if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
        return 900.0
    if isinstance(exc, TimeoutError):
        return 180.0
    if isinstance(exc, urllib.error.URLError):
        return 120.0
    return 0.0


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
    if not text:
        return None
    if text.startswith("{") and text.endswith("}"):
        try:
            obj = json.loads(text)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            return [obj]
    if text.startswith("[") and text.endswith("]"):
        try:
            arr = json.loads(text)
            if isinstance(arr, list):
                return [x for x in arr if isinstance(x, dict)]
            if isinstance(arr, dict):
                return [arr]
        except Exception:
            pass

    def _balanced_spans(open_char: str, close_char: str) -> Iterable[str]:
        depth = 0
        start = -1
        in_string = False
        escape = False
        for i, ch in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == open_char:
                if depth == 0:
                    start = i
                depth += 1
            elif ch == close_char and depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    yield text[start : i + 1]

    for chunk in list(_balanced_spans("[", "]")) + list(_balanced_spans("{", "}")):
        try:
            parsed = json.loads(chunk)
        except Exception:
            continue
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    return None


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

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))

    return _parse_google_array(body, use_json_mode=use_json_mode)


# ---------------------------------------------------------------------------
# OpenAI-compatible hosted backends
# ---------------------------------------------------------------------------

def _normalize_nvidia_model_name(model: str) -> str:
    model = model.strip()
    if not model:
        return model
    if "/" in model:
        return model
    return NVIDIA_MODEL_ALIASES.get(model, model)


def _normalize_provider_model_name(provider: str, model: str) -> str:
    model = model.strip()
    if provider == "nvidia":
        return _normalize_nvidia_model_name(model)
    return model


def _extract_openai_chat_text(body: dict) -> str:
    def _coerce_text(payload: object) -> str:
        if isinstance(payload, str):
            return payload if payload.strip() else ""
        if isinstance(payload, dict):
            for key in ("content", "text", "output_text", "message", "reasoning_content", "arguments"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            parts = payload.get("parts")
            if isinstance(parts, list):
                text_parts = []
                for part in parts:
                    part_text = _coerce_text(part)
                    if part_text:
                        text_parts.append(part_text)
                if text_parts:
                    return "".join(text_parts)
        if isinstance(payload, list):
            text_parts = []
            for part in payload:
                part_text = _coerce_text(part)
                if part_text:
                    text_parts.append(part_text)
            if text_parts:
                return "".join(text_parts)
        return ""

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        for key in ("output_text", "text", "response"):
            text = _coerce_text(body.get(key))
            if text:
                return text
        raise ValueError("openai_chat_missing_choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("openai_chat_missing_message")

    function_call = message.get("function_call")
    if isinstance(function_call, dict):
        arguments = function_call.get("arguments")
        if isinstance(arguments, str) and arguments.strip():
            return arguments

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            func = tool_call.get("function")
            if isinstance(func, dict):
                arguments = func.get("arguments")
                if isinstance(arguments, str) and arguments.strip():
                    return arguments

    for key in ("content", "reasoning_content", "output_text", "text", "response"):
        text = _coerce_text(message.get(key))
        if text:
            return text

    for key in ("output_text", "text", "response"):
        text = _coerce_text(body.get(key))
        if text:
            return text

    raise ValueError("openai_chat_missing_content")


def _parse_openai_chat_array(body: dict) -> list[dict]:
    return _extract_json_array(_extract_openai_chat_text(body)) or []


def _call_openai_compatible(
    *,
    prompt: str,
    model: str,
    api_key: str,
    timeout: int,
    max_output_tokens: int,
    url: str,
    provider: str,
    auth_scheme: str = "Bearer",
) -> list[dict]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_output_tokens,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"{auth_scheme} {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))

    return _parse_openai_chat_array(body)


def _call_nvidia(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _call_openai_compatible(
        prompt=prompt,
        model=_normalize_nvidia_model_name(model),
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        url=NVIDIA_CHAT_URL,
        provider="nvidia",
    )


def _call_cerebras(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _call_openai_compatible(
        prompt=prompt,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        url=CEREBRAS_CHAT_URL,
        provider="cerebras",
    )


def _call_fireworks(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _call_openai_compatible(
        prompt=prompt,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        url=FIREWORKS_CHAT_URL,
        provider="fireworks",
    )


def _call_groq(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _call_openai_compatible(
        prompt=prompt,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        url=GROQ_CHAT_URL,
        provider="groq",
    )


def _call_mistral(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _call_openai_compatible(
        prompt=prompt,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        url=MISTRAL_CHAT_URL,
        provider="mistral",
    )


def _call_huggingface(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _call_openai_compatible(
        prompt=prompt,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        url=HUGGINGFACE_CHAT_URL,
        provider="huggingface",
    )


def _call_vercel(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _call_openai_compatible(
        prompt=prompt,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        url=VERCEL_CHAT_URL,
        provider="vercel",
    )


def _call_opencode(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _call_openai_compatible(
        prompt=prompt,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        url=OPENCODE_CHAT_URL,
        provider="opencode",
    )


def _call_hosted_model(
    *,
    prompt: str,
    spec: HostedModelSpec,
    api_key: str,
    timeout: int,
    max_output_tokens: int,
) -> list[dict]:
    if spec.provider == "google":
        return _call_google(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    if spec.provider == "nvidia":
        return _call_nvidia(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    if spec.provider == "cerebras":
        return _call_cerebras(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    if spec.provider == "fireworks":
        return _call_fireworks(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    if spec.provider == "groq":
        return _call_groq(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    if spec.provider == "mistral":
        return _call_mistral(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    if spec.provider == "huggingface":
        return _call_huggingface(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    if spec.provider == "vercel":
        return _call_vercel(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    if spec.provider == "opencode":
        return _call_opencode(
            prompt,
            model=spec.name,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
    raise ValueError(f"unsupported_hosted_provider:{spec.provider}")


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


def _norm_tristate(v: object) -> int | None:
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"negative", "bearish", "down", "lower", "bad", "miss", "misses", "missed", "decrease", "decline", "weak"}:
            return -1
        if s in {"neutral", "flat", "none", "unchanged", "mixed", "unclear"}:
            return 0
        if s in {"positive", "bullish", "up", "higher", "good", "beat", "beats", "beat out", "increase", "rise", "strong"}:
            return 1
    return _norm_small_int(v, {-1, 0, 1})


def _norm_level(v: object) -> int | None:
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"low", "weak", "minor", "small"}:
            return 0
        if s in {"medium", "mid", "moderate", "medium-high", "middle"}:
            return 1
        if s in {"high", "strong", "large", "major", "big"}:
            return 2
    if isinstance(v, (int, float)):
        try:
            x = float(v)
        except Exception:
            return None
        if 0.0 <= x <= 1.0:
            if x < 0.34:
                return 0
            if x < 0.67:
                return 1
            return 2
    return _norm_small_int(v, {0, 1, 2})


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
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"company", "firm", "issuer", "stock"}:
            return "stock"
    return None


def _norm_enum(v: object, allowed: set[str]) -> str | None:
    if isinstance(v, str):
        s = v.strip().lower()
        if s in allowed:
            return s
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
        "sentiment": _norm_tristate(raw.get("sentiment")),
        "confidence": _norm_level(raw.get("confidence")),
        "event_type": ev,
        "magnitude": _norm_level(raw.get("magnitude")),
        "is_forward_looking": _norm_bool(raw.get("is_forward_looking")),
        "market_tone": _norm_tristate(raw.get("market_tone")),
        "is_rumor": _norm_bool(raw.get("is_rumor")),
        "surprise_direction": _norm_tristate(raw.get("surprise_direction")),
        "impact_scope": _norm_impact_scope(raw.get("impact_scope")),
        "named_persons": _norm_str_list(raw.get("named_persons")),
        "expectation_alignment": _norm_enum(raw.get("expectation_alignment"), EXPECTATION_ALIGNMENTS),
        "information_novelty": _norm_enum(raw.get("information_novelty"), INFORMATION_NOVELTIES),
        "macro_theme": _norm_enum(raw.get("macro_theme"), MACRO_THEMES),
        "source_authority": _norm_enum(raw.get("source_authority"), SOURCE_AUTHORITIES),
        "causal_impact_label": _norm_enum(raw.get("causal_impact_label"), CAUSAL_IMPACT_LABELS),
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
        "expectation_alignment": None,
        "information_novelty": None,
        "macro_theme": None,
        "source_authority": None,
        "causal_impact_label": None,
        "llm_error": err,
    }


def _blank_record_with_enrichment(article: dict, err: str) -> dict:
    record = _blank_record(article, err)
    record.update(_article_enrichment(article))
    return record


def _article_enrichment(article: dict) -> dict[str, object]:
    text_blob = _text_blob(article)
    norm_text = _strip_vi(text_blob)
    return {
        "published_at": _clean_str(article.get("published_at")) or None,
        "source_domain": _source_domain_from_url(article.get("url")),
        "event_time_type": _event_time_type_from_published_at(article.get("published_at")),
        "article_text_length": int(len(text_blob.strip())),
        "article_has_numbers": bool(re.search(r"\d", norm_text)),
        "article_mentions_percent": bool(
            re.search(r"%|\bpercent\b|\bphan tram\b", norm_text)
        ),
    }


# ---------------------------------------------------------------------------
# Hosted pool resolution
# ---------------------------------------------------------------------------

def _split_model_arg(model_arg: str) -> list[str]:
    return [part.strip() for part in str(model_arg or "").split(",") if part.strip()]


def _spec_from_name(provider: str, model_name: str) -> HostedModelSpec:
    normalized = _normalize_provider_model_name(provider, model_name)
    for cfg in PROVIDER_MODEL_POOLS.get(provider, []):
        if cfg["name"] == normalized:
            return _build_hosted_spec(provider, cfg)
    return HostedModelSpec(
        provider=provider,
        name=normalized,
        api_key_envs=tuple(_api_env_names_for_provider(provider, normalized)),
    )


def _resolve_auto_model_token(token: str) -> HostedModelSpec:
    if ":" in token:
        provider, model_name = token.split(":", 1)
        if provider in HOSTED_PROVIDER_NAMES:
            return _spec_from_name(provider, model_name)
    matches: list[HostedModelSpec] = []
    for provider in HOSTED_PROVIDER_NAMES:
        normalized = _normalize_provider_model_name(provider, token)
        for cfg in PROVIDER_MODEL_POOLS.get(provider, []):
            cfg_name = str(cfg["name"])
            short_name = cfg_name.split("/", 1)[-1]
            if cfg_name == normalized or short_name == token:
                matches.append(_build_hosted_spec(provider, cfg))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"ambiguous auto model token '{token}'")
    raise ValueError(
        f"auto model token '{token}' must be fully qualified as provider:model "
        f"or match a unique curated model"
    )


def _select_hosted_model_pool(provider: str, model_arg: str) -> list[HostedModelSpec]:
    if provider == "auto":
        requested = _split_model_arg(model_arg)
        if requested:
            return [_resolve_auto_model_token(token) for token in requested]
        specs: list[HostedModelSpec] = []
        for hosted_provider in HOSTED_PROVIDER_NAMES:
            for cfg in PROVIDER_MODEL_POOLS.get(hosted_provider, []):
                spec = _build_hosted_spec(hosted_provider, cfg)
                if _resolve_provider_api_key(hosted_provider, model_name=spec.name):
                    tier = 0 if hosted_provider in AUTO_STABLE_PROVIDER_NAMES else 1
                    specs.append(replace(spec, priority_tier=tier))
        return specs
    requested = _split_model_arg(model_arg)
    if requested:
        return [_spec_from_name(provider, token) for token in requested]
    return [_build_hosted_spec(provider, cfg) for cfg in PROVIDER_MODEL_POOLS.get(provider, [])]


def _resolve_api_keys_for_specs(
    specs: list[HostedModelSpec],
    provider: str,
    cli_api_key: str,
) -> dict[str, str]:
    keys: dict[str, str] = {}
    for spec in specs:
        resolved = _resolve_provider_api_key(
            spec.provider,
            cli_api_key if provider == spec.provider and provider != "auto" else "",
            model_name=spec.name,
        )
        if resolved:
            keys[spec.key] = resolved
    return keys


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
    rate_limiter: "HostedModelScheduler | None" = None,
    api_keys: dict[str, str] | None = None,
    workers: int = 1,
) -> dict:
    date = path.stem
    day_t0 = time.time()
    _log(f"[{date}] start")
    articles = _load_articles(path)
    filtered = [a for a in articles if _is_financial_article(a)]
    for i, a in enumerate(filtered, start=1):
        a["id"] = f"{date}_{i:04d}"
    _log(f"[{date}] loaded total={len(articles):,} filtered={len(filtered):,}")
    article_meta = {a["id"]: _article_enrichment(a) for a in filtered}

    parsed_ok = 0
    parse_fail = 0
    timeout_fail = 0
    pool_exhausted = False
    rows: list[dict] = []
    batches = list(enumerate(_chunk(filtered, batch_size), start=1))
    n_batches = len(batches)
    done_batches = 0
    hosted_mode = provider in HOSTED_PROVIDERS
    abort_event = threading.Event()

    def _abort_batch(batch: list[dict], err: str) -> tuple[list[dict], int, int, int, bool]:
        return ([_blank_record_with_enrichment(a, err) for a in batch], 0, 0, 0, True)

    def _run_batch(batch: list[dict], depth: int = 0) -> tuple[list[dict], int, int, int, bool]:
        if abort_event.is_set():
            return _abort_batch(batch, "pool_exhausted")
        prompt = _build_prompt(batch, max_summary_chars=max_summary_chars)
        by_id = {a["id"]: a for a in batch}
        model_used = model
        provider_used = provider
        spec_used: HostedModelSpec | None = None
        max_hosted_retries = len(rate_limiter.specs()) if rate_limiter is not None else 0

        try:
            if abort_event.is_set():
                return _abort_batch(batch, "pool_exhausted")
            if hosted_mode:
                if rate_limiter is not None:
                    spec_used = rate_limiter.acquire_spec(acquire_timeout=300.0)
                    if spec_used is None:
                        abort_event.set()
                        return _abort_batch(batch, "pool_exhausted")
                else:
                    if provider == "auto":
                        raise ValueError("provider=auto requires a hosted scheduler")
                    spec_used = _spec_from_name(provider, model)
                provider_used = spec_used.provider
                model_used = spec_used.name
                resolved_api_key = (api_keys or {}).get(spec_used.key, "")
                if not resolved_api_key:
                    resolved_api_key = _resolve_provider_api_key(provider_used, api_key, model_name=model_used)
                if not resolved_api_key:
                    raise ValueError(f"missing_api_key:{provider_used}")
                call_t0 = time.time()
                arr = _call_hosted_model(
                    prompt=prompt,
                    spec=spec_used,
                    api_key=resolved_api_key,
                    timeout=timeout,
                    max_output_tokens=num_predict,
                )
                if rate_limiter is not None and arr:
                    rate_limiter.record_success(spec_used.key, time.time() - call_t0)
            else:
                resp = _call_ollama(prompt, model=model, timeout=timeout, num_predict=num_predict)
                arr = _extract_json_array(resp) or []
        except Exception as e:
            if hosted_mode and rate_limiter is not None and spec_used is not None:
                rate_limiter.record_failure(
                    spec_used.key,
                    cooldown_seconds=_remote_cooldown_seconds(e),
                    provider_cooldown_seconds=_provider_cooldown_seconds(e),
                )
            if abort_event.is_set():
                return _abort_batch(batch, "pool_exhausted")
            if hosted_mode and rate_limiter is not None and len(batch) == 1 and depth < max_hosted_retries:
                _log(
                    f"[{date}] batch error provider={provider_used} model={model_used} size=1 "
                    f"depth={depth} err={type(e).__name__}: {e} | retrying alternate model"
                )
                return _run_batch(batch, depth=depth + 1)
            if len(batch) > 1:
                split_at = max(1, len(batch) // 2)
                _log(
                    f"[{date}] batch error provider={provider_used} model={model_used} size={len(batch)} "
                    f"depth={depth} err={type(e).__name__}: {e} | retrying smaller slices"
                )
                left_rows, left_ok, left_pf, left_tf, left_pool = _run_batch(batch[:split_at], depth=depth + 1)
                if left_pool:
                    remaining = [_blank_record_with_enrichment(a, "pool_exhausted") for a in batch[split_at:]]
                    return (left_rows + remaining, left_ok, left_pf, left_tf, True)
                right_rows, right_ok, right_pf, right_tf, right_pool = _run_batch(batch[split_at:], depth=depth + 1)
                return (
                    left_rows + right_rows,
                    left_ok + right_ok,
                    left_pf + right_pf,
                    left_tf + right_tf,
                    right_pool,
                )
            err_prefix = _provider_error_prefix(provider_used)
            return ([_blank_record_with_enrichment(batch[0], f"{err_prefix}:{e}")], 0, 0, 1, False)

        if not arr:
            if hosted_mode and rate_limiter is not None and spec_used is not None:
                rate_limiter.record_failure(spec_used.key, cooldown_seconds=43200.0)
            if abort_event.is_set():
                return _abort_batch(batch, "pool_exhausted")
            if hosted_mode and rate_limiter is not None and len(batch) == 1 and depth < max_hosted_retries:
                _log(
                    f"[{date}] empty/invalid JSON provider={provider_used} model={model_used} size=1 "
                    f"depth={depth} | retrying alternate model"
                )
                return _run_batch(batch, depth=depth + 1)
            if len(batch) > 1:
                split_at = max(1, len(batch) // 2)
                _log(
                    f"[{date}] empty/invalid JSON provider={provider_used} model={model_used} size={len(batch)} "
                    f"depth={depth} | retrying smaller slices"
                )
                left_rows, left_ok, left_pf, left_tf, left_pool = _run_batch(batch[:split_at], depth=depth + 1)
                if left_pool:
                    remaining = [_blank_record_with_enrichment(a, "pool_exhausted") for a in batch[split_at:]]
                    return (left_rows + remaining, left_ok, left_pf, left_tf, True)
                right_rows, right_ok, right_pf, right_tf, right_pool = _run_batch(batch[split_at:], depth=depth + 1)
                return (
                    left_rows + right_rows,
                    left_ok + right_ok,
                    left_pf + right_pf,
                    left_tf + right_tf,
                    right_pool,
                )
            return ([_blank_record_with_enrichment(batch[0], "json_parse_fail")], 0, 1, 0, False)

        batch_rows: list[dict] = []
        seen: set[str] = set()
        batch_ok = 0
        for obj in arr:
            rid = str(obj.get("id", "") or "").strip()
            if rid in by_id and rid not in seen:
                norm = _normalize_record(obj, rid)
                norm.update(article_meta.get(rid, {}))
                norm["llm_error"] = None
                batch_rows.append(norm)
                seen.add(rid)
                batch_ok += 1

        missing = [a for a in batch if a["id"] not in seen]
        if missing and len(batch) > 1:
            if abort_event.is_set():
                return _abort_batch(batch, "pool_exhausted")
            _log(
                f"[{date}] partial batch response provider={provider_used} model={model_used} size={len(batch)} "
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

        if missing and hosted_mode and rate_limiter is not None and spec_used is not None:
            rate_limiter.record_failure(spec_used.key, cooldown_seconds=60.0)
        if abort_event.is_set():
            return _abort_batch(batch, "pool_exhausted")
        if missing and hosted_mode and rate_limiter is not None and len(batch) == 1 and depth < max_hosted_retries:
            _log(
                f"[{date}] missing object provider={provider_used} model={model_used} size=1 "
                f"depth={depth} | retrying alternate model"
            )
            return _run_batch(batch, depth=depth + 1)
        for article in missing:
            blank = _blank_record_with_enrichment(article, "missing_object_in_batch")
            blank.update(article_meta.get(article["id"], {}))
            batch_rows.append(blank)

        return (batch_rows, batch_ok, len(missing), 0, False)

    if workers <= 1 or n_batches <= 1:
        for batch_idx, batch in batches:
            b_t0 = time.time()
            batch_rows, batch_ok, batch_pf, batch_tf, batch_pool_exhausted = _run_batch(batch)
            rows.extend(batch_rows)
            parsed_ok += batch_ok
            parse_fail += batch_pf
            timeout_fail += batch_tf
            done_batches += 1
            if batch_pool_exhausted:
                pool_exhausted = True
                abort_event.set()
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
    else:
        with cf.ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"llm-{date}-batch") as ex:
            inflight: dict[cf.Future, tuple[int, list[dict], float]] = {}
            next_batch = 0

            def _submit_next() -> bool:
                nonlocal next_batch
                if abort_event.is_set() or next_batch >= n_batches:
                    return False
                batch_idx, batch = batches[next_batch]
                next_batch += 1
                inflight[ex.submit(_run_batch, batch)] = (batch_idx, batch, time.time())
                return True

            for _ in range(min(workers, n_batches)):
                _submit_next()

            while inflight:
                done, _ = cf.wait(list(inflight.keys()), return_when=cf.FIRST_COMPLETED)
                for fut in done:
                    batch_idx, batch, submit_t0 = inflight.pop(fut)
                    b_elapsed = time.time() - submit_t0
                    if fut.cancelled():
                        batch_rows, batch_ok, batch_pf, batch_tf, batch_pool_exhausted = _abort_batch(batch, "pool_exhausted")
                    else:
                        batch_rows, batch_ok, batch_pf, batch_tf, batch_pool_exhausted = fut.result()
                    rows.extend(batch_rows)
                    parsed_ok += batch_ok
                    parse_fail += batch_pf
                    timeout_fail += batch_tf
                    done_batches += 1
                    if batch_pool_exhausted:
                        pool_exhausted = True
                        abort_event.set()
                        if rate_limiter is not None:
                            _log(f"[{date}] all model daily limits exhausted — stopping | {rate_limiter.status()}")
                        for pending_fut in inflight:
                            pending_fut.cancel()
                    if log_every_batches > 0 and (
                        done_batches == 1
                        or done_batches % log_every_batches == 0
                        or done_batches == n_batches
                    ):
                        elapsed = time.time() - day_t0
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
                while not abort_event.is_set() and len(inflight) < workers and next_batch < n_batches:
                    _submit_next()

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
    ap.add_argument(
        "--provider",
        type=str,
        default="auto",
        choices=sorted(HOSTED_PROVIDERS | {"ollama"}),
        help=(
            "LLM provider. 'auto' builds one hosted pool across configured providers and "
            "uses the fastest observed models first."
        ),
    )
    ap.add_argument("--model", type=str, default="",
                    help=(
                        "Optional model override. Supports comma-separated lists. In auto mode, "
                        "use provider:model entries such as google:gemini-2.5-flash-lite."
                    ))
    ap.add_argument("--api-key", type=str, default="",
                    help=(
                        "Optional provider API key override. Auto mode ignores this and reads "
                        "provider-specific keys from the environment or .env."
                    ))
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--num-predict", type=int, default=8192,
                    help="Max output tokens per batch (8192 needed for batch-size=20 with full schema).")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--workers", type=int, default=1,
                    help="Number of parallel batch workers within each day (default 1).")
    ap.add_argument("--max-summary-chars", type=int, default=400,
                    help="Truncate article summary in prompt to this many chars (0 = no truncation).")
    ap.add_argument("--log-every-batches", type=int, default=5,
                    help="Log progress every N batches within each day (default 5).")
    args = ap.parse_args()
    if args.provider == "ollama" and not args.model:
        args.model = DEFAULT_MODELS["ollama"]
    if args.workers <= 0:
        raise SystemExit("ERROR: --workers must be positive")

    rate_limiter: HostedModelScheduler | None = None
    api_keys_by_model: dict[str, str] = {}
    if args.provider in HOSTED_PROVIDERS:
        if args.provider == "auto" and args.api_key:
            _log("Ignoring --api-key in auto mode; using provider-specific env vars from environment/.env.")
        try:
            model_pool = _select_hosted_model_pool(args.provider, args.model)
        except ValueError as exc:
            raise SystemExit(f"ERROR: {exc}") from exc
        if not model_pool:
            if args.provider == "auto":
                raise SystemExit(
                    "ERROR: no configured hosted providers found. Add provider API keys to .env "
                    "or use --provider ollama."
                )
            env_names = ", ".join(_api_env_names_for_provider(args.provider, args.model))
            raise SystemExit(
                f"ERROR: no models available for provider '{args.provider}'. "
                f"Set one of: {env_names}"
            )
        api_keys_by_model = _resolve_api_keys_for_specs(model_pool, args.provider, args.api_key)
        missing_keys = [spec.key for spec in model_pool if spec.key not in api_keys_by_model]
        if missing_keys:
            if args.model:
                raise SystemExit(
                    "ERROR: missing API keys for requested hosted models: "
                    + ", ".join(missing_keys)
                )
            model_pool = [spec for spec in model_pool if spec.key in api_keys_by_model]
        if not model_pool:
            raise SystemExit("ERROR: hosted model pool resolved but no models had valid credentials.")
        rate_limiter = HostedModelScheduler(model_pool, stats_path=HOSTED_MODEL_STATS_PATH)
        _log(f"Model pool: {[spec.key for spec in rate_limiter.specs()]}")

    files = _iter_dates(args.date_from, args.date_to)
    if not files:
        print("No input files matched date filters.")
        return

    if args.model:
        run_model = args.model
    elif args.provider == "auto":
        run_model = "auto_pool"
    elif args.provider in HOSTED_PROVIDER_NAMES:
        run_model = f"{args.provider}_pool"
    else:
        run_model = DEFAULT_MODELS["ollama"]
    _log(
        f"Run config: files={len(files)} from={args.date_from or '-'} to={args.date_to or '-'} "
        f"provider={args.provider} model={run_model} batch_size={args.batch_size} batch_workers={args.workers} "
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
    for i, p in enumerate(pending, start=1):
        stats = process_day(
            p,
            batch_size=args.batch_size,
            workers=args.workers,
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            timeout=args.timeout,
            num_predict=args.num_predict,
            max_summary_chars=args.max_summary_chars,
            log_every_batches=args.log_every_batches,
            rate_limiter=rate_limiter,
            api_keys=api_keys_by_model,
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
