# Session 337 - 2026-05-17

### H524 - State Combination Alpha
**Hypothesis:**
Test if simultaneous multiple states (e.g., onset+amplified together, C23+C24) capture information that individual states miss. H507-H521 tested states in isolation; combo states are untested.

**Command / code:**
`python analysis/h524_state_combo_alpha.py`

**Inputs:**
- S1 panel (xs_barrier_vol_1d_hose_full.parquet) 2015-2025
- C16 signals (xs_order_pressure_daily.parquet): order_volume_ratio_rank, can_buy_next_open

**Saved artifact:**
- `artifacts/run_summaries/20260517_141104_state_combo_alpha_research_branch.json`
- `artifacts/run_summaries/20260517_141104_state_combo_alpha_results.parquet`

| Metric | Value | Note |
|--------|-------|------|
| Best individual | state_router | IC=0.1795, 11/11 pos yrs |
| Best union combo | union_router_only | IC=0.1795 (same as individual) |
| Best intersect combo | intersect_router_buyable | IC=0.1796, +0.0002 lift |
| Lift (combo vs individual) | +0.0002 | essentially no improvement |
| Lift vs baseline | +0.0520 | state_router alone provides this |
| Dev IC | 0.1838 | 2015-2022 |
| Validation IC | 0.1814 | 2023-2024 |
| Confirmation IC | 0.1487 | 2025 (degrades) |

**Result:**
- **FAILED**: Combo states do NOT capture information beyond individual states
- Union combos (OR logic) hurt: adding more states dilutes the signal
- Intersection combos (AND logic) provide minimal (+0.0002) improvement
- Best individual (state_router) remains the champion

**Key Discovery:**
- state_quiet (IC=0.1552) is actually a STRONG signal, not neutral as previously assumed
- This is unexpected: high pressure (quiet) stocks have positive IC

**Verdict: FAILED**

**Interpretation:**
The latent state structure from H507-H515 already captured the signal organization. Adding state combinations (union or intersection) doesn't improve upon the best individual state (router). The signal is in the individual state, not in the combination.

**Next step:**
- Move to next Eureka idea: Cross-Sectional Breadth as Regime Signal
- Or investigate why state_quiet is strong (unexpected finding)