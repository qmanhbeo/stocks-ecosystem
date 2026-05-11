# Session 00009 - Cash Mechanics Autopsy (2026-05-11)

## Objective

Trace why heuristic-trader stays under-invested in bull years even when signal
quality is present.

## Context

alpha-research-lab H510 returned NEGATIVE FINDING:
- C23 active state is NOT missing in failure bull years
- 2017 had stronger IC (0.149) than 2021 (0.123) and 2022 (0.082)
- Cash drag is NOT explained by missing latent signal states
- Problem is execution / portfolio construction / filter mechanics

## Method

Ran `analyze_cash_mechanics.py` on `blend_70_30_top5` strategy with:
- Focus years: 2017, 2021, 2022, 2025
- Traced every rebalance date
- Counted candidates considered, passed, bought
- Identified bottleneck

## Key Results

| Year | Avg Cash % | Avg Invested % | Avg Holdings | Avg Candidates Passed | Underinvested % |
|------|------------|---------------|--------------|----------------------|-----------------|
| 2017 | 56.5% | 43.5% | 2.16 | 2.16 | 100% |
| 2021 | 55.4% | 44.6% | 3.20 | 3.20 | 72% |
| 2022 | 74.4% | 25.6% | 2.46 | 2.46 | 83% |
| 2025 | 70.4% | 29.6% | 2.80 | 2.80 | 80% |

**Main mechanism**: FILTER BOTTLENECK
- Average candidates passed per rebalance: only 2-3 (far below target of 5)
- 2017 worst: only 2.16 candidates passed
- 2021 best: 3.20 candidates passed
- No price-missing issues (0%)
- No cash-insufficiency issues (0%)

## Conclusion

Hypothesis A confirmed: **Filter bottleneck** is the main cause of cash drag.

The liquidity/tradability filters are rejecting too many candidates. Even though
the signal has valid IC, not enough candidates pass the filter to fill the
portfolio.

This is NOT caused by:
- Position sizing (0% failed due to insufficient cash)
- Price missing (0% failed due to missing prices)
- Top-k * 3 cap (candidates pass but are filtered out before the cap)

## Artifact Path

`artifacts/cash_mechanics/20260511_175932/`

Files:
- `rebalance_cash_mechanics.csv`
- `year_cash_mechanics_summary.csv`
- `summary.json`
- `README.md`

## Next Action

Investigate why filters reject too many candidates:
- Check trad_lookup coverage by year
- Check liquid_lookup coverage by year
- Determine if some years have systematically worse coverage
- Consider relaxing filters OR improving coverage data