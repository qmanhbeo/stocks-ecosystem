# Session 232: Triple Storm Extension Tests

Date: 2026-05-03
Focus: Test Triple Storm on other signal families

## Hypothesis
- **Claim**: Triple Storm conditions amplify ANY signal
- **Mechanism**: liquid + down + divergence filters

## Results

| Signal | Baseline IC | +Triple IC | Boost | Result |
|--------|-----------|-------------|-------|--------|
| C16 (order pressure) | +0.078 | +0.158 | +104% | PASSED |
| S1 + Triple | +0.078 | +0.145 | +90% | PASSED |
| Dual (liquid+down) | +0.078 | +0.108 | +39% | NEUTRAL |
| Quadruple (+C4) | +0.158 | +0.172 | +9% | MIXED |
| Foreign flow | -0.013 | -0.010 | - | FAILED |
| Volume zscore | +0.043 | +0.059 | +38% | PASSED |
| Reversal | +0.027 | +0.042 | +60% | PASSED |
| Sector rotation | -0.035 | -0.113 | - | FAILED |
| Return skewness | -0.001 | +0.009 | - | PASSED |

## Key Findings

1. **Triple amplifies ANOMALY/MICROSTRUCTURE signals** (order, volume, reversal, skewness)
2. Triple does NOT amplify POSITION signals (foreign, sector) — still negative
3. Dual (liquid+down) = 90% of triple with half the reduction

## Scripts
- ad-hoc inline Python tests (no reusable script yet)

## Next Steps
- Queue exhausted for now
- Need new signal sources
- Write reusable triple_test.py script