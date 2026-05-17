# Session 330 - 2026-05-17

### H516 - Robustness Audit for H515 (Forced K=5 Variant)
**Hypothesis:**
The H515 amplified-axis improvement should remain robust by phase/year and not
collapse into a single dominant sparse pocket.

**Command / code:**
`python analysis/h513_h512_phase_stability_audit.py --h512-summary-path artifacts/run_summaries/20260517_133818_amplified_axis_refinement_research_branch.json`

**Inputs:**
- `artifacts/run_summaries/20260517_133818_amplified_axis_refinement_research_branch.json`
- derived active result/yearly artifacts from that run

**Saved artifact:**
- `artifacts/run_summaries/20260517_133945_h512_phase_stability_audit_research_branch.json`
- `artifacts/research_branches/20260517_133945_h512_phase_stability_audit_*.parquet`

| Metric | Value | Note |
|--------|-------|------|
| Selected active k | `5` | from H515 summary |
| Strong cluster count | `2` | both above base IC with `>=5000` rows |
| Dominant cluster share | `0.65535` | below one-pocket guardrail (`0.80`) |
| Multi-cluster strength flag | `True` | passed |
| Phase-positive flag | `True` | passed |
| Not-single-pocket flag | `True` | passed |
| Cluster 4 avg IC | `0.19662` | dev `0.20370`, val `0.20622`, conf `0.15275` |
| Cluster 3 avg IC | `0.17082` | dev `0.16702`, val `0.12762`, conf `0.22488` |

**Result:**
- Robustness is supported for the forced-`k=5` amplified-refinement branch.
- Improved amplified separation survives phase checks without one-pocket collapse.

**Verdict: PASSED**

**Next step:**
- Continue with a narrow selection-discipline audit:
  define and freeze active-`k` selection contract (pure silhouette vs
  silhouette+axis objective) so this branch does not drift into ad-hoc picks.
