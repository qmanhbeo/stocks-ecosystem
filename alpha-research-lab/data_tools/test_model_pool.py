"""
Smoke-test hosted model pools against one real batch of articles per model.

Usage:
    cd alpha-research-lab
    conda run -n stocks python data_tools/test_model_pool.py --provider auto --max-models 6
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

# Allow sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from extract_llm_news_features import (
    HOSTED_MODEL_STATS_PATH,
    HostedModelScheduler,
    _build_prompt,
    _call_hosted_model,
    _is_financial_article,
    _load_articles,
    _normalize_record,
    _resolve_api_keys_for_specs,
    _select_hosted_model_pool,
)
from path_utils import data_path

RAW_DIR = data_path("news/cafef/raw")
CACHE_DIR = data_path("llm_cache")


def _sample_days(n: int) -> list[str]:
    raw = sorted(
        p.stem for p in RAW_DIR.glob("*.jsonl")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)
    )
    uncached = [day for day in raw if not (CACHE_DIR / f"{day}.jsonl").exists()]
    pool = uncached or raw
    if not pool:
        raise SystemExit("No raw news files found.")
    days: list[str] = []
    for index in range(n):
        days.append(pool[index % len(pool)])
    return days


SCHEMA_FIELDS = [
    "tickers", "related_tickers", "sentiment", "confidence", "event_type",
    "magnitude", "is_forward_looking", "market_tone", "is_rumor",
    "surprise_direction", "impact_scope", "named_persons",
]


def score_record(norm: dict) -> float:
    filled = sum(
        1 for field in SCHEMA_FIELDS
        if norm.get(field) is not None and norm.get(field) != [] and norm.get(field) != ""
    )
    return filled / len(SCHEMA_FIELDS)


def test_model(spec, day: str, api_key: str, batch_size: int = 5) -> dict:
    raw_path = RAW_DIR / f"{day}.jsonl"
    if not raw_path.exists():
        return {"model": spec.key, "day": day, "status": "no_raw_file"}

    articles = _load_articles(raw_path)
    filtered = [article for article in articles if _is_financial_article(article)]
    for index, article in enumerate(filtered, start=1):
        article["id"] = f"{day}_{index:04d}"

    if not filtered:
        return {"model": spec.key, "day": day, "status": "no_filtered_articles"}

    batch = filtered[:batch_size]
    prompt = _build_prompt(batch, max_summary_chars=300)

    t0 = time.time()
    try:
        arr = _call_hosted_model(
            prompt=prompt,
            spec=spec,
            api_key=api_key,
            timeout=60,
            max_output_tokens=8192,
        )
    except Exception as exc:
        return {
            "model": spec.key,
            "day": day,
            "status": "api_error",
            "error": str(exc),
            "elapsed": round(time.time() - t0, 2),
        }
    elapsed = round(time.time() - t0, 2)

    if not arr:
        return {"model": spec.key, "day": day, "status": "parse_fail", "elapsed": elapsed}

    by_id = {article["id"]: article for article in batch}
    matched = 0
    scores = []
    for obj in arr:
        rid = str(obj.get("id", "") or "").strip()
        if rid in by_id:
            norm = _normalize_record(obj, rid)
            scores.append(score_record(norm))
            matched += 1

    avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0
    return {
        "model": spec.key,
        "day": day,
        "status": "ok",
        "batch_sent": len(batch),
        "filtered_total": len(filtered),
        "returned": len(arr),
        "matched_ids": matched,
        "avg_field_fill": avg_score,
        "elapsed": elapsed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["auto", "google", "nvidia", "mistral", "huggingface", "vercel"], default="auto")
    ap.add_argument("--models", type=str, default="", help="Optional comma-separated override list. Auto mode uses provider:model entries.")
    ap.add_argument("--batch-size", type=int, default=5)
    ap.add_argument("--max-models", type=int, default=0,
                    help="Optional limit on how many models from the selected pool to test.")
    ap.add_argument("--record-stats", action="store_true",
                    help="Persist observed latency/failure stats into the shared hosted stats file.")
    args = ap.parse_args()

    try:
        model_pool = _select_hosted_model_pool(args.provider, args.models)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    if args.max_models > 0:
        model_pool = model_pool[: args.max_models]
    if not model_pool:
        raise SystemExit("ERROR: no hosted models resolved for the requested provider.")

    api_keys = _resolve_api_keys_for_specs(model_pool, args.provider, "")
    missing = [spec.key for spec in model_pool if spec.key not in api_keys]
    if missing:
        raise SystemExit("ERROR: missing API keys for: " + ", ".join(missing))

    test_days = _sample_days(len(model_pool))
    scheduler = HostedModelScheduler(model_pool, stats_path=HOSTED_MODEL_STATS_PATH) if args.record_stats else None

    print(f"Testing {len(model_pool)} hosted models from provider={args.provider}\n{'─'*80}")
    results = []
    for spec, day in zip(model_pool, test_days):
        print(f"  {spec.key:<48} day={day} ...", end="", flush=True)
        result = test_model(spec, day, api_keys[spec.key], batch_size=args.batch_size)
        results.append(result)
        status = result["status"]
        if scheduler is not None:
            if status == "ok":
                scheduler.record_success(spec.key, float(result["elapsed"]))
            else:
                scheduler.record_failure(spec.key, cooldown_seconds=0.0)
        if status == "ok":
            print(
                f"  OK matched={result['matched_ids']}/{result['batch_sent']}"
                f" fill={result['avg_field_fill']:.0%} {result['elapsed']}s"
            )
        else:
            print(f"  FAIL {status} {result.get('error', '')}")

    print(f"\n{'─'*80}")
    ok = sum(1 for result in results if result["status"] == "ok")
    print(f"Passed: {ok}/{len(results)}")
    if scheduler is not None:
        print(f"Recorded stats to: {HOSTED_MODEL_STATS_PATH}")

    failed = [result for result in results if result["status"] != "ok"]
    if failed:
        print("\nFailed models:")
        for result in failed:
            print(f"  {result['model']}: {result['status']} {result.get('error', '')}")


if __name__ == "__main__":
    main()
