# Session 82 Log

## Objective
Run `H251` and test whether the published event surface can improve selector quality as trust context even though the same surface already failed as an exit / continuation predictor.

This session did not try to change the live branch.
It kept the question narrow: same locked selector windows, same published event surface, no `2026+` read.

## Starting point

Coming in:
- `H201` was still the current offline selector lead:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- `H250` had produced one real contradiction-state router:
  - `h250_disagreement_balance`
  - but it did **not** dislodge `H201`
- the next materially different queued question was whether event-surface v1 still contains useful selector trust context even though it failed as exit alpha

## What changed

Added:
- `analysis/h251_event_surface_trust_modulator.py`

Shared support added:
- `src/event_surface_trust_research.py`

Regression coverage added:
- `tests/test_event_surface_trust_research.py`

## H251 outcome

### Contract audited

`H251` stayed on the locked selector protocol:
- date range used:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no `2026+` lockbox read

Selector backbones compared:
- `full_library_baseline`
- `state_blend__h199_sector_laggard_gap_absorb__30`
- `full_library_plus__h250_disagreement_balance`

Event regimes screened:
- `top5_any_event_ge1`
- `top5_recent_filing_ge1`
- `top5_report_window_ge2`

Promotion rule:
- require support to be adequate
- require both validation and confirmation IC deltas to stay positive
- require both validation and confirmation top-5 edge deltas to stay positive

### What passed

Promoted trust regimes appeared only on the `H201` winner.

Best candidate:
- `state_blend__h199_sector_laggard_gap_absorb__30 + top5_report_window_ge2`
- overall gate share `49.21%`
- validation gate share `49.90%`
- confirmation gate share `50.60%`
- validation IC delta `+0.0104`
- confirmation IC delta `+0.0134`
- validation top-5 edge delta `+0.0174`
- confirmation top-5 edge delta `+0.0146`

Second promoted regime:
- `state_blend__h199_sector_laggard_gap_absorb__30 + top5_recent_filing_ge1`
- overall gate share `58.99%`
- validation IC delta `+0.0038`
- confirmation IC delta `+0.0198`
- validation top-5 edge delta `+0.0016`
- confirmation top-5 edge delta `+0.0043`

Interpretation:
- event-surface v1 is still useful on the current stack
- but the usable role is narrow
- it helps decide when the `H201` selector is more trustworthy
- it does **not** behave like a general-purpose new selector family

### What stayed mixed

Mixed only:
- `full_library_baseline + top5_report_window_ge2`
  - validation edge delta `+0.0255`
  - confirmation edge delta `+0.0339`
  - validation IC delta `-0.0021`
  - confirmation IC delta `-0.0052`
- `full_library_plus__h250_disagreement_balance + top5_report_window_ge2`
  - validation edge delta `+0.0166`
  - confirmation edge delta `+0.0417`
  - validation IC delta `-0.0023`
  - confirmation IC delta `-0.0044`
- `full_library_plus__h250_disagreement_balance + top5_recent_filing_ge1`
  - validation edge delta `-0.0190`
  - confirmation edge delta `+0.0302`
  - validation IC delta `+0.0143`
  - confirmation IC delta `+0.0292`

Interpretation:
- the event surface does not rescue the baseline selector cleanly
- it does not rescue the `H250` additive winner cleanly either
- the pass is specific to `H201`

## Branch decision

Do **not** change the live branch.

What `H251` resolves:
- event surface v1 remains closed as an exit / continuation predictor on the current local stack
- event surface v1 does reopen as a narrow trust modulator for `state_blend__h199_sector_laggard_gap_absorb__30`
- the cleanest next follow-through is a light offline trust-audit, not a broader event search

Branch effect:
- `H251` is **PASSED**
- keep `H201` as the current offline lead
- keep `H250` as offline-only evidence
- if the model-side queue is intentionally continued later, move to `H252`

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h251_event_surface_trust_modulator.py src/event_surface_trust_research.py tests/test_event_surface_trust_research.py`
- `pytest -q tests/test_event_surface_trust_research.py tests/test_contradiction_state_router.py`
- full `python analysis/h251_event_surface_trust_modulator.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_event_surface_trust_modulator.json`
- `artifacts/portfolio_baselines/20260331_110052_h251_event_surface_trust_modulator_results.parquet`
- `artifacts/portfolio_baselines/20260331_110052_h251_event_surface_trust_modulator_topk_frame.parquet`
