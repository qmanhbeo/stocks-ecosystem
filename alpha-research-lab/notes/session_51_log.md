# Session 51 Log

## Objective
Run the follow-up wave after Session 50, in order:

1. H147: audit the H145 near-miss for opportunity density
2. H148: try only local gate refinement around that near-miss
3. H149: test whether a soft activation score beats the hard gate
4. H150: decompose the current signal library inside tradable states

Hard rule remained unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions

## Implementation

### Helper changes
Updated `src/portfolio_friction_features.py`:
- added `make_gate_label()`
- added `add_liquidity_opening_gate_columns()`
- added `add_soft_activation_score_variants()`

Updated tests:
- `tests/test_portfolio_friction_features.py`

Validation before running the new scripts:
- `python -m py_compile ...`
- `conda run -n stocks python -m pytest alpha-research-lab/tests/test_portfolio_friction_features.py alpha-research-lab/tests/test_deterministic_portfolio.py alpha-research-lab/tests/test_portfolio_construction_search.py`

Result:
- `23 passed`

### New analysis scripts
Added:
- `analysis/h147_liquidity_state_opportunity_audit.py`
- `analysis/h148_local_liquidity_gate_refinement.py`
- `analysis/h149_soft_activation_score.py`
- `analysis/h150_conditional_alpha_decomposition.py`

### Runtime cleanup
Updated `analysis/h150_conditional_alpha_decomposition.py` after the first run to skip constant-input Spearman cases before correlation, so the saved artifact and terminal output are clean and reproducible.

## Experiment results

### H147 liquidity-state opportunity audit
Artifacts:
- `artifacts/run_summaries/20260328_204256_h147_liquidity_state_opportunity_audit_portfolio_liquidity_state_opportunity_audit.json`
- `artifacts/portfolio_baselines/20260328_204256_h147_liquidity_state_opportunity_audit_results.parquet`
- `artifacts/portfolio_baselines/20260328_204256_h147_liquidity_state_opportunity_audit_daily.parquet`

Best audited state:
- score variant = `liq_blend_50_50`
- gate = `adv20_125_clv45` or `adv20_125_clv50`
- construction = `k3_r5_eq`
- `20m`
- `5%` ADV cap
- `1B` ADV20 floor
- `+93.88%` total
- `-0.49%` relative vs VNINDEX
- `33.52%` cash
- `4/7` positive years

Critical audit facts:
- raw zero-candidate days are about `97%`
- `2019` and `2020` are fully in cash in the best scenario
- the good state is sparse, not broad

Verdict:
- the H145 near-miss is mainly an opportunity-density problem
- threshold polishing alone is unlikely to solve deployability

### H148 local liquidity-gate refinement
Artifacts:
- `artifacts/run_summaries/20260328_204946_h148_local_liquidity_gate_refinement_portfolio_local_liquidity_gate_refinement.json`
- `artifacts/portfolio_baselines/20260328_204946_h148_local_liquidity_gate_refinement_results.parquet`
- `artifacts/portfolio_baselines/20260328_204946_h148_local_liquidity_gate_refinement_top.parquet`
- `artifacts/portfolio_baselines/20260328_204946_h148_local_liquidity_gate_refinement_best_by_gate.parquet`

Best scenario:
- still the old H145 near-miss
- `adv20_125_clv45` or `adv20_125_clv50`
- `k3_r5_eq`
- `20m`
- `5%` ADV cap
- `1B` floor
- `+93.88%` total
- `-0.49%` relative
- `33.52%` cash
- `4/7` positive years

Verdict:
- no retail-viable scenario
- the local-refinement branch is exhausted
- `H142` blotter was not run because no H148 winner cleared the retail gate

### H149 soft activation score
Artifacts:
- `artifacts/run_summaries/20260328_205046_h149_soft_activation_score_portfolio_soft_activation_score.json`
- `artifacts/portfolio_baselines/20260328_205046_h149_soft_activation_score_results.parquet`
- `artifacts/portfolio_baselines/20260328_205046_h149_soft_activation_score_top.parquet`
- `artifacts/portfolio_baselines/20260328_205046_h149_soft_activation_score_best_by_variant.parquet`

Best scenario:
- `soft_85_15`
- `k3_r5_eq`
- `50m`
- `5%` ADV cap
- `500m` floor
- `-0.57%` total
- `-48.97%` relative
- `36.65%` cash
- `3/7` positive years

Verdict:
- hard fail
- softer activation increases activity and turnover but makes the economics materially worse
- the H145 gate is not failing because it is too binary

### H150 conditional alpha decomposition
Artifacts:
- `artifacts/run_summaries/20260328_210047_h150_conditional_alpha_decomposition_portfolio_conditional_alpha_decomposition.json`
- `artifacts/portfolio_baselines/20260328_210047_h150_conditional_alpha_decomposition_results.parquet`
- `artifacts/portfolio_baselines/20260328_210047_h150_conditional_alpha_decomposition_uplift.parquet`
- `artifacts/portfolio_baselines/20260328_210047_h150_conditional_alpha_decomposition_daily_ic.parquet`

Best unrestricted signal:
- `s1_proba`
- avg daily IC `+0.1491`
- `11/11` positive years

Best liquidity-opening state:
- `s1_proba` under `tv110`
- avg daily IC `+0.1510`
- `11/11` positive years

Strongest conditional uplifts vs unrestricted:
- `c7_ceiling_count_5d` under `tv125_clv50`: `+0.0592`
- `c12_gap_absorb_3` under `tv125_clv50`: `+0.0496`
- `c13_compress_blowoff_2` under `tv110`: `+0.0464`
- `c10_illiq_level_rank` under `tv110`: `+0.0343`
- `c8_vol_zscore_5d` also improves materially in liquidity-opening states

Verdict:
- the current library has a tradability-conditioned sub-core
- current construction still does not monetize it under the retail gate
- the next honest step is a narrow tradability-conditioned composite, not another generic construction sweep

## Conclusion
Session 51 resolved the follow-up wave:
- H147 AUDIT
- H148 FAIL
- H149 FAIL
- H150 PASS

The critical update is:
- construction-only tuning around H145 is mostly exhausted
- the library still contains useful tradability-conditioned components
- the next branch should narrow onto that conditioned sub-core instead of softening or re-sweeping construction

## Next queue
1. H151: narrow tradability-conditioned composite centered on `s1_proba`, `c7`, `c12`, `c13`, `c10`, with `c8` as a secondary candidate
2. H152: new long-only alpha hypotheses defined conditionally on liquidity-opening / tradability states
3. Keep H142 blotter and any RL work deferred until a benchmark-positive retail candidate exists
