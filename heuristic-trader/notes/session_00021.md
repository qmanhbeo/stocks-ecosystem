# Session 21: Reallocate Fallback Verdict + Artifact Cleanup

**Date:** 2026-05-13
**Status:** NEGATIVE FINDING (execution fallback deprioritized)

## Purpose
Record patched-code apples-to-apples walk-forward verdict for `fallback_mode=reallocate_selected` and clean generated verification artifacts after preserving conclusions in notes.

## Strategies Compared (2015-2025 WFV)
- `s1_top5_rebal10`
- `s1_top5_rebal10_depth5`
- `s1_top5_rebal10_reallocate`
- `s1_top5_rebal10_depth5_reallocate`

## Headline Result
- Reallocate-selected fallback **worsened** aggregate metrics for both S1 comparator families.
- It did not provide a robust cash-drag fix.
- Marked **NEGATIVE/DEPRIORITIZED** (keep variants for reproducibility only).

## Key Aggregate Metrics
| Strategy | Mean Ann Return | Mean Excess | Positive Folds | Beats Benchmark | Mean Max DD | Total Trades |
|----------|------------------|-------------|----------------|------------------|-------------|--------------|
| s1_top5_rebal10 | -4.68% | -17.49% | 4/11 | 2/11 | 22.07% | 985 |
| s1_top5_rebal10_depth5 | +0.98% | -11.87% | 6/11 | 5/11 | 25.47% | 1568 |
| s1_top5_rebal10_reallocate | -9.02% | -21.77% | 3/11 | 3/11 | 31.54% | 701 |
| s1_top5_rebal10_depth5_reallocate | -1.57% | -14.40% | 5/11 | 4/11 | 28.41% | 1380 |

## Interpretation
- Reallocation across selected names increases concentration but does not solve execution bottlenecks.
- Cash drag is not fixed by concentration alone; selected-name quality/timing remains the key issue.
- Do not promote reallocation variants as candidates.

## Artifact Provenance
- Artifacts were generated during the 2026-05-13 patched-code WFV comparison and removed after metrics were extracted into this session log and compact notes.
