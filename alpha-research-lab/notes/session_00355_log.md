# Session 355 - H547 Breadth-Concentration Interaction

**Date**: 2026-05-17

**Hypothesis**: H543 found composite×low_breadth is strongest (IC=0.2364). Now test if signal CONCENTRATION (top-5 share of S1 mass) adds value on top of breadth filter.

**Command**: `python analysis/h547_breadth_concentration_interaction.py`

**Saved artifact**: `artifacts/run_summaries/20260517_152634_breadth_concentration_interaction_research_branch.json`

## Results

| State | IC | Lift vs Baseline | Positive Years |
|-------|-----|------------------|----------------|
| all_rows (baseline) | 0.1298 | — | 11/11 |
| low_breadth | 0.1299 | +0.0001 | 11/11 |
| composite×low_breadth (H543) | 0.2364 | +0.1066 | 8/11 |
| **distributed_low_breadth** | **0.2604** | **+0.1306** | 4/11 |
| concentrated_low_breadth | 0.1955 | +0.0658 | 2/11 |

## Key Finding: OPPOSITE of Hypothesis!

**Concentration goes the WRONG way**:
- Distributed (low concentration, signal mass spread across more stocks) = IC 0.2604 (+0.1306)
- Concentrated (high concentration, top-5 hold most signal mass) = IC 0.1955 (+0.0658)
- **Concentration effect: -0.0648** (distributed beats concentrated!)

**Interpretation**: When signal mass is spread more evenly (distributed), the signal is STRONGER than when concentrated among top-5. This is the opposite of the hypothesis.

**Confirms H543**: composite×low_breadth = 0.2364 is validated.

## Verdict: MIXED

- Both concentrated and distributed beat baseline
- Distributed is STRONGER than concentrated (opposite of hypothesis)
- Distributed has fewer positive years (4 vs 2) - less robust
- The effect direction is meaningful but concentration is NOT the right amplifier

**Next**: Test #48 Quiet-State Duration Sweet Spot (H534 found active state has "longer = stronger", now test quiet state)