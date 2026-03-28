# Session 49 Log

## Objective
Implement the retail-scale deployability plan after H138/H139:

1. add retail-sized liquidity controls to the deterministic portfolio engine
2. test whether the fixed-menu long-only rules survive explicit retail ADV floors and participation caps
3. if a viable region exists, run a tiny construction sweep inside it
4. if a viable winner exists, emit a live/paper-trade blotter for execution validation

## Implementation

### Engine changes
Updated `src/deterministic_portfolio.py` to:
- align tradability flags and `ADV20` to the **signal-date** row instead of the execution-date row
- add retail liquidity controls:
  - `min_adv20_value_vnd`
  - `max_position_vnd`
  - `max_names_if_liquidity_thin`
- keep `max_adv_participation` as the percentage-of-ADV position cap
- add optional blotter capture for per-ticker execution detail

This fixed a real timing bug:
- previous logic used `can_buy_next_open`, `can_sell_next_open`, and `ADV20` from row `T+1`
- the shared execution contract defines them from row `T`, because they govern the next open after `T`

### Search helpers and tests
Updated:
- `src/portfolio_construction_search.py`
- `tests/test_deterministic_portfolio.py`
- `tests/test_portfolio_construction_search.py`

Validation run:
- `python -m py_compile ...`
- `conda run -n stocks python -m pytest alpha-research-lab/tests/test_deterministic_portfolio.py alpha-research-lab/tests/test_portfolio_construction_search.py`

Result:
- `16 passed`

### New scripts
Added:
- `analysis/h140_retail_capacity_aware_validation.py`
- `analysis/h141_capacity_aware_construction_sweep.py`
- `analysis/h142_live_candidate_blotter.py`

## Rerun for consistency: H138 / H139

Because the liquidity-timing fix changed the economic meaning of tradability/capacity, H138 and H139 were rerun on the corrected engine.

### Corrected H138
Artifacts:
- `artifacts/run_summaries/20260328_175657_h138_fixed_menu_validation_portfolio_fixed_menu_validation.json`
- `artifacts/portfolio_baselines/20260328_175657_h138_fixed_menu_validation_results.parquet`
- `artifacts/portfolio_baselines/20260328_175657_h138_fixed_menu_validation_oos_daily.parquet`

Corrected holdout results (`2019-2025`):

| Rule | Total Return | Annualized | Relative vs VNINDEX | IR | Max DD | Positive Years |
|---|---:|---:|---:|---:|---:|---:|
| `k5_r5_eq` | +769.49% | +36.59% | +346.29% | 0.81 | -34.04% | 7/7 |
| `k3_r5_eq` | +748.57% | +36.11% | +335.55% | 0.70 | -34.96% | 6/7 |
| `k5_r10_eq` | +573.69% | +31.65% | +245.79% | 0.67 | -45.53% | 4/7 |

Interpretation:
- the fixed-rule long-only baseline is stronger than Session 48 suggested
- the one-day liquidity indexing bug materially affected the measured opportunity

### Corrected H139
Artifacts:
- `artifacts/run_summaries/20260328_175739_h139_fixed_menu_capacity_fee_stress_portfolio_capacity_fee_stress.json`
- `artifacts/portfolio_baselines/20260328_175739_h139_fixed_menu_capacity_fee_stress_results.parquet`

Corrected stress result:
- uncapped scenarios are very strong
- with any positive ADV cap in the tested `0.5% / 1.0% / 2.0%` grid, positive benchmark-relative scenario count remains `0`

Key corrected summary:
- best uncapped scenario: `k5_r5_eq`, `+769.49%` total, `+346.29%` relative, `3.90%` avg cash
- best relative return by cap:
  - `0.0%`: `+346.29%`
  - `0.5%`: `-47.52%`
  - `1.0%`: `-46.36%`
  - `2.0%`: `-43.24%`
- minimum avg cash by cap:
  - `0.5%`: `99.40%`
  - `1.0%`: `98.81%`
  - `2.0%`: `97.74%`

Interpretation:
- the qualitative capacity conclusion survives the correction unchanged
- the edge is still uncapped-economics-dependent

## H140 retail capacity-aware validation
Artifacts:
- `artifacts/run_summaries/20260328_175527_h140_retail_capacity_aware_validation_portfolio_retail_validation.json`
- `artifacts/portfolio_baselines/20260328_175527_h140_retail_capacity_aware_validation_results.parquet`
- `artifacts/portfolio_baselines/20260328_175527_h140_retail_capacity_aware_validation_viable.parquet`

Grid:
- notionals `20m, 50m, 100m, 200m VND`
- ADV caps `2%, 5%, 10%`
- ADV20 floors `250m, 500m, 1B, 2B, 5B VND`
- round-trip cost `0.30%, 0.50%`
- candidate menu = corrected H138 fixed rules

Retail viability gate:
- `relative_total_return > 0`
- `avg_cash_weight < 25%`
- `positive_years >= 5/7`

Result:
- viable scenarios: `0`
- best scenario:
  - `k5_r10_eq`
  - `20m` notional
  - `2%` ADV cap
  - `1B` ADV20 floor
  - `0.30%` RT
  - `+12.00%` total but `-42.51%` relative
  - `87.13%` average cash
  - `2/7` positive years

Interpretation:
- the current long-only library does not have a deployable retail region once explicit liquidity rules are imposed

## H141 capacity-aware construction sweep
Artifact:
- `artifacts/run_summaries/20260328_175539_h141_capacity_aware_construction_sweep_portfolio_capacity_aware_sweep.json`

Result:
- H140 returned zero viable liquidity settings
- H141 therefore stopped immediately with `liquidity_setting_count = 0`

Interpretation:
- there is no honest long-only retail region left to optimize inside

## H142 live candidate blotter
Artifacts:
- `artifacts/run_summaries/20260328_175636_h142_live_candidate_blotter_portfolio_live_candidate_blotter.json`
- `artifacts/portfolio_baselines/20260328_175636_h142_live_candidate_blotter_detail.parquet`
- `artifacts/portfolio_baselines/20260328_175636_h142_live_candidate_blotter_daily.parquet`

Because H141 had no winner, H142 was run manually on the top H140 scenario as a diagnostic only:
- `top_k=5`
- rebalance every `10` days
- equal weighting
- `20m` notional
- `2%` ADV cap
- `1B` ADV20 floor
- `0.30%` RT

Latest diagnostic snapshot (`2025-12-31` execution):
- held only `SHB`
- target notional about `19.70m VND`
- target usage about `1.87%` of ADV20
- cash still `12.06%`

Interpretation:
- blotter tooling is ready for future live/paper-trade validation
- the candidate itself is not worthy of promotion

## Conclusion
Session 49 resolved the retail-deployability branch:
- the deterministic engine is now consistent with the shared execution contract
- corrected H138/H139 show that uncapped long-only economics are stronger than previously logged
- but H140 shows there is still **no** viable retail-sized long-only region under explicit ADV floors and caps
- H141 therefore stops, and H142 is only diagnostic

## Next queue
1. Hedged / benchmark-relative constructions using the current signal library
2. If staying long-only, explicitly embrace a tiny-capital illiquidity-harvesting framing instead of pretending scalability
3. Keep RL deferred until a deterministic deployable baseline exists
