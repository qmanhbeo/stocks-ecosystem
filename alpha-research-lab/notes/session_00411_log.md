# Session 411 - H625 Ticker-Specific Breadth (Self-Reference)

**Date**: 2026-05-18

## Hypothesis

Queue item 129: ticker self-referenced breadth context may outperform
market-wide breadth conditioning.

## Command

```bash
python analysis/h625_ticker_self_breadth_reference.py
```

## Inputs

- Cached base panel from H621 (`artifacts/cache/h62x_base_panel_2015_2025.parquet`)

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_182642_h625_ticker_self_breadth_reference_research_branch.json`
- Results: `artifacts/research_branches/20260518_182642_h625_ticker_self_breadth_reference_results.parquet`
- Yearly: `artifacts/research_branches/20260518_182642_h625_ticker_self_breadth_reference_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_self_hist_hot | 0.2475 | 13,692 | 11/11 |
| composite_2plus | 0.2456 | 29,542 | 11/11 |
| composite_market_low | 0.2406 | 3,392 | 11/11 |
| composite_self_hist_quiet | 0.2220 | 1,185 | 6/6 |

Derived:
- best self-variant lift vs market-low baseline = `+0.0069`

## Result

Ticker self-history context is informative (hot-history > quiet-history), but
lift over market-low breadth is below promotion threshold.

## Verdict: MIXED

## Next

- Advance to queue item 130 (Signal Decay Acceleration / Exit Zone).
