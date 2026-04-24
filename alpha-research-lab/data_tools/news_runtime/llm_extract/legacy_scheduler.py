from __future__ import annotations

import json
import statistics
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class HostedModelSpec:
    provider: str
    name: str
    api_key_envs: tuple[str, ...] = ()
    rpm: int | None = None
    rpd: int | None = None
    priority_tier: int = 0
    slot_id: str = ""

    @property
    def key(self) -> str:
        if self.slot_id:
            return f"{self.provider}:{self.name}#{self.slot_id}"
        return f"{self.provider}:{self.name}"


class HostedModelScheduler:
    def __init__(
        self,
        models: list[HostedModelSpec | dict | str],
        stats_path: Path | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._stats_path = stats_path or Path("artifacts/llm_runtime/hosted_model_stats.json")
        self._models = [self._coerce_hosted_spec(item) for item in models]
        self._models_by_key = {item.key: item for item in self._models}
        self._stats = self._load_stats_locked()
        self._cooldown_until = {
            model.key: float(self._stats.get(model.key, {}).get("cooldown_until", 0.0) or 0.0)
            for model in self._models
        }
        self._provider_cooldown_until = {model.provider: 0.0 for model in self._models}
        self._rpm_windows = {model.key: [] for model in self._models}
        self._rpd_counts = {model.key: 0 for model in self._models}
        self._day_ymd = self._current_day_ymd()
        self._inflight_model_counts = {model.key: 0 for model in self._models}
        self._inflight_provider_counts = {model.provider: 0 for model in self._models}

    def specs(self) -> list[HostedModelSpec]:
        return list(self._models)

    @staticmethod
    def _coerce_hosted_spec(item: HostedModelSpec | dict | str, default_provider: str = "hosted") -> HostedModelSpec:
        if isinstance(item, HostedModelSpec):
            return item
        if isinstance(item, dict):
            return HostedModelSpec(
                provider=str(item.get("provider", default_provider)),
                name=str(item.get("name", "")),
                api_key_envs=tuple(str(v) for v in (item.get("api_key_envs") or ())),
                rpm=item.get("rpm"),
                rpd=item.get("rpd"),
                priority_tier=int(item.get("priority_tier", 0) or 0),
                slot_id=str(item.get("slot_id", "") or ""),
            )
        return HostedModelSpec(provider=default_provider, name=str(item))

    @staticmethod
    def _current_day_ymd() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_stats_locked(self) -> dict[str, dict]:
        try:
            payload = json.loads(self._stats_path.read_text(encoding="utf-8"))
            models = payload.get("models", {}) if isinstance(payload, dict) else {}
            return models if isinstance(models, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_stats_locked(self) -> None:
        self._stats_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": _utc_now_iso_z(),
            "models": self._stats,
        }
        tmp = self._stats_path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.replace(self._stats_path)

    def _maybe_reset_day_locked(self) -> None:
        current = self._current_day_ymd()
        if current == self._day_ymd:
            return
        self._day_ymd = current
        for model in self._models:
            self._rpd_counts[model.key] = 0

    def _prune_rpm_locked(self, now: float) -> None:
        cutoff = now - 60.0
        for model in self._models:
            window = self._rpm_windows[model.key]
            while window and window[0] < cutoff:
                window.pop(0)

    def _resolve_key(self, model_name_or_key: str) -> str:
        if model_name_or_key in self._models_by_key:
            return model_name_or_key
        matches = [model.key for model in self._models if model.name == model_name_or_key]
        if len(matches) == 1:
            return matches[0]
        raise KeyError(f"unknown hosted model '{model_name_or_key}'")

    def _latency_score_locked(self, model: HostedModelSpec) -> float:
        stats = self._stats.get(model.key, {})
        values = [float(v) for v in (stats.get("recent_latencies") or []) if float(v) > 0]
        if not values:
            return 9999.0
        return statistics.mean(values[-10:])

    def _score_locked(self, model: HostedModelSpec, index: int) -> tuple[float, int, int]:
        return (self._latency_score_locked(model), int(model.priority_tier), index)

    def _provider_is_cooldown_locked(self, provider: str, now: float) -> bool:
        return self._provider_cooldown_until.get(provider, 0.0) > now

    def _reserve_locked(self, model: HostedModelSpec, now: float) -> None:
        self._rpm_windows[model.key].append(now)
        self._rpd_counts[model.key] += 1
        self._inflight_model_counts[model.key] = self._inflight_model_counts.get(model.key, 0) + 1
        self._inflight_provider_counts[model.provider] = self._inflight_provider_counts.get(model.provider, 0) + 1

    def _release_locked(self, model: HostedModelSpec) -> None:
        self._inflight_model_counts[model.key] = max(0, self._inflight_model_counts.get(model.key, 0) - 1)
        self._inflight_provider_counts[model.provider] = max(0, self._inflight_provider_counts.get(model.provider, 0) - 1)

    def acquire_spec(self, acquire_timeout: float = 300.0) -> HostedModelSpec | None:
        deadline = time.time() + acquire_timeout
        while True:
            with self._lock:
                self._maybe_reset_day_locked()
                now = time.time()
                self._prune_rpm_locked(now)
                candidates: list[tuple[tuple[float, int, int], HostedModelSpec]] = []
                any_rpd_left = False
                for index, model in enumerate(self._models):
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
        spec = self.acquire_spec(acquire_timeout=acquire_timeout)
        return spec.name if spec is not None else None

    def record_success(self, model_name_or_key: str, latency_sec: float) -> None:
        with self._lock:
            key = self._resolve_key(model_name_or_key)
            model = self._models_by_key[key]
            self._release_locked(model)
            stats = self._stats.setdefault(
                key,
                {
                    "provider": model.provider,
                    "name": model.name,
                    "spec": asdict(model),
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
                    "provider": model.provider,
                    "name": model.name,
                    "spec": asdict(model),
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
            if cooldown_seconds > 0:
                until = time.time() + float(cooldown_seconds)
                if until > self._cooldown_until.get(key, 0.0):
                    self._cooldown_until[key] = until
                    stats["cooldown_until"] = until
            if provider_cooldown_seconds > 0:
                until = time.time() + float(provider_cooldown_seconds)
                if until > self._provider_cooldown_until.get(model.provider, 0.0):
                    self._provider_cooldown_until[model.provider] = until
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
            self._save_stats_locked()

    def provider_cooldown(self, provider: str, seconds: float) -> None:
        if seconds <= 0:
            return
        with self._lock:
            until = time.time() + seconds
            if until > self._provider_cooldown_until.get(provider, 0.0):
                self._provider_cooldown_until[provider] = until

    def all_daily_exhausted(self) -> bool:
        with self._lock:
            self._maybe_reset_day_locked()
            return all(
                model.rpd is not None and self._rpd_counts[model.key] >= model.rpd
                for model in self._models
            )

    def _model_is_available_locked(self, model: HostedModelSpec) -> bool:
        return self._inflight_model_counts.get(model.key, 0) < 1

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
                provider_cooldown_label = f" provider_cd={provider_cooldown_left:.0f}s" if provider_cooldown_left > 0 else ""
                parts.append(
                    f"{key}(rpm={len(self._rpm_windows[key])}/{model.rpm if model.rpm is not None else '-'} "
                    f"rpd={self._rpd_counts[key]}/{model.rpd if model.rpd is not None else '-'} "
                    f"lat={self._latency_score_locked(model):.1f}s fail_streak={int(stats.get('failure_streak', 0) or 0)}"
                    f"{cooldown_label}{provider_cooldown_label})"
                )
            return " | ".join(parts)


def remote_cooldown_seconds(exc: Exception) -> float:
    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    message = str(exc).lower()
    if code == 429 or status == 429 or "429" in message or "rate limit" in message:
        return 60.0
    if code == 503 or status == 503 or "503" in message:
        return 180.0
    if code == 500 or status == 500 or "500" in message:
        return 60.0
    if "timeout" in message:
        return 300.0
    return 0.0


def provider_cooldown_seconds(exc: Exception) -> float:
    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    message = str(exc).lower()
    if code == 429 or status == 429 or "429" in message or "rate limit" in message:
        return 900.0
    return 0.0

