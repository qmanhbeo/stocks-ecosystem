# Session 196 Log - Order-Pressure Standalone Gate (2026-04-28)

## Objective

Continue the evergreen loop while the guarded Ollama residual backfill remains
the single active heavy job.

The cheap branch selected for this pass was a distinct daily side-channel
question:
- H340 proved CafeF posted buy-volume pressure as a `C5` conditioner
- H353 showed that H340 is not a clean entry-alpha prior
- H355 showed order pressure helps smart-exit state only marginally
- no prior pass had tested whether CafeF order pressure is a broad standalone
  alpha source on the canonical 1d barrier target

This session stayed CPU-only and excluded `2026` predictive data.

## Watchdog State

Before running H356:
- tmux session `ollama_guarded_backfill` was still active
- status file `artifacts/job_status/ollama_guarded_publish.json` was fresh
- completed batches had reached `156 / 7344`
- processed input rows had reached `3,120`
- GPU memory use was about `2.3GB / 4GB`

The Ollama job was left running.

## Experiment

### H356 - Order-Pressure Standalone Gate

**Hypothesis:**
CafeF order-pressure imbalance may be a broad standalone daily demand signal,
not only a conditioner on bullish insider rows.

**Command / code:**
`python analysis/h356_order_pressure_standalone_gate.py`

**Inputs:**
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_172528_h356_order_pressure_standalone_gate_research_branch_order_pressure_standalone_gate.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `PASSED` | strict 1d and 5d splits passed |
| panel rows / dates / tickers | `826,404 / 2,748 / 394` | 2015-2025 only |
| order-row coverage | `99.44%` | near-dense surface |
| best feature | `order_volume_ratio_rank` | rank of posted buy-vs-sell volume imbalance |
| 1d avg IC | `+0.0738` | `11 / 11` positive years |
| 1d dev / validation / confirmation IC | `+0.0799 / +0.0593 / +0.0713` | strict split passed |
| 1d corr with S1 | `+0.0342` | low redundancy |
| 5d avg IC | `+0.0797` | `11 / 11` positive years |
| 5d dev / validation / confirmation IC | `+0.0844 / +0.0647 / +0.0669` | diagnostic target also passed |
| strict 1d pass count | `6 / 7` | all except lagged count ratio |
| strict 5d pass count | `6 / 7` | all except lagged count ratio |

**Result:**
The broad order-pressure surface is much stronger than expected. Same-day
posted buy-volume pressure passes the signal-library style standalone gate
with dense coverage, low S1 correlation, and stable validation and confirmation
results. The raw CafeF `buy_sell_volume_imbalance` rank, order count rank, 5d
volume-ratio rank, average-size rank, and lagged volume-ratio rank also passed
the strict 1d split.

**Verdict: PASSED**

## Branch Decision

Promote H356 to a high-priority integration audit, not directly to a live or
published consumer contract yet.

Next experiment:
- test `order_volume_ratio_rank` against the frozen signal matrix and selector
  contract
- check whether it remains useful after `S1` and the current candidate library
  anchors
- decide whether to publish a formal order-pressure feature artifact or keep
  it as research-only state

## Memory Changes

Updated:
- `notes/next_steps.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h356_order_pressure_standalone_gate.py`

Durable finding:
- `F296`

Signal-library update:
- added C16 as a candidate order-pressure signal pending integration audit

## Verification

Completed:
- `python -m py_compile analysis/h356_order_pressure_standalone_gate.py`
- `python analysis/h356_order_pressure_standalone_gate.py`
- read the saved run summary and result parquet
- rechecked the Ollama backfill status after the pass

The broader test suite was not run.

## Next Step

Run one CPU-only H357 integration audit for `order_volume_ratio_rank` while the
Ollama residual backfill continues, unless the backfill needs watchdog
intervention first.
