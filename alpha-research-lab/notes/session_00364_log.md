# Session 364 - H565 Capacity-Breadth Direction Combo

**Date**: 2026-05-17

**Hypothesis**: Test capacity × breadth interaction. H474 found tight_capacity +0.055, H531 found tight+low_breadth=0.1979. Now test tight × low_breadth combo at raw S1 level.

**Command**: `python analysis/h565_capacity_breadth_combo.py`

**Saved artifact**: `artifacts/run_summaries/20260517_155450_capacity_breadth_direction_combo_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| **tight_low_breadth** | **0.2062** | 17,041 | 3/3 |
| tight_capacity | 0.1648 | 127,566 | 11/11 |
| low_breadth | 0.1073 | 119,952 | 3/4 |

## Key Finding: PASSED

**Combo beats both components**:
- Tight + Low Breadth = 0.2062
- vs Tight alone = 0.1648 (**+0.0414**)
- vs Low Breadth alone = 0.1073 (**+0.0989**)

**This is a strong amplification**:
- Both components are needed
- The combination is NOT redundant (tight alone = 0.165, combo = 0.206)
- Both conditions together capture hidden demand + regime shift

**Important**: This is different from H531 which tested on C23/C24 signals. H565 tests tight capacity on raw S1 and finds similar amplification.

## Verdict: PASSED

- Combo lifts +0.041 vs tight alone, +0.099 vs low_breadth alone
- Both components needed - non-redundant combination
- This confirms the hidden state: tight capacity + low breadth = stronger alpha
- Finding F437

**Next**: #64 Time-Since-Active as Hidden State