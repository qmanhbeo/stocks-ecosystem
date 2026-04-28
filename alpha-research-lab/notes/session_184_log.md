# Session 184 Log - Foreign Accumulation Change-Point Audit (2026-04-28)

## Objective

Continue the evergreen loop with data already available on disk:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid GPU / Ollama / PhoBERT training jobs
- resolve the queued H95 continuation after raw foreign-flow ranks, simple
  conditioning, and room-residual discontinuities failed

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Watchdog state

Preflight checks:
- `ollama ps` returned no loaded model
- `nvidia-smi` showed no running GPU process

Decision:
- do not resume the multi-day Ollama residual backfill
- run one bounded CPU/parquet audit over the existing CafeF foreign-flow panel

## Experiment

### H345 - Foreign Accumulation Change-Point

**Hypothesis:**
The H95 foreign-flow signal may live in slower accumulation / ownership regime
changes rather than one-day or five-day raw foreign buy/sell ranks, simple
participation/room-scarcity states, or room-residual discontinuities.

**Command / code:**
`python analysis/h345_foreign_accumulation_change_point.py`

**Inputs:**
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- local daily stock volume panel under `data/stock/`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_070831_h345_foreign_accumulation_change_point_research_branch_foreign_accumulation_change_point.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | no predeclared feature clears the unchanged H327/H333 gate |
| merged rows | `817,074` | same 2015-2025 predictive universe as prior CafeF tests |
| merged tickers / dates | `391 / 2,741` | excludes `2026` |
| feature count | `6` | small predeclared accumulation / ownership-change set |
| best feature | `xs_ff_room_scarcity_delta_20d_volnorm_rank` | strongest validation row |
| best dev IC | `+0.0020` | far below `0.01` gate |
| best validation IC | `+0.0024` | below validation threshold |
| best confirmation IC | `+0.0086` | positive but not useful because dev/validation failed |
| best S1 corr | `-0.0023` | orthogonal but too weak |
| near-pass features | `0` | no dev+validation structure to confirm |

**Result:**
The accumulation / ownership-change thesis does not rescue H95 as a standalone
signal. Every predeclared feature is near zero in dev and validation. The
positive 2025 confirmation values are not actionable because the fixed
pre-confirmation structure is absent.

**Verdict: FAILED**

## Branch decision

Do not keep tuning standalone CafeF foreign-flow features:
- raw ranks failed in H327
- raw participation / room-scarcity conditioning failed in H328
- room-residual discontinuities failed in H333
- accumulation / ownership-change change-points failed in H345

If the foreign-flow branch reopens, it should be as a distinct interaction
branch, for example:
- foreign-insider agreement
- foreign-flow versus proprietary-flow conflict/agreement
- sector-specific ownership pressure with a new sector-state contract

## Memory changes

Updated:
- `notes/next_steps.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h345_foreign_accumulation_change_point.py`

Durable finding:
- `F285`

No durable dead-end file exists in the current repo note convention, so the
negative standalone-foreign-flow result is recorded in the active findings
chunk and signal library.

## Verification

Completed:
- `python -m py_compile analysis/h345_foreign_accumulation_change_point.py`
- `python analysis/h345_foreign_accumulation_change_point.py`

## Next step

The evergreen loop should not spend another pass on standalone foreign-flow
thresholds or accumulation windows. Continue with a different existing-data
hypothesis, preferably a small CPU-only pass, unless the user explicitly wants
to resume the multi-day Ollama residual backfill.
