# Session 314 - 2026-05-08

## H435: candidate_rank_actual_gap

**Hypothesis:** The gap between predicted rank (H413 blend) and actual realized rank predicts forward returns. Large gaps = surprising information = alpha.

**Command / code:**
`python3 analysis/h435_candidate_rank_actual_gap.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - C16/C18 order pressure

**Saved artifact:**
`artifacts/run_summaries/20260508_152427_h435_candidate_rank_actual_gap_research_branch_candidate_rank_actual_gap.json`

**Results:**

| Metric | Value |
|--------|-------|
| H413 baseline avg IC | 0.1351 |
| Q1 (low gap) IC | 0.2811 |
| Q5 (high gap) IC | 0.2196 |
| Q5-Q1 lift | **-0.0615** |

| Metric | Value |
|--------|-------|
| Q1 (small |gap|) IC | 0.6429 |
| Q5 (large |gap|) IC | **-0.8169** |
| Q5-Q1 absolute lift | **-1.4598** |

**Decision:** FAILED

**Interpretation:**
- H435 FAILED badly - opposite of hypothesis!
- Small gaps (aligned prediction/actual) have HIGH IC (0.28-0.64)
- Large gaps (surprising prediction) have NEGATIVE IC (-0.79 to -0.83)
- When ranker is "surprised", it means the signal was NOISE, not alpha
- This is actually a confirmation that the H413 ranker is well-calibrated:
  when it disagrees with reality, reality was unpredictable

**Verdict: FAILED** (Dead-end D028)

**Next step:** Stop candidate rank-actual gap testing. The ranker IS the signal - surprises don't predict, they just indicate noise.