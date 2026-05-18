# Session 417 - H644 Formalized Retests (Priority 6)

**Date**: 2026-05-18

## Hypothesis

Formalize and strictly retest the six highest-value unresolved hypotheses from
post-backlog review:
- #99 triple amplification
- #91 volatility expansion depth conditioner
- #100 accumulation × low-breadth composite
- #103 tight × high-accumulation interaction
- BM07 hierarchical context gating
- BM17 Wardrop-style sector pressure equilibrium

## Command

```bash
python analysis/h644_formalized_retests.py
```

## Inputs

- Base panel cache: `artifacts/cache/h62x_base_panel_2015_2025.parquet`
- Tradability: `data/features/execution/tradability_daily.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- Sector map: `data/features/sector_classification.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_214804_h644_formalized_retests_research_branch.json`
- Decisions: `artifacts/research_branches/20260518_214804_h644_formalized_retests_decisions.parquet`
- Results: `artifacts/research_branches/20260518_214804_h644_formalized_retests_results.parquet`
- Yearly: `artifacts/research_branches/20260518_214804_h644_formalized_retests_yearly.parquet`

## Results

| Item | Verdict | Better vs Base | Lift | Better Rows | Base Rows |
|------|---------|----------------|------|-------------|-----------|
| 99 | PASSED | triple_amp vs pair_tight_iso | +0.0271 | 1,717 | 9,123 |
| 91 | PASSED | vol_deep vs vol_mild | +0.0572 | 82,268 | 80,615 |
| 100 | FAILED | high_accum_low_breadth vs high_accum | -0.0017 | 37,200 | 183,074 |
| 103 | PASSED | tight_high_accum vs tight_low_accum | +0.0699 | 112,703 | 15,531 |
| BM07 | MIXED | best_macro_router_block vs router_pooled | +0.0062 | n/a | n/a |
| BM17 | FAILED | high-dispersion vs low-dispersion sector-pressure state | -0.0045 | n/a | n/a |

Batch totals:
- PASSED: 3
- MIXED: 1
- FAILED: 2
- DATA_GATED: 0

## Result

Formalization converts prior data-gated statuses into clear outcomes:
- #91 and #103 are now promotable passes.
- #100 and BM17 are now explicit fails.
- BM07 remains only marginally positive (mixed), below strict promotion.
- #99 remains robustly positive under stricter comparison.

## Verdict: BATCH_COMPLETED

## Next

- Promote durable pass/fail updates into findings/dead-ends and update
  live_state to remove stale data-gated statuses.
