# Session 384 - H595 Multi-Signal Co-occurrence Superposition

**Date**: 2026-05-17

**Hypothesis**: C23/C24/C25/C26 fire on different days. When MULTIPLE fire together on same ticker (co-occurrence), does that indicate stronger hidden demand? "Multiple mechanisms firing simultaneously = stronger alpha" hypothesis.

**Command**: `python analysis/h595_multi_signal_cooccurrence.py`

**Saved artifact**: `artifacts/run_summaries/20260517_173614_multi_signal_cooccurrence_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| **composite_2+ (AND)** | **0.2445** | 29,542 | **11/11** |
| signal_2 | 0.2413 | 21,374 | 11/11 |
| signal_3+ | 0.2330 | 8,168 | 11/11 |
| composite_any (OR) | 0.1988 | 97,236 | 11/11 |
| signal_1 | 0.1724 | 67,694 | 11/11 |
| baseline | 0.1298 | 809,019 | 11/11 |

## Key Finding: PASSED

**Multi-signal co-occurrence is STRONGER**:
- composite_2+ (AND) IC = 0.2445 (+0.0457 vs OR)
- Signal 2+ vs Signal 1: **+0.0689 lift** (> +0.01 threshold)
- 11/11 positive years for all multi-signal states

**Mechanism**: When multiple hidden-demand mechanisms fire simultaneously on the same ticker, it indicates stronger cumulative demand than any single mechanism alone. The intersection (AND) of signals captures "verified hidden demand" - multiple independent signals pointing to the same stock = higher confidence alpha.

**Verdict: PASSED** - Finding F445

- Add to findings as F445
- This confirms the hypothesis: multiple signals together > single signal
- The AND (intersection) approach beats the OR (any signal) approach

**Next**: H96 (Zero-Cofire Edge)