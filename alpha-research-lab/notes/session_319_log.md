# Session 319 - 2026-05-08

## H440: news_novelty_first_repeat

**Hypothesis:** News novelty (first article in N days vs repeat coverage vs high-frequency saturation) predicts forward IC differently from raw article count. Among news-present stocks, NEW vs REPEAT vs high-frequency may show different patterns. Connected to H383 (active news + high C16 = confirmation).

**Command / code:**
`python3 analysis/h440_news_novelty_first_repeat.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - C16 order pressure
- `data/features/news/datasets/news_daily_features.parquet` - PhoBERT news features

**Saved artifact:**
`artifacts/run_summaries/20260508_160823_h440_news_novelty_first_repeat_research_branch.json`

**Results:**

| Metric | Value |
|--------|-------|
| all_rows avg IC | 0.1196 (8/8 pos years) |
| has_news avg IC | 0.0968 (8/8 pos years) |
| first_in_5d avg IC | 0.1234 (8/8 pos years, 23266 rows) |
| repeat_news avg IC | 0.0912 (8/8 pos years) |
| high_freq_news avg IC | 0.0958 (8/8 pos years) |
| single_article avg IC | 0.0999 (8/8 pos years) |
| **First vs Repeat lift** | **+0.0322** |
| first_strong_flow avg IC | 0.1613 (8/8 pos years) |
| repeat_strong_flow avg IC | 0.1396 (8/8 pos years) |
| high_freq_strong_flow avg IC | 0.1392 (8/8 pos years) |

**Decision:** PASSED

**Interpretation:**
- H440 PASSED clearly! First article in 5 days (IC=0.123) beats repeat coverage (IC=0.091) by +0.032 IC
- First-in-5d is stronger than generic has_news (0.097) and single-article (0.100) - it's the novelty that matters, not just presence
- Combined with strong C16 flow: first+flow IC=0.161, repeat+flow IC=0.140 - the novelty bonus persists
- High freq news and repeat news are both BELOW all-rows baseline - confirming that repeat/high-frequency is weaker
- This aligns with H383's active-news-strong-flow confirmation, but adds the key NOVELTY dimension
- The mechanism: first-in-a-while coverage means new information has arrived, which is more alphagenic than re-discussion of known topics

**Verdict: PASSED** - First news in 5d is a real novelty signal. Use as news-state conditioner or combined with C16 flow. Not a ranker replacement but useful as context/state feature.

**Next step:** Record as confirmed finding. Consider H441 follow-through: first-in-5d with C16 rank delta (H431) as combined novelty+momentum signal.