from __future__ import annotations

import math
import time

from data_tools.news_runtime.llm_extract.status import tracker_payload


def run_canonical_extraction(
    *,
    files,
    pending,
    completed_days,
    retry_only_days,
    skipped_existing_days,
    process_day,
    tracker,
    log,
    provider,
    model,
    batch_size,
    api_key,
    timeout,
    num_predict,
    max_summary_chars,
    log_every_batches,
    rate_limiter,
    api_keys_by_model,
    workers,
) -> None:
    total_days = 0
    total_filtered = 0
    total_ok = 0
    total_fail = 0
    total_timeout = 0
    total_elapsed = 0.0
    tracker.write(
        status="running",
        phase="extract",
        progress=tracker_payload(
            pending_days=[p.stem for p in pending],
            completed_days=completed_days,
            retry_only_days=retry_only_days,
            current_day=None,
            skipped_existing_days=skipped_existing_days,
            aggregate_counts={
                "filtered_articles": total_filtered,
                "parsed_ok": total_ok,
                "parse_fail": total_fail,
                "timeout_fail": total_timeout,
            },
        ),
    )

    start = time.time()
    try:
        for index, path in enumerate(pending, start=1):
            tracker.write(
                status="running",
                phase="extract",
                progress=tracker_payload(
                    pending_days=[item.stem for item in pending[index - 1 :]],
                    completed_days=completed_days,
                    retry_only_days=retry_only_days,
                    current_day=path.stem,
                    skipped_existing_days=skipped_existing_days,
                    aggregate_counts={
                        "filtered_articles": total_filtered,
                        "parsed_ok": total_ok,
                        "parse_fail": total_fail,
                        "timeout_fail": total_timeout,
                    },
                    current_index=index,
                    total_pending_days=len(pending),
                ),
            )
            stats = process_day(
                path,
                batch_size=batch_size,
                provider=provider,
                model=model,
                api_key=api_key,
                timeout=timeout,
                num_predict=num_predict,
                max_summary_chars=max_summary_chars,
                log_every_batches=log_every_batches,
                rate_limiter=rate_limiter,
                api_keys=api_keys_by_model,
                workers=workers,
            )
            total_days += 1
            total_filtered += stats["articles_filtered"]
            total_ok += stats["parsed_ok"]
            total_fail += stats["parse_fail"]
            total_timeout += stats["timeout_fail"]
            total_elapsed += stats["elapsed_sec"]
            completed_days.append(path.stem)
            wall = time.time() - start
            day_rate = total_days / wall if wall > 0 else 0.0
            rem_days = len(pending) - total_days
            eta_days = rem_days / day_rate if day_rate > 0 else float("inf")
            eta_s = "inf" if not math.isfinite(eta_days) else f"{eta_days/60:.1f}m"
            log(
                f"[progress] {index}/{len(pending)} days done | "
                f"filtered={total_filtered:,} ok={total_ok:,} parse_fail={total_fail:,} timeout={total_timeout:,} "
                f"day_rate={day_rate:.3f} days/s eta={eta_s}"
            )
            tracker.write(
                status="running",
                phase="extract",
                progress=tracker_payload(
                    pending_days=[item.stem for item in pending[index:]],
                    completed_days=completed_days,
                    retry_only_days=retry_only_days,
                    current_day=None,
                    skipped_existing_days=skipped_existing_days,
                    aggregate_counts={
                        "filtered_articles": total_filtered,
                        "parsed_ok": total_ok,
                        "parse_fail": total_fail,
                        "timeout_fail": total_timeout,
                    },
                    current_index=index,
                    total_pending_days=len(pending),
                ),
                throughput={
                    "days_per_second": day_rate,
                    "filtered_articles_per_second": (total_filtered / wall) if wall > 0 else 0.0,
                },
            )
            if stats.get("pool_exhausted"):
                log(f"All {provider} model daily limits exhausted after {total_days} days — stopping early.")
                break
    except Exception as exc:
        tracker.write(
            status="failed",
            phase="extract",
            progress=tracker_payload(
                pending_days=[item.stem for item in pending[max(total_days, 0):]],
                completed_days=completed_days,
                retry_only_days=retry_only_days,
                current_day=pending[total_days].stem if total_days < len(pending) else None,
                skipped_existing_days=skipped_existing_days,
                aggregate_counts={
                    "filtered_articles": total_filtered,
                    "parsed_ok": total_ok,
                    "parse_fail": total_fail,
                    "timeout_fail": total_timeout,
                },
            ),
            error={"message": str(exc), "type": exc.__class__.__name__},
        )
        raise

    wall_total = time.time() - start
    art_rate_wall = total_filtered / wall_total if wall_total > 0 else 0.0
    log("Done.")
    log(f"Processed days: {total_days} | skipped existing: {skipped_existing_days}")
    log(f"Filtered articles: {total_filtered:,}")
    log(f"Parsed ok: {total_ok:,} | parse_fail: {total_fail:,} | timeout_fail: {total_timeout:,}")
    log(
        f"Wall time: {wall_total:.1f}s | sum(day elapsed): {total_elapsed:.1f}s | "
        f"wall throughput: {art_rate_wall:.2f} filtered art/s"
    )
    tracker.write(
        status="complete",
        phase="complete",
        progress=tracker_payload(
            pending_days=[item.stem for item in pending[total_days:]],
            completed_days=completed_days,
            retry_only_days=retry_only_days,
            current_day=None,
            skipped_existing_days=skipped_existing_days,
            aggregate_counts={
                "filtered_articles": total_filtered,
                "parsed_ok": total_ok,
                "parse_fail": total_fail,
                "timeout_fail": total_timeout,
            },
        ),
        throughput={
            "days_per_second": (total_days / wall_total) if wall_total > 0 else 0.0,
            "filtered_articles_per_second": art_rate_wall,
        },
    )
