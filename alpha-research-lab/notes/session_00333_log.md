# Session 333 - 2026-05-17

### H519 - Carry Axis Representation Refinement
**Hypothesis:**
Adding carry-focused temporal/flow continuity features to the active-manifold emissions should improve carry-state separation while preserving H512/H515 quiet/C24/amplified gates and active-vs-random lift gap.

**Command / code:**
`python analysis/h519_carry_axis_refinement.py --force-active-k 5`

**Inputs:**
- `artifacts/research_branches/20260510_144827_latent_state_discovery_clustered_panel.parquet`
- `artifacts/run_summaries/20260517_134504_carry_axis_bottleneck_audit_research_branch.json`

**Saved artifact:**
- `artifacts/run_summaries/20260517_135318_carry_axis_refinement_research_branch.json`
- `artifacts/research_branches/20260517_135318_carry_axis_refinement_*.parquet`

| Metric | Value | Note |
|--------|-------|------|
| carry_jaccard | 0.1458 | Improved from H518 baseline 0.090 (+62%) |
| amplified_jaccard | 0.0308 | Dropped from H518 baseline 0.151 (-80%) |
| onset_jaccard | 0.1126 | Stable |
| quiet_recovery | 0.963 | Preserved (≥0.95) |
| c24_recovery | 0.966 | Preserved (≥0.80) |
| active_vs_random_lift | +0.047 | Preserved (≥0.01) |
| strong_clusters | 3 | Preserved (≥2) |
| disentangle_mean | 0.096 | Below threshold (≥0.10) |

**Result:**
- Carry axis improved significantly (+62% Jaccard)
- But amplified axis degraded significantly (-80%)
- Trade-off: carry-focused features help carry state but hurt amplified state
- 5/7 guard gates passed → MIXED decision

**Verdict: MIXED**

**Key Finding:**
Carry-focused temporal features (flow_persist, imbalance_persist, order_pressure_sustain, carry_candidate_flag) improve carry separation but at the cost of amplified state overlap. The carry-amplified trade-off is intrinsic to these features.

**Next step:**
- Consider a balanced feature set that preserves both carry AND amplified, or
- Accept that carry/amplified are naturally conflicting and document the boundary, or
- Try a weaker carry feature set to minimize amplified damage