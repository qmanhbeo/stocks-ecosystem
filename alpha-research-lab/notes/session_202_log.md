# Session 202 Log - Event-v2 Sparse-Clock Portfolio Audit (2026-04-28)

## Objective

Test the only remaining event-v2 reopening condition left by H352: a strict
portfolio-level sparse-clock contract. This was not another event overlay
tuning pass. It tested one fixed rule and was designed to close the branch if
the executable portfolio did not improve.

The guarded Ollama residual backfill remained the single heavy local-model job.
H361 was CPU-only and excluded `2026+`.

## Watchdog State

Latest checked state:
- status `running`
- completed batches `582 / 7344`
- processed input rows `11,640`
- status heartbeat `2026-04-28T21:55:02.194592+00:00`

The Ollama job was left running.

## Experiment

### H361 - Event-v2 Sparse-Clock Portfolio Audit

**Command / code:**
`python analysis/h361_event_v2_sparse_clock_portfolio.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/execution/tradability_daily.parquet`
- `artifacts/run_summaries/latest_research_branch_hawkes_disclosure_cascade.json`

**Saved artifact:**
`artifacts/run_summaries/20260428_215245_h361_event_v2_sparse_clock_portfolio_research_branch_event_v2_sparse_clock_portfolio.json`

Fixed rule:
- add `+0.03` score bonus only when:
  - `today_self_accel_high` or `recent5_high_self_no_today`
  - full-library score is already in the daily top quintile
  - `can_buy_next_open` is true

Result:
- verdict `FAILED`
- event active rows: `5,770`
- eligible bonus rows: `891`
- portfolio gate `False`
- execution-health gate `True`
- downside-tail gate `True`
- validation relative-return delta: `-4.96%`
- validation IR delta: `-0.1972`
- confirmation relative-return delta: `-2.66%`
- confirmation IR delta: `-0.1376`
- validation daily q10 delta: `-0.00016`
- confirmation daily q10 delta: `+0.00028`

## Branch Decision

Keep event-v2 parked under the current target and executable selector contract.
The remaining portfolio-level sparse-clock rescue did not work; the problem was
not execution or downside tails, but lack of portfolio benefit.

## Memory Changes

Updated:
- `notes/live_state.md`
- `notes/findings-301-330.md`
- `notes/signal_library.md`

Added:
- `analysis/h361_event_v2_sparse_clock_portfolio.py`
- `notes/session_202_log.md`

Durable finding:
- `F302`

## Verification

Completed:
- `python -m py_compile analysis/h361_event_v2_sparse_clock_portfolio.py`
- `python analysis/h361_event_v2_sparse_clock_portfolio.py`
- read the saved summary and result table

The broader suite was not run after H361.

## Next Step

Continue the evergreen loop while monitoring `ollama_guarded_backfill`. Avoid
GPU work until the Ollama residual backfill completes; prefer small CPU-only
checks that are not parked by the current notes.

Live state: [live_state.md](./live_state.md)
Durable finding: [findings-301-330.md](./findings-301-330.md)
