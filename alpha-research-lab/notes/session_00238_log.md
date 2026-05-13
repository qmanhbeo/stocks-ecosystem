# Session 238: S238 eureka tests

**Date:** 2026-05-03
**Focus:** Test S238 bright-mind ideas

## Reference Baselines
- Random: ~0.00 (noise)
- C16: +0.078
- S1: +0.149 (PRIMARY for RL)

## Results

| Test | IC | vs Random | Tier | Use |
|------|-----|----------|------|-----|
| vol_rank>0.8 | 0.091 | +0.09 | T2 | volume regime filter |
| A/D Q1 | 0.093 | +0.09 | T2 | breadth filter |
| A/D Q5 | 0.050 | +0.05 | T3 | opposite (use Q1) |
| price tier low | 0.086 | +0.09 | T2 | price tier filter |
| quarter_end | 0.066 | +0.07 | T3 | weak/failed |
| quarter_start | 0.098 | +0.10 | T2 | timing filter |

## Findings

- **vol regime**: High vol AMPLIFIES C16 (+38%) - TIER 2 filter
- **market breadth**: A/D quintile 1-2 (most decline) works best - TIER 2 contrarian
- **price tier**: Weak (+13%) - TIER 2 filter
- **quarter_end**: WORSE (-15%) - TIER 3, don't use
- **quarter_start**: +26% - TIER 2 timing filter - NEW!
- Reusable script: x240_wf_ic_test.py

## Key Discovery

- **Quarter START (+26%)** beats quarter END (-15%) - TIER 2 timing filter
- A/D breadth is contrarian: more decline = stronger signal - TIER 2 filter
- These are VALID RL STATE FEATURES