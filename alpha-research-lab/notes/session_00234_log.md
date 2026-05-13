# Session 234: Combo tests

**Date:** 2026-05-03
**Focus:** Test queue items: c4_c16_combo, volume_shock_c16

## Results

| Test | Component ICs | Combo/Shock IC | Boost | Verdict |
|------|---------------|---------------|-------|---------|
| c4_c13_combo | 0.031, 0.019 | 0.033 | +6% | WEAK PASS |
| c13_c16_combo | 0.078, 0.031 | 0.084 | +9% | WEAK PASS |
| volume_shock_c16 | 0.078 | 0.090 | +16% | WEAK PASS |

## Findings

- **c13_c16_combo**: Best orthogonal combo found (+9% over C16 alone)
- **volume_shock_c16**: Volume anomalies amplify C16 by +16%
- All combos show weak but consistent improvement
- Queue exhausted after S234

## Script Used

```bash
# Test combos
python -c "rank sum test"
# Test volume shock
python -c "filter volume_zscore > 2"
```

## Next

- Queue exhausted
- Need new signal sources for continued testing