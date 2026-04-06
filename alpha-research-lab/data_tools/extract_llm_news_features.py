"""
Canonical Google-only CafeF LLM extractor.

The older multi-provider implementation has been moved to
`extract_llm_news_features_legacy.py` for compatibility and historical rebuilds.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import os
import statistics
import threading
import time
from pathlib import Path
import urllib.error

from path_utils import data_path
from src.repo_paths import artifact_path

try:  # pragma: no cover - import style depends on script vs package execution
    from . import extract_llm_news_features_legacy as legacy
except ImportError:  # pragma: no cover
    import extract_llm_news_features_legacy as legacy

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = data_path("news/cafef/raw")
CACHE_DIR = data_path("llm_cache")
HOSTED_MODEL_STATS_PATH = artifact_path("llm_runtime", "hosted_model_stats.json")

EVENT_TYPES = legacy.EVENT_TYPES
PROMPT_TAXONOMY = legacy.PROMPT_TAXONOMY
FIN_KEYWORDS = legacy.FIN_KEYWORDS

GOOGLE_MODEL_POOL = legacy.GOOGLE_MODEL_POOL
NVIDIA_MODEL_POOL = legacy.NVIDIA_MODEL_POOL
MISTRAL_MODEL_POOL = legacy.MISTRAL_MODEL_POOL
HUGGINGFACE_MODEL_POOL = legacy.HUGGINGFACE_MODEL_POOL
VERCEL_MODEL_POOL = legacy.VERCEL_MODEL_POOL
CEREBRAS_MODEL_POOL = legacy.CEREBRAS_MODEL_POOL
FIREWORKS_MODEL_POOL = legacy.FIREWORKS_MODEL_POOL
GROQ_MODEL_POOL = legacy.GROQ_MODEL_POOL
OPENCODE_MODEL_POOL = legacy.OPENCODE_MODEL_POOL
MODEL_POOL = GOOGLE_MODEL_POOL
DEFAULT_MODEL = GOOGLE_MODEL_POOL[0]["name"]

HOSTED_PROVIDERS = {"google"}
HOSTED_PROVIDER_NAMES = {"google"}
AUTO_PROVIDER_NAMES = {"google"}
AUTO_STABLE_PROVIDER_NAMES = {"google"}
PROVIDER_MODEL_POOLS = {"google": GOOGLE_MODEL_POOL}
DEFAULT_MODELS = {"google": DEFAULT_MODEL}

HostedModelSpec = legacy.HostedModelSpec
HostedModelScheduler = legacy.HostedModelScheduler

_LEGACY_RESOLVE_GOOGLE_API_KEY = legacy._resolve_google_api_key
_LEGACY_RESOLVE_NVIDIA_API_KEY = legacy._resolve_nvidia_api_key
_LEGACY_RESOLVE_MISTRAL_API_KEY = legacy._resolve_mistral_api_key
_LEGACY_RESOLVE_HUGGINGFACE_API_KEY = legacy._resolve_huggingface_api_key
_LEGACY_RESOLVE_VERCEL_API_KEY = legacy._resolve_vercel_api_key
_LEGACY_RESOLVE_PROVIDER_API_KEY = legacy._resolve_provider_api_key
_LEGACY_SELECT_HOSTED_MODEL_POOL = legacy._select_hosted_model_pool
_LEGACY_RESOLVE_API_KEYS_FOR_SPECS = legacy._resolve_api_keys_for_specs
_LEGACY_LOAD_ARTICLES = legacy._load_articles
_LEGACY_CACHE_HAS_SUCCESSFUL_ROWS = legacy._cache_has_successful_rows
_LEGACY_IS_FINANCIAL_ARTICLE = legacy._is_financial_article
_LEGACY_BUILD_PROMPT = legacy._build_prompt
_LEGACY_NORMALIZE_RECORD = legacy._normalize_record
_LEGACY_ARTICLE_ENRICHMENT = legacy._article_enrichment
_LEGACY_PARSE_GOOGLE_ARRAY = legacy._parse_google_array
_LEGACY_PARSE_OPENAI_CHAT_ARRAY = legacy._parse_openai_chat_array
_LEGACY_NORMALIZE_NVIDIA_MODEL_NAME = legacy._normalize_nvidia_model_name
_LEGACY_CALL_GOOGLE = legacy._call_google
_LEGACY_LOAD_ENV_FILE = legacy._load_env_file
_GOOGLE_API_ENV_NAMES = (
    "GOOGLE_API_KEY",
    "GOOGLE_API_KEY_2",
    "GOOGLE_API_KEY_3",
    "GOOGLE_API_KEY_4",
    "GOOGLE_API_KEY_5",
)

_utc_now_iso_z = legacy._utc_now_iso_z
_log = legacy._log
_api_env_names_for_provider = legacy._api_env_names_for_provider


def _sync_legacy_repo_root() -> None:
    legacy.REPO_ROOT = REPO_ROOT


def _iter_dates(date_from: str, date_to: str) -> list[Path]:
    files = sorted(p for p in RAW_DIR.glob("*.jsonl") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem))
    if date_from:
        files = [p for p in files if p.stem >= date_from]
    if date_to:
        files = [p for p in files if p.stem <= date_to]
    return files


def _load_articles(path: Path) -> list[dict]:
    return _LEGACY_LOAD_ARTICLES(path)


def _cache_has_successful_rows(path: Path) -> bool:
    return _LEGACY_CACHE_HAS_SUCCESSFUL_ROWS(path)


def _is_financial_article(article: dict) -> bool:
    return _LEGACY_IS_FINANCIAL_ARTICLE(article)


def _build_prompt(batch: list[dict], max_summary_chars: int = 400) -> str:
    return _LEGACY_BUILD_PROMPT(batch, max_summary_chars=max_summary_chars)


def _normalize_record(raw: dict, fallback_id: str) -> dict:
    return _LEGACY_NORMALIZE_RECORD(raw, fallback_id)


def _article_enrichment(article: dict) -> dict[str, object]:
    return _LEGACY_ARTICLE_ENRICHMENT(article)


def _parse_google_array(body: dict, use_json_mode: bool) -> list[dict]:
    return _LEGACY_PARSE_GOOGLE_ARRAY(body, use_json_mode=use_json_mode)


def _parse_openai_chat_array(body: dict) -> list[dict]:
    return _LEGACY_PARSE_OPENAI_CHAT_ARRAY(body)


def _normalize_nvidia_model_name(model_name: str) -> str:
    return _LEGACY_NORMALIZE_NVIDIA_MODEL_NAME(model_name)


def _call_google(prompt: str, model: str, api_key: str, timeout: int, max_output_tokens: int) -> list[dict]:
    return _LEGACY_CALL_GOOGLE(
        prompt,
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
    )


def _split_google_api_keys(raw: str) -> list[str]:
    keys = []
    for chunk in str(raw or "").split(","):
        key = chunk.strip()
        if key:
            keys.append(key)
    return keys


def _resolve_google_api_keys(cli_value: str) -> list[str]:
    _sync_legacy_repo_root()
    if cli_value.strip():
        return _split_google_api_keys(cli_value)

    candidates = [
        Path.cwd() / ".env",
        REPO_ROOT / ".env",
        legacy.workspace_path(".env"),
    ]
    env_maps: list[dict[str, str]] = []
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        env_maps.append(_LEGACY_LOAD_ENV_FILE(candidate))

    keys: list[str] = []
    pool_value = os.environ.get("GOOGLE_API_KEYS", "").strip()
    if not pool_value:
        for env_map in env_maps:
            value = env_map.get("GOOGLE_API_KEYS", "").strip()
            if value:
                os.environ["GOOGLE_API_KEYS"] = value
                pool_value = value
                break
    if pool_value:
        keys.extend(_split_google_api_keys(pool_value))

    for env_name in _GOOGLE_API_ENV_NAMES[:1]:
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            keys.extend(_split_google_api_keys(env_value))
            break
        for env_map in env_maps:
            value = env_map.get(env_name, "").strip()
            if value:
                os.environ[env_name] = value
                keys.extend(_split_google_api_keys(value))
                break
        if keys:
            break

    for env_name in _GOOGLE_API_ENV_NAMES[1:]:
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            keys.extend(_split_google_api_keys(env_value))
            continue
        for env_map in env_maps:
            value = env_map.get(env_name, "").strip()
            if value:
                os.environ[env_name] = value
                keys.extend(_split_google_api_keys(value))
                break

    deduped: list[str] = []
    seen_key: set[str] = set()
    for key in keys:
        if key not in seen_key:
            seen_key.add(key)
            deduped.append(key)
    return deduped


def _resolve_google_api_key(cli_value: str) -> str:
    keys = _resolve_google_api_keys(cli_value)
    return keys[0] if keys else ""


def _resolve_nvidia_api_key(cli_value: str) -> str:
    _sync_legacy_repo_root()
    return _LEGACY_RESOLVE_NVIDIA_API_KEY(cli_value)


def _resolve_mistral_api_key(cli_value: str, model_name: str = "") -> str:
    _sync_legacy_repo_root()
    return _LEGACY_RESOLVE_MISTRAL_API_KEY(cli_value, model_name=model_name)


def _resolve_huggingface_api_key(cli_value: str) -> str:
    _sync_legacy_repo_root()
    return _LEGACY_RESOLVE_HUGGINGFACE_API_KEY(cli_value)


def _resolve_vercel_api_key(cli_value: str) -> str:
    _sync_legacy_repo_root()
    return _LEGACY_RESOLVE_VERCEL_API_KEY(cli_value)


def _resolve_provider_api_key(provider: str, cli_value: str = "", model_name: str = "") -> str:
    _sync_legacy_repo_root()
    return _LEGACY_RESOLVE_PROVIDER_API_KEY(provider, cli_value, model_name=model_name)


def _select_hosted_model_pool(provider: str, model_arg: str) -> list[HostedModelSpec]:
    _sync_legacy_runtime()
    prev = legacy._resolve_provider_api_key
    legacy._resolve_provider_api_key = _resolve_provider_api_key
    try:
        return _LEGACY_SELECT_HOSTED_MODEL_POOL(provider, model_arg)
    finally:
        legacy._resolve_provider_api_key = prev


def _resolve_api_keys_for_specs(
    specs: list[HostedModelSpec],
    provider: str,
    cli_api_key: str,
) -> dict[str, str]:
    _sync_legacy_runtime()
    prev = legacy._resolve_provider_api_key
    legacy._resolve_provider_api_key = _resolve_provider_api_key
    try:
        return _LEGACY_RESOLVE_API_KEYS_FOR_SPECS(specs, provider, cli_api_key)
    finally:
        legacy._resolve_provider_api_key = prev


def _select_google_model_pool(model_arg: str) -> list[HostedModelSpec]:
    _sync_legacy_runtime()
    prev = legacy._resolve_provider_api_key
    legacy._resolve_provider_api_key = _resolve_provider_api_key
    try:
        return _LEGACY_SELECT_HOSTED_MODEL_POOL("google", model_arg)
    finally:
        legacy._resolve_provider_api_key = prev


def _resolve_google_api_keys_for_specs(
    specs: list[HostedModelSpec],
    google_keys: list[str],
) -> dict[str, str]:
    _sync_legacy_runtime()
    if not google_keys:
        return {}
    out: dict[str, str] = {}
    for index, spec in enumerate(specs):
        out[spec.key] = google_keys[index % len(google_keys)]
    return out


class GoogleKeyRotationScheduler(HostedModelScheduler):
    """Google-only scheduler that cools down API keys, not the whole provider."""

    def __init__(
        self,
        models: list[HostedModelSpec | dict | str],
        api_keys_by_model: dict[str, str],
        stats_path: Path | None = None,
    ) -> None:
        super().__init__(models, stats_path=stats_path)
        self._api_keys_by_model = dict(api_keys_by_model)
        self._api_key_cooldown_until: dict[str, float] = {
            key: 0.0 for key in sorted({value for value in self._api_keys_by_model.values() if value})
        }

    def _api_key_for_model(self, model: HostedModelSpec) -> str:
        return self._api_keys_by_model.get(model.key, "")

    def _api_key_is_cooldown_locked(self, api_key: str, now: float) -> bool:
        return self._api_key_cooldown_until.get(api_key, 0.0) > now

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
                    api_key = self._api_key_for_model(model)
                    rpm_limit = model.rpm
                    rpd_limit = model.rpd
                    if rpd_limit is None or self._rpd_counts[key] < rpd_limit:
                        any_rpd_left = True
                    if not api_key or self._api_key_is_cooldown_locked(api_key, now):
                        continue
                    if now < self._cooldown_until[key]:
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
            stats["last_success"] = _utc_now_iso_z()
            stats["cooldown_until"] = 0.0
            self._cooldown_until[key] = 0.0
            api_key = self._api_key_for_model(model)
            if api_key:
                self._api_key_cooldown_until[api_key] = 0.0
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
            stats["last_failure"] = _utc_now_iso_z()
            cooldown = max(float(cooldown_seconds or 0.0), float(provider_cooldown_seconds or 0.0))
            # Only actual rate-limit / transient network failures should force a key rotation.
            # Parse failures and missing-object retries need to reuse the same key so the
            # batch-splitting fallback can keep working on one-key pools.
            should_rotate_key = provider_cooldown_seconds > 0 or cooldown in {180.0, 300.0, 900.0}
            if cooldown > 0 and should_rotate_key:
                until = time.time() + cooldown
                if until > self._cooldown_until.get(key, 0.0):
                    self._cooldown_until[key] = until
                    stats["cooldown_until"] = until
                api_key = self._api_key_for_model(model)
                if api_key and until > self._api_key_cooldown_until.get(api_key, 0.0):
                    self._api_key_cooldown_until[api_key] = until
            self._save_stats_locked()

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
            api_key = self._api_key_for_model(self._models_by_key[key])
            if api_key and until > self._api_key_cooldown_until.get(api_key, 0.0):
                self._api_key_cooldown_until[api_key] = until
            self._save_stats_locked()

    def provider_cooldown(self, provider: str, seconds: float) -> None:
        return None

    def all_daily_exhausted(self) -> bool:
        with self._lock:
            self._maybe_reset_day_locked()
            return all(
                model.rpd is not None and self._rpd_counts[model.key] >= model.rpd
                for model in self._models
            )

    def status(self) -> str:
        with self._lock:
            now = time.time()
            self._prune_rpm_locked(now)
            parts = []
            for model in self._models:
                key = model.key
                api_key = self._api_key_for_model(model)
                stats = self._stats.get(key, {})
                cooldown_left = max(0.0, self._cooldown_until.get(key, 0.0) - now)
                cooldown_label = f" cooldown={cooldown_left:.0f}s" if cooldown_left > 0 else ""
                api_cooldown_left = max(0.0, self._api_key_cooldown_until.get(api_key, 0.0) - now)
                api_cooldown_label = f" api_cd={api_cooldown_left:.0f}s" if api_cooldown_left > 0 else ""
                parts.append(
                    f"{key}(rpm={len(self._rpm_windows[key])}/{model.rpm if model.rpm is not None else '-'} "
                    f"rpd={self._rpd_counts[key]}/{model.rpd if model.rpd is not None else '-'} "
                    f"lat={self._latency_score_locked(model):.1f}s fail_streak={int(stats.get('failure_streak', 0) or 0)}"
                    f"{cooldown_label}{api_cooldown_label} inflight={self._inflight_model_counts.get(key, 0)}/"
                    f"{self._inflight_provider_counts.get(model.provider, 0)})"
                )
            return " | ".join(parts)


def _sync_legacy_runtime() -> None:
    _sync_legacy_repo_root()
    legacy.CACHE_DIR = CACHE_DIR
    legacy.RAW_DIR = RAW_DIR
    legacy._load_articles = _load_articles
    legacy._cache_has_successful_rows = _cache_has_successful_rows
    legacy._is_financial_article = _is_financial_article
    legacy._build_prompt = _build_prompt
    legacy._normalize_record = _normalize_record
    legacy._article_enrichment = _article_enrichment
    legacy._parse_google_array = _parse_google_array
    legacy._parse_openai_chat_array = _parse_openai_chat_array
    legacy._normalize_nvidia_model_name = _normalize_nvidia_model_name
    legacy._call_google = _call_google
    legacy._log = _log


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
    if provider != "google":
        raise ValueError("canonical extractor only supports provider='google'")
    _sync_legacy_runtime()
    resolved_api_keys = _resolve_google_api_keys(api_key)
    resolved_api_key = resolved_api_keys[0] if resolved_api_keys else ""
    unique_google_keys = list(dict.fromkeys(resolved_api_keys))
    if rate_limiter is None and len(unique_google_keys) > 1:
        model_pool = _select_google_model_pool(model)
        api_keys = _resolve_google_api_keys_for_specs(model_pool, unique_google_keys)
        rate_limiter = GoogleKeyRotationScheduler(model_pool, api_keys, stats_path=HOSTED_MODEL_STATS_PATH)
    elif rate_limiter is not None and api_keys is None:
        api_keys = _resolve_google_api_keys_for_specs(rate_limiter.specs(), unique_google_keys)
    elif rate_limiter is None:
        api_keys = None
    return legacy.process_day(
        path,
        batch_size=batch_size,
        provider="google",
        model=model or DEFAULT_MODEL,
        api_key=resolved_api_key,
        timeout=timeout,
        num_predict=num_predict,
        max_summary_chars=max_summary_chars,
        log_every_batches=log_every_batches,
        rate_limiter=rate_limiter,
        api_keys=api_keys,
        workers=workers,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", type=str, default="")
    ap.add_argument("--date-to", type=str, default="")
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--provider", type=str, choices=["google"], default="google",
                    help="Pinned to the canonical Google-only pipeline.")
    ap.add_argument(
        "--model",
        type=str,
        default="",
        help="Optional Google model override. Supports comma-separated model names.",
    )
    ap.add_argument(
        "--api-key",
        type=str,
        default="",
        help="Optional Google key override or comma-separated key list. Otherwise reads GOOGLE_API_KEY*, GOOGLE_API_KEYS, and .env.",
    )
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument(
        "--num-predict",
        type=int,
        default=8192,
        help="Max output tokens per batch (8192 needed for batch-size=20 with full schema).",
    )
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel batch workers within each day (default 1).",
    )
    ap.add_argument(
        "--max-summary-chars",
        type=int,
        default=400,
        help="Truncate article summary in prompt to this many chars (0 = no truncation).",
    )
    ap.add_argument(
        "--log-every-batches",
        type=int,
        default=5,
        help="Log progress every N batches within each day (default 5).",
    )
    args = ap.parse_args()
    if args.workers <= 0:
        raise SystemExit("ERROR: --workers must be positive")

    google_keys = _resolve_google_api_keys(args.api_key)
    if not google_keys:
        raise SystemExit(
            "ERROR: missing Google API key(s). Set GOOGLE_API_KEY*, GOOGLE_API_KEYS, or .env in your environment."
        )
    api_key = google_keys[0]

    try:
        model_pool = _select_google_model_pool(args.model)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    if not model_pool:
        raise SystemExit("ERROR: no Google models resolved for the canonical extractor.")

    api_keys_by_model = _resolve_google_api_keys_for_specs(model_pool, google_keys)
    if not api_keys_by_model:
        raise SystemExit("ERROR: no Google models had a resolved Google API key.")

    if len(list(dict.fromkeys(google_keys))) > 1:
        rate_limiter = GoogleKeyRotationScheduler(model_pool, api_keys_by_model, stats_path=HOSTED_MODEL_STATS_PATH)
    else:
        rate_limiter = None
    model_pool_keys = [spec.key for spec in (rate_limiter.specs() if rate_limiter is not None else model_pool)]
    _log(f"Model pool: {model_pool_keys}")

    files = _iter_dates(args.date_from, args.date_to)
    if not files:
        print("No input files matched date filters.")
        return

    run_model = args.model if args.model else "google_pool"
    _log(
        f"Run config: files={len(files)} from={args.date_from or '-'} to={args.date_to or '-'} "
        f"provider=google model={run_model} batch_size={args.batch_size} batch_workers={args.workers} "
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
            provider="google",
            model=args.model,
            api_key=api_key,
            timeout=args.timeout,
            num_predict=args.num_predict,
            max_summary_chars=args.max_summary_chars,
            log_every_batches=args.log_every_batches,
            rate_limiter=rate_limiter,
            api_keys=api_keys_by_model,
            workers=args.workers,
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
            _log(f"All Google model daily limits exhausted after {total_days} days — stopping early.")
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
