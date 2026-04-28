# Session 203 Log - Dividend Sparse-Clock Portfolio Audit (2026-04-28)

## Objective

Test the allowed dividend-clock reopening condition left by H354: a strict
portfolio-level sparse clock using one fixed pre-ex-dividend rule. This was a
fail-closed audit, not a dividend-window or bonus search.

The guarded Ollama residual backfill remained the single heavy local-model job.
H362 was CPU-only and excluded `2026+`.

## Watchdog State

Latest checked state:
- status `running`
- completed batches `608 / 7344`
- processed input rows `12,160`
- status heartbeat `2026-04-28T22:06:13.050061+00:00`

The Ollama job was left running.

## Experiment

### H362 - Dividend Sparse-Clock Portfolio Audit

**Command / code:**
`python analysis/h362_dividend_sparse_clock_portfolio.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/event_surface_daily.parquet`
- `data/features/execution/tradability_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_215722_h362_dividend_sparse_clock_portfolio_research_branch_dividend_sparse_clock_portfolio.json`

Fixed rule:
- add `+0.015` score bonus only when:
  - `dividend_window_pre_20d > 0`
  - full-library score is already in the daily top quintile
  - `can_buy_next_open` is true

Result:
- verdict `FAILED`
- active rows: `3,423`
- eligible bonus rows: `395`
- portfolio gate `False`
- execution-health gate `True`
- downside-tail gate `True`
- validation relative-return delta: effectively `0.00%` but slightly negative
  at floating precision
- confirmation relative-return delta: `+0.96%`
- confirmation IR delta: `+0.0448`

## Branch Decision

Keep dividend-clock timing parked under the current target and executable
selector contract. The sparse clock did not damage execution or downside tails,
but it did not improve validation.

## Memory Changes

Updated:
- `notes/live_state.md`
- `notes/findings-301-330.md`
- `notes/signal_library.md`

Added:
- `analysis/h362_dividend_sparse_clock_portfolio.py`
- `notes/session_203_log.md`

Durable finding:
- `F303`

## Verification

Completed:
- `python -m py_compile analysis/h362_dividend_sparse_clock_portfolio.py`
- `python analysis/h362_dividend_sparse_clock_portfolio.py`
- read the saved summary and result table

The broader suite was not run after H362.

## Next Step

Continue monitoring `ollama_guarded_backfill`. Until it finishes, do not start
GPU work; prefer only small CPU-only checks that are explicitly allowed by the
current notes.

Live state: [live_state.md](./live_state.md)
Durable finding: [findings-301-330.md](./findings-301-330.md)
