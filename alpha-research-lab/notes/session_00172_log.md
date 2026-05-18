# Session 172 Log - PhoBERT Article-Scope And Source-Type Heads (2026-04-24)

## Objective

Implement the next two local PhoBERT news heads after `forward_looking`:

- `article_scope`
- `source_type`

The goal was to reuse the existing forward-looking distillation pattern rather
than introducing another separate monolith.

This session did not change the live alpha branch.
It stayed long-only.

## What changed

### New PhoBERT binary-head framework

Added a shared binary-head path for local PhoBERT heads that follows the same
teacher -> stage -> train -> publish pattern already used by the
forward-looking lane.

The new shared modules now cover:

- teacher-label reconstruction from legacy `data/llm_cache/`
- tagged-only stage dataset assembly with date splits
- sequential candidate training
- winner-based publish/export

### New local heads

Added two repo-native PhoBERT heads:

- `phobert_article_scope`
  - positive label: `stock_news`
  - negative label: `market_news`
- `phobert_source_type`
  - positive label: `official_or_regulatory`
  - negative label: `media_or_commentary`

Both heads now have:

- dedicated dataset and manifest paths
- durable checkpoint/model roots under `data/model_checkpoints/news/`
- job-status paths
- published article-level and ticker-day datasets
- merge-column wiring into the canonical combined news export path

### Publish-path repair

While wiring the new heads, the publish path initially reused scorer rows
against ticker-expanded article rows and broke on multi-ticker articles.

The final contract now matches the forward-looking lane:

- score unique article rows once
- then fan those scores out across tagged ticker rows

## Verification

Completed during this pass:

- `python -m py_compile research_pipelines/news_features/core/phobert_binary_head_common.py research_pipelines/news_features/core/phobert_binary_head_train.py research_pipelines/news_features/core/phobert_binary_head_teacher_stage.py research_pipelines/news_features/core/phobert_binary_head_publish.py research_pipelines/news_features/core/train_phobert_article_scope.py research_pipelines/news_features/core/train_phobert_source_type.py research_pipelines/news_features/core/build_phobert_article_scope_features.py research_pipelines/news_features/core/build_phobert_source_type_features.py research_pipelines/news_features/core/aggregate_daily_features.py research_pipelines/news_features/config.py research_pipelines/news_features/tests/test_feature_builders.py`
- `python -m pytest research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `33 passed`

What was not executed:

- no real PhoBERT training run for the two new heads
- no full shared-warehouse rebuild
- no downstream alpha usefulness audit yet

## Results

- worked:
  - the repo now has real `article_scope` and `source_type` PhoBERT heads in
    code, not just roadmap intent
  - the combined news export contract now has the wiring needed to carry these
    heads into per-ticker daily surfaces
  - the implementation reused the existing low-resource forward-looking pattern
    rather than fragmenting the local-ML path again
- unresolved:
  - the new heads still need honest training/evaluation runs on real teacher
    labels
  - residual Ollama usefulness still needs downstream audit before more local
    semantic expansion

## Durable Promotion Status

- promoted findings:
  - `F275`
- promoted dead ends:
  - none

## Pointers

- live state:
  - `notes/live_state.md`
- durable findings touched:
  - `notes/findings-00241-00270.md#f275`
