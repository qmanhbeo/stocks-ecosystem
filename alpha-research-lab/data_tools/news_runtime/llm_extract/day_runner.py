from __future__ import annotations

from pathlib import Path


def run_day(
    *,
    path: Path,
    batch_size: int,
    provider: str,
    model: str,
    api_key: str,
    timeout: int,
    num_predict: int,
    max_summary_chars: int,
    log_every_batches: int,
    rate_limiter,
    api_keys,
    api_key_ordinals,
    workers: int,
    sync_legacy_runtime,
    legacy_process_day,
    default_models: dict[str, str],
    default_model: str,
    simple_providers: set[str],
) -> dict:
    sync_legacy_runtime()
    resolved_model = model or (default_models.get(provider, "") if provider in simple_providers else default_model)
    return legacy_process_day(
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
        api_keys=api_keys,
        api_key_ordinals=api_key_ordinals,
        workers=workers,
    )
