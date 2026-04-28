# Session 201 Log - C16 Published Contract Parity Audit (2026-04-28)

## Objective

Run one fixed, non-search audit to verify that the newly published C16
order-pressure artifact reproduces the H359 winner when consumed through the
documented downstream formula.

This was not a sizing search. The only tested strategy was the published
contract:

```text
blended_score = (1 - w) * full_library_score + w * order_volume_ratio_rank
```

where `w = order_pressure_h359_blend_weight`.

## Watchdog State

The guarded Ollama residual backfill remained the only heavy local-model job.
Latest checked state:
- status `running`
- completed batches `570 / 7344`
- processed input rows `11,400`
- status heartbeat `2026-04-28T21:49:48.655891+00:00`

The H360 audit was CPU-only and the Ollama job was left running.

## Experiment

### H360 - Order-Pressure Published Contract Audit

**Command / code:**
`python analysis/h360_order_pressure_published_contract_audit.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/xs_order_pressure_daily.parquet`
- `data/features/execution/tradability_daily.parquet`
- `artifacts/run_summaries/latest_research_branch_order_pressure_sizing_scope_audit.json`

**Saved artifact:**
`artifacts/run_summaries/20260428_214819_h360_order_pressure_published_contract_audit_research_branch_order_pressure_published_contract_audit.json`

Result:
- verdict `PASSED`
- portfolio gate `True`
- execution health `True`
- parity pass `True`
- max absolute parity delta versus H359 winner: `9.10e-15`
- validation relative-return delta: `+32.20%`
- confirmation relative-return delta: `+5.82%`
- validation cash delta: `+0.0036`
- confirmation cash delta: `-0.0067`

## Branch Decision

C16 is now closed as a published, opt-in feature contract. Do not run more C16
search unless a downstream matrix/export consumer explicitly changes the
contract and needs a focused integration audit.

## Memory Changes

Updated:
- `notes/live_state.md`
- `notes/findings.md`
- `notes/findings-301-330.md`
- `notes/signal_library.md`

Added:
- `analysis/h360_order_pressure_published_contract_audit.py`
- `notes/session_201_log.md`

Durable finding:
- `F301`

## Verification

Completed:
- `python -m py_compile analysis/h360_order_pressure_published_contract_audit.py`
- `python analysis/h360_order_pressure_published_contract_audit.py`

The broader suite was not rerun after H360; the shared recommendation unit test
suite had already passed during Session 200 after the artifact-registry change.

## Next Step

Continue the evergreen loop with C16 closed. While `ollama_guarded_backfill`
runs, avoid GPU work and prefer a bounded CPU-only branch that is not parked by
the current notes.

Live state: [live_state.md](./live_state.md)
Durable finding: [findings-301-330.md](./findings-301-330.md)
