# Session 334 - 2026-05-17

### H521 - Balanced Carry-Amplified Feature Search
**Hypothesis:**
Testing minimal carry features (simple lags, no flow_persist/imbalance_persist) should improve carry separation while preserving amplified state.

**Command / code:**
`python analysis/h521_balanced_carry_amplified_search.py`

**Inputs:**
- `artifacts/research_branches/20260510_144827_latent_state_discovery_clustered_panel.parquet`
- `artifacts/run_summaries/20260517_134504_carry_axis_bottleneck_audit_research_branch.json`

**Saved artifact:**
- `artifacts/run_summaries/20260517_135555_balanced_carry_amplified_search_research_branch.json`
- `artifacts/research_branches/20260517_135555_balanced_carry_amplified_search_*.parquet`

| Metric | Base (no carry) | Weak Carry | H518 Baseline |
|--------|-----------------|------------|---------------|
| carry_jaccard | 0.109 | 0.136 | 0.090 |
| amplified_jaccard | 0.055 | 0.034 | 0.151 |

**Result:**
- Carry improved: 0.136 vs 0.109 (+25%) vs H518 0.090 (+51%)
- Amplified degraded: 0.034 vs 0.055 (-38%) vs H518 0.151 (-77%)
- Trade-off persists even with "weak" carry features (simple lags only)
- 5/7 guard gates passed → MIXED decision

**Verdict: MIXED**

**Key Finding:**
Carry and amplified states are inherently in tension in the observable representation space. Any carry-focused feature (even simple lags) improves carry but damages amplified. This is a structural property of the latent manifold, not a feature engineering issue.

**Next step:**
- Document carry/amplified as naturally conflicting latent states
- This concludes the carry-axis exploration branch
- Consider: is there a representation that separates all three (onset/amplified/carry) cleanly, or is the manifold inherently limited to 2-3 clean separations?