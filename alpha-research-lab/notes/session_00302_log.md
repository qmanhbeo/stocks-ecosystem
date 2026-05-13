# Session 302 Log

**Date**: 2026-05-06
**Focus**: H420-H424 experiments - extend confirmed additive pattern

## Summary

All variations of the confirmed additive pattern (H413: 0.1V+0.9S) FAIL to improve.

| Experiment | Result | Delta vs H413 |
|------------|--------|--------------|
| H420 Rank-Based | FAILED | -0.004 |
| H421 Time-Varying | MIXED | +0.002 |
| H422 Volatility | FAILED | -0.002 |
| H423 Sector | FAILED | -0.002 |
| H424 Dual-Additive | MIXED | +0.0001 |

**CONCLUSION: 0.1V+0.9S is the ROBUST STANDARD**

## H420 - Rank-Based Weight

- Top-heavy, Top-light both hurt
- Uniform is optimal

## H421 - Time-Varying

- Year-by-year optimization shows marginal variation
- But gains within noise

## H422 - Volatility-Weighted

- High vol stocks don't benefit from different weights
- Uniform works everywhere

## H423 - Sector-Adjusted

- 18 sectors, no improvement
- Raw additive is best

## H424 - Dual-Additive

- Combining 0.1V+0.9S with other weight ratios gives marginal
- Not practically better

## Key Files

- H420: `analysis/h420_rank_based_weight.py`
- H421: `analysis/h421_time_varying_weights.py`  
- H422: `analysis/h422_volatility_weighted_additive.py`
- H423: `analysis/h423_sector_adjusted_additive.py`
- H424: `analysis/h424_dual_additive_combo.py`
- Artifacts: `artifacts/run_summaries/`

## Notes

- Pattern holds across position, time, volatility, sector dimensions
- This is the most robust signal discovered in lab history
- First VERIFIED real signal (H417 hold-out proved not survivor bias)