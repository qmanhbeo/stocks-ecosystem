# Session 367 - H573 Capacity-Breadth-Signal Triple Amplifier

**Date**: 2026-05-17

**Hypothesis**: Test capacity × breadth × signal triple intersection. H565 found tight+low_breadth=0.1966, H543 found composite×low_breadth=0.2364. Add tight capacity to signal+low_breadth for triple.

**Command**: `python analysis/h573_capacity_breadth_signal_triple.py`

**Saved artifact**: `artifacts/run_summaries/20260517_160617_capacity_breadth_signal_triple_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| tight_low_breadth | 0.1966 | 24,035 | 3/3 |
| c23_signal | 0.1923 | 24,953 | 11/11 |
| tight_capacity | 0.1897 | 160,628 | 11/11 |
| signal_low_breadth | 0.1652 | 3,732 | 2/2 |
| low_breadth | 0.1550 | 121,504 | 3/3 |
| **triple** | **0.1394** | **2,903** | **2/2** |

## Key Finding: FAILED (Negative)

**Triple is WORSE than best pair**:
- Triple (tight + low_breadth + C23) = 0.1394
- Best pair (tight + low_breadth) = 0.1966
- Difference: **-0.0571** (below +0.01 threshold)

**Why it fails**:
1. tight+low_breadth already captures hidden demand + regime
2. Adding C23 (illiquidity × vol_expansion) is redundant or adds noise
3. Triple intersection is too sparse (2,903 rows vs 24,035 for tight+low)
4. Selected triple rows have worse IC than the pair alone

**Verdict: FAILED**

- Triple intersection does NOT improve over the pair
- Both components (tight_capacity, low_breadth) are needed, but adding signal HURTS
- Finding: tight+low_breadth is the optimal combination - adding more filters degrades
- Dead-end D073

**Next**: #74 Implementation Pain as Positive Signal, or #75 Foreign Flow Regime Conditioner