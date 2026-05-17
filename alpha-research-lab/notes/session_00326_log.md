# Session 326 - 2026-05-17

### H512 - C24-Preserving Active Manifold Refinement
**Hypothesis:**
H511 failed mainly because the dev-silhouette global selection (`k=5`) degraded C24 recovery. If we keep the same dev-only protocol but use the C24-preserving global representation (`k=4`) and then rerun active-only subclustering, active-manifold disentangling should improve while preserving quiet/C24 structure.

**Command / code:**
`python analysis/h511_active_manifold_disentangling.py --silhouette-sample 4000 --force-global-k 4`

**Inputs:**
- `artifacts/research_branches/20260510_144827_latent_state_discovery_clustered_panel.parquet`
- Same H509 observable-emission features and lag deltas
- 2015-2025 only (dev 2015-2022, validation 2023-2024, confirmation 2025)

**Saved artifact:**
- `artifacts/run_summaries/20260517_132235_active_manifold_disentangling_research_branch.json`
- `artifacts/research_branches/20260517_132235_active_manifold_disentangling_*.parquet`

| Metric | Value | Note |
|--------|-------|------|
| Forced global k | `4` | C24-preserving refinement relative to H511 |
| Quiet cluster in quiet | `0.96344` | passes quiet-preservation gate |
| C24 symbolic-in-cluster | `0.96598` | C24 distinctness restored |
| Active rows | `436,076` | non-quiet manifold under global `k=4` |
| Selected active k (dev silhouette) | `4` | best active partition in this representation |
| Active lift minus random lift | `+0.06043` | stronger than H511 |
| Mean disentangle Jaccard (onset/amplified/carry) | `0.10481` | above non-trivial bar |
| Max onset Jaccard | `0.12309` | improved |
| Max amplified Jaccard | `0.06011` | improved but still weakest axis |
| Max carry Jaccard | `0.13123` | improved |
| Strong non-sparse active clusters | `2` | meets strength gate |

**Result:**
- All five structural flags passed:
  - quiet recovery preserved
  - C24 recovery preserved
  - active clusters beat random
  - non-trivial onset/amplified/carry disentangling
  - non-sparse active strength
- This resolves the immediate H511 failure mode as a representation-selection issue rather than a hard impossibility of active-manifold separation.

**Verdict: PASSED**

**Next step:**
- Run one robustness follow-through under the same strict dev-only discipline:
  confirm the H512 mapping remains stable by phase/year and is not driven by one sparse state pocket.
