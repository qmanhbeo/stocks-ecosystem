# Session 320 - 2026-05-08

## H441: cross_ticker_correlation_shock

**Hypothesis:** When market-level cross-sectional correlation drops (stocks less aligned), individual stock IC may change. Compute date-level cross-sectional correlation between S1 scores and returns. Flag high vs low corr dates. Test whether S1 IC differs by date-level correlation regime.

**Command / code:**
`python3 analysis/h441_cross_ticker_correlation_shock.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - C16 order pressure
- `data/features/news/datasets/news_daily_features.parquet` - PhoBERT news features

**Saved artifact:**
`artifacts/run_summaries/20260508_162600_h441_cross_ticker_correlation_shock_research_branch.json`

**Results:**

| Metric | Value |
|--------|-------|
| all_rows avg IC | 0.1196 (8/8 pos years) |
| high_corr_date avg IC | 0.1315 (8/8 pos years, 130431 rows) |
| low_corr_date avg IC | 0.1282 (8/8 pos years, 130373 rows) |
| **High vs Low lift** | **+0.0033** |
| high_corr_strong_flow avg IC | 0.1667 (8/8 pos years) |
| low_corr_strong_flow avg IC | 0.1437 (8/8 pos years) |
| high_corr_first_news avg IC | 0.1298 (6/6 pos years) |
| low_corr_first_news avg IC | 0.1534 (5/5 pos years) |

**Decision:** FAILED

**Interpretation:**
- H441 FAILED on the primary shock question: high vs low corr dates lift is only +0.0033, below the 0.01 threshold
- Secondary finding: strong C16 flow works BETTER in high-corr dates (IC=0.167 vs 0.144, +0.023 lift)
- Interesting contrast: first-in-5d news works BETTER in LOW-corr dates (IC=0.153 vs 0.130, +0.023)
- The correlation shock mechanism (decorrelation = alpha) is weak at the date level
- But the cross-regime combination effects are interesting: C16 flow prefers high-corr, first-news prefers low-corr

**Verdict: FAILED** - Primary shock signal too weak (+0.003 lift). Secondary cross-regime finding interesting but not strong enough to promote. Dead-end D032.

**Next step:** Stop correlation shock testing. The effect is too small for the primary question. Consider H442: rank acceleration (second derivative of rank) as a follow-through from H431 (rank delta first derivative).