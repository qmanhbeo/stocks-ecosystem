# Session 237: Calendar/Breadth/Vol ideas

**Date:** 2026-05-03
**Focus:** Test S237 bright-mind ideas

## Reference Baselines
- Random: ~0.00 (noise)
- C16: +0.078
- S1: +0.149 (PRIMARY for RL)

## Results

| Test | IC | vs Random | Tier | Use |
|------|-----|----------|------|-----|
| C16 Mon | 0.084 | +0.08 | T2 | calendar filter |
| C16 Thu | 0.071 | +0.07 | T3 | calendar filter (inverse) |
| C16 vol<20% | 0.066 | +0.07 | T3 | vol regime (weak) |
| C16 vol>80% | 0.091 | +0.09 | T2 | vol regime filter |
| C16 Tet | 0.097 | +0.10 | T2 | holiday filter |
| baseline | 0.078 | +0.08 | T2 | C16 baseline |

## Findings

- **monday_gap**: Monday C16 +17% over Thursday - TIER 2 filter
- **volatility_regime**: C16 +38% in high vol (>80%) - TIER 2 filter
- **holiday_effect**: Tet period +25% - TIER 2 filter

## Key Discovery

- **High volatility regime AMPLIFIES C16** - TIER 2 filter for RL
- **Tet holiday** shows strongest calendar effect - TIER 2 filter
- These are VALID RL STATE FEATURES