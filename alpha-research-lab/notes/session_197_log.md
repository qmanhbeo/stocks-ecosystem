# Session 197 Log - Order-Pressure Integration Audit (2026-04-28)

## Objective

Continue the H356 daily side-channel branch while the guarded Ollama residual
backfill remains the single active heavy job.

H356 showed that CafeF posted order-volume pressure is a strong standalone
signal. H357 tested whether that signal still matters after the existing RL
signal matrix and frozen selector contract are taken into account.

This session stayed CPU-only and excluded `2026` predictive data.

## Watchdog State

Before H357:
- tmux session `ollama_guarded_backfill` was still active
- status file `artifacts/job_status/ollama_guarded_publish.json` was fresh
- completed batches had reached `175 / 7344`
- processed input rows had reached `3,500`
- GPU memory use was about `2.3GB / 4GB`

The Ollama job was left running.

## Experiment

### H357 - Order-Pressure Integration Audit

**Hypothesis:**
The H356 `order_volume_ratio_rank` signal remains useful after accounting for
the existing matrix columns and improves a frozen label-level full-library
selector when added as one equal-weight feature.

**Command / code:**
`python analysis/h357_order_pressure_integration_audit.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_173427_h357_order_pressure_integration_audit_research_branch_order_pressure_integration_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `PASSED` | residual and selector gates passed |
| panel rows / dates / tickers | `810,201 / 2,748 / 394` | 2015-2025 only |
| full-library columns | `13` | existing matrix anchors |
| raw order-pressure avg IC | `+0.0738` | same as H356 |
| residual avg IC | `+0.0687` | after daily residualization vs full library |
| residual dev / validation / confirmation IC | `+0.0728 / +0.0585 / +0.0613` | strict split passed |
| max candidate-library corr | `0.1877` | with `c13_compress_blowoff_2`, negative |
| validation top-5 edge delta | `+0.0152` | full library + order pressure vs full library |
| confirmation top-5 edge delta | `+0.0554` | same fixed label-level selector |
| validation daily IC delta | `+0.0122` | selector score IC |
| confirmation daily IC delta | `+0.0154` | selector score IC |

**Result:**
Order pressure survives as independent signal-library state. Residualizing it
against the full library barely weakens the result, and no existing candidate
has high correlation with it. Adding it as a single equal-weight column to the
full-library label-level selector improves dev, validation, and confirmation
top-5 edge and daily IC.

**Verdict: PASSED**

## Branch Decision

Advance C16, but still do not publish a consumer contract yet.

Next required steps:
- design a formal low-resource feature publisher for
  `data/features/xs_order_pressure_daily.parquet` or the equivalent shared
  artifact
- run a portfolio/tradability audit before changing downstream consumers
- update producer/consumer docs only if publication proceeds

## Memory Changes

Updated:
- `notes/next_steps.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h357_order_pressure_integration_audit.py`

Durable finding:
- `F297`

## Verification

Completed:
- `python -m py_compile analysis/h357_order_pressure_integration_audit.py`
- `python analysis/h357_order_pressure_integration_audit.py`
- read the saved run summary, selector summary, and correlation artifacts
- rechecked the Ollama backfill status after the pass

The broader test suite was not run.

## Next Step

Run a CPU-only order-pressure portfolio/tradability audit before any feature
publication or consumer-contract change.
