# Session 360 - H561 Breadth Regime Hierarchy (Cascade)

**Date**: 2026-05-17

**Hypothesis**: H550 found C25 alone (0.2115) > C24×own_breadth (0.2080) > C23 (0.1896). Test priority cascade: use strongest available signal each day.

**Command**: `python analysis/h561_breadth_regime_cascade.py`

**Saved artifact**: `artifacts/run_summaries/20260517_154656_breadth_regime_cascade_research_branch.json`

## Results

| State | IC | Rows |
|-------|-----|------|
| C25 alone | 0.2090 | 27,409 |
| Composite (C23+C24+C25+C26) | 0.1977 | 74,078 |
| **Cascade (C25→C24×breadth→C23)** | **0.1907** | 56,121 |
| C23 alone | 0.1885 | 54,755 |
| C24 × own_breadth | 0.1240 | 158,752 |

## Key Finding: FAILED

**Cascade does NOT beat composite**:
- Cascade IC = 0.1907
- Composite IC = 0.1977
- Lift = **-0.0070** (composite wins!)

The cascade logic fails because C24×own_breadth is actually weaker than C23 alone (0.124 vs 0.188). The cascade prioritizes the wrong signal.

**Confirms C25 alone is strongest** (0.2090 matches H550's 0.2115 finding).

## Verdict: FAILED

- Cascade is worse than composite
- C25 alone is still the strongest signal
- The cascade priority model is flawed

**Next**: #67 Breadth Velocity (Change Rate)