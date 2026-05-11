# Session 00015 - Depth Frontier Walk-Forward Results (2026-05-11)

## Context

- Session 00014: Valid walk-forward execution ablation showing depth20 improves 2021 but breaks 2022
- This session: Depth frontier mapping (3, 5, 10, 15, 20) for fixed_initial sizing

## Key Results

### Blend (blend_70_30_top5) - Fixed Initial Sizing

| Depth | 2021 Excess | 2022 Excess | 2022 Total | Trade-off |
|-------|-------------|-------------|------------|-----------|
| 3 (baseline) | +49.2% | +31.9% | -0.9% | BEST for 2022 |
| 5 | +58.0% | +14.6% | -18.2% | Moderate |
| 10 | +81.3% | +2.6% | -30.1% | Aggressive |
| 15 | +81.3% | +2.0% | -30.8% | Aggressive |
| 20 | +81.3% | +2.0% | -30.8% | Aggressive (same as 15) |

### S1 (s1_top5_rebal10) - Fixed Initial Sizing

| Depth | 2021 Excess | 2022 Excess | 2022 Total | Trade-off |
|-------|-------------|-------------|------------|-----------|
| 3 (baseline) | -4.3% | +25.3% | -7.5% | Best 2022 |
| **5** | **+5.7%** | **+27.5%** | **-5.3%** | **SWEET SPOT** |
| 10 | +15.0% | +2.8% | -29.9% | Aggressive |
| 15 | +15.0% | +2.8% | -29.9% | Aggressive |
| 20 | +15.0% | +2.8% | -29.9% | Aggressive (same as 15) |

## Decision Questions Answered

1. **Is trade-off monotonic?** YES for blend, PARTIAL for s1
2. **Does depth5 or depth10 improve 2021 without destroying 2022?**
   - Blend: NO - depth5 hurts 2022 (+14.6% vs +31.9%)
   - S1: **YES - depth5 improves 2021 (+5.7% vs -4.3%) AND preserves 2022 (+27.5% vs +25.3%)**
3. **Is depth20 too aggressive?** YES for both - plateaus at depth=10, depth15/20 same as 10
4. **Does s1 behave differently?** YES - s1 has a sweet spot (depth5), blend doesn't
5. **Is there any depth that improves both 2021 and preserves 2022?**
   - Blend: **NO** - all depths that improve 2021 hurt 2022
   - S1: **YES - depth5** improves both
6. **Conclusion: Bull/bear exposure frontier?** For blend YES, for s1 NO (depth5 works)

## Key Insight

**s1_top5_rebal10_depth5 is the only variant that improves both 2021 AND preserves 2022:**
- 2021: -4.3% → +5.7% (improvement)
- 2022: +25.3% → +27.5% (preserved, actually slightly better!)
- 2022 total: -7.5% → -5.3% (less negative)

This is a genuine finding: S1 signal benefits from moderate candidate expansion (depth=5), but blend signal saturates earlier.

## Artifact Path

`artifacts/execution_depth_frontier_walkforward/20260511_184054/`

## Next Steps

1. For blend: either accept trade-off (depth10 for 2021, baseline for 2022) or use regime-aware
2. For s1: consider depth5 as the balanced choice
3. Need to verify if this finding is stable across validation

**Do NOT finalize** - need validation pass and parity check first.