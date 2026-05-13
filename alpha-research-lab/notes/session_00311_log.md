# Session 311 - 2026-05-08

## H432: volume_price_divergence

**Hypothesis:** Price vs volume response divergence defines edge. Large move on small volume = real force; large move on large volume = fade.

**Command / code:**
`python3 analysis/h432_volume_price_divergence.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - volume-z data

**Saved artifact:**
`artifacts/run_summaries/h432_volume_price_divergence_summary.json`

**Results:**

| Divergence State | Mean IC | Lift vs Baseline |
|------------------|---------|------------------|
| real_force (high ret + low vol) | +0.0921 | -0.0261 |
| fade (high ret + high vol) | +0.0892 | -0.0289 |
| hidden_support (low ret + high vol) | +0.0391 | -0.0791 |
| crowded (low ret + low vol) | +0.0477 | -0.0705 |

Baseline: mean IC +0.1181

Validation (2023-2025): real_force = +0.0955, fade = +0.0771

**Result:**
FAILED - all divergence states have negative lift vs baseline. The hypothesis that return vs volume-z divergence captures hidden pressure is NOT supported. Even the "real_force" state underperforms baseline.

**Verdict: FAILED**

**Interpretation:**
- Divergence states do not add predictive value
- Both "real force" and "fade" are WORSE than the baseline ranker
- The energy conservation hypothesis doesn't translate to alpha
- Do not use divergence as a conditioner

**Next step:** Continue to next queue item - sector_rotation_reversal (item #6)