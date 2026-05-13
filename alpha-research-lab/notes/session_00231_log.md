# Session 231: Walk-Forward Validation

Date: 2026-05-03
Focus: Validate C16 discoveries using walk-forward (train < Y, test = Y)

## Hypothesis
- **Claim**: Walk-forward confirms robustness of findings
- **Risk**: Single split may miss regime shifts

## Results

### Walk-Forward IC (2017-2025)

| Year | Baseline | DOWN | Liquid | Triple |
|------|----------|------|--------|--------|
| 2017 | +0.077 | +0.096 | +0.096 | +0.156 |
| 2018 | +0.062 | +0.101 | +0.072 | +0.161 |
| 2019 | +0.063 | +0.094 | +0.085 | +0.162 |
| 2020 | +0.092 | +0.108 | +0.096 | +0.163 |
| 2021 | +0.105 | +0.110 | +0.118 | +0.142 |
| 2022 | +0.090 | +0.091 | +0.097 | +0.121 |
| 2023 | +0.058 | +0.067 | +0.063 | +0.138 |
| 2024 | +0.061 | +0.076 | +0.071 | +0.134 |
| 2025 | +0.071 | +0.087 | +0.081 | +0.129 |

### Summary

| Signal | WF Mean | vs Baseline | Positive Years |
|--------|---------|-------------|----------------|
| Baseline | +0.075 | - | 9/9 |
| DOWN (X226) | +0.092 | +22% | 9/9 |
| Liquid (X53) | +0.086 | +15% | 9/9 |
| **Triple (X229)** | **+0.145** | **+92%** | **9/9** |

## Verdict: ROBUST - ALL SIGNALS CONFIRMED

All signals work in every single year (9/9 positive IC).
Triple Storm maintains +92% boost in walk-forward.
No regime degradation over time.

## Scripts
- x231_walk_forward.py

## Next Steps
- C16 branch is VERIFIED and CLOSED
- Move to new signal families