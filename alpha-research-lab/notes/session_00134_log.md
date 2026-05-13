# Session 134 Log — Batch 17 BU1 market_wide_vol_regime (2026-05-09)

## Objective

Run batch 17 experiments, starting with BU1: market_wide_vol_regime.
The hypothesis: c16_low×C23 works at ticker level; market-level vol expansion
may be the systemic analog.

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one research script:
- `analysis/h497_market_wide_vol_regime.py`

### BU1 - market_wide_vol_regime (H497)

**Hypothesis:**
c16_low×C23 (IC 0.2838 from batch 16) works at ticker level. Test market-level
vol expansion as systemic analog. When market-wide vol is in top 20%, C23 should
amplify. Compare market_vol_exp×C23 vs C23 alone vs random.

**Command / code:**
`python analysis/h497_market_wide_vol_regime.py`

**Inputs:**
- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV for Amihud illiquidity

**Saved artifact:**
`artifacts/run_summaries/20260509_235413_market_wide_vol_regime_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| panel_rows | 809,019 | |
| baseline (all_rows) IC | 0.1298 | |
| c23_ticker_level IC | 0.2616 | +0.1318 lift, 11/11 years |
| c23_market_vol_exp IC | 0.2006 | +0.0708 lift, 11/11 years |
| c23_both_vol_exp IC | 0.2575 | +0.1277 lift, 10/11 years |
| ticker_vol_exp_alone IC | 0.1753 | +0.0455 lift |
| market_vol_exp_alone IC | 0.1271 | +0.003 (noise) |

**Result:**
Ticker-level vol expansion (IC 0.2616) beats market-level vol expansion (IC 0.2006)
by +0.061. Market-wide vol expansion DOES work as a signal conditioner (+0.07 lift)
but is significantly weaker than ticker-level. The hypothesis that market-level vol
would be analogous to ticker-level is NOT supported.

**Verdict: MIXED**

---

## Branch decision

BU1 is MIXED:
- Market-wide vol expansion provides +0.07 IC lift vs baseline — real but weaker
- Ticker-level vol expansion is STRONGER (+0.132 vs +0.07)
- Combining both (c23_both_vol_exp) hurts vs ticker-level alone (too sparse: 6590 rows)
- Market vol expansion alone (without illiq) is noise

Key finding: the regime amplification mechanism works at the INDIVIDUAL STOCK level,
not at the market level. Do not use market-wide vol as a regime conditioner.

Next in batch 17:
- BU2: c17_standalone (C17 raw vs C16 blended)
- BU3: multi_day_c23_accumulation
- BU4: cross_signal_day_complementarity
- BU5: sector_vol_regime
- BU6: c26_without_vol_expansion_isolation
- BU7: foreign_flow_regime_as_conditioner
- BU8: earnings_quality_regime_interaction