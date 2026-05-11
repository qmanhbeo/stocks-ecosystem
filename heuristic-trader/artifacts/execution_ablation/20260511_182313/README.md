# Execution Ablation Results (CORRECTED)

Generated: 20260511_182313

## Variants Tested

| Variant | candidate_scan_multiplier | sizing_mode |
|---------|--------------------------|-------------|
| baseline | 3 | fixed_initial |
| depth_only | 20 | fixed_initial |
| sizing_only | 3 | dynamic_portfolio |
| depth_plus_sizing | 20 | dynamic_portfolio |

## Definitions

- **fixed_initial**: target = initial_capital / top_k
- **dynamic_portfolio**: target = current_portfolio_value / top_k

## Canonical Engine

This ablation uses the canonical `simulate_topk_constraint_compliant()` function from backtest.py with proper params.

## Strategies Tested

- blend_70_30_top5 (signal=blend, K=5, rebal=10d)
- s1_top5_rebal10 (signal=s1_proba, K=5, rebal=10d)

## Focus Years

- Failure bull: 2017, 2025
- Success contrast: 2021, 2022
- Secondary: 2019, 2024

## Decision Criteria Results

See decision_criteria in summary.json for detailed results.

## Next Steps

This is an ablation, NOT a winner selection.
- If depth_only helps: candidate scan cap was a real bottleneck
- If sizing_only helps: fixed sizing was a real bottleneck  
- If both help: execution plumbing is fixable
- If neither helps: cash drag is deeper than scan/sizing

## Artifacts

- strategy_variant_year_metrics.csv
- strategy_variant_summary.csv
- cash_exposure_by_year.csv
- focus_year_comparison.csv
- summary.json
