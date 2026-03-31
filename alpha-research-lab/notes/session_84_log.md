# Session 84 Log

## Objective
Run `H253` and test whether the `H252` hard report-window gate around `H201` survives a real frozen compatibility audit against the incumbent sticky branch.

This session did not try to change the live branch.
It kept the event-conditioned selector branch narrow, offline, and locked to `2015-2025`, with no `2026+` read.

## Starting point

Coming in:
- `H201` was still the current offline selector lead:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- `H252` had passed only as a hard event gate:
  - `winner_report_window_gate`
  - regime:
    - `top5_report_window_ge2`
- the live / incumbent branch was still:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- the next queued question was whether the hard-gated `H201` branch was strong enough to survive direct comparison against that frozen sticky benchmark

## What changed

Added:
- `analysis/h253_h252_frozen_compatibility_audit.py`

No shared support or new regression coverage was needed for this pass.

## H253 outcome

### Contract audited

`H253` stayed narrow and direct:
- date range used:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no `2026+` lockbox read

Carried selector:
- `state_blend__h199_sector_laggard_gap_absorb__30`

Carried regime:
- `top5_report_window_ge2`

Variants audited:
- `winner_report_window_gate`
- `winner_always_on`
- `full_library_plus_sticky`

### What happened

The promoted `H252` implementation stayed real, but it did **not** survive frozen compatibility:
- `winner_report_window_gate`
- overall gate share `49.34%`
- validation gate share `49.90%`
- confirmation gate share `50.60%`
- validation relative `+59.57%`
- validation delta vs incumbent sticky `+29.91%`
- validation IR delta `+0.62`
- confirmation relative `-10.98%`
- confirmation delta vs incumbent sticky `-29.78%`
- confirmation IR delta `-1.17`

The ungated `H201` path also failed compatibility:
- `winner_always_on`
- validation delta vs incumbent sticky `+16.51%`
- confirmation delta vs incumbent sticky `-32.24%`

Frozen incumbent benchmark:
- `full_library_plus_sticky`
- validation relative `+29.65%`
- confirmation relative `+18.80%`

Interpretation:
- the report-window gate is not noise
- it clearly strengthens `H201` on validation
- but neither the gated nor always-on `H201` path is robust enough to beat the frozen sticky incumbent through confirmation

### Branch decision

Do **not** change the live branch.

What `H253` resolves:
- `H252` does **not** become a live-adjacent compatibility winner
- the event-conditioned `H201` path remains offline evidence only
- the correct next synthesis follow-through, if the model-side queue is intentionally continued later, is a hybrid switchboard audit rather than more local event tuning

Branch effect:
- `H253` is **MIXED**
- keep `winner_report_window_gate` as offline regime evidence only
- keep the live sticky branch frozen
- if the model-side queue is intentionally continued later, move to `H254`

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h253_h252_frozen_compatibility_audit.py`
- full `conda run -n stocks python analysis/h253_h252_frozen_compatibility_audit.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_h252_frozen_compatibility_audit.json`
- `artifacts/portfolio_baselines/20260331_115415_h253_h252_frozen_compatibility_audit_results.parquet`
- `artifacts/portfolio_baselines/20260331_115415_h253_h252_frozen_compatibility_audit_candidate_daily.parquet`
- `artifacts/portfolio_baselines/20260331_115415_h253_h252_frozen_compatibility_audit_gate_frame.parquet`
