# Session 129: H480 extreme_negative_sentiment

**Date:** 2026-05-09
**Hypothesis:** EXTREME negative PhoBERT (bottom 5-10%) + next-day reversal? H383 passed positive; test EXTREME NEGATIVE for capitulation-reversal.

**Command:**
```bash
python analysis/h480_extreme_negative_sentiment.py
```

**Inputs:**
- S1 from xs_barrier_vol_1d_hose_full.parquet (default)
- PhoBERT sentiment from phobert_ticker_day_sentiment.parquet
- Test years: 2018-2025

**Saved artifact:** artifacts/run_summaries/20260509_230822_extreme_negative_sentiment_research_branch.json

**Results:**
| State | Avg IC | Lift vs baseline | Positive Years |
|-------|-------|----------------|---------------|
| ultra_negative (bottom 5%) | 0.1068 | **+0.0100** | 8/8 |
| moderate_negative (70-90%) | 0.0987 | +0.0019 | 8/8 |
| extreme_neg_high_share | 0.0975 | +0.0007 | 8/8 |
| extreme_negative (bottom 10%) | 0.0972 | +0.0004 | 8/8 |
| all_rows (baseline) | 0.0968 | - | 8/8 |
| extreme_sentiment_negative | 0.0904 | -0.0064 | 8/8 |

**Result:** Ultra-negative (bottom 5%) achieves +0.0100 IC lift vs baseline — passes the +0.01 threshold. Extreme negative at bottom 10% is marginal (+0.0004). Sentiment score-based extreme negative actually underperforms.

**Verdict: PASSED** — Extreme negative sentiment (bottom 5% prob_neg) predicts next-day returns with +0.01 IC lift. Captures capitulation-reversal mechanism at the most extreme level only.

**Finding:** F407 - ultra_negative (bottom 5% PhoBERT prob_neg) is a new signal state with +0.01 IC lift and 8/8 positive years. Mechanism: extreme panic/capitulation in sentiment predicts reversal.

**Source anchor:** F407

**Next action:** AV: breadth_threshold_finder (next in queue)