# Session 327 - 2026-05-17

### H513 - H512 Phase/Year Stability Audit
**Hypothesis:**
The H512 active-manifold map is not a one-pocket artifact; it should show
multi-cluster strength with positive validation/confirmation phase IC under the
same strict dev-only discipline.

**Command / code:**
`python analysis/h513_h512_phase_stability_audit.py`

**Inputs:**
- `artifacts/run_summaries/20260517_132235_active_manifold_disentangling_research_branch.json`
- `artifacts/research_branches/20260517_132235_active_manifold_disentangling_active_results.parquet`
- `artifacts/research_branches/20260517_132235_active_manifold_disentangling_active_yearly.parquet`
- `artifacts/research_branches/20260517_132235_active_manifold_disentangling_chosen_active_panel.parquet`

**Saved artifact:**
- `artifacts/run_summaries/20260517_132509_h512_phase_stability_audit_research_branch.json`
- `artifacts/research_branches/20260517_132509_h512_phase_stability_audit_*.parquet`

| Metric | Value | Note |
|--------|-------|------|
| Strong cluster count | `2` | both above base IC with `>=5000` pooled rows |
| Dominant cluster share | `0.5762` | below one-pocket guardrail (`0.80`) |
| Multi-cluster strength flag | `True` | gate passed |
| Phase-positive flag | `True` | strong clusters positive in validation and confirmation |
| Not-single-pocket flag | `True` | concentration acceptable |
| Cluster 0 avg IC | `0.2067` | dev `0.2092`, validation `0.2179`, confirmation `0.1846` |
| Cluster 3 avg IC | `0.1873` | dev `0.1719`, validation `0.2234`, confirmation `0.2376` |

**Result:**
- H512 robustness is supported: recovered structure is not driven by one sparse
  pocket, and both strong clusters keep positive out-of-dev phase IC.

**Verdict: PASSED**

**Next step:**
- Continue with a narrow structural refinement focused on the weakest axis
  (amplified-state separation), still under dev-only discipline.
