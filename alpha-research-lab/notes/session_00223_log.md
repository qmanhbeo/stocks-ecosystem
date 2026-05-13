# Session 223: Sector Convergence Contrarian Test

Date: 2026-05-03
Focus: High C16 in fragmented (high kurtosis) sector = contrarian

## Hypothesis
- Claim: High C16 in fragmented sector = contrarian outlier with alpha
- S221 showed: unanimous sector = strong signal
- This tests: OPPOSITE - fragmented sector + high conviction = contrarian?

## Results

| Filter | IC | n |
|--------|-----|-----|
| Baseline | +0.0777 | 553,857 |
| Fragmented sector only | +0.0306 | 97,354 |
| High C16 in fragmented | +0.0351 | 51,612 |

**Diff vs baseline: -55%**

## Verdict: FAILED

- Fragmented sectors have WEAK signals regardless
- High C16 doesn't rescue the weakness
- The "contrarian" theory is wrong direction
- Should kill this branch

## Scripts

- `analysis/x223_sector_contrarian.py`

## Next Steps

- Kill `sector_convergence_contrarian`
- Move to `c16_roc_filtered` or skip to find new directions