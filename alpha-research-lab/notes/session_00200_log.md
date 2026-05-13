# Session 200 Log - C16 Order-Pressure Published Artifact (2026-04-28)

## Objective

Continue the C16 order-pressure branch after H359 promoted the scoped
`order_w0050_buyable` variant to publisher / contract design. The goal was to
publish a low-resource shared feature artifact without changing RL or
recommendation behavior by default.

The guarded Ollama residual backfill remained the single heavy local-model job.
This session stayed CPU-only and kept the default feature output capped at
`2025-12-31` to preserve the 2026 lockbox.

## Watchdog State

Latest checked state during this session:
- tmux session `ollama_guarded_backfill` was active
- status file: `artifacts/job_status/ollama_guarded_publish.json`
- status `running`
- completed batches `554 / 7344`
- processed input rows `11,080`
- GPU memory about `2.32GB / 4GB`

The Ollama job was left running.

## Implementation

Added:
- `data_tools/build_order_pressure_features.py`

Published:
- `data/features/xs_order_pressure_daily.parquet`

Registered:
- `shared_recommendation.artifacts.ArtifactKey.ORDER_PRESSURE_DAILY`
- `default_order_pressure_path()`

Updated docs:
- root `AGENTS.md`
- root `README.md`
- `data/README.md`
- `alpha-research-lab/README.md`
- `alpha-research-lab/data_tools/README.md`
- `alpha-research-lab/notes/data_sources.md`
- `shared-recommendation/README.md`
- `RL-trading-agent/README.md`
- `RL-trading-agent/docs/pipeline_contracts.md`

## Contract

The artifact columns are:
- `time`
- `ticker`
- `order_volume_ratio`
- `order_volume_ratio_rank`
- `order_pressure_available`
- `can_buy_next_open`
- `order_pressure_h359_active`
- `order_pressure_h359_blend_weight`

The downstream blend formula is:

```text
blended_score = (1 - w) * base_score + w * order_volume_ratio_rank
```

where `w = order_pressure_h359_blend_weight`.

The builder sets `w = 0.05` only when the order-pressure rank exists and
`can_buy_next_open` is true. Otherwise `w = 0.0`, preserving the H359
state-scoped variant rather than the H358 equal-feature addition.

## Verification

Completed:
- `python -m py_compile data_tools/build_order_pressure_features.py`
- `python data_tools/build_order_pressure_features.py`
- schema/coverage inspection of `data/features/xs_order_pressure_daily.parquet`
- 2026 lockbox guard probe with `--end-date 2026-01-01`, which failed before
  reading or writing data unless `--include-2026` is supplied
- `python -m py_compile shared_recommendation/artifacts.py shared_recommendation/__init__.py`
- `python -m pytest shared-recommendation/tests/test_engine.py`
- shared registry import probe for `default_order_pressure_path()`

Verified artifact:
- rows: `1,315,778`
- tickers: `402`
- dates: `4,622`
- date range: `2007-07-02` through `2025-12-31`
- duplicate ticker-days: `0`
- rank range: `0.0025` to `1.0`
- blend weights: `[0.0, 0.05]`
- active/positive-weight mismatch count: `0`
- active H359 blend rows: `1,211,194` (`92.05%`)

Saved summary:
- `artifacts/run_summaries/20260428_213951_build_order_pressure_features_published_feature_order_pressure_daily.json`
- `artifacts/run_summaries/latest_published_feature_order_pressure_daily.json`

## Branch Decision

C16 is now a published shared feature surface, but it remains downstream
opt-in. RL and recommendation defaults were intentionally not changed.

The next C16 step should only happen when a consumer explicitly merges the
feature into a promoted matrix/export path. Do not run more C16 sizing search
without a changed downstream contract.

## Memory Changes

Updated:
- `notes/live_state.md`
- `notes/findings-00271-00300.md`
- `notes/signal_library.md`
- `notes/data_sources.md`

Added:
- `notes/session_00200_log.md`

Durable finding:
- `F300`

## Next Step

Continue monitoring `ollama_guarded_backfill` as the only heavy job. For the
research loop, prefer a non-GPU, bounded follow-up while the backfill runs; C16
can pause until a downstream consumer requests an explicit matrix/export merge.

Live state: [live_state.md](./live_state.md)
Durable finding: [findings-00271-00300.md](./findings-00271-00300.md)
