"""
Smoke-test each model in a hosted provider pool against one real batch of articles.

For each model:
  - Picks the next uncached day from 2026-03-15..2026-03-20
  - Loads + filters articles, takes first min(5, filtered) as the batch
  - Calls the model once and reports parse success / field completeness

Usage:
    cd alpha-research-lab
    conda run -n stocks python data_tools/test_model_pool.py --provider google
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
    PROVIDER_MODEL_POOLS,
    _build_prompt,
    _call_google,
    _call_nvidia,
    _is_financial_article,
    _load_articles,
    _normalize_record,
    _resolve_google_api_key,
    _resolve_nvidia_api_key,
)
from path_utils import data_path

RAW_DIR = data_path("news/cafef/raw")
CACHE_DIR = data_path("llm_cache")


def _uncached_days(n: int) -> list[str]:
    """Return the n most recent raw days that have no llm_cache output yet."""
    raw = sorted(
        p.stem for p in RAW_DIR.glob("*.jsonl")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)
    )
    uncached = [d for d in raw if not (CACHE_DIR / f"{d}.jsonl").exists()]
    if len(uncached) < n:
        raise SystemExit(
            f"Need {n} uncached days for testing but only {len(uncached)} available."
        )
    return uncached[-n:]  # most recent

SCHEMA_FIELDS = [
    "tickers", "related_tickers", "sentiment", "confidence", "event_type",
    "magnitude", "is_forward_looking", "market_tone", "is_rumor",
    "surprise_direction", "impact_scope", "named_persons",
]


def score_record(norm: dict) -> float:
    """Fraction of schema fields that are non-None / non-empty."""
    filled = sum(
        1 for f in SCHEMA_FIELDS
        if norm.get(f) is not None and norm.get(f) != [] and norm.get(f) != ""
    )
    return filled / len(SCHEMA_FIELDS)


def test_model(model_name: str, day: str, api_key: str, provider: str, batch_size: int = 5) -> dict:
    raw_path = RAW_DIR / f"{day}.jsonl"
    if not raw_path.exists():
        return {"model": model_name, "day": day, "status": "no_raw_file"}

    articles = _load_articles(raw_path)
    filtered = [a for a in articles if _is_financial_article(a)]
    for i, a in enumerate(filtered, start=1):
        a["id"] = f"{day}_{i:04d}"

    if not filtered:
        return {"model": model_name, "day": day, "status": "no_filtered_articles"}

    batch = filtered[:batch_size]
    prompt = _build_prompt(batch, max_summary_chars=300)

    t0 = time.time()
    try:
        if provider == "google":
            arr = _call_google(prompt, model=model_name, api_key=api_key, timeout=60, max_output_tokens=8192)
        else:
            arr = _call_nvidia(prompt, model=model_name, api_key=api_key, timeout=60, max_output_tokens=8192)
    except Exception as e:
        return {
            "model": model_name, "day": day, "status": "api_error",
            "error": str(e), "elapsed": round(time.time() - t0, 2),
        }
    elapsed = round(time.time() - t0, 2)

    if not arr:
        return {"model": model_name, "day": day, "status": "parse_fail", "elapsed": elapsed}

    by_id = {a["id"]: a for a in batch}
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
        "model": model_name,
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
    ap.add_argument("--provider", choices=["google", "nvidia"], default="google")
    ap.add_argument("--max-models", type=int, default=0,
                    help="Optional limit on how many models from the provider pool to test.")
    args = ap.parse_args()

    if args.provider == "google":
        api_key = _resolve_google_api_key("")
    else:
        api_key = _resolve_nvidia_api_key("")
    if not api_key:
        env_name = "GOOGLE_API_KEY" if args.provider == "google" else "NVIDIA_API_KEY"
        sys.exit(f"ERROR: set {env_name} or add it to .env")

    model_pool = PROVIDER_MODEL_POOLS[args.provider]
    if args.max_models > 0:
        model_pool = model_pool[: args.max_models]

    test_days = _uncached_days(len(model_pool))

    print(f"Testing {len(model_pool)} {args.provider} models, one batch each\n{'─'*70}")
    results = []
    for model_cfg, day in zip(model_pool, test_days):
        name = model_cfg["name"]
        print(f"  {name:<30}  day={day}  ...", end="", flush=True)
        r = test_model(name, day, api_key, provider=args.provider)
        results.append(r)
        status = r["status"]
        if status == "ok":
            print(
                f"  OK  matched={r['matched_ids']}/{r['batch_sent']}"
                f"  fill={r['avg_field_fill']:.0%}  {r['elapsed']}s"
            )
        else:
            print(f"  FAIL  {status}  {r.get('error', '')}")

    print(f"\n{'─'*70}")
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"Passed: {ok}/{len(results)}")

    failed = [r for r in results if r["status"] != "ok"]
    if failed:
        print("\nFailed models:")
        for r in failed:
            print(f"  {r['model']}: {r['status']} {r.get('error','')}")


if __name__ == "__main__":
    main()
