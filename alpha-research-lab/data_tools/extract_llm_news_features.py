"""
Canonical CafeF LLM extractor.

Supported providers: google, nvidia, cerebras, groq, mistral.
The older multi-provider implementation has been moved to
`extract_llm_news_features_legacy.py` for compatibility and historical rebuilds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import os
import time
from pathlib import Path

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

_SIMPLE_PROVIDERS = {"nvidia", "cerebras", "groq", "mistral"}
_CANONICAL_PROVIDERS = {"google"} | _SIMPLE_PROVIDERS
_ALL_PROVIDER_CHOICES = _CANONICAL_PROVIDERS | {"auto"}

HOSTED_PROVIDERS = _CANONICAL_PROVIDERS
HOSTED_PROVIDER_NAMES = _CANONICAL_PROVIDERS
AUTO_PROVIDER_NAMES = _CANONICAL_PROVIDERS
AUTO_STABLE_PROVIDER_NAMES = _CANONICAL_PROVIDERS
PROVIDER_MODEL_POOLS = {
    "google":   GOOGLE_MODEL_POOL,
    "nvidia":   NVIDIA_MODEL_POOL,
    "cerebras": CEREBRAS_MODEL_POOL,
    "groq":     GROQ_MODEL_POOL,
    "mistral":  MISTRAL_MODEL_POOL,
}
DEFAULT_NVIDIA_MODEL   = NVIDIA_MODEL_POOL[0]["name"]
DEFAULT_CEREBRAS_MODEL = CEREBRAS_MODEL_POOL[0]["name"]
DEFAULT_GROQ_MODEL     = GROQ_MODEL_POOL[0]["name"]
DEFAULT_MISTRAL_MODEL  = MISTRAL_MODEL_POOL[0]["name"]
DEFAULT_MODELS = {
    "google":   DEFAULT_MODEL,
    "nvidia":   DEFAULT_NVIDIA_MODEL,
    "cerebras": DEFAULT_CEREBRAS_MODEL,
    "groq":     DEFAULT_GROQ_MODEL,
    "mistral":  DEFAULT_MISTRAL_MODEL,
}

# Env-var names for each single-key provider (checked in order)
_SIMPLE_KEY_ENV_NAMES: dict[str, list[str]] = {
    "nvidia":   ["NVIDIA_API_KEY", "NGC_API_KEY"],
    "cerebras": ["CEREBRAS_API_KEY"],
    "groq":     ["GROQ_API_KEY"],
    "mistral":  ["MISTRAL_API_KEY", "MISTRAL_COSTRAL_API_KEY"],
}

HostedModelSpec = legacy.HostedModelSpec
HostedModelScheduler = legacy.HostedModelScheduler


class ShuffledModelScheduler(HostedModelScheduler):
    """Picks uniformly at random among eligible specs.

    Keeps all hard gates (RPM/RPD limits, cooldowns) but replaces the
    score-based min() selection with random.choice so that model-specific
    extraction biases are spread evenly across articles rather than being
    correlated with whichever model was fastest/available at the time.
    """

    def acquire_spec(self, acquire_timeout: float = 300.0) -> "HostedModelSpec | None":
        deadline = time.time() + acquire_timeout
        while True:
            with self._lock:
                self._maybe_reset_day_locked()
                now = time.time()
                self._prune_rpm_locked(now)
                candidates: list[HostedModelSpec] = []
                any_rpd_left = False
                for model in self._models:
                    key = model.key
                    rpd_limit = model.rpd
                    rpm_limit = model.rpm
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
                    candidates.append(model)
                if candidates:
                    chosen = random.choice(candidates)
                    self._reserve_locked(chosen, now)
                    return chosen
                if not any_rpd_left:
                    return None
            if time.time() >= deadline:
                return None
            time.sleep(1.0)

_LEGACY_LOAD_ENV_FILE = legacy._load_env_file
_LEGACY_RESOLVE_PROVIDER_API_KEY = legacy._resolve_provider_api_key
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


def _resolve_simple_api_key(provider: str, cli_value: str) -> str:
    """Resolve a single API key for any provider in _SIMPLE_KEY_ENV_NAMES.

    Priority: CLI arg → os.environ → .env files.
    """
    _sync_legacy_repo_root()
    if cli_value.strip():
        return cli_value.strip()
    env_names = _SIMPLE_KEY_ENV_NAMES.get(provider, [])
    for name in env_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    candidates = [
        Path.cwd() / ".env",
        REPO_ROOT / ".env",
        legacy.workspace_path(".env"),
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        env_map = _LEGACY_LOAD_ENV_FILE(candidate)
        for name in env_names:
            value = env_map.get(name, "").strip()
            if value:
                os.environ.setdefault(name, value)
                return value
    return ""


def _resolve_nvidia_api_key(cli_value: str) -> str:
    return _resolve_simple_api_key("nvidia", cli_value)


def _resolve_cerebras_api_key(cli_value: str) -> str:
    return _resolve_simple_api_key("cerebras", cli_value)


def _resolve_groq_api_key(cli_value: str) -> str:
    return _resolve_simple_api_key("groq", cli_value)


def _resolve_mistral_api_key(cli_value: str, model_name: str = "") -> str:
    _sync_legacy_repo_root()
    if cli_value.strip():
        return cli_value.strip()
    env_names = legacy._mistral_api_env_names(model_name)
    # Check .env files first so codestral-specific keys beat a generic MISTRAL_API_KEY
    # that may have been cached in os.environ by a prior call.
    candidates = [Path.cwd() / ".env", REPO_ROOT / ".env", legacy.workspace_path(".env")]
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        env_map = _LEGACY_LOAD_ENV_FILE(candidate)
        for name in env_names:
            value = env_map.get(name, "").strip()
            if value:
                return value
    for name in env_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _resolve_huggingface_api_key(cli_value: str) -> str:
    _sync_legacy_repo_root()
    return legacy._resolve_huggingface_api_key(cli_value)


def _resolve_vercel_api_key(cli_value: str) -> str:
    _sync_legacy_repo_root()
    return legacy._resolve_vercel_api_key(cli_value)


def _resolve_provider_api_key(provider: str, cli_value: str = "", model_name: str = "") -> str:
    _sync_legacy_repo_root()
    if provider == "google":
        keys = _resolve_google_api_keys(cli_value)
        return keys[0] if keys else ""
    if provider in _SIMPLE_PROVIDERS:
        return _resolve_simple_api_key(provider, cli_value)
    return _LEGACY_RESOLVE_PROVIDER_API_KEY(provider, cli_value, model_name=model_name)


def _select_hosted_model_pool(provider: str, model_arg: str) -> list[HostedModelSpec]:
    prev_rpak = legacy._resolve_provider_api_key
    legacy._resolve_provider_api_key = _resolve_provider_api_key
    try:
        return legacy._select_hosted_model_pool(provider, model_arg)
    finally:
        legacy._resolve_provider_api_key = prev_rpak


def _resolve_api_keys_for_specs(
    specs: list[HostedModelSpec],
    provider: str,
    cli_api_key: str,
) -> dict[str, str]:
    prev = legacy._resolve_provider_api_key
    legacy._resolve_provider_api_key = _resolve_provider_api_key
    try:
        return legacy._resolve_api_keys_for_specs(specs, provider, cli_api_key)
    finally:
        legacy._resolve_provider_api_key = prev


def _select_google_model_pool(model_arg: str) -> list[HostedModelSpec]:
    prev = legacy._resolve_provider_api_key
    legacy._resolve_provider_api_key = _resolve_provider_api_key
    try:
        return legacy._select_hosted_model_pool("google", model_arg)
    finally:
        legacy._resolve_provider_api_key = prev


def _resolve_google_api_keys_for_specs(
    specs: list[HostedModelSpec],
    google_keys: list[str],
) -> dict[str, str]:
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
        all_keys = sorted({v for v in self._api_keys_by_model.values() if v})
        # Load persisted API key cooldowns so dead keys (403-denied) survive restarts
        # and don't waste requests re-probing them on every process start.
        persisted_key_cooldowns = self._load_api_key_cooldowns(all_keys)
        now = time.time()
        self._api_key_cooldown_until: dict[str, float] = {
            key: (cd if cd > now else 0.0)
            for key, cd in persisted_key_cooldowns.items()
        }

    @staticmethod
    def _api_key_fingerprint(api_key: str) -> str:
        digest = hashlib.sha256(str(api_key).encode("utf-8")).hexdigest()
        return f"sha256:{digest[:16]}"

    def _load_api_key_cooldowns(self, all_keys: list[str]) -> dict[str, float]:
        """Read persisted api_key_cooldowns from the stats file, if present."""
        try:
            payload = json.loads(self._stats_path.read_text(encoding="utf-8"))
            raw = payload.get("api_key_cooldowns", {}) if isinstance(payload, dict) else {}
            if not isinstance(raw, dict):
                return {}
            out: dict[str, float] = {}
            for api_key in all_keys:
                fingerprint = self._api_key_fingerprint(api_key)
                value = raw.get(fingerprint, raw.get(api_key))
                if value is None:
                    continue
                out[api_key] = float(value)
            return out
        except (OSError, json.JSONDecodeError, AttributeError):
            return {}

    def _save_stats_locked(self) -> None:
        self._stats_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": _utc_now_iso_z(),
            "api_key_cooldowns": {
                self._api_key_fingerprint(api_key): until
                for api_key, until in sorted(self._api_key_cooldown_until.items())
                if api_key
            },
            "models": self._stats,
        }
        tmp = self._stats_path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.replace(self._stats_path)

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
            if cooldown > 0:
                until = time.time() + cooldown
                if until > self._cooldown_until.get(key, 0.0):
                    self._cooldown_until[key] = until
                    stats["cooldown_until"] = until
                # Only rotate the API key for rate-limit / transient network errors.
                # Auth failures (403: model not accessible on this key) and parse
                # errors should NOT rotate the key — the key itself is fine.
                should_rotate_key = provider_cooldown_seconds > 0 or cooldown in {180.0, 300.0, 900.0}
                if should_rotate_key:
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

    _HIGH_STREAK_THRESHOLD = 10
    _MAX_INFLIGHT_PER_MODEL = 2

    def _model_is_available_locked(self, model: "HostedModelSpec") -> bool:
        # Exclude models on a very long consecutive failure streak.  They will
        # almost certainly fail again (e.g. gemma-3-12b-it with seed_latency>timeout),
        # so having workers wait 1 s at a time for a better model is cheaper than
        # burning 45 s on a doomed timeout.  The streak resets on the first success,
        # so the model gets another chance after a process restart or if conditions improve.
        stats = self._stats.get(model.key, {})
        if int(stats.get("failure_streak", 0) or 0) >= self._HIGH_STREAK_THRESHOLD:
            return False
        # Allow up to 2 concurrent requests per model.  inflight=3 was tried but
        # caused intermittent 429s on the workhorse: 503 errors trigger immediate
        # retries, momentarily spiking to 5 RPM slots and blowing the 15-RPM limit.
        # A 429 on the sole working model causes a 900s cooldown (15-min stall),
        # erasing far more throughput than inflight=3 gained.  inflight=2 keeps the
        # burst well under 15 RPM even when two retries fire simultaneously.
        return self._inflight_model_counts.get(model.key, 0) < self._MAX_INFLIGHT_PER_MODEL

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


def _build_rate_limiter(
    provider: str,
    model_arg: str,
    cli_api_key: str,
) -> "tuple[str, dict[str, str], HostedModelScheduler | None, list[HostedModelSpec], dict[str, int]]":
    """Build (resolved_api_key, api_keys_by_model, rate_limiter, model_pool, api_key_ordinals).

    Called when no external rate_limiter is supplied. Handles all three provider paths.
    """
    _sync_legacy_runtime()
    if provider == "auto":
        pool = _select_hosted_model_pool("auto", model_arg)
        api_keys = _resolve_api_keys_for_specs(pool, "auto", cli_api_key)
        return "", api_keys, ShuffledModelScheduler(pool, stats_path=HOSTED_MODEL_STATS_PATH), pool, {}
    if provider in _SIMPLE_PROVIDERS:
        key = _resolve_simple_api_key(provider, cli_api_key)
        pool = _select_hosted_model_pool(provider, model_arg)
        api_keys = {spec.key: key for spec in pool if key}
        return key, api_keys, ShuffledModelScheduler(pool, stats_path=HOSTED_MODEL_STATS_PATH), pool, {}
    # google
    google_keys = _resolve_google_api_keys(cli_api_key)
    key = google_keys[0] if google_keys else ""
    unique = list(dict.fromkeys(google_keys))
    pool = _select_google_model_pool(model_arg)
    api_keys = _resolve_google_api_keys_for_specs(pool, unique)
    ordinals = {k: i + 1 for i, k in enumerate(unique)}
    limiter: HostedModelScheduler | None = (
        GoogleKeyRotationScheduler(pool, api_keys, stats_path=HOSTED_MODEL_STATS_PATH)
        if len(unique) > 1 else None
    )
    return key, api_keys, limiter, pool, ordinals


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
    if provider not in _ALL_PROVIDER_CHOICES:
        raise ValueError(
            f"canonical extractor supports {sorted(_ALL_PROVIDER_CHOICES)}, got {provider!r}"
        )
    _sync_legacy_runtime()
    if rate_limiter is None:
        api_key, api_keys_map, rate_limiter, model_pool, api_key_ordinals = _build_rate_limiter(
            provider, model, api_key
        )
        resolved_model = (
            model or (DEFAULT_MODELS.get(provider, "") if provider in _SIMPLE_PROVIDERS else DEFAULT_MODEL)
        )
    else:
        api_keys_map = api_keys or {spec.key: api_key for spec in rate_limiter.specs() if api_key}
        api_key_ordinals = {api_key: 1} if api_key and provider not in ("auto", "google") else {}
        resolved_model = (
            model or (DEFAULT_MODELS.get(provider, "") if provider in _SIMPLE_PROVIDERS else DEFAULT_MODEL)
        )
    return legacy.process_day(
        path,
        batch_size=batch_size,
        provider=provider,
        model=resolved_model,
        api_key=api_key,
        timeout=timeout,
        num_predict=num_predict,
        max_summary_chars=max_summary_chars,
        log_every_batches=log_every_batches,
        rate_limiter=rate_limiter,
        api_keys=api_keys_map,
        api_key_ordinals=api_key_ordinals if api_key_ordinals else None,
        workers=workers,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", type=str, default="")
    ap.add_argument("--date-to", type=str, default="")
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument(
        "--provider", type=str,
        choices=sorted(_ALL_PROVIDER_CHOICES), default="auto",
        help="LLM provider (default: auto). Supported: " + ", ".join(sorted(_ALL_PROVIDER_CHOICES)),
    )
    ap.add_argument(
        "--model",
        type=str,
        default="",
        help="Optional model override. Supports comma-separated model names.",
    )
    ap.add_argument(
        "--api-key",
        type=str,
        default="",
        help=(
            "Optional API key override. For google: comma-separated list or reads GOOGLE_API_KEY* / .env. "
            "For others: reads the provider-specific env var from os.environ or .env."
        ),
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
        default=16,
        help="Number of parallel batch workers within each day (default 16).",
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

    try:
        api_key, api_keys_by_model, rate_limiter, model_pool, _ = _build_rate_limiter(
            args.provider, args.model, args.api_key
        )
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    if not model_pool:
        raise SystemExit(
            "ERROR: no models found — check provider keys in .env "
            "(GOOGLE_API_KEY, NVIDIA_API_KEY, CEREBRAS_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY)."
        )
    if not api_keys_by_model and args.provider != "auto":
        env_names = " / ".join(_SIMPLE_KEY_ENV_NAMES.get(args.provider, ["GOOGLE_API_KEY*"]))
        raise SystemExit(f"ERROR: no API keys resolved — set {env_names} in .env.")
    model_pool_keys = [spec.key for spec in (rate_limiter.specs() if rate_limiter is not None else model_pool)]
    if args.provider == "auto":
        providers_in_pool = sorted({spec.provider for spec in model_pool})
        _log(f"Provider: auto | Active providers: {providers_in_pool} | Pool size: {len(model_pool_keys)}")
    else:
        _log(f"Provider: {args.provider} | Model pool: {model_pool_keys}")

    files = _iter_dates(args.date_from, args.date_to)
    if not files:
        print("No input files matched date filters.")
        return

    run_model = args.model if args.model else f"{args.provider}_pool"
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
            provider=args.provider,
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
            _log(f"All {args.provider} model daily limits exhausted after {total_days} days — stopping early.")
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
