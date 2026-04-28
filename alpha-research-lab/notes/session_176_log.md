# Session 176 Log - Binary-Head Publish Checkpoint Parity With Forward-Looking (2026-04-25)

## Objective

Make `article_scope` and `source_type` publish behave like the working
forward-looking publish lane instead of restarting from scratch after an
interruption.

The issue was specific:

- binary-head training already had a forward-looking-style staged contract
- binary-head publish did not
- publish still scored the whole universe and only wrote final outputs at the
  end

This session did not change the live alpha branch.
It stayed long-only.

## What changed

### Binary-head publish checkpoint contract

Reworked `research_pipelines/news_features/core/phobert_binary_head_publish.py`
to mirror the forward-looking publish lane more closely:

- per-run checkpoint manifest
- per-batch shard writes under the head-specific checkpoint directory
- resume-safe batch skipping when a shard already exists
- finalize-from-shards before promoting the public article/ticker-day datasets
- publish job-status heartbeat updates across:
  - preflight
  - model load
  - score
  - finalize
  - reuse
  - failed

### Compatibility retained

Preserved the injected-scorer test path so the helper still works for local
fake scorers even when no real winner fixture exists.

## Verification

Completed during this pass:

- `python -m py_compile research_pipelines/news_features/core/phobert_binary_head_publish.py research_pipelines/news_features/tests/test_feature_builders.py`
- `python -m pytest research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `39 passed`

Focused new coverage added:

- binary-head publish partial run leaves:
  - `status == in_progress`
  - one shard file
  - no public outputs yet
- rerun resumes from that checkpoint and finishes cleanly

## Runtime note

The live `article_scope` CUDA train canary stayed healthy during this unrelated
publish-path patch:

- it advanced from late epoch 1 into epoch 2
- throughput stayed around `23.7-23.9 rows/s`

This pass did not interrupt the live training process.

## Results

- worked:
  - binary-head publish now matches the forward-looking publish shape much more
    closely
  - `article_scope` / `source_type` publish runs can now resume from batch
    shards instead of rescoring everything
  - tests cover the new resume boundary
- unresolved:
  - binary-head training itself is still only candidate/epoch durable, not
    exact optimizer-step resumable

## Durable Promotion Status

- promoted findings:
  - `F279`
- promoted dead ends:
  - none

## Pointers

- live state:
  - `notes/live_state.md`
- durable findings touched:
  - `notes/findings-271-300.md#f279`
