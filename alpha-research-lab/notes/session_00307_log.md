# Session 307 - 2026-05-08

## H428: ranker_error_taxonomy (S1 Rank Degradation Test)

**Hypothesis:** High S1-ranked tickers predictably degrade in next-day ranker quality (S1 mean reversion).

**Command / code:**
`python3 analysis/h428_ranker_error_taxonomy.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - volume data

**Saved artifact:**
`artifacts/run_summaries/h428_ranker_error_taxonomy_v5_summary.json`

**Results:**

| S1 Quintile | Mean Next-Day IC | Lift vs Baseline |
|-------------|------------------|------------------|
| Q1_bot (low) | +0.1471 | +0.0118 |
| Q2 | +0.1184 | -0.0169 |
| Q3 | +0.1123 | **-0.0230** |
| Q4 | +0.1196 | -0.0157 |
| Q5_top (high) | +0.1616 | **+0.0263** |

Baseline (all dates): mean IC = +0.1353, 8/8 positive years

Validation (2023-2025): Top-S1 = +0.1592, Baseline = +0.1318, **Degradation = +0.0274** (NOT degraded!)

**Result:**
The hypothesis was WRONG. Top S1 tickers DO NOT decay - they actually IMPORVE in next-day IC (+0.0263 lift). This is the opposite of the hypothesized mean-reversion. Q3 (mid-S1) is the weakest pocket, not the top.

**Verdict: FAILED**

**Interpretation:**
- The ranker does NOT systematically mispredict top-S1 tickers
- High-quality tickers remain high-quality next day (momentum, not mean-reversion)
- Q3 is the weakest pocket - neither top nor bottom
- Do not use S1 rank as an error-state indicator

**Next step:** Proceed to next queue item - signal_half_life_router (item #2)