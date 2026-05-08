# Session 321 - 2026-05-08

## H442: ticker_rank_acceleration

**Hypothesis:** Rank acceleration (second derivative of rank) is the edge. Different from H407 (phase lag cross-product), H412 (additive levels), and H431 (rank delta first derivative). H431 passed with C16 rank delta (+0.0114 IC lift). Now test the SECOND derivative: rank acceleration = delta of delta.

**Command / code:**
`python3 analysis/h442_ticker_rank_acceleration.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - C16 order pressure

**Saved artifact:**
`artifacts/run_summaries/20260508_163124_h442_ticker_rank_acceleration_research_branch.json`

**Results:**

| Metric | Value |
|--------|-------|
| all_rows avg IC | 0.1196 (8/8 pos years) |
| c16_rank_high avg IC | 0.1576 (8/8 pos years) |
| c16_rank_low avg IC | 0.1425 (8/8 pos years) |
| rank_delta_pos avg IC | 0.1199 (8/8 pos years) |
| rank_delta_neg avg IC | 0.1110 (8/8 pos years) |
| rank_accel_up avg IC | 0.1200 (8/8 pos years, 295747 rows) |
| rank_accel_down avg IC | 0.1191 (8/8 pos years, 291119 rows) |
| rank_delta_pos_strong_flow avg IC | 0.1482 (8/8 pos years) |
| rank_accel_up_strong_flow avg IC | 0.1476 (8/8 pos years) |
| rank_accel_down_strong_flow avg IC | 0.1468 (8/8 pos years) |
| **Accel Up vs Down lift** | **+0.0009** |
| **Accel Up vs Delta Pos lift** | **+0.00006** |

**Decision:** FAILED

**Interpretation:**
- H442 FAILED badly - the second derivative of C16 rank does NOT predict forward IC
- Accel Up vs Down lift is only +0.0009, near zero and far below the threshold
- C16 rank LEVEL is the dominant signal (IC=0.158), far above acceleration or delta
- Both accel_up_strong_flow and accel_down_strong_flow are about equal (~0.147), showing acceleration direction doesn't matter
- The H431 rank delta worked BY BEING CLOSER TO THE RANK LEVEL EFFECT, not as an independent second-order signal
- The second derivative (acceleration) is pure noise - adding it on top of the first derivative makes things worse

**Verdict: FAILED** (Dead-end D033)

**Next step:** Stop rank acceleration testing. The first derivative (H431 rank delta) works because it's correlated with rank level, not as an independent signal. The second derivative is noise. Move to next queue item.