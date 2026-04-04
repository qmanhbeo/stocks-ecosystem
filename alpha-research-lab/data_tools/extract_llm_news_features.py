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
from path_utils import data_path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = data_path("news/cafef/raw")
CACHE_DIR = data_path("llm_cache")

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
MODEL_POOL = [
    {"name": "gemini-3-flash-preview",       "rpm": 5,  "rpd": 20},
    {"name": "gemini-3.1-flash-lite-preview", "rpm": 15, "rpd": 500},
    {"name": "gemini-2.5-flash",             "rpm": 5,  "rpd": 20},
    {"name": "gemini-2.5-flash-lite",        "rpm": 10, "rpd": 20},
    {"name": "gemma-3-27b-it",               "rpm": 30, "rpd": 14400},
    {"name": "gemma-3-12b-it",               "rpm": 30, "rpd": 14400},
]


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
                    self._rpm_windows[name] = [t for t in self._rpm_windows[name] if now - t < 60.0]
                    if self._rpd_counts[name] < m["rpd"]:
                        any_rpd_left = True
                        if len(self._rpm_windows[name]) < m["rpm"]:
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
            return all(self._rpd_counts[m["name"]] >= m["rpd"] for m in self._models)

    def status(self) -> str:
        with self._lock:
            now = time.time()
            parts = []
            for m in self._models:
                name = m["name"]
                rpm_used = sum(1 for t in self._rpm_windows[name] if now - t < 60.0)
                parts.append(f"{name}(rpm={rpm_used}/{m['rpm']} rpd={self._rpd_counts[name]}/{m['rpd']})")
            return " | ".join(parts)


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

    text = body["candidates"][0]["content"]["parts"][0]["text"]

    if use_json_mode:
        arr = json.loads(text)
    else:
        arr = _extract_json_array(text)

    if isinstance(arr, list):
        return [x for x in arr if isinstance(x, dict)]
    return arr or []


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

    for batch in _chunk(filtered, batch_size):
        b_t0 = time.time()
        prompt = _build_prompt(batch, max_summary_chars=max_summary_chars)
        by_id = {a["id"]: a for a in batch}

        arr: list[dict] | None = None

        if provider == "google":
            if rate_limiter is not None:
                model_used = rate_limiter.acquire(acquire_timeout=300.0)
                if model_used is None:
                    pool_exhausted = True
                    _log(f"[{date}] all model daily limits exhausted — stopping | {rate_limiter.status()}")
                    rows.extend(_blank_record(a, "pool_exhausted") for a in batch)
                    break
            else:
                model_used = model
            try:
                arr = _call_google(prompt, model=model_used, api_key=api_key, timeout=timeout, max_output_tokens=num_predict)
            except Exception as e:
                timeout_fail += len(batch)
                rows.extend(_blank_record(a, f"google_error:{e}") for a in batch)
                done_batches += 1
                continue
        else:  # ollama
            try:
                resp = _call_ollama(prompt, model=model, timeout=timeout, num_predict=num_predict)
            except Exception:
                timeout_fail += len(batch)
                rows.extend(_blank_record(a, "ollama_timeout_or_error") for a in batch)
                done_batches += 1
                continue
            arr = _extract_json_array(resp)

        if not arr:
            parse_fail += len(batch)
            rows.extend(_blank_record(a, "json_parse_fail") for a in batch)
            done_batches += 1
            continue

        seen = set()
        for obj in arr:
            rid = str(obj.get("id", "") or "").strip()
            if rid in by_id:
                norm = _normalize_record(obj, rid)
                norm["llm_error"] = None
                rows.append(norm)
                seen.add(rid)
                parsed_ok += 1
        for a in batch:
            if a["id"] not in seen:
                parse_fail += 1
                rows.append(_blank_record(a, "missing_object_in_batch"))

        done_batches += 1
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
    ap.add_argument("--provider", type=str, default="google", choices=["ollama", "google"],
                    help="LLM provider: 'google' (AI Studio) or 'ollama' (local).")
    ap.add_argument("--model", type=str, default="",
                    help="Model name. Defaults: google=gemini-2.5-flash-lite, ollama=qwen3.5:4b.")
    ap.add_argument("--api-key", type=str, default="",
                    help="Google AI Studio API key (or set GOOGLE_API_KEY env var).")
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

    # Resolve model default per provider
    if not args.model:
        args.model = "gemini-2.5-flash-lite" if args.provider == "google" else "qwen3.5:4b"

    # Resolve API key
    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY", "")
    if args.provider == "google" and not api_key:
        raise SystemExit("ERROR: --api-key or GOOGLE_API_KEY required for google provider.")

    # Always use the model pool for google provider
    rate_limiter: ModelRateLimiter | None = None
    if args.provider == "google":
        rate_limiter = ModelRateLimiter(MODEL_POOL)
        _log(f"Model pool: {[m['name'] for m in MODEL_POOL]}")

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
    pending: list[Path] = []
    for p in files:
        out = CACHE_DIR / f"{p.stem}.jsonl"
        if out.exists() and not args.overwrite:
            skipped += 1
        else:
            pending.append(p)

    _log(f"Days pending={len(pending)} skipped_existing={skipped}")

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
