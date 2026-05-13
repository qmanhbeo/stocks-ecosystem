# Session 87 Log

## Objective
Run `H256` and test whether the `H252` report-window dates are concentrated opportunity states where smaller breadth (`K=1` or `K=2`) beats the gated top-5 baseline.

This session did not try to change the live branch.
It kept the branch narrow, offline, and locked to `2015-2025`, with no `2026+` read.

## Starting point

Coming in:
- `H255` had already shown that nesting the contradiction router inside the report-window gate is not promotable
- the last remaining synthesis question on the current stack was whether the report-window dates simply want smaller breadth
- the carried pieces were:
  - `H201` winner:
    - `state_blend__h199_sector_laggard_gap_absorb__30`
  - `H252` regime:
    - `top5_report_window_ge2`
  - breadth set:
    - `K in {1,2,5}`

## What changed

Added:
- `analysis/h256_event_driven_dynamic_breadth.py`

No shared support or new regression coverage was needed for this pass.

## H256 outcome

### Contract audited

`H256` stayed narrow:
- date range used:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no `2026+` lockbox read

Carried components:
- selector:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- gate regime:
  - `top5_report_window_ge2`
- breadth variants:
  - `K=1`
  - `K=2`
  - `K=5`

Variants audited:
- `winner_report_window_gate_k1`
- `winner_report_window_gate_k2`
- `winner_report_window_gate_k5`
- `full_library_plus_sticky`

### What happened

Both smaller-breadth variants are real validation-only near-misses, but neither is promotable.

`K=1`:
- validation relative `+74.44%`
- validation delta vs `H252` baseline `+14.87%`
- confirmation relative `-50.07%`
- confirmation delta vs `H252` baseline `-39.08%`

`K=2`:
- validation relative `+69.33%`
- validation delta vs `H252` baseline `+9.76%`
- confirmation relative `-42.63%`
- confirmation delta vs `H252` baseline `-31.65%`

`H252` carried baseline:
- `K=5`
- validation relative `+59.57%`
- confirmation relative `-10.98%`

Interpretation:
- the report-window dates really do look more concentrated on validation
- but the smaller-breadth contracts fail catastrophically in `2025`
- that is not a survivable tradeoff under the locked protocol

## Branch decision

Do **not** change the live branch.

What `H256` resolves:
- the current stack does not support event-driven dynamic breadth as a promotable branch
- the small-book intuition is real only as validation-side structure
- it does not survive the honest confirmation test inside the report-window regime

Branch effect:
- `H256` is **MIXED**
- keep it as synthesis-only offline evidence
- close the current-data event-driven dynamic breadth branch
- close the current daily-data synthesis queue on this branch family

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h256_event_driven_dynamic_breadth.py`
- full `conda run -n stocks python analysis/h256_event_driven_dynamic_breadth.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_event_driven_dynamic_breadth.json`
- `artifacts/portfolio_baselines/20260331_122703_h256_event_driven_dynamic_breadth_results.parquet`
- `artifacts/portfolio_baselines/20260331_122703_h256_event_driven_dynamic_breadth_candidate_daily.parquet`
- `artifacts/portfolio_baselines/20260331_122703_h256_event_driven_dynamic_breadth_gate_frame.parquet`
