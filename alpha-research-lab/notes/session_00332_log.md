# Session 332 - 2026-05-17

### H518 - Carry Axis Bottleneck Audit
**Hypothesis:**
Under the H515 guarded contract, carry-axis weakness is likely a representation
overlap bottleneck rather than a phase-instability collapse.

**Command / code:**
`python analysis/h518_carry_axis_bottleneck_audit.py`

**Inputs:**
- `artifacts/run_summaries/20260517_133818_amplified_axis_refinement_research_branch.json`
- associated active overlap/results/yearly artifacts

**Saved artifact:**
- `artifacts/run_summaries/20260517_134504_carry_axis_bottleneck_audit_research_branch.json`
- `artifacts/research_branches/20260517_134504_carry_axis_bottleneck_audit_*.parquet`

| Axis | Best Cluster | Jaccard | Symbolic-in-Cluster | Cluster-in-Symbolic | Cluster Rows | Avg IC |
|------|--------------|---------|---------------------|---------------------|--------------|--------|
| onset | `h514_active_k5_cluster_2` | `0.2081` | `0.7648` | `0.2223` | `72,010` | `0.1417` |
| amplified | `h514_active_k5_cluster_0` | `0.1511` | `0.7274` | `0.1602` | `4,113` | `0.1763` |
| carry | `h514_active_k5_cluster_4` | `0.0900` | `0.2064` | `0.1376` | `52,609` | `0.1966` |

Carry stability check (best carry cluster):
- positive years: `11/11`
- yearly IC spread: `0.0730`

**Result:**
- Carry remains the weakest overlap axis (`0.0900`) versus onset/amplified.
- But carry cluster itself is not unstable (11/11 positive years), so the
  problem is overlap representation, not phase collapse.

**Verdict: PASSED (diagnostic)**

**Next step:**
- Next pass should be carry-focused representation refinement under the frozen
  guarded active-k selection contract.
