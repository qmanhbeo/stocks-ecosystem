# Session 325 - 2026-05-17

### H511 - Active Manifold Disentangling
**Hypothesis:**
With strict dev-only `k` selection and active-only unsupervised subclustering, the H509 active manifold can be meaningfully disentangled into onset/amplification/carry-like substructure while preserving quiet/C24 structural recovery and beating random partitions.

**Command / code:**
`python analysis/h511_active_manifold_disentangling.py --silhouette-sample 4000`

**Inputs:**
- `artifacts/research_branches/20260510_144827_latent_state_discovery_clustered_panel.parquet`
- H509 observable-emission feature set + lag deltas
- 2015-2025 only (no 2026), dev years 2015-2022 for cluster-selection discipline

**Saved artifact:**
- `artifacts/run_summaries/20260517_131855_active_manifold_disentangling_research_branch.json`
- `artifacts/research_branches/20260517_131855_active_manifold_disentangling_*.parquet`

| Metric | Value | Note |
|--------|-------|------|
| Selected global k (dev silhouette) | `5` | replaces H509 full-period IC-driven k choice |
| Quiet cluster in quiet | `0.99797` | quiet recovery preserved strongly |
| C24 symbolic-in-cluster | `0.59114` | misses preservation bar |
| Active rows | `420,604` | non-quiet manifold under selected global k |
| Selected active k (dev silhouette) | `3` | active-only subclustering choice |
| Active lift minus random lift | `+0.04266` | non-random structure persists |
| Mean disentangle Jaccard (onset/amplified/carry) | `0.05923` | below non-trivial bar |
| Max onset Jaccard | `0.08038` | partial overlap only |
| Max amplified Jaccard | `0.02598` | weak separation |
| Max carry Jaccard | `0.07134` | partial overlap only |
| Strong non-sparse active clusters | `1` | below required multi-cluster strength |

**Result:**
- Quiet-vs-active structure is still strong under dev-only `k` discipline.
- Active manifold still beats random partitions.
- But the substructure remains entangled: onset/amplified/carry overlaps are weak, and C24 recovery degrades under the dev-silhouette-selected global representation.
- Therefore this pass does not validate the desired H509 follow-through claim.

**Verdict: FAILED**

**Next step:**
- Keep H509/H511 as structural evidence only.
- Next queue item should stay narrow: representation-first refinement for C24/active disentangling under strict dev-only model selection (no HMM/manifold jump yet).
