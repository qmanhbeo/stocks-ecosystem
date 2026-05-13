# Session 317 - 2026-05-08

## H438: news_consensus_divergence

**Hypothesis:** When news sources agree (consensus) vs disagree (divergence), disagreement may indicate hidden information and alpha. Use PhoBERT source type and sentiment to define consensus vs divergence. Connected to H382 which showed source type matters but consensus vs disagreement not tested.

**Command / code:**
`python3 analysis/h438_news_consensus_divergence.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - C16 order pressure
- `data/features/news/datasets/news_daily_features.parquet` - PhoBERT news features

**Saved artifact:**
`artifacts/run_summaries/20260508_155930_h438_news_consensus_divergence_research_branch.json`

**Results:**

| Metric | Value |
|--------|-------|
| all_rows avg IC | 0.1196 (8/8 pos years) |
| consensus_news IC | 0.1020 (8/8 pos years) |
| divergence_news IC | 0.0934 (8/8 pos years) |
| consensus_positive IC | 0.1057 (8/8 pos years) |
| divergence_positive IC | 0.0954 (8/8 pos years) |
| consensus_negative IC | 0.1058 (3/3 pos years) |
| divergence_negative IC | 0.0977 (5/5 pos years) |
| Diverge vs Consensus lift | **-0.0086** |

**Decision:** MIXED

**Interpretation:**
- H438 MIXED - consensus beats divergence, opposite of hypothesis
- Consensus (all same source type) IC=0.102 beats divergence IC=0.093
- Both consensus and divergence are positive (not noise)
- But neither is strong enough to beat all-rows (IC=0.120)
- The ~0.0086 lift is small and neither state beats the baseline
- This aligns with H382: source TYPE matters (official is strong), but CONSENSUS vs DIVERGENCE does not create alpha
- The hidden information hypothesis is not supported; if anything, consensus is slightly better

**Verdict: MIXED** (Neither PASS nor FAIL - small effect, both positive but below baseline)

**Next step:** This aligns with H382 finding that source type matters. Stop consensus vs divergence testing. Neither consensus nor divergence beats the all-rows baseline. Move to next queue item.