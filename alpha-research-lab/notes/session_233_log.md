# Session 233: Triple Extension Tests

**Date:** 2026-05-03
**Focus:** Test new signals with Triple Storm

## Results

| Signal | Base IC | Triple IC | Boost | Verdict |
|--------|--------|----------|-------|--------|
| c4_oc_asym_5d | 0.019 | 0.053 | +180% | PASSED ✅ |
| c10_illiq | 0.026 | 0.009 | -63% | FAILED ❌ |
| c12_gap_absorb | 0.031 | 0.063 | +103% | PASSED ✅ |
| c13_compress | 0.031 | 0.126 | +307% | PASSED ✅ |
| s1_proba | 0.134 | 0.246 | +84% | PASSED ✅ |

## Findings

- **C13 (compress/blow-off) is the STRONGEST Triple amplifier**: +307% boost
- C12 (gap absorption) also strongly amplified: +103%
- C4 (OC asymmetry) strongly amplified: +180%
- C10 (Amihud illiquidity) FAILED - Triple doesn't help illiquidity signals
- Position signals continue to fail (confirmed mechanism boundary)

## Mechanism Update

Triple Storm amplifies ANOMALY/MICROSTRUCTURE signals:
- C4, C12, C13, C16, volume, reversal, skewness → ALL PASS
- Foreign, sector, C10 (illiq) → FAIL

C13's +307% is extraordinary - highest Triple amplifier found.