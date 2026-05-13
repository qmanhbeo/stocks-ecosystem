# Session 138 - 2026-05-10

## Batch 17: sector_vol_regime (BU5)

**Hypothesis:** Sector-level vol expansion (>50% stocks hitting vol_expansion) as regime gate. D038 killed sector MOMENTUM; test sector VOL regime.

**Test:** sector_vol_exp × C23 vs C23 alone

**Results:**

| Metric | Value | Note |
|--------|-------|------|
| Baseline IC | 0.1303 | |
| Always C23 IC | 0.2176 | +0.0873 lift |
| Sector vol expansion IC | 0.1558 | regime filter |
| Sector × C23 IC | 0.2223 | +0.0919 lift |

**Key findings:**
- sector_c23 marginally beats always_c23 (+0.0046 IC)
- BUT sector_c23 is VERY sparse (2853 rows, 2/11 positive years)
- validation/confirmation have NaN due to insufficient data
- The sector vol regime is not robust - too few years positive
- Pattern similar to cofire_2: regime amplification from sector-level co-occurrence
- D038 killed sector momentum, sector VOL regime is barely better

**Verdict: MIXED** — marginal improvement but not robust across years

**Batch 17 status:**
- BU1: MIXED
- BU2: FAILED (D049)
- BU3: MIXED
- BU4: PASSED (confirms C23 alone)
- BU5: MIXED (sector vol regime marginal + not robust)

**Next:** BU6 (c26_without_vol_expansion_isolation)

---