# Session 86 Log

## Objective
Run `H255` and test whether the promoted `H250` contradiction router helps only inside the `H252` report-window dates.

This session did not try to change the live branch.
It kept the branch narrow, offline, and locked to `2015-2025`, with no `2026+` read.

## Starting point

Coming in:
- `H254` had already closed the broader report-window selector-switchboard branch
- the next remaining synthesis question was narrower:
  - inside the `H252` on-dates only, does the promoted `H250` contradiction router improve `H201`
- the carried pieces were:
  - `H201` winner:
    - `state_blend__h199_sector_laggard_gap_absorb__30`
  - `H250` winner:
    - `h250_disagreement_balance`
  - `H252` regime:
    - `top5_report_window_ge2`

## What changed

Added:
- `analysis/h255_report_window_contradiction_expert.py`

No shared support or new regression coverage was needed for this pass.

## H255 outcome

### Contract audited

`H255` stayed narrow:
- date range used:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no `2026+` lockbox read

Carried components:
- base selector:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- contradiction overlay:
  - `h250_disagreement_balance`
- gate regime:
  - `top5_report_window_ge2`

Variants audited:
- `winner_plus_router_report_window_gate`
- `winner_report_window_gate`
- `full_library_plus_sticky`

### What happened

The nested contradiction overlay did not survive as a real branch winner.

Candidate:
- `winner_plus_router_report_window_gate`
- validation relative `+5.65%`
- validation delta vs `H252` baseline `-53.92%`
- validation IR delta vs `H252` baseline `-1.04`
- confirmation relative `-8.20%`
- confirmation delta vs `H252` baseline `+2.78%`
- confirmation IR delta vs `H252` baseline `+0.04`
- confirmation delta vs frozen sticky `-27.00%`

Interpretation:
- the contradiction overlay does help confirmation slightly inside the report-window dates
- but the cost is catastrophic on validation
- that is not a promotable tradeoff under the locked protocol

Reference baseline:
- `winner_report_window_gate`
- validation relative `+59.57%`
- confirmation relative `-10.98%`

## Branch decision

Do **not** change the live branch.

What `H255` resolves:
- `H250` does not become a useful nested overlay inside the `H252` on-dates
- the contradiction family remains interesting as secondary offline evidence only
- the nested event x contradiction branch is not strong enough to promote

Branch effect:
- `H255` is **MIXED**
- keep it as synthesis-only offline evidence
- do not reopen the failed switchboard from it
- if the model-side queue is intentionally continued later, move to `H256`

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h255_report_window_contradiction_expert.py`
- full `conda run -n stocks python analysis/h255_report_window_contradiction_expert.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_report_window_contradiction_expert.json`
- `artifacts/portfolio_baselines/20260331_121916_h255_report_window_contradiction_expert_results.parquet`
- `artifacts/portfolio_baselines/20260331_121916_h255_report_window_contradiction_expert_candidate_daily.parquet`
- `artifacts/portfolio_baselines/20260331_121916_h255_report_window_contradiction_expert_gate_frame.parquet`
- `artifacts/portfolio_baselines/20260331_121916_h255_report_window_contradiction_expert_audit_scored.parquet`
