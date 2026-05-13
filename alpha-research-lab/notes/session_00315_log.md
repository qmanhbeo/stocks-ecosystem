# Session 315 - 2026-05-08

## H436: signal_ignorance_weight

**Hypothesis:** True edge is knowing WHEN to ignore S1/C16, not how to weight them. Train a classifier on regime features (market breadth, C16 volatility, news state, calendar) to predict signal degradation, use as cash/veto signal.

**Command / code:**
`python3 analysis/h436_signal_ignorance_weight.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - C16 order pressure
- `data/features/news/datasets/news_daily_features.parquet` - PhoBERT news features

**Saved artifact:**
`artifacts/run_summaries/20260508_155246_h436_signal_ignorance_weight_research_branch.json`

**Results:**

| Metric | Value |
|--------|-------|
| all_rows avg IC | 0.1196 |
| always_buy_top10 avg IC | 0.0859 (8/8 pos years) |
| always_buy_in_degrade avg IC | 0.1001 (8/8 pos years) |
| ignore_degrade_state avg IC | 0.0533 (8/8 pos years) |
| Degrade lift (ignore vs always) | **-0.0469** |

**Decision:** FAILED

**Interpretation:**
- H436 FAILED badly - opposite of hypothesis!
- Signal does NOT degrade when composite regimes fire
- Top-10 S1 buyers in degrade-state still have IC=0.10 (STRONGER than all-rows)
- Ignoring signal drops to IC=0.053 (WORSE than always-buy top10)
- The composite degrade indicators are NOT capturing true signal degradation
- This means S1/C16 are robust across these regime features - they don't need gating

**Verdict: FAILED** (Dead-end D030)

**Next step:** Stop signal ignorance testing. The S1/C16 signals are robust across regime conditions - composite ignorance signals do not add value. Move to next queue item from live_state.md.