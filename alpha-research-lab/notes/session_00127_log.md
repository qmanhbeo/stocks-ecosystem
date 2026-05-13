# Session 127: H441 replacement_quality_delta

**Date:** 2026-05-09
**Hypothesis:** Quality CHANGE (delta S1) predicts forward IC, not quality LEVEL. H437 tested quality LEVEL (entering IC=0.066 weakest) - this tests CHANGE.

**Command:**
```bash
python analysis/h441_replacement_quality_delta.py
```

**Inputs:**
- S1 from xs_barrier_vol_1d_hose_full.parquet (default)
- Test years: 2018-2025
- lookback_days: 5

**Saved artifact:** artifacts/run_summaries/20260509_195148_replacement_quality_delta_quality_change.json

**Results:**
| State | Avg IC | Lift vs baseline | Positive Years |
|-------|-------|----------------|---------------|
| strong_positive_delta | 0.1206 | +0.0012 | 8/8 |
| all_rows (baseline) | 0.1194 | - | 8/8 |
| positive_delta | 0.1169 | -0.0025 | 8/8 |
| negative_delta | 0.0837 | -0.0357 | 8/8 |
| strong_negative_delta | 0.0784 | -0.0410 | 8/8 |

**Result:** Quality change shows weak evidence only for strong positive delta (>0.05). Main positive delta state underperforms baseline. Decline states significantly underperform.

**Verdict: MIXED** - The signal is too weak to promote. Quality change prediction is inconsistent across thresholds.

**Finding:** Quality delta is a marginal signal at best (strong_positive_delta +0.0012 lift), not a reliable predictor. H437 finding (quality LEVEL) already showed entering ticker quality is weakest - quality CHANGE doesn't rescue it.

**Source anchor:** F405, D027