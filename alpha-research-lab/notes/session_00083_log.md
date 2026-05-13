# Session 83 Log

## Objective
Run `H252` and test whether the `H251` event-surface trust signal survives a real deterministic selector audit around `H201`, rather than only a pre-integration decomposition.

This session did not try to change the live branch.
It kept the event branch narrow, offline, and locked to `2015-2025`, with no `2026+` read.

## Starting point

Coming in:
- `H201` was still the current offline selector lead:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- `H251` had already shown that the published event surface improves `H201` as trust context
- the strongest promoted regime from `H251` was:
  - `top5_report_window_ge2`
- the only secondary carry worth testing was:
  - `top5_recent_filing_ge1`
- the next queued question was whether a light deterministic trust modifier could turn that decomposition into a real offline selector improvement

## What changed

Added:
- `analysis/h252_h201_event_surface_trust_audit.py`

Shared support added:
- `build_event_regime_activation_scale()` in `src/event_surface_trust_research.py`

Regression coverage extended:
- `tests/test_event_surface_trust_research.py`

## H252 outcome

### Contract audited

`H252` stayed on the locked selector protocol:
- date range used:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no `2026+` lockbox read

Carried selector:
- `state_blend__h199_sector_laggard_gap_absorb__30`

Event regimes carried from `H251`:
- primary:
  - `top5_report_window_ge2`
- secondary:
  - `top5_recent_filing_ge1`

Exposure variants tested:
- `winner_always_on`
- `winner_report_window_gate`
  - on scale `1.0`
  - off scale `0.0`
- `winner_report_window_half_off`
  - on scale `1.0`
  - off scale `0.5`
- `winner_recent_filing_half_off`
  - on scale `1.0`
  - off scale `0.5`

### What passed

Promoted winner:
- `winner_report_window_gate`
- regime:
  - `top5_report_window_ge2`
- overall gate share `49.34%`
- validation gate share `49.90%`
- confirmation gate share `50.60%`
- validation relative `+59.57%`
- validation delta vs always-on `H201` `+13.40%`
- validation IR delta `+0.33`
- confirmation relative `-10.98%`
- confirmation delta vs always-on `H201` `+2.45%`
- confirmation IR delta `+0.10`

Interpretation:
- the `H251` report-window signal survives real integration
- the useful implementation is stronger than “just trust it a bit more”
- on the current stack, it behaves like a real on/off exposure decision

### What stayed mixed or failed

Mixed only:
- `winner_report_window_half_off`
- validation relative delta `-7.13%`
- validation IR delta `-0.01`
- confirmation relative delta `+0.26%`
- confirmation IR delta `-0.09`

Failed:
- `winner_recent_filing_half_off`
- validation relative delta `-25.97%`
- validation IR delta `-0.39`
- confirmation relative delta `-12.43%`

Interpretation:
- partial exposure is not the winner here
- the weaker recent-filing carry does not survive deterministic audit
- the branch should stay focused on the hard report-window gate only

## Branch decision

Do **not** change the live branch.

What `H252` resolves:
- event-surface reuse is still narrow and specific
- the only surviving deterministic implementation is:
  - `H201 + top5_report_window_ge2` as a hard gate
- the branch does **not** justify a broader event-family reopen
- the next honest follow-through, if the model-side queue is intentionally continued later, is a frozen compatibility audit rather than more local event tweaking

Branch effect:
- `H252` is **PASSED**
- keep `winner_report_window_gate` as offline evidence only
- keep `H250` as secondary offline evidence
- if the model-side queue is intentionally continued later, move to `H253`

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h252_h201_event_surface_trust_audit.py src/event_surface_trust_research.py tests/test_event_surface_trust_research.py`
- `pytest -q tests/test_event_surface_trust_research.py tests/test_contradiction_state_router.py`
- full `python analysis/h252_h201_event_surface_trust_audit.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_h201_event_surface_trust_audit.json`
- `artifacts/portfolio_baselines/20260331_112309_h252_h201_event_surface_trust_audit_results.parquet`
- `artifacts/portfolio_baselines/20260331_112309_h252_h201_event_surface_trust_audit_best_daily.parquet`
- `artifacts/portfolio_baselines/20260331_112309_h252_h201_event_surface_trust_audit_topk_frame.parquet`
