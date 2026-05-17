# Session 331 - 2026-05-17

### H517 - Active-K Selection Contract Audit
**Hypothesis:**
A constrained guarded active-k selection rule can prevent silhouette-only drift
while preserving strict dev-only discipline and structural quality gates.

**Command / code:**
`python analysis/h517_active_k_selection_contract_audit.py`

**Inputs:**
- `artifacts/run_summaries/20260517_132235_active_manifold_disentangling_research_branch.json` (H512)
- `artifacts/run_summaries/20260517_133731_amplified_axis_refinement_research_branch.json` (H514)

**Saved artifact:**
- `artifacts/run_summaries/20260517_134248_active_k_selection_contract_audit_research_branch.json`
- `artifacts/research_branches/20260517_134248_active_k_selection_contract_audit_comparison.parquet`

| Run | Silhouette K | Guarded K | Silhouette Amp Jaccard | Guarded Amp Jaccard | Lift Gap (guarded) |
|-----|--------------|-----------|-------------------------|---------------------|--------------------|
| H512 | `4` | `4` | `0.0601` | `0.0601` | `+0.0604` |
| H514 | `3` | `5` | `0.0325` | `0.1511` | `+0.0479` |

Guarded rule gates:
- `max_jaccard_amplified >= 0.06`
- `mean_disentangle_jaccard >= 0.10`
- `active_lift_minus_random_lift >= 0.01`
- `strong_non_sparse_clusters >= 2`
- tie-break by highest dev silhouette within gated candidates

**Result:**
- Guarded contract exists and improves H514 amplified separation materially
  (`0.1511` vs `0.0325`) without violating lift-gap or strength gates.
- H512 remains unchanged (`k=4`) under both rules, so guarded contract does not
  destabilize prior pass.

**Verdict: PASSED**

**Next step:**
- Freeze guarded active-k contract for this branch and continue only with
  representation tweaks that must satisfy the same guarded gates.
