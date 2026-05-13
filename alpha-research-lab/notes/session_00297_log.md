# Session 297 Log

**Date**: 2026-05-05
**Focus**: H416 `market_state_gated`

## Summary

- Activated Bright-Mind B51 idea (Market-State Gated).
- Added `analysis/h416_market_state_gated.py`.
- Tested Vol+S1 additive in VNI-up vs VNI-down markets.
- Verdict: **PASSED**. Works in BOTH states (+0.016 to +0.018 lift).

## H416 - Market State Gated

**Hypothesis:**
Different weights in different market states.

**Command / code:**
```bash
python alpha-research-lab/analysis/h416_market_state_gated.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1)
- `data/features/xs_order_pressure_daily.parquet` (Volume)
- `data/stock/gia_lich_su_VNINDEX_1D.parquet` (Market)

**Protocol:**
- Split by VNI-up vs VNI-down days

| Market | S1 Alone | 0.1V+0.9S | Lift |
|--------|----------|-------------|------|
| VNI up | +0.116 | +0.132 | +0.016 |
| VNI down | +0.120 | +0.138 | +0.018 |
| All | +0.118 | +0.135 | +0.017 |

**Verdict: PASSED**

- Works in BOTH market states
- Slightly better in VNI down (contrarian)
- Confirms ROBUST pattern

**Next**: Portfolio test or add new signals.

Source anchor: F380