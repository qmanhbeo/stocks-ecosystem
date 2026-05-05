# Session 288 Log

**Date**: 2026-05-05
**Focus**: H407 `phase_lead` (simplified)

## Summary

- Activated 14th S272/S273 queue item.
- Added `analysis/h407_hilbert_phase_lead.py`.
- Tested lagged C16 × price cross-product as phase proxy.
- Verdict: **PASSED**. Phase lag adds +0.022 IC with 7/8 positive years.

## H407 - Phase Lead (Simplified)

**Hypothesis:**
C16-phase leading price-phase through lag interaction predicts.

**Command / code:**
```bash
python alpha-research-lab/analysis/h407_hilbert_phase_lead.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1)
- `data/features/xs_order_pressure_daily.parquet` (C16)

**Protocol:**
- No `2026+` rows, test years `2018-2025`
- Fixed lag definitions: C16_lag1 × price_lag1 cross-product
- Compare vs C16 level and both individual lags

| State | Forward IC | Positive Years |
|-------|-----------|----------------|
| C16 level | -0.02966 | 0/8 |
| **Phase lag (C16×price lag1)** | **+0.02221** | **7/8** |
| Corr diff | -0.00486 | - |
| C16 leads signal | -0.00455 | - |
| Price leads signal | +0.01790 | - |

**Saved artifact:**
`artifacts/run_summaries/...`

**Verdict: PASSED**

Phase lag (cross-product of lagged C16 and price) adds +0.022 IC with 7/8 positive 
years. This is a NEW feature class: cross-product of lags, different from the 
level derivatives (ROC, Haar, calendar - all failed) or simple lags.

NOT a signal-library promotion (IC < 0.05) but useful as C16 conditioner or 
portfolio context.

**Next**: H408 (Bright-Mind B-ideas or queue item 15)

Source anchor: F371