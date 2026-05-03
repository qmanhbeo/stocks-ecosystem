# Session 227: C16 Acceleration Test

Date: 2026-05-03
Focus: Test eureka idea #1 - C16 velocity vs level

## Hypothesis
- **Claim**: C16 velocity (ROC) matters MORE than C16 level
- **Mechanism**: Order flow acceleration = smarter money than static level

## Results

| Signal | IC | Diff vs Baseline |
|--------|-----|---------------|
| C16 Level | +0.0778 | baseline |
| C16 ROC | +0.0560 | -28% |
| C16 Combined | +0.0664 | -15% |

## Verdict: FAILED

C16 level beats ROC by 28%. The "acceleration" hypothesis is wrong - static C16 level is the stronger signal.

## Scripts
- x227_c16_acceleration.py

## Next Steps
- Try other eureka ideas:
  - c16_divergence (price vs C16 direction)
  - liquidity_adjusted_contrarian (X53 + X226 combined)
  - deep_down_only (market bottom 20%)