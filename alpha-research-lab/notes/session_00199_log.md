# Session 199 Log - Order-Pressure Sizing / State-Scope Audit (2026-04-28)

## Objective

Continue the C16 order-pressure branch after H358 returned a `MIXED`
portfolio / tradability result. H358 showed real executable relevance, but the
equal feature addition narrowly failed validation cash-drag health. The
predeclared follow-up was one bounded sizing / state-scope audit, not an open
search.

The guarded Ollama residual backfill remained the single heavy local-model job.
This session stayed CPU-only and excluded `2026+` predictive data.

## Watchdog State

Before and after H359:
- tmux session `ollama_guarded_backfill` was active
- status file: `artifacts/job_status/ollama_guarded_publish.json`
- latest checked state after H359:
  - status `running`
  - completed batches `530 / 7344`
  - processed input rows `10,600`
  - GPU memory about `2.32GB / 4GB`

The Ollama job was left running.

## Experiment

### H359 - Order-Pressure Sizing / State-Scope Audit

**Hypothesis:**
The H358 cash-drag issue comes from using raw equal-feature order pressure too
broadly. A smaller order-pressure blend or a next-open-buyable scope can keep
the portfolio uplift while passing execution-health gates.

**Command / code:**
`python analysis/h359_order_pressure_sizing_scope_audit.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/stock/gia_lich_su_VNINDEX_1D.parquet`
- `data/stock/gia_lich_su_<TICKER>_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_213148_h359_order_pressure_sizing_scope_audit_research_branch_order_pressure_sizing_scope_audit.json`

| Variant | Validation Rel Delta | Confirmation Rel Delta | Validation Cash Delta | Health | Verdict |
|---------|----------------------|------------------------|-----------------------|--------|---------|
| `order_w0025` | `+20.30%` | `+6.75%` | `+0.0073` | pass | `PASSED` |
| `order_w0050` | `+29.92%` | `+5.27%` | `+0.0194` | pass | `PASSED` |
| `order_w0050_buyable` | `+32.20%` | `+5.82%` | `+0.0036` | pass | `PASSED` |
| `order_w0071_buyable` | `+19.09%` | `+11.69%` | `+0.0036` | pass | `PASSED` |

Selected winner:
- `order_w0050_buyable`
- formula: blend full-library score with `5%` `order_volume_ratio_rank` only
  where `can_buy_next_open` is true
- validation IR delta: `+0.3735`
- confirmation IR delta: `+0.2738`
- confirmation cash delta: `-0.0067`
- validation / confirmation blocked-buy events per day deltas:
  `+0.0020 / +0.0040`

**Result:**
The bounded state-scope follow-up solved the H358 execution-health blocker.
C16 advances to low-resource publisher / contract design for the scoped
order-pressure surface.

**Verdict: PASSED**

## Branch Decision

Advance C16 to publication-design work, not more sizing search.

The next artifact should make the scoped contract explicit:
- source order-pressure rank from `data/order_stats/cafef/order_stats_daily.parquet`
- scope via `data/features/execution/tradability_daily.parquet`
  `can_buy_next_open`
- scoped blend contract with weight `0.05`

Do not update consumers until the artifact shape is verified.

## Memory Changes

Updated:
- `notes/live_state.md`
- `notes/findings-00271-00300.md`
- `notes/signal_library.md`

Added:
- `analysis/h359_order_pressure_sizing_scope_audit.py`

Durable finding:
- `F299`

## Verification

Completed:
- `python -m py_compile analysis/h359_order_pressure_sizing_scope_audit.py`
- `python analysis/h359_order_pressure_sizing_scope_audit.py`
- read the saved run summary and detail artifact
- rechecked the Ollama backfill status after H359

The broader test suite was not run.

## Next Step

Design and verify a low-resource published C16 scoped order-pressure artifact.
Use the shared producer/consumer contract rules before changing downstream
docs or consumers.

Live state: [live_state.md](./live_state.md)
Durable finding: [findings-00271-00300.md](./findings-00271-00300.md)
