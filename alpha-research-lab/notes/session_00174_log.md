# Session 174 Log - Operator-Default Offline PhoBERT Runtime (2026-04-25)

## Objective

Remove the need for shell-level offline prefixes from the local PhoBERT
operator commands.

The problem was not model quality. It was operator-default behavior:

- the repo had already decided these lanes were local-file-first
- but the shell examples still needed explicit `HF_HUB_OFFLINE=1` and
  `TRANSFORMERS_OFFLINE=1`
- that meant the repo contract still lived partly in operator memory instead of
  in code

This session did not change the live alpha branch.
It stayed long-only.

## What changed

### Local runtime helper

Added a small repo-local runtime helper:

- `research_pipelines/news_features/local_runtime.py`

It now applies the offline Hugging Face / transformers environment defaults
automatically when the repo config says local PhoBERT operations should prefer
local files.

### Entry-point hardening

Applied that helper to the main local PhoBERT operator entrypoints:

- `train_phobert_forward_looking`
- `publish_phobert_forward_looking_features`
- `train_phobert_article_scope`
- `build_phobert_article_scope_features`
- `train_phobert_source_type`
- `build_phobert_source_type_features`

Also applied the same helper inside the actual model-loading paths so
programmatic calls inherit the same local-first behavior.

### Tests and docs

Added focused tests for the runtime helper and removed the extra offline env
prefixes from the main binary-head operator examples in the README.

## Verification

Completed during this pass:

- `python -m py_compile research_pipelines/news_features/local_runtime.py research_pipelines/news_features/core/train_phobert_forward_looking.py research_pipelines/news_features/core/train_phobert_article_scope.py research_pipelines/news_features/core/train_phobert_source_type.py research_pipelines/news_features/core/build_phobert_article_scope_features.py research_pipelines/news_features/core/build_phobert_source_type_features.py research_pipelines/news_features/core/publish_phobert_forward_looking_exports.py research_pipelines/news_features/core/phobert_forward_looking_train.py research_pipelines/news_features/core/phobert_binary_head_train.py research_pipelines/news_features/core/build_phobert_forward_looking_features.py research_pipelines/news_features/core/phobert_binary_head_publish.py research_pipelines/news_features/tests/test_feature_builders.py`
- `python -m pytest research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `35 passed`

What was not executed:

- no fresh real PhoBERT train run after this exact runtime-default patch
- no shared-warehouse publish rebuild

## Results

- worked:
  - the local PhoBERT operator commands now encode the intended offline default
    directly in repo code
  - the repo no longer relies on the user remembering shell-level offline
    prefixes for the main local PhoBERT lanes
  - the helper is covered by targeted tests
- unresolved:
  - stale status files from interrupted earlier canaries may still exist until
    the next clean train/publish pass overwrites them

## Durable Promotion Status

- promoted findings:
  - `F277`
- promoted dead ends:
  - none

## Pointers

- live state:
  - `notes/live_state.md`
- durable findings touched:
  - `notes/findings-00271-00300.md#f277`
