# Session 285 Log

**Date**: 2026-05-05
**Focus**: H404 `haar_cascade_pressure`

## Summary

- Activated the 11th S272/S273 eureka queue item.
- Added `analysis/h404_haar_cascade_pressure.py`.
- Tested C16 wavelet energy at scales 1/2/4/8 days vs plain C16.
- Verdict: **FAILED**. Haar wavelets add no signal beyond C16.

## H404 - Haar Cascade Pressure

**Hypothesis:**
Hidden demand may become tradable when C16 energy migrates from short to medium 
horizons. Wavelet scale-jumps predict beyond plain C16 level.

**Command / code:**
```bash
python alpha-research-lab/analysis/h404_haar_cascade_pressure.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1 panel)
- `data/features/xs_order_pressure_daily.parquet` (C16)

**Protocol:**
- No `2026+` rows. Test years `2018-2025`.
- Panel rows with C16 and order-stats coverage.
- Fixed Haar wavelet definitions at scales 1/2/4/8 days.

| Scale | Overall IC | Positive Years |
|-------|----------|---------------|
| C16 level | -0.02953 | 0/8 |
| Haar 1d | NaN | - |
| Haar 2d | -0.00447 | 3/8 |
| Haar 4d | -0.00100 | - |
| Haar 8d | -0.00091 | - |
| Haar jump 2->4 | +0.00491 | - |
| Haar energy sum | +0.00501 | - |
| C16 accel | -0.01722 | - |

**Saved artifact:**
`artifacts/run_summaries/20260505_231229_haar_cascade_pressure_research_branch.json`

**Result:**
- Panel rows: 645,012
- Best Haar vs C16 IC lift: N/A (1d was constant per-ticker)
- Haar 2d positive years: 3/8 (poor)

**Verdict: FAILED**

Haar wavelets add no signal beyond C16. Best scale (Haar jump 2->4) was 
only +0.00491, and with 3/8 positive years for 2d, consistency is poor.
This confirms prior C16 acceleration failures - scale derivatives 
are not the edge.

**Next item**: H405 queue item 12
Source anchor: D019