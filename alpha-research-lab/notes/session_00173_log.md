# Session 173 Log - Binary-Head Trainer Parity With Forward-Looking (2026-04-25)

## Objective

Bring the new PhoBERT `article_scope` and `source_type` heads closer to the
working `forward_looking` lane at the trainer/runtime level rather than only at
the high-level pipeline shape.

The immediate trigger was operator friction:

- the binary heads were functionally training
- but they still felt "stuck" because the trainer loop did not expose the same
  epoch-level visibility as the forward-looking lane
- the local-file/offline behavior also needed to stay explicit on this box

This session did not change the live alpha branch.
It stayed long-only.

## What changed

### Binary-head trainer parity

The shared binary-head trainer now mirrors the working forward-looking lane much
more closely:

- epoch-level progress lines
- per-epoch job-status updates
- per-epoch in-progress candidate state writes
- gradient clipping before optimizer steps
- best-checkpoint save + reload before final split evaluation
- candidate-level complete / failed summaries
- forward-looking-style winner selection based on validation metrics

### Local-first operating behavior

The binary-head path now keeps the same local-cache-first posture expected on
this workstation:

- `phobert_forward_looking_prefer_local_files` defaults to `True`
- operator canary commands should use:
  - `HF_HUB_OFFLINE=1`
  - `TRANSFORMERS_OFFLINE=1`

### Docs / operator guidance

Updated the news-features README so the operator path for:

- `train_phobert_article_scope`
- `build_phobert_article_scope_features`
- `train_phobert_source_type`
- `build_phobert_source_type_features`

is now documented next to the forward-looking lane instead of living only in
code.

## Verification

Completed during this pass:

- `python -m py_compile research_pipelines/news_features/core/phobert_binary_head_train.py research_pipelines/news_features/core/phobert_binary_head_pipeline.py research_pipelines/news_features/core/train_phobert_article_scope.py research_pipelines/news_features/core/train_phobert_source_type.py research_pipelines/news_features/config.py`
- `python -m pytest research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `33 passed`

What was not executed:

- no fresh full real training completion for `article_scope`
- no fresh full real training completion for `source_type`
- no publish rebuild over the shared warehouse

## Results

- worked:
  - the binary-head trainer is now operationally much closer to the proven
    forward-looking lane
  - future canary runs should no longer look silent between model load and
    candidate completion
  - local offline model loading is now the default posture instead of an
    accidental network-first detour
- unresolved:
  - the new heads still need their real canary train/publish sequence finished
  - stale status files from interrupted earlier attempts may still need to be
    overwritten by the next clean run

## Durable Promotion Status

- promoted findings:
  - `F276`
- promoted dead ends:
  - none

## Pointers

- live state:
  - `notes/live_state.md`
- durable findings touched:
  - `notes/findings-00271-00300.md#f276`
