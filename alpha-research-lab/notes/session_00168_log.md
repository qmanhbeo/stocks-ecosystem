# Session 168 Log - Strict `data_tools/` Runtime Hardening Wave (2026-04-24)

## Objective

Complete the planned strict runtime-hardening pass on the five remaining
`data_tools/` offenders:

- `fetch_hnx_official_disclosures.py`
- `build_llm_news_features.py`
- `extract_llm_news_features.py`
- `extract_llm_news_features_legacy.py`
- `fetch_news.py`

This session was an infrastructure / producer-hardening pass.
It did not change the live alpha branch.
It stayed long-only.

---

## What changed

Added one small shared helper:
- `data_tools/job_status.py`

That helper now backs the canonical machine-readable status files for the five
target scripts:
- `alpha-research-lab/artifacts/job_status/fetch_hnx_official_disclosures.json`
- `alpha-research-lab/artifacts/job_status/build_llm_news_features.json`
- `alpha-research-lab/artifacts/job_status/extract_llm_news_features.json`
- `alpha-research-lab/artifacts/job_status/extract_llm_news_features_legacy.json`
- `alpha-research-lab/artifacts/job_status/fetch_news.json`

### `fetch_hnx_official_disclosures.py`

- added durable per-ticker shard/state writeback under
  `data/official_disclosures/hnx/per_ticker/`
- made aggregate latest-run parquets rebuild from durable ticker shards instead
  of only from one in-memory list
- added ticker-level reuse so reruns skip already-satisfied ticker work unless
  the operator explicitly requests a text-cache refresh
- moved transaction-attachment extraction to a ticker-durable path as well
- added structured status progress for:
  - universe refresh
  - ticker fetch
  - ticker reuse
  - transaction extract rebuild

### `build_llm_news_features.py`

- stopped rebuilding from one giant in-memory cache read
- added staged per-day aggregate shards under
  `data/features/_llm_news_build_stage/`
- kept final published outputs stable:
  - `data/features/xs_llm_news_ticker_day.parquet`
  - `data/features/xs_llm_news_market_daily.parquet`
- made final publish atomic after staged-day reuse / rebuild completes

### `extract_llm_news_features.py`

- added canonical structured status with:
  - pending days
  - completed days
  - retry-only days
  - current day
  - aggregate parsed / failed / timeout counts
- kept the existing day-level durable cache contract unchanged

### `extract_llm_news_features_legacy.py`

- added the same structured status surface so the legacy path remains
  watchdog-compatible
- kept the file in compatibility mode rather than broad internal refactoring

### `fetch_news.py`

- added canonical structured crawler status without changing the existing raw
  batch-save contract
- exposed sitemap / listing / candidate / flush progress through the job status
  surface so resume state is discoverable without replaying console logs

### Docs updated

- `data_tools/README.md`
- `notes/live_state.md`

---

## Validation

Completed during this pass:
- `python -m py_compile data_tools/job_status.py data_tools/build_llm_news_features.py data_tools/extract_llm_news_features.py data_tools/extract_llm_news_features_legacy.py data_tools/fetch_news.py data_tools/fetch_hnx_official_disclosures.py`
- `pytest tests/test_build_llm_news_features.py tests/test_hnx_official_disclosures.py tests/test_extract_llm_news_features.py research_pipelines/news_features/tests/test_fetch_news.py`
  - `69 passed`

What was not executed:
- no live network crawl against HNX or CafeF inside this pass
- no real hosted-LLM backfill run
- no real published LLM feature rebuild against the shared production cache

---

## Results

- worked:
  - all five targeted scripts now expose canonical status files
  - all five now have explicit restart / reuse surfaces instead of relying only
    on operator log reading
  - the two highest-risk scripts no longer depend on end-of-run-only in-memory
    state for their main durable progress boundary
- unresolved:
  - `extract_llm_news_features_legacy.py` is still a legacy monolith; this pass
    kept it compatible and observable rather than rewriting it
  - HNX and CafeF live-network behavior still needs bounded operator smoke runs
    when those network paths are intentionally resumed
- next step:
  - use the new status files as the first recovery surface when the next real
    long job is resumed, starting with `llm-cache-fill`

## Durable Promotion Status

- promoted findings:
  - `F273`
- promoted dead ends:
  - none

## Pointers

- live state:
  - `notes/live_state.md`
- durable findings touched:
  - `notes/findings-00271-00300.md#f273`
- durable dead ends touched:
  - none
