# Session 80 Log

## Objective
Run `H249` and test whether the `H201` offline selector lead fails under sticky activation only because the gate is calibrated to `full_library` rather than to the selector's own recent relative returns.

This session did not try to change the live branch.
It kept the question narrow: same `H201` winner, same sticky displacement rule, no `2026+` read.

## Starting point

Coming in:
- `H201` had already produced the strongest offline selector lead in the `H199` family:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- `H202` had already shown that this winner fails under the frozen sticky overlay built from `full_library`:
  - validation relative `+16.64%` vs incumbent `+29.65%`
  - confirmation relative `+24.70%` vs incumbent `+18.80%`
- the next queued model-side question was whether selector-relative activation calibration rescues that compatibility failure without touching the live branch

## What changed

Added:
- `analysis/h249_selector_relative_activation_audit.py`

Shared support added:
- `selector_meta_from_daily()` in `src/activation_meta.py`

Regression coverage added:
- `tests/test_activation_meta.py`

## H249 outcome

### Contract audited

`H249` stayed on the locked selector protocol:
- date range used:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no `2026+` lockbox read

Carried selector:
- `state_blend__h199_sector_laggard_gap_absorb__30`

Variants compared:
- `winner_always_on`
- `winner_plus_full_rel2_sticky`
  - control rerun of the `H202` frozen sticky logic
- `winner_plus_selector_rel2_sticky`
  - same sticky displacement rule
  - gate rebuilt from the winner's own prior-cycle relative returns
- incumbent:
  - `full_library_plus_sticky`

### Gate behavior

Frozen incumbent gate:
- overall on-rate `54.26%`
- validation on-rate `54.31%`
- confirmation on-rate `41.77%`

Selector-relative gate:
- overall on-rate `53.82%`
- validation on-rate `55.51%`
- confirmation on-rate `42.57%`

Agreement:
- overall gate agreement `72.63%`

Interpretation:
- the selector-relative gate is not a tiny perturbation of the incumbent rule
- it materially changes roughly a quarter of gate days

### Results

Always-on selector:
- validation relative `+46.17%`
- validation IR `0.90`
- confirmation relative `-13.43%`

Incumbent sticky branch:
- validation relative `+29.65%`
- validation IR `0.61`
- confirmation relative `+18.80%`

Control rerun with incumbent gate on the winner:
- `winner_plus_full_rel2_sticky`
- validation relative `+16.64%`
- validation delta vs incumbent `-13.01%`
- confirmation relative `+24.70%`
- confirmation delta vs incumbent `+5.90%`

Selector-relative gate candidate:
- `winner_plus_selector_rel2_sticky`
- validation relative `+16.18%`
- validation delta vs incumbent `-13.47%`
- validation IR delta `-0.21`
- confirmation relative `-19.10%`
- confirmation delta vs incumbent `-37.90%`

Interpretation:
- the control variant reproduces the original `H202` failure mode cleanly
- switching the gate source from `full_library` to the winner's own `rel2` does **not** improve validation
- it makes confirmation materially worse than both the incumbent sticky branch and the `H202` control

## Branch decision

Do **not** promote the `H201` selector into the live branch.

What `H249` resolves:
- the `H201` compatibility problem is **not** fixed by rebuilding `rel2 > 0` on the selector's own recent relative returns
- `state_blend__h199_sector_laggard_gap_absorb__30` remains selector-only offline evidence
- the current branch should not keep tuning local `rel_span` / `rel_threshold` variants against the same locked windows

Branch effect:
- `H249` fails
- if the model-side queue is intentionally continued later, move to `H250`, not more local `H249` variants

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h249_selector_relative_activation_audit.py src/activation_meta.py tests/test_activation_meta.py`
- `pytest -q tests/test_activation_meta.py`
- full `python analysis/h249_selector_relative_activation_audit.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_selector_relative_activation_audit.json`
- `artifacts/portfolio_baselines/20260331_102754_h249_selector_relative_activation_audit_results.parquet`
- `artifacts/portfolio_baselines/20260331_102754_h249_selector_relative_activation_audit_best_daily.parquet`
- `artifacts/portfolio_baselines/20260331_102754_h249_selector_relative_activation_audit_selector_meta.parquet`
- `artifacts/portfolio_baselines/20260331_102754_h249_selector_relative_activation_audit_gate_frame.parquet`
