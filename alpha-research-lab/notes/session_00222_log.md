# Session 222: Dynamic Liquidity Regime Test

Date: 2026-05-03
Focus: Test C16 by market liquidity regime (high vs low market-wide liquidity days)

## Hypothesis
- Claim: C16 strength varies by market liquidity regime
- Baseline: S221 showed Liquid C16 works (+25%), but that's stock-level liquidity
- This tests: market-wide regime effect

## Results

| Regime | IC | n |
|--------|-----|-----|
| Overall | +0.0777 | 555,840 |
| High market liquidity | +0.0809 | 269,251 |
| Low market liquidity | +0.0744 | 286,589 |

**Diff: +0.0065** (high - low)

## Verdict: WEAK PASS

- C16 is slightly better in high-liquidity market regimes
- But the difference is small (~8% boost)
- Not enough to warrant regime switching
- Could be useful for sizing only

## Scripts

- `analysis/x222_dynamic_regime.py`

## Next Steps

- Test next branch: `sector_convergence_contrarian`
- Or kill this if no material difference