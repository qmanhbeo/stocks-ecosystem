# Session 372 - H582 C27 × Signal Composite

**Date**: 2026-05-17

**Hypothesis**: C27 (blocked stocks) × composite signal (C23/C24/C25) amplifies the composite since C27 is a different mechanism from latent signals.

**Command**: `python analysis/h582_c27_signal_composite.py`

**Saved artifact**: `artifacts/run_summaries/20260517_163527_c27_signal_composite_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| c24_signal | 0.1670 | 148,128 | 11/11 |
| c23_active | 0.1648 | 127,566 | 11/11 |
| blocked_composite | 0.1499 | 15,081 | 10/10 |
| blocked_either (C27) | 0.1477 | 15,848 | 10/10 |
| all_rows | 0.1302 | 826,404 | 11/11 |
| composite_signal | 0.1301 | 803,842 | 11/11 |
| c25_signal | 0.1201 | 688,627 | 11/11 |

## Key Finding: PASSED (but mechanism is circular)

- C27 × composite: IC=0.1499 (+0.0198 vs composite alone)
- Raw composite: IC=0.1301 ≈ baseline (0.1302) — composite is TOO BROAD
- The composite (C23 OR C24 OR C25 OR all the rest) = 97% of all rows
- The "composite" in this test is effectively the full universe
- blocked_composite is NOT an intersection effect — it's just "blocked within the universe"
- The lift comes from C27 alone, not from a true signal × blocked interaction
- The individual latent signals (C23/C24) remain stronger than the blocked combo

**Caveat**: Composite definition is too broad (includes almost everything). A meaningful test would require the H543-type composite (intersection of active signals), but that needs the precomputed features from H550/H543 runs.

## Verdict: PASSED (mechanistically circular — dead-end D076)

- Meets pass criterion (+0.0198 > +0.01) but the composite is useless (baseline IC)
- This confirms C27 is a standalone signal, not a combo amplifier
- C27 works best as a direct filter, not as an add-on to weak composites

**Next**: #84 C27 as Signal Router (S1 IC conditional on blocked vs not)