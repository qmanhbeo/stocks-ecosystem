# Session 329 - 2026-05-17

### H515 - Amplified Axis Refinement (Forced Active K=5 Follow-Through)
**Hypothesis:**
H514's weakness was active-partition selection (`k=3`), not representation. If
we keep the same feature-refined setup and force `active_k=5`, amplified-axis
separation should improve while preserving quiet/C24 and robustness gates.

**Command / code:**
`python analysis/h514_amplified_axis_refinement.py --force-active-k 5`

**Inputs:**
- same inputs/features as H514
- baseline comparator: `artifacts/run_summaries/20260517_132235_active_manifold_disentangling_research_branch.json`

**Saved artifact:**
- `artifacts/run_summaries/20260517_133818_amplified_axis_refinement_research_branch.json`
- `artifacts/research_branches/20260517_133818_amplified_axis_refinement_*.parquet`

| Metric | Value | Note |
|--------|-------|------|
| Selected global k | `4` | fixed C24-preserving representation |
| Forced active k | `5` | follow-through selection |
| Quiet cluster in quiet | `0.96344` | preserved |
| C24 symbolic-in-cluster | `0.96598` | preserved |
| Active-vs-random lift gap | `+0.04790` | preserved |
| Max onset Jaccard | `0.20806` | improved |
| Max amplified Jaccard | `0.15115` | **strong improvement** vs H512 `0.06011` |
| Max carry Jaccard | `0.09001` | stable/modest |
| Mean disentangle Jaccard | `0.14974` | improved |
| Strong non-sparse clusters | `2` | preserved |

**Result:**
- All structural gates passed, including explicit amplified-axis improvement.
- The weak-axis objective is now satisfied without breaking quiet/C24 or
  random-gap constraints.

**Verdict: PASSED**

**Next step:**
- Run robustness audit on this forced-`k=5` refinement to confirm it is not a
  single-pocket or phase-fragile artifact.
