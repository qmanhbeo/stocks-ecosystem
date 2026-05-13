# Session 194 Log - Order-Pressure Step-Hazard Audit (2026-04-28)

## Objective

Continue the evergreen loop after H354 parked dividend timing as offline
calendar evidence:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid heavyweight local-model jobs
- test whether the H340-validated CafeF order-pressure surface is the richer
  post-entry state that H339 said smart exits were missing

This session stayed CPU-only.
It did not use `2026` for predictive tuning.

## Branch Selection

H339 showed that skip-aware labels can remove the smart-exit label ceiling, but
the current daily state still cannot learn the rare continuation pockets. Its
next reopening condition was richer post-entry state/data.

H340 later showed that same-day posted buy-volume pressure is a strong daily
state for bullish `C5`. The smallest honest smart-exit continuation was to add
order-pressure state to the saved H337 legal-step rows without rebuilding the
oracle universe.

## Experiment

### H355 - Order-Pressure Step Hazard

**Hypothesis:**
CafeF order-pressure state at the current legal exit decision date should
improve the H337 one-step wait/exit hazard if smart exits were missing
post-entry demand information.

**Command / code:**
`python analysis/h355_order_pressure_step_hazard.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_replacement_aware_step_hazard.json`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `artifacts/run_summaries/latest_portfolio_exit_strength_exhaustion.json`

**Saved artifact:**
`artifacts/run_summaries/20260428_160858_h355_order_pressure_step_hazard_research_branch_order_pressure_step_hazard.json`

| Metric | H337 refit | Best order result | Note |
|--------|------------|-------------------|------|
| verdict | `MIXED` | `MIXED` | no feature set passed the material-improvement gate |
| validation uplift vs fixed 3d | `+0.00245` | `+0.00387` | current-order set improved validation most |
| confirmation uplift vs fixed 3d | `+0.00253` | `+0.00306` | minimal-order-delta improved confirmation most |
| validation oracle recovery | `6.14%` | `9.68%` | current-order set |
| confirmation oracle recovery | `5.75%` | `6.97%` | minimal-order-delta set |
| validation AUC | `0.5107` | `0.5190` | full entry/current/delta set |
| confirmation AUC | `0.5587` | `0.5597` | current-order set |

**Result:**
Order pressure is not useless as post-entry state, but it is not the missing
smart-exit key. It improves different held-out metrics depending on the feature
set:
- `current_order_pressure` improves validation uplift and AUC but weakens
  confirmation utility
- `minimal_order_delta` improves both validation and confirmation utility
  versus the H337 refit, but by only `+0.00065 / +0.00053`
- `entry_current_order_delta` improves validation utility and AUC, but weakens
  confirmation utility

None of the deltas reached the predeclared `+0.002` validation and confirmation
improvement bar.

**Verdict: MIXED**

## Branch Decision

Keep H355 as offline post-entry-state evidence only:
- do not integrate order-pressure smart-exit features
- do not reopen H337/H339 through more linear feature-set tweaks
- smart-exit ML remains parked until genuinely richer post-entry state/data or
  a materially different model contract exists

## Memory Changes

Updated:
- `notes/live_state.md`
- `notes/findings-00271-00300.md`
- `notes/signal_library.md`

Added:
- `analysis/h355_order_pressure_step_hazard.py`

Durable finding:
- `F295`

No promoted signal or exit policy was added.

## Verification

Completed:
- `python -m py_compile analysis/h355_order_pressure_step_hazard.py`
- `python analysis/h355_order_pressure_step_hazard.py`
- read the saved run summary, results, and phase-result artifacts

The broader test suite was not run.

## Next Step

Continue the evergreen loop. Cheap existing-data side branches are now thin.
The main high-value blocker remains the local-news combined audit, which needs
the Ollama residual surface unless a distinct non-news mechanism is identified.
