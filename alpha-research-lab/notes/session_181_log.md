# Session 181 Log - Ollama Guarded Score Cache And Checkpoint Migration (2026-04-28)

## Objective

Investigate whether the guarded Ollama builder unnecessarily rescored work
when only `checkpoint_rows` changed, then repair resume behavior without
starting the long backfill.

This session did not change the live alpha branch.
It stayed long-only.

## Investigation

The suspicion was true.

Before this change, `_ollama_guarded_run_signature` included
`ollama_guarded_checkpoint_rows`. If an earlier run used one checkpoint cadence
and the next run used another, the checkpoint signature changed and the builder
cleared existing checkpoint shards before scoring. That made a flush-cadence
change behave like a scoring-contract change.

True expensive outputs:
- per-article Ollama inference results
- final article-ticker and ticker-day published datasets after finalize

Bookkeeping / cadence artifacts:
- input cache manifest
- checkpoint manifest
- checkpoint shard grouping and batch indexes

## Change

Added a reusable per-article score cache under:
- `data/features/news/datasets/ollama_guarded_score_cache/<score_signature_hash>/`

The score key includes article identity/content after prompt truncation plus
the real scoring contract:
- score cache version
- prompt version
- model name
- timeout
- `num_predict`
- `num_ctx`
- temperature
- schema mode
- prompt variant
- field set
- body char/word truncation

The score key intentionally excludes:
- `checkpoint_rows`
- `keep_alive`
- stop-after-call behavior

`checkpoint_rows` now controls checkpoint flush cadence only. If it changes,
the builder can reuse cached per-article scores or migrate compatible completed
checkpoint shards into the score cache, then write checkpoint shards using the
new cadence.

Final published-output reuse and whole-checkpoint migration still require the
same input universe. If the BERT gate or source inputs change, the builder
falls back to row-level cache hits only, so overlapping article scores can be
reused without treating the old final dataset as valid for the new universe.

## Observability

The builder now logs and writes job-status fields for:
- total candidate rows
- reused cached rows
- cache miss rows
- newly scored rows
- skipped completed rows
- migrated checkpoint rows
- checkpoint files written
- score signature hash

It also prints a final compact cache summary.

## Verification

Completed:
- `python -m py_compile research_pipelines/news_features/config.py research_pipelines/news_features/core/build_ollama_guarded_features.py research_pipelines/news_features/tests/test_feature_builders.py`
- `pytest research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `48 passed`

No long Ollama backfill was started or restarted.
