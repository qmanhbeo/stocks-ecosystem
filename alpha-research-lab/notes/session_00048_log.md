# Session 48 Log

## Objective
Continue after H137 by removing selector complexity and answering two direct questions:

1. Do a few simple fixed long-only rules beat the benchmark on the honest holdout?
2. If yes, do they remain deployable once capacity and higher fee assumptions are imposed?

## Implementation

Added:
- `analysis/h138_fixed_menu_validation.py`
  - honest fixed-rule validation on a tiny reduced menu
  - train window for context: `2015-2018`
  - holdout test window: `2019-2025`
- `analysis/h139_fixed_menu_capacity_fee_stress.py`
  - capacity and fee stress on the fixed-rule survivors
- extended `src/portfolio_construction_search.py`
  - fixed-menu candidate parsing

Validation:
- `python -m py_compile`
- `pytest tests/test_deterministic_portfolio.py tests/test_portfolio_construction_search.py tests/test_tradability_flags.py`
- `git diff --check`

## H138 fixed-menu validation
Artifacts:
- `artifacts/run_summaries/20260328_172830_h138_fixed_menu_validation_portfolio_fixed_menu_validation.json`
- `artifacts/portfolio_baselines/20260328_172830_h138_fixed_menu_validation_results.parquet`
- `artifacts/portfolio_baselines/20260328_172830_h138_fixed_menu_validation_oos_daily.parquet`

Fixed candidate menu:
- `k3_r5_eq` = top-3, 5-day cadence, equal weight
- `k5_r5_eq` = top-5, 5-day cadence, equal weight
- `k5_r10_eq` = top-5, 10-day cadence, equal weight

Holdout results (`2019-2025`):

| Rule | Total Return | Annualized | Relative vs VNINDEX | IR | Max DD | Positive Years |
|---|---:|---:|---:|---:|---:|---:|
| `k3_r5_eq` | +303.01% | +22.25% | +106.86% | 0.43 | -47.61% | 5/7 |
| `k5_r5_eq` | +271.38% | +20.82% | +90.62% | 0.42 | -47.23% | 6/7 |
| `k5_r10_eq` | +241.90% | +19.39% | +75.49% | 0.38 | -56.56% | 4/7 |

Interpretation:
- the long-only path is not dead
- H137 failed because the selector overfit, not because fixed simple constructions were hopeless
- `k3_r5_eq` is the best holdout performer by return / benchmark-relative edge
- `k5_r10_eq` is slower and lower-turnover, but still clearly positive

## H139 capacity / fee stress
Artifacts:
- `artifacts/run_summaries/20260328_173118_h139_fixed_menu_capacity_fee_stress_portfolio_capacity_fee_stress.json`
- `artifacts/portfolio_baselines/20260328_173118_h139_fixed_menu_capacity_fee_stress_results.parquet`

Stress grid:
- notionals `50m, 100m, 250m, 500m, 1B VND`
- ADV caps `0.0%, 0.5%, 1.0%, 2.0%`
- round-trip costs `0.30%, 0.50%`
- holdout window `2019-2025`

Key results:
- with **no ADV cap**, all three rules remain strong
- at `0.50%` RT and no cap:
  - `k5_r10_eq`: `+154.31%` total, `+30.53%` relative
  - `k3_r5_eq`: `+118.56%` total, `+12.18%` relative
  - `k5_r5_eq`: `+102.18%` total, `+3.78%` relative

But with any tested ADV cap:
- positive relative-return scenarios: **0**
- best capped relative return stays around `-48%`
- capped scenarios remain almost entirely in cash (`97%+`)

Interpretation:
- the edge survives fee stress
- the edge does **not** survive realistic capacity constraints under the current construction
- deployability, not raw predictive content, is still the central bottleneck

## Conclusion
Session 48 tightened the picture:
- fixed simple long-only rules are better than ML-style config selection
- there is real uncapped economic value
- but deployability collapses as soon as explicit ADV constraints are imposed

## Next queue
1. Capacity-aware long-only construction
2. If that fails, hedged constructions
3. Only then revisit ML/RL overlays
