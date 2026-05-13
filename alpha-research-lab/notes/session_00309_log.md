# Session 309 - 2026-05-08

## H430: candidate_temperature_entropy

**Hypothesis:** Candidate panel score entropy predicts forward returns. When scores cluster tight (low entropy), forward degrades; dispersed (high entropy) means hidden alpha.

**Command / code:**
`python3 analysis/h430_candidate_temperature_entropy.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - volume data
- `data/features/activation_state_daily.parquet` - full_top10_score_entropy

**Saved artifact:**
`artifacts/run_summaries/h430_candidate_temperature_entropy_summary.json`

**Results:**

| Entropy Quintile | Mean IC | Lift vs Baseline |
|------------------|---------|------------------|
| Q1_low | +0.1291 | -0.0062 |
| Q2 | +0.1458 | **+0.0105** |
| Q3 | +0.1305 | -0.0048 |
| Q4 | +0.1422 | +0.0068 |
| Q5_high | +0.1324 | -0.0029 |

Baseline (all dates): mean IC +0.1354, 8/8 positive years

Validation (2023-2025): High entropy = +0.1276, Low entropy = +0.1133, **Lift = +0.0143**

**Result:**
MIXED - no simple high-entropy = good pattern. Q2 (second quintile) is best in dev, but Q5_high is actually negative. Validation shows positive lift for high-entropy, but pattern is inconsistent across development years. Not a clean monotonic relationship.

**Verdict: MIXED**

**Interpretation:**
- Entropy is NOT a simple monotonic predictor
- Q2 (mid-low entropy) has best dev performance, not extremes
- Validation favors high-entropy, but dev favors mid-low
- Cannot recommend as standalone predictor without more validation

**Next step:** Continue to next queue item - cross_sectional_rank_delta (item #4)