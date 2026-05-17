# Session 353 — H545 Breadth-Adaptive Exit Rules

## Hypothesis

H526 found exit timing (fresh vs sustained) makes NO difference overall. But H525 found high-breadth dates have weaker signal than low-breadth dates. Now test if exit timing differs BY breadth regime.

## Command / Code

```bash
python analysis/h545_breadth_adaptive_exit.py --start-year 2015 --end-year 2025
```

## Inputs

- S1 decision panel (2015-2025)
- C23 signal (high_illiq × vol_expansion)
- Breadth: fraction of tickers with C23 signal per date
- Exit timing: fresh (same day) vs sustained (2d+)

## Saved Artifact

`artifacts/run_summaries/20260517_151919_breadth_adaptive_exit_rules_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| all_rows (baseline) | 0.1298 | 809,019 | 11/11 |
| low_breadth_any | 0.2712 | 4,745 | 5/11 |
| high_breadth_any | 0.2525 | 10,767 | 11/11 |
| low_breadth_fresh | 0.2393 | 3,435 | 1/11 |
| low_breadth_sustained | NaN | 1,310 | 0/11 |
| high_breadth_fresh | 0.2625 | 7,664 | 9/11 |
| high_breadth_sustained | NaN | 3,103 | 0/11 |

## Analysis

- **Breadth confirms H525**: Low breadth (0.2712) > High breadth (0.2525) = stronger signal
- **Exit timing cannot be tested**: Sustained states are too sparse (0 positive years)
- **Data limitation**: The intersection of low breadth + sustained holding is too rare to evaluate

## Verdict: FAILED (data-gated)

The hypothesis cannot be properly tested due to data sparsity. The sustained exit states (holding for 2+ days) combined with breadth filtering don't have enough rows with positive IC years to compute valid comparisons.