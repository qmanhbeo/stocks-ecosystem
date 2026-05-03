# Session 238: S238 eureka tests

**Date:** 2026-05-03
**Focus:** Test S238 bright-mind ideas

## Results

| Test | IC | Boost | Verdict |
|------|-----|-------|--------|
| vol_rank>0.8 | 0.091 | +38% | PASSED |
| A/D Q1 | 0.093 | +30% | PASSED |
| A/D Q5 | 0.050 | -36% | opposite |
| price tier low | 0.086 | +13% | WEAK |
| quarter_end | 0.066 | -15% | FAILED |
| quarter_start | 0.098 | +26% | PASSED |

## Findings

- **vol regime**: High vol AMPLIFIES C16 (+38%) - same as S237
- **market breadth**: A/D quintile 1-2 (most decline) works best - contrarian
- **price tier**: Weak (+13% for low price stocks)
- **quarter_end**: WORSE (-15%) - institutional pump is noise
- **quarter_start**: +26% - NEW FINDING!
- Reusable script: x240_wf_ic_test.py

## Key Discovery

- Quarter START (+26%) beats quarter END (-15%) - opposite of Western效应!
- A/D breadth is contrarian: more decline = stronger signal