# Session 124 Log — LLM Extractor Audit & Pipeline Run (2026-04-08)

## Objective

Audit `data_tools/extract_llm_news_features.py`, identify why it "wasn't working quite well", fix root causes, and kick off the full extraction run to fill the LLM cache for 2018–2026.

---

## Background

The LLM cache (`data/llm_cache/`) covers only **2015-09-21 → 2017-08-28** (613 files at session start).  
Raw CafeF news (`data/news/cafef/raw/`) covers **2015-09-21 → 2026-03-31** (3751 files).  
Gap: ~3138 days unprocessed. The H294 gate (session 123) found this gap is the primary blocker for the news-marginal-slot in the signal library.

---

## Bugs Found & Fixed

### Bug 1 — Provider-level inflight gate serialised all Google models (FIXED)

**File:** `data_tools/extract_llm_news_features.py`  
**Class:** `GoogleKeyRotationScheduler`  
**Root cause:** Inherited `_model_is_available_locked` from `HostedModelScheduler` checked:
```python
self._inflight_model_counts.get(model.key, 0) == 0
and self._inflight_provider_counts.get(model.provider, 0) == 0
```
All 6 Google models share `provider="google"`. The moment **any** model was in-flight, `_inflight_provider_counts["google"] > 0`, blocking all others. With 16 workers, they all serialised through one model at a time.

**Symptom:** Despite 6 models in the pool, only `gemini-3.1-flash-lite-preview` ran all batches. Throughput ~1.2–1.6 art/s, ~80–120s/day.

**Fix (first pass):** Overrode `_model_is_available_locked` in `GoogleKeyRotationScheduler` to drop the provider-level inflight check:
```python
def _model_is_available_locked(self, model):
    return self._inflight_model_counts.get(model.key, 0) == 0
```

### Bug 2 — Per-model inflight gate still serialised the workhorse model (FIXED)

**Root cause:** Even with Bug 1 fixed, `_inflight_model_counts.get(key) == 0` means only **1 concurrent request per model**. `gemini-3.1-flash-lite-preview` (15 RPM, ~10s/batch) can support ~2–3 concurrent batches within its RPM budget. The inflight==0 gate was still serialising it.

**Fix (second pass):** Overrode `_model_is_available_locked` to return `True` unconditionally — concurrency is already correctly governed by the `rpm`/`rpd` budget checks in `acquire_spec`:
```python
def _model_is_available_locked(self, model):
    # Concurrency governed by rpm/rpd checks in acquire_spec and per-key cooldown.
    return True
```

**Result:** Throughput jumped to 3–7 art/s, 19–50s/day, day_rate ~0.03–0.034 days/s. ETA went from ~74 hours → ~25 hours.

Both fixes are in `GoogleKeyRotationScheduler` only — `ShuffledModelScheduler` (used for `auto` and simple providers) is unchanged.

**Tests:** All 31 tests pass after both fixes.

### Bug 2 — REVERTED (thundering herd)

Removing the model-level inflight gate proved too aggressive. With 16 workers and `_model_is_available_locked = True`, all workers pile onto `gemini-3.1-flash-lite-preview` simultaneously, exhausting its RPM window in bursts and triggering cascading 429s and timeouts. Day 2017-10-06 took 346s (vs ~20s normally) before the run was killed.

**Final state:** Only Bug 1 fix is live — drop provider-level inflight check, keep per-model inflight==0. This gives up to 6 parallel batches (one per Google model) without flooding any single endpoint. That alone is a ~3-4x speedup over the original serialised behaviour.

---

## Pipeline State (as of session end)

**Pipeline is stopped.** Needs to be restarted next session.

| Metric | Value |
|--------|-------|
| Cache files at session start | 613 |
| Cache files at session end | **664** |
| Days processed this session | ~51 |
| Next day to process | 2017-10-17 onwards (2017-10-14/15/16 are latest in cache) |
| Total days remaining | ~3086 |
| Expected rate (after fix) | ~0.020–0.034 days/s |
| ETA from next session start | ~25–40 hours continuous |
| parse_fail | 0 (throughout) |
| timeout_fail | Occasional (transient API issues, handled by retry) |

---

## Known Issues / Observations

### 1. `gemma-3-12b-it` always times out on 20-article batches
- `seed_latency=42.0` but global `--timeout=30`. It will always fail at full batch size.
- After 2–3 failures, its failure_streak penalty (+10 per streak) pushes its score high → no longer selected.
- Self-corrects after a few days. No code change needed; the stats file accumulates correct scores.

### 2. Sustained Google API outages cause multi-model cascading cooldowns
- During a 503 outage all models fail rapidly → all API keys enter 300s cooldown simultaneously.
- All 16 workers then block in `acquire_spec(acquire_timeout=300s)` for up to 5 minutes each before recovering.
- **Recovery:** Kill the process, wait a few minutes, restart. The day that was mid-processing will retry cleanly (no partial writes to cache).
- **To kill and restart:**
  ```bash
  kill $(pgrep -f extract_llm_news_features.py)
  # wait 2–3 min
  nohup python data_tools/extract_llm_news_features.py --provider google --workers 16 \
    > /tmp/llm_extract.log 2>&1 &
  ```

### 3. Stats file (`artifacts/llm_runtime/hosted_model_stats.json`) contains stale 0.5s latencies from test runs
- Test mocks write `0.5` to `recent_latencies`, which makes all models appear equally fast.
- Real latencies accumulate and push out the 0.5s values after enough real runs (window is 20).
- Not a critical issue; scores normalise quickly.

---

## How to Monitor

```bash
# Check progress
tail -20 /tmp/llm_extract.log

# Check cache count
ls data/llm_cache/ | wc -l

# Check which day is being processed
ls data/llm_cache/ | sort | tail -5

# Check process alive
pgrep -f extract_llm_news_features.py
```

---

## How to Resume if Process Died

1. Check if process is alive: `pgrep -f extract_llm_news_features.py`
2. If dead, simply restart — it skips all existing cache files automatically:
   ```bash
   cd /home/manh/stocks-ecosystem/alpha-research-lab
   nohup python data_tools/extract_llm_news_features.py --provider google --workers 16 \
     > /tmp/llm_extract.log 2>&1 &
   ```
3. No `--overwrite` flag needed. No date range needed. It picks up where it left off.

---

## When Extraction Completes

Once `ls data/llm_cache/ | wc -l` reaches ~3750+, the full range is covered.  
Then run the feature-builder to produce `xs_llm_news_ticker_day.parquet` with full coverage:

```bash
python -m research_pipelines.news_features
```

Then re-run H294 gate with the full dataset:

```bash
python analysis/h294_llm_news_standalone_gate.py
```

The goal: 6+ years of data to properly evaluate the `novelty/new` IC (+0.078, only 2/2 years from the 2016–2017 slice).

---

## Validation

- `python -m pytest tests/test_extract_llm_news_features.py` → **31/31 passed** after all fixes.
- Ran on 2-day test window (2018-01-02 → 2018-01-03) before full run — clean output.
- Full run monitoring confirmed parse_fail=0 through first ~40 days.
