# Session 395 - H609 Triple-Factor Alpha Portfolio

**Date**: 2026-05-18

## Hypothesis

Queue item 109: combine three strong components:

- F445 `composite_2plus` (2+ signals)
- F440 `cofire_q1` isolation context
- F441 `persist_q4` sustained active-state context

Test whether the triple intersection beats `composite_2plus` baseline.

## Command

```bash
python analysis/h609_triple_factor_alpha_portfolio.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- Order pressure: `data/features/xs_order_pressure_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_162111_h609_triple_factor_alpha_portfolio_research_branch.json`
- Results: `artifacts/research_branches/20260518_162111_h609_triple_factor_alpha_portfolio_results.parquet`
- Yearly: `artifacts/research_branches/20260518_162111_h609_triple_factor_alpha_portfolio_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus | 0.2445 | 29,542 | 11/11 |
| composite_2plus_persist_q4 | 0.2424 | 16,570 | 11/11 |
| cofire_q1_c23 | 0.2423 | 8,550 | 11/11 |
| cofire_q1_persist_q4 | 0.2413 | 5,054 | 11/11 |
| composite_2plus_cofire_q1 | 0.2224 | 6,647 | 11/11 |
| triple_factor_109 | 0.2172 | 3,796 | 11/11 |
| persist_q4 | 0.1760 | 197,217 | 11/11 |
| all_rows | 0.1298 | 809,019 | 11/11 |

## Result

Triple-factor stacking fails under the current contract:

- lift(`triple_factor_109` vs `composite_2plus`) = `-0.0273`
- both pair terms involving `composite_2plus` are below `composite_2plus`

## Verdict: FAILED

## Next

- Advance to queue item 113 (Regime Transition Timing Alpha).
