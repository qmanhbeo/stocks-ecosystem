# Session 50 Log

## Objective
Run the next long-only friction-extraction wave after H140-H142:

1. H143: test liquidity-aware scoring
2. H144: test multi-day entry slicing
3. H145: test volume-confirmed / liquidity-opening entry gates
4. H146: test variable portfolio breadth

Hard rule remained unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions

## Implementation

### Engine and helper changes
Updated `src/deterministic_portfolio.py` to support the new construction experiments:
- expanded `load_price_panel()` to carry `high`, `low`, `traded_value_vnd`, `adv5_value`, and `clv`
- added optional `entry_allowed_matrix` so entry gates can block **new buys** without forcing liquidation of existing holdings
- added optional `entry_slice_days` with pending buy plans
- added optional `daily_buy_adv_participation` so sliced runs treat ADV caps as daily buy limits instead of overall position caps
- added optional `min_deployable_weight` for variable-breadth selection
- extended summary metrics with pending-entry stats

Added helper module:
- `src/portfolio_friction_features.py`
  - build merged friction feature frame
  - derive tradability-aware score variants
  - pivot entry-gate booleans into simulation matrices

### New analysis scripts
Added:
- `analysis/h143_liquidity_aware_scoring.py`
- `analysis/h144_entry_slicing_simulation.py`
- `analysis/h145_volume_confirmed_entry_filter.py`
- `analysis/h146_variable_breadth_portfolio.py`

### Tests
Added/updated:
- `tests/test_deterministic_portfolio.py`
- `tests/test_portfolio_friction_features.py`

Validation:
- `python -m py_compile ...`
- `conda run -n stocks python -m pytest alpha-research-lab/tests/test_deterministic_portfolio.py alpha-research-lab/tests/test_portfolio_friction_features.py`

Result:
- `13 passed`

## Experiment results

### H143 liquidity-aware scoring
Artifacts:
- `artifacts/run_summaries/20260328_195908_h143_liquidity_aware_scoring_portfolio_liquidity_aware_scoring.json`
- `artifacts/portfolio_baselines/20260328_195908_h143_liquidity_aware_scoring_results.parquet`
- `artifacts/portfolio_baselines/20260328_195908_h143_liquidity_aware_scoring_viable.parquet`
- `artifacts/portfolio_baselines/20260328_195908_h143_liquidity_aware_scoring_best_by_variant.parquet`

Best scenario:
- `liq_blend_50_50`
- `k3_r5_eq`
- `20m`
- `10%` ADV cap
- `250m` ADV20 floor
- `+32.46%` total
- `-32.01%` relative vs VNINDEX
- `25.11%` cash
- `4/7` positive years

Verdict:
- no retail-viable scenario
- soft tradability-aware scoring helps, but does not solve deployability

### H144 entry slicing simulation
Artifacts:
- `artifacts/run_summaries/20260328_200058_h144_entry_slicing_simulation_portfolio_entry_slicing_simulation.json`
- `artifacts/portfolio_baselines/20260328_200058_h144_entry_slicing_simulation_results.parquet`
- `artifacts/portfolio_baselines/20260328_200058_h144_entry_slicing_simulation_unsliced.parquet`
- `artifacts/portfolio_baselines/20260328_200058_h144_entry_slicing_simulation_sliced.parquet`

Best scenario:
- `liq_x_tradability_rank`
- unsliced baseline
- `20m`
- `5%` ADV cap
- `250m` ADV20 floor
- `+28.57%` total
- `-34.01%` relative

Best sliced scenarios:
- small cash-weight improvement only
- no benchmark-relative improvement
- many partial / expired pending plans

Verdict:
- no retail-viable scenario
- more realistic entry mechanics do not rescue the economics

### H145 volume-confirmed entry filter
Artifacts:
- `artifacts/run_summaries/20260328_200355_h145_volume_confirmed_entry_filter_portfolio_volume_confirmed_entry_filter.json`
- `artifacts/portfolio_baselines/20260328_200355_h145_volume_confirmed_entry_filter_results.parquet`
- `artifacts/portfolio_baselines/20260328_200355_h145_volume_confirmed_entry_filter_viable.parquet`

Best scenario:
- score variant = `liq_blend_50_50`
- gate = `adv20_125_clv50`
- `k3_r5_eq` or `k5_r5_eq`
- `20m`
- `5%` ADV cap
- `1B` ADV20 floor
- `+93.88%` total
- `-0.49%` relative
- `33.52%` cash
- `4/7` positive years

Verdict:
- no retail-viable scenario
- this is the closest the retail long-only branch has come so far
- liquidity-opening state is the strongest lever discovered in this wave

### H146 variable-breadth portfolio
Artifacts:
- `artifacts/run_summaries/20260328_202443_h146_variable_breadth_portfolio_portfolio_variable_breadth.json`
- `artifacts/portfolio_baselines/20260328_202443_h146_variable_breadth_portfolio_results.parquet`
- `artifacts/portfolio_baselines/20260328_202443_h146_variable_breadth_portfolio_viable.parquet`

Best scenario:
- score variant = `liq_blend_50_50`
- gate = `adv20_125_clv50`
- `max_k=3` or `5`
- `20m`
- `5%` ADV cap
- `1B` ADV20 floor
- `+93.88%` total
- `-0.49%` relative
- `33.52%` cash
- average holdings `0.74`

Verdict:
- no retail-viable scenario
- variable breadth does not improve on the H145 near-miss

## Runtime note
The first H146 run completed the expensive simulation pass but crashed in result printing because
`max_names_if_liquidity_thin` could be `NaN` in the output table.

Fix applied:
- handle `NaN` safely in the printer
- reduce the default thin-name-cap grid from `0,1,2,3` to `0,2`

Implication:
- H146 is still valid, but its default grid is materially heavier than the other Session 50 runs
- future sessions should avoid re-opening broad H146-style sweeps unless there is a stronger reason

## Conclusion
Session 50 resolved the friction-extraction wave:
- H143 FAIL
- H144 FAIL
- H145 NEAR-MISS
- H146 FAIL

The important update is not “construction is solved.” It is:
- liquidity-opening entry gates matter
- but current long-only construction still does not clear the retail viability bar
- fixed `top_k` is not the main remaining bottleneck

## Next queue
1. New long-only alpha search conditioned on tradability / liquidity-opening states
2. If staying in construction land, only do local refinement around the H145 near-miss
3. Keep RL deferred until a deterministic long-only retail-positive baseline exists
