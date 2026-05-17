# Session 340 - 2026-05-17

### H527 - Quiet-State Inverse Alpha
**Hypothesis:**
Test if QUIET stocks (not in C23) in active markets (high date-level C23 coverage) are contrarian opportunities. From H524, state_quiet is STRONG (IC=0.1552). Does market activity level modulate quiet-stock quality?

**Command / code:**
`python analysis/h527_quiet_state_inverse_alpha.py`

**Inputs:**
- S1 panel (xs_barrier_vol_1d_hose_full.parquet) 2015-2025
- C16 signals (xs_order_pressure_daily.parquet): order_volume_ratio_rank

**Saved artifact:**
- `artifacts/run_summaries/20260517_142721_quiet_state_inverse_alpha_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| Quiet only IC | 0.1205 | all quiet stocks |
| Quiet in high breadth IC | 0.1248 | top 20% dates |
| Quiet in low breadth IC | 0.1225 | bottom 20% dates |
| Lift (high - low) | +0.0022 | below 0.01 threshold |
| Active only IC | 0.1698 | better than quiet |
| Active in low breadth | 0.1759 | BEST in regime |
| Active in high breadth | 0.1642 | weaker in crowded regime |

**Result:**
- **FAILED**: Quiet stocks in high-breadth dates have only +0.0022 lift over low-breadth dates - essentially noise
- Contrarian hypothesis NOT supported: market activity level does NOT meaningfully modulate quiet-stock quality
- Confirms state_quiet alone is still strong (IC=0.1205, 11/11 positive years)
- Confirms H525: high breadth = bad for signal quality (active in high breadth 0.1642 vs low breadth 0.1759)

**Verdict: FAILED** - No meaningful contrarian effect found.

**Next step:**
- Try next Eureka idea: Multi-Signal Day Superposition (OR of any active state vs single state)