# Session 318 - 2026-05-08

## H439: volatility_regime_transition

**Hypothesis:** Volatility expansion vs contraction is a different regime than static high/low vol. Compute vol_z 5d change, test forward IC. High vol + expanding vs high vol + contracting are different regimes.

**Command / code:**
`python3 analysis/h439_volatility_regime_transition.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - C16 order pressure

**Saved artifact:**
`artifacts/run_summaries/20260508_160212_h439_volatility_regime_transition_research_branch.json`

**Results:**

| Metric | Value |
|--------|-------|
| all_rows avg IC | 0.1196 (8/8 pos years) |
| vol_z_q5 (high vol) avg IC | 0.1712 (8/8 pos years) |
| vol_z_q1 (low vol) avg IC | 0.0930 (8/8 pos years) |
| high_vol_expanding avg IC | 0.1670 (8/8 pos years) |
| high_vol_contracting avg IC | 0.1953 (8/8 pos years) |
| low_vol_expanding avg IC | 0.0854 (8/8 pos years) |
| low_vol_contracting avg IC | 0.0940 (8/8 pos years) |
| Expanding vs Contracting lift | +0.0094 |
| HVE vs HVC lift | -0.0283 |

**Decision:** MIXED

**Interpretation:**
- H439 MIXED - interesting pattern but not as a NEW signal
- High vol states are MUCH stronger than low vol states (0.17-0.20 vs 0.09-0.10)
- High vol + contracting is strongest (IC=0.195), but this is just the high-vol regime effect
- The TRANSITION component: contracting slightly beats expanding (+0.009 overall)
- But within high-vol, contracting beats expanding (-0.028, opposite direction)
- This is a vol LEVEL effect, not a transition effect
- The primary finding is: volatility level matters a lot (high vol = strong signal)
- Volatility TRANSITION (expanding vs contracting) is secondary

**Verdict: MIXED** - Not a new signal, but confirms high volatility regime has stronger signal. Use as conditioner/context, not as standalone signal.

**Next step:** This aligns with H411 (volume levels matter) and H434 (signal strength). High-vol states are strong but this is already captured by the H413 ranker (which already includes vol). Stop testing volatility transition as independent signal. Move to next queue item.