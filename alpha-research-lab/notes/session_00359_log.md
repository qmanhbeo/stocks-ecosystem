# Session 359 - H560 Signal Mass Entropy as Regime Detector

**Date**: 2026-05-17

**Hypothesis**: H547 found distributed (0.2604) > concentrated (0.1955) by +0.0648. Test if ENTROPY of signal mass distribution is a hidden regime: high entropy = dispersed alpha, low entropy = crowded.

**Command**: `python analysis/h560_signal_mass_entropy_regime.py`

**Saved artifact**: `artifacts/run_summaries/20260517_154126_signal_mass_entropy_regime_research_branch.json`

## Results

| State | IC | Lift vs Baseline | Rows |
|-------|-----|------------------|------|
| low_entropy_low_breadth | 0.1477 | +0.0175 | 164,614 |
| low_breadth | 0.1475 | +0.0173 | 165,415 |
| entropy_q1 (concentrated) | 0.1449 | +0.0147 | 165,281 |
| low_entropy | 0.1447 | +0.0145 | 165,422 |
| all_rows (baseline) | 0.1302 | — | 826,404 |
| high_entropy | 0.1067 | -0.0235 | 165,525 |
| entropy_q5 (dispersed) | 0.1067 | -0.0235 | 165,281 |

## Key Finding: OPPOSITE of Hypothesis

**Entropy is NOT a regime detector**:
- High entropy (dispersed) IC = 0.1067 (-0.0235 below baseline)
- Low entropy (concentrated) IC = 0.1447 (+0.0145 above baseline)
- Entropy lift: **-0.0380** (negative - the opposite of hypothesis!)

**Entropy adds NOTHING on low_breadth**:
- low_entropy_low_breadth = 0.1477
- low_breadth alone = 0.1475
- Difference: +0.0002 (essentially zero)

**No overlap**: high_entropy_low_breadth has 0 rows - low breadth naturally has low entropy.

## Verdict: FAILED

- Entropy effect is OPPOSITE of hypothesis: concentrated beats dispersed
- Entropy does not improve on low_breadth filter
- This is a dead-end - entropy does not capture hidden regime structure

**Next**: #66 Breadth Regime Hierarchy (Cascade) - use strongest signal each day based on H550 finding