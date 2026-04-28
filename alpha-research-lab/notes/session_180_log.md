# Session 180 Log - Ollama BERT-Gated Defaults (2026-04-28)

## Objective

Make the previously chosen Ollama residual priority path the no-flag default
so reruns do not require remembering operator overrides.

This session did not change the live alpha branch.
It stayed long-only.

## Change

Updated `research_pipelines/news_features/config.py` so the guarded Ollama
builder defaults to:
- `ollama_guarded_min_article_scope_prob = 0.28`
- `ollama_guarded_checkpoint_rows = 20`

The 20-row checkpoint default already existed in code. The missing part was
the article-scope gate default.

Operator effect:
- `python -m research_pipelines.news_features.core.build_ollama_guarded_features`
  now means the BERT-gated event-family residual backfill by default
- explicit flags remain available for diagnostics or widened runs
- `--min-article-scope-prob 0.0` can still intentionally force the full
  tagged universe

## Documentation

Updated:
- `README.md`
- `research_pipelines/news_features/README.md`
- `notes/next_steps.md`

The live note now records that the earlier tmux run is not active and that
stale Ollama checkpoint/status files should be treated as partial resume state.

## Verification

Completed:
- `python -m py_compile research_pipelines/news_features/config.py research_pipelines/news_features/core/build_ollama_guarded_features.py research_pipelines/news_features/tests/test_feature_builders.py`
- default-resolution check returned:
  - `0.28 20 event_only 512 300`
- `pytest research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `44 passed`
