# Session 328 - 2026-05-17

### H514 - Amplified Axis Refinement (Feature-Augmented, Dev-Silhouette Selection)
**Hypothesis:**
Adding non-symbolic flow/ceiling interaction features should improve amplified
state separation while preserving H512 quiet/C24 and robustness gates.

**Command / code:**
`python analysis/h514_amplified_axis_refinement.py`

**Inputs:**
- `artifacts/research_branches/20260510_144827_latent_state_discovery_clustered_panel.parquet`
- baseline comparator: `artifacts/run_summaries/20260517_132235_active_manifold_disentangling_research_branch.json`
- global representation fixed at `k=4` (C24-preserving), active `k` selected by dev silhouette

**Saved artifact:**
- `artifacts/run_summaries/20260517_133731_amplified_axis_refinement_research_branch.json`
- `artifacts/research_branches/20260517_133731_amplified_axis_refinement_*.parquet`

| Metric | Value | Note |
|--------|-------|------|
| Selected active k | `3` | dev-silhouette winner |
| Quiet cluster in quiet | `0.96344` | preserved |
| C24 symbolic-in-cluster | `0.96598` | preserved |
| Active-vs-random lift gap | `+0.04724` | preserved |
| Max onset Jaccard | `0.16322` | improved vs H512 |
| Max amplified Jaccard | `0.03246` | **worse** vs H512 (`0.06011`) |
| Max carry Jaccard | `0.07979` | weaker |
| Mean disentangle Jaccard | `0.09182` | below non-trivial bar |
| Strong non-sparse clusters | `2` | passes strength |

**Result:**
- The feature set helped onset but hurt amplified-axis separation under the
  dev-silhouette-selected active partition.
- This pass is inconclusive for the target objective.

**Verdict: MIXED**

**Next step:**
- Run immediate selection follow-through: keep same representation/features but
  force `active_k=5` (which already shows stronger amplified overlap in the
  same run diagnostics) and re-check full gate set.
