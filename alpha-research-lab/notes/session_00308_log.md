# Session 308 - 2026-05-08

## H429: signal_half_life_router

**Hypothesis:** Alpha states should carry estimated decay half-life rather than one universal label. Different signals should win only on their natural horizon.

**Command / code:**
`python3 analysis/h429_signal_half_life_router.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - volume data

**Saved artifact:**
`artifacts/run_summaries/h429_signal_half_life_router_summary.json`

**Results:**

| Half-Life Class | Best Horizon | Best Lift | Note |
|-----------------|--------------|-----------|------|
| s1_momentum | 1d | -0.1134 | All horizons negative vs 1d baseline |
| s1_reversion | 1d | -0.0948 | All horizons negative vs 1d baseline |
| vol_high | 1d | -0.1132 | All horizons negative vs 1d baseline |
| vol_low | 1d | -0.1072 | Becomes negative at 5d+ (-0.0020) |

**Baseline ICs (1d):** s1_momentum +0.1368, s1_reversion +0.1123, vol_high +0.1281, vol_low +0.1166

**Result:**
All half-life classes perform WORSE at longer horizons - no signal shows horizon-specific advantage. The 1d baseline is always the best. vol_low becomes negative at 5d+ horizons, indicating signal loss. This does NOT support the half-life routing hypothesis.

**Verdict: FAILED**

**Interpretation:**
- Signal decay is uniform across declared half-life classes
- No evidence that momentum signals decay slower than reversion signals at longer horizons
- No evidence that volume state predicts horizon-specific performance
- The current fixed 1d barrier target remains optimal

**Next step:** Continue to next queue item - candidate_temperature_entropy (item #3)