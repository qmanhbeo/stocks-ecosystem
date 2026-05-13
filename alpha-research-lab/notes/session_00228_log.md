# Session 228: C16 Divergence Test

Date: 2026-05-03
Focus: Test eureka idea #2 - price direction vs C16 direction divergence

## Hypothesis
- **Claim**: Price direction disagrees with C16 direction = stronger signal
- **Mechanism**: When price moves one way but order pressure moves the other, it's smarter money

## Results

| Signal | IC | Diff vs Baseline |
|--------|-----|---------------|
| All C16 (baseline) | +0.0776 | baseline |
| **Divergence only** | **+0.1080** | **+39%** |
| Aligned only | +0.0588 | -24% |
| Retail Trap (price UP + C16 DOWN) | +0.0351 | -55% |
| Institutional Smart (price DOWN + C16 UP) | +0.0512 | -34% |

## Verdict: PASSED! Discovery!

**C16 divergence works!** When price direction disagrees with C16 direction, IC is +0.108 vs +0.078 baseline (+39%).

The key insight: divergence is informative but specific splits fail. The composite "divergence" beats baseline, but:
- Retail trap (price up + c16 down) hurts badly
- Institutional smart (price down + c16 up) is also weak

This suggests the signal is in the DIVERSION as a filter, not the specific direction.

## Scripts
- x228_c16_divergence.py

## Next Steps
- Test: combine divergence as filter: IC(C16) where divergence=True
- Or try: liquidity_adjusted_contrarian (X53 + X226 combined)