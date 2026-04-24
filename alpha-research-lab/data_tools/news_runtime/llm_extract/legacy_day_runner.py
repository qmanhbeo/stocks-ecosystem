from __future__ import annotations

import concurrent.futures as cf
import json
import math
import threading
import time
from pathlib import Path


def process_day(
    path: Path,
    *,
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
    hosted_providers,
    provider_error_prefix,
    default_models,
    resolve_provider_api_key,
    build_prompt,
    load_articles,
    is_financial_article,
    article_enrichment,
    log,
    chunk,
    call_ollama,
    call_hosted_model,
    extract_json_array,
    normalize_record,
    blank_record_with_enrichment,
    remote_cooldown_seconds,
    provider_cooldown_seconds,
    spec_from_name,
    cache_dir,
) -> dict:
    date = path.stem
    day_t0 = time.time()
    log(f"[{date}] start")
    articles = load_articles(path)
    filtered = [a for a in articles if is_financial_article(a)]
    for index, article in enumerate(filtered, start=1):
        article["id"] = f"{date}_{index:04d}"
    log(f"[{date}] loaded total={len(articles):,} filtered={len(filtered):,}")
    article_meta = {article["id"]: article_enrichment(article) for article in filtered}

    parsed_ok = 0
    parse_fail = 0
    timeout_fail = 0
    pool_exhausted = False
    rows: list[dict] = []
    batches = list(enumerate(chunk(filtered, batch_size), start=1))
    n_batches = len(batches)
    done_batches = 0
    hosted_mode = provider in hosted_providers
    abort_event = threading.Event()

    def abort_batch(batch: list[dict], err: str):
        return ([_blank(article, err) for article in batch], 0, 0, 0, True, provider, model)

    def _blank(article: dict, err: str) -> dict:
        return blank_record_with_enrichment(article, err)

    def run_batch(batch: list[dict], depth: int = 0):
        if abort_event.is_set():
            return abort_batch(batch, "pool_exhausted")
        prompt = build_prompt(batch, max_summary_chars=max_summary_chars)
        by_id = {article["id"]: article for article in batch}
        model_used = model
        provider_used = provider
        summary_provider = provider_used
        summary_model = model_used
        spec_used = None
        max_hosted_retries = len(rate_limiter.specs()) if rate_limiter is not None else 0

        try:
            if abort_event.is_set():
                return abort_batch(batch, "pool_exhausted")
            if hosted_mode:
                if rate_limiter is not None:
                    spec_used = rate_limiter.acquire_spec(acquire_timeout=300.0)
                    if spec_used is None:
                        abort_event.set()
                        return abort_batch(batch, "pool_exhausted")
                else:
                    if provider == "auto":
                        raise ValueError("provider=auto requires a hosted scheduler")
                    spec_used = spec_from_name(provider, model)
                provider_used = spec_used.provider
                model_used = spec_used.name
                resolved_api_key = (api_keys or {}).get(spec_used.key, "")
                if not resolved_api_key:
                    resolved_api_key = resolve_provider_api_key(provider_used, api_key, model_name=model_used)
                if not resolved_api_key:
                    raise ValueError(f"missing_api_key:{provider_used}")
                call_t0 = time.time()
                api_key_label = ""
                if api_key_ordinals:
                    api_key_label = f"api_key={_ordinal_label(api_key_ordinals.get(resolved_api_key, 0), len(api_key_ordinals))}"
                    log(f"[{date}] calling provider={provider_used} model={model_used} {api_key_label} size={len(batch)} depth={depth}")
                arr = call_hosted_model(
                    prompt=prompt,
                    spec=spec_used,
                    api_key=resolved_api_key,
                    timeout=timeout,
                    max_output_tokens=num_predict,
                )
                if rate_limiter is not None and arr:
                    rate_limiter.record_success(spec_used.key, time.time() - call_t0)
                summary_provider = provider_used
                summary_model = model_used
            else:
                resp = call_ollama(prompt, model=model, timeout=timeout, num_predict=num_predict)
                arr = extract_json_array(resp) or []
        except Exception as exc:
            if hosted_mode and rate_limiter is not None and spec_used is not None:
                rate_limiter.record_failure(
                    spec_used.key,
                    cooldown_seconds=remote_cooldown_seconds(exc),
                    provider_cooldown_seconds=provider_cooldown_seconds(exc),
                )
            if abort_event.is_set():
                return abort_batch(batch, "pool_exhausted")
            if hosted_mode and rate_limiter is not None and len(batch) == 1 and depth < max_hosted_retries:
                log(
                    f"[{date}] batch error provider={provider_used} model={model_used} size=1 "
                    f"depth={depth} err={type(exc).__name__}: {exc} | retrying alternate model"
                )
                return run_batch(batch, depth=depth + 1)
            if len(batch) > 1:
                split_at = max(1, len(batch) // 2)
                log(
                    f"[{date}] batch error provider={provider_used} model={model_used} size={len(batch)} "
                    f"depth={depth} err={type(exc).__name__}: {exc} | retrying smaller slices"
                )
                left_rows, left_ok, left_pf, left_tf, left_pool, left_provider, left_model = run_batch(batch[:split_at], depth=depth + 1)
                if left_pool:
                    remaining = [_blank(article, "pool_exhausted") for article in batch[split_at:]]
                    return (left_rows + remaining, left_ok, left_pf, left_tf, True, left_provider, left_model)
                right_rows, right_ok, right_pf, right_tf, right_pool, right_provider, right_model = run_batch(batch[split_at:], depth=depth + 1)
                return (
                    left_rows + right_rows,
                    left_ok + right_ok,
                    left_pf + right_pf,
                    left_tf + right_tf,
                    right_pool,
                    right_provider,
                    right_model,
                )
            err_prefix = provider_error_prefix(provider_used)
            return ([_blank(batch[0], f"{err_prefix}:{exc}")], 0, 0, 1, False, provider_used, model_used)

        if not arr:
            if hosted_mode and rate_limiter is not None and spec_used is not None:
                rate_limiter.record_failure(spec_used.key, cooldown_seconds=43200.0)
            if abort_event.is_set():
                return abort_batch(batch, "pool_exhausted")
            if hosted_mode and rate_limiter is not None and len(batch) == 1 and depth < max_hosted_retries:
                log(f"[{date}] empty/invalid JSON provider={provider_used} model={model_used} size=1 depth={depth} | retrying alternate model")
                return run_batch(batch, depth=depth + 1)
            if len(batch) > 1:
                split_at = max(1, len(batch) // 2)
                log(
                    f"[{date}] empty/invalid JSON provider={provider_used} model={model_used} size={len(batch)} "
                    f"depth={depth} | retrying smaller slices"
                )
                left_rows, left_ok, left_pf, left_tf, left_pool, left_provider, left_model = run_batch(batch[:split_at], depth=depth + 1)
                if left_pool:
                    remaining = [_blank(article, "pool_exhausted") for article in batch[split_at:]]
                    return (left_rows + remaining, left_ok, left_pf, left_tf, True, left_provider, left_model)
                right_rows, right_ok, right_pf, right_tf, right_pool, right_provider, right_model = run_batch(batch[split_at:], depth=depth + 1)
                return (
                    left_rows + right_rows,
                    left_ok + right_ok,
                    left_pf + right_pf,
                    right_tf + left_tf,
                    right_pool,
                    right_provider,
                    right_model,
                )
            return ([_blank(batch[0], "json_parse_fail")], 0, 1, 0, False, provider_used, model_used)

        batch_rows: list[dict] = []
        seen: set[str] = set()
        batch_ok = 0
        for obj in arr:
            rid = str(obj.get("id", "") or "").strip()
            if rid in by_id and rid not in seen:
                norm = normalize_record(obj, rid)
                norm.update(article_meta.get(rid, {}))
                norm["llm_error"] = None
                batch_rows.append(norm)
                seen.add(rid)
                batch_ok += 1

        missing = [article for article in batch if article["id"] not in seen]
        if missing and len(batch) > 1:
            if abort_event.is_set():
                return abort_batch(batch, "pool_exhausted")
            log(
                f"[{date}] partial batch response provider={provider_used} model={model_used} size={len(batch)} "
                f"matched={len(seen)} missing={len(missing)} depth={depth} | retrying missing subset"
            )
            retry_rows, retry_ok, retry_pf, retry_tf, retry_pool, retry_provider, retry_model = run_batch(missing, depth=depth + 1)
            return (batch_rows + retry_rows, batch_ok + retry_ok, retry_pf, retry_tf, retry_pool, retry_provider, retry_model)

        if missing and hosted_mode and rate_limiter is not None and spec_used is not None:
            rate_limiter.record_failure(spec_used.key, cooldown_seconds=60.0)
        if abort_event.is_set():
            return abort_batch(batch, "pool_exhausted")
        if missing and hosted_mode and rate_limiter is not None and len(batch) == 1 and depth < max_hosted_retries:
            log(f"[{date}] missing object provider={provider_used} model={model_used} size=1 depth={depth} | retrying alternate model")
            return run_batch(batch, depth=depth + 1)
        for article in missing:
            batch_rows.append(_blank(article, "missing_object_in_batch"))
        return (batch_rows, batch_ok, len(missing), 0, False, summary_provider, summary_model)

    if workers <= 1 or n_batches <= 1:
        for _batch_idx, batch in batches:
            batch_t0 = time.time()
            batch_rows, batch_ok, batch_pf, batch_tf, batch_pool_exhausted, batch_provider, batch_model = run_batch(batch)
            rows.extend(batch_rows)
            parsed_ok += batch_ok
            parse_fail += batch_pf
            timeout_fail += batch_tf
            done_batches += 1
            if batch_pool_exhausted:
                pool_exhausted = True
                abort_event.set()
                if rate_limiter is not None:
                    log(f"[{date}] all model daily limits exhausted — stopping | {rate_limiter.status()}")
                break
            if log_every_batches > 0 and (done_batches == 1 or done_batches % log_every_batches == 0 or done_batches == n_batches):
                elapsed = time.time() - day_t0
                batch_elapsed = time.time() - batch_t0
                done_items = parsed_ok + parse_fail + timeout_fail
                rate = done_items / elapsed if elapsed > 0 else 0.0
                rem = max(0, len(filtered) - done_items)
                eta = rem / rate if rate > 0 else float("inf")
                eta_s = "inf" if not math.isfinite(eta) else f"{eta:.1f}s"
                log(
                    f"[{date}] batch {done_batches}/{n_batches} provider={batch_provider} model={batch_model} "
                    f"batch_sec={batch_elapsed:.2f} elapsed={elapsed:.1f}s done={done_items:,}/{len(filtered):,} "
                    f"rate={rate:.2f} art/s eta={eta_s} ok={parsed_ok:,} parse_fail={parse_fail:,} timeout={timeout_fail:,}"
                )
    else:
        with cf.ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"llm-{date}-batch") as executor:
            inflight: dict[cf.Future, tuple[int, list[dict], float]] = {}
            next_batch = 0

            def submit_next() -> bool:
                nonlocal next_batch
                if abort_event.is_set() or next_batch >= n_batches:
                    return False
                batch_idx, batch = batches[next_batch]
                next_batch += 1
                inflight[executor.submit(run_batch, batch)] = (batch_idx, batch, time.time())
                return True

            for _ in range(min(workers, n_batches)):
                submit_next()

            while inflight:
                done, _ = cf.wait(list(inflight.keys()), return_when=cf.FIRST_COMPLETED)
                for future in done:
                    _batch_idx, batch, submit_t0 = inflight.pop(future)
                    batch_elapsed = time.time() - submit_t0
                    if future.cancelled():
                        batch_rows, batch_ok, batch_pf, batch_tf, batch_pool_exhausted, batch_provider, batch_model = abort_batch(batch, "pool_exhausted")
                    else:
                        batch_rows, batch_ok, batch_pf, batch_tf, batch_pool_exhausted, batch_provider, batch_model = future.result()
                    rows.extend(batch_rows)
                    parsed_ok += batch_ok
                    parse_fail += batch_pf
                    timeout_fail += batch_tf
                    done_batches += 1
                    if batch_pool_exhausted:
                        pool_exhausted = True
                        abort_event.set()
                        if rate_limiter is not None:
                            log(f"[{date}] all model daily limits exhausted — stopping | {rate_limiter.status()}")
                        for pending_future in inflight:
                            pending_future.cancel()
                    if log_every_batches > 0 and (done_batches == 1 or done_batches % log_every_batches == 0 or done_batches == n_batches):
                        elapsed = time.time() - day_t0
                        done_items = parsed_ok + parse_fail + timeout_fail
                        rate = done_items / elapsed if elapsed > 0 else 0.0
                        rem = max(0, len(filtered) - done_items)
                        eta = rem / rate if rate > 0 else float("inf")
                        eta_s = "inf" if not math.isfinite(eta) else f"{eta:.1f}s"
                        log(
                            f"[{date}] batch {done_batches}/{n_batches} provider={batch_provider} model={batch_model} "
                            f"batch_sec={batch_elapsed:.2f} elapsed={elapsed:.1f}s done={done_items:,}/{len(filtered):,} "
                            f"rate={rate:.2f} art/s eta={eta_s} ok={parsed_ok:,} parse_fail={parse_fail:,} timeout={timeout_fail:,}"
                        )
                while not abort_event.is_set() and len(inflight) < workers and next_batch < n_batches:
                    submit_next()

    order = {article["id"]: index for index, article in enumerate(filtered)}
    rows.sort(key=lambda row: order.get(row["id"], 10**9))

    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cache_dir / f"{date}.jsonl.tmp"
    out = cache_dir / f"{date}.jsonl"
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(out)
    day_elapsed = time.time() - day_t0
    done_items = parsed_ok + parse_fail + timeout_fail
    rate = done_items / day_elapsed if day_elapsed > 0 else 0.0
    log(
        f"[{date}] done sec={day_elapsed:.1f} total={len(articles):,} filtered={len(filtered):,} "
        f"ok={parsed_ok:,} parse_fail={parse_fail:,} timeout={timeout_fail:,} rate={rate:.2f} art/s out={out}"
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


def _ordinal_label(index: int, total: int | None = None) -> str:
    if index <= 0:
        return "unknown"
    if 10 <= index % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(index % 10, "th")
    label = f"{index}{suffix}"
    if total is not None and total > 0:
        label = f"{label}/{total}"
    return label
