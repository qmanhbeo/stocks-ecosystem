# Session 217 Log

Date: 2026-05-03

## X75 - Benford's Law Liquidity Proxy

### Hypothesis
First-digit volume distribution deviation from Benford's Law → algorithmic/wash trading → predict returns.

### Results
| Year | n | Deviation | Chi2 | p-value |
|------|-----|------------|------|---------|
| 2015 | 65,178 | 0.0274 | 67.1 | 0.0000 |
| 2016 | 70,115 | 0.0100 | 9.7 | 0.2889 |
| 2017 | 77,001 | 0.0140 | 21.9 | 0.0052 |
| 2018 | 84,201 | 0.0192 | 42.7 | 0.0000 |
| 2019 | 88,203 | 0.0177 | 38.3 | 0.0000 |
| 2020 | 87,986 | 0.0139 | 27.2 | 0.0007 |
| 2021 | 91,600 | 0.0185 | 37.7 | 0.0000 |
| 2022 | 94,518 | 0.0246 | 64.6 | 0.0000 |

### IC Test
| Signal | IC | Positive Years |
|--------|-----|------------|
| Benford Deviation | +0.0023 | 4/8 |
| Benford Conformity | +0.0023 | 4/8 |

### Verdict
**FAILED** — IC +0.0023 << threshold 0.02, only 4/8 years positive.

The market DOES deviate from Benford's Law (confirmed chi2 tests), but this doesn't predict future returns.

### Promotion
Dead end. Benford deviation is a descriptive stat, not a predictive signal.

### Next
X72: Spectral regime shift (FFT on volume), or X68: Mandelbrot Hurst resonance.

---

## Previous
- Session 216: H366 order+ceiling — FAILED (IC +0.0639 vs +0.0767)
- Session 215: H367 order+gap — FAILED (IC +0.0574 vs +0.0767)
- Session 214: H365 C16 standalone — PASSED