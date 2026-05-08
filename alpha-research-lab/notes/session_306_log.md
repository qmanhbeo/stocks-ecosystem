# Session 306 - 2026-05-08

## H427: volume_attention_budget

**Hypothesis:** Date-level volume concentration (Herfindahl) acts as a market regime indicator that affects ranker activation quality.

**Command / code:**
`python3 analysis/h427_volume_attention_budget.py`

**Inputs:**
- `data/order_stats/cafef/order_stats_daily.parquet` - volume data
- `data/features/xs_rl_signal_matrix.parquet` - S1 scores

**Saved artifact:**
`artifacts/run_summaries/h427_volume_attention_budget_summary.json`

**Results:**

| Concentration | Mean IC | Positive Years |
|---------------|---------|----------------|
| Q1_low (most distributed) | 0.1017 | 7/8 |
| Q2 | 0.1335 | 8/8 |
| Q3 (mid) | **0.1389** | **8/8** |
| Q4 | 0.1208 | 8/8 |
| Q5_high (most concentrated) | 0.1214 | 8/8 |

Baseline (all dates): mean IC = 0.1264, positive years = 8/8

**Best regime:** Q3 (mid-concentration)
**IC lift vs baseline:** +0.0125

**Result:**
The test found that date-level volume concentration does predict signal quality. There's a sweet spot - mid-concentration (Q3) outperforms both highly concentrated (Q5) and highly distributed (Q1) dates. The lift is +0.0125 IC with 8/8 positive years.

**Verdict: PASSED**

**Interpretation:**
- Volume concentration is a useful market regime indicator
- Mid-concentration regime (Q3) is the best for signal activation
- Both extreme concentration and extreme distribution hurt signal quality
- This is offline evidence - needs follow-up test against candidate-count policy

**Next step:** Test if volume concentration improves candidate-count policy routing (H380 follow-through)