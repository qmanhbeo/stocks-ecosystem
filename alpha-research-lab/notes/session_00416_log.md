# Session 416 - H643 Bright-Mind Backlog Batch (Wake/Sleep + Traffic)

**Date**: 2026-05-18

## Hypothesis

Resolve the remaining Bright-Mind backlog using first-honest-test proxies for
all wake/sleep and traffic-inspired items.

Covered items:
- 11 wake/sleep backlog items
- 6 traffic-inspired backlog items

## Command

```bash
python analysis/h643_brightmind_remaining_batch.py
```

## Inputs

- Cached base panel: `artifacts/cache/h62x_base_panel_2015_2025.parquet`
- Tradability: `data/features/execution/tradability_daily.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_212901_h643_brightmind_remaining_batch_research_branch.json`
- Decisions: `artifacts/research_branches/20260518_212901_h643_brightmind_remaining_batch_decisions.parquet`
- Results: `artifacts/research_branches/20260518_212901_h643_brightmind_remaining_batch_results.parquet`
- Yearly: `artifacts/research_branches/20260518_212901_h643_brightmind_remaining_batch_yearly.parquet`

## Results

| Item | Verdict | Key comparison | Lift |
|------|---------|----------------|------|
| BM01 nested-phase stack | DATA_GATED | triple vs pair | NaN |
| BM02 arousal-fatigue spread | PASSED | af_high vs af_low | +0.0592 |
| BM03 wake pulse vs chronic | PASSED | pulse vs chronic | +0.0507 |
| BM04 local-global desync | FAILED | desync vs sync | -0.0026 |
| BM05 cooldown half-life | FAILED | 3-5d vs 1-2d | -0.0212 |
| BM06 cycle-stability gate | PASSED | stable_lowb vs unstable_lowb | +0.0761 |
| BM07 hierarchical context | DATA_GATED | macro A vs C | NaN |
| BM08 fatigue threshold | FAILED | low fatigue vs high fatigue | -0.0236 |
| BM09 phase-lag gate | FAILED | allow vs suppress | -0.0048 |
| BM10 regime-conditional router | PASSED | c23_only vs c24_only | +0.0772 |
| BM11 macro persistence gate | PASSED | established vs new | +0.0170 |
| BM12 fundamental diagram | FAILED | mid density vs high density | -0.0045 |
| BM13 shockwave block | FAILED | non-shock vs shock | -0.0033 |
| BM14 relaxation gap | PASSED | low gap vs high gap | +0.0160 |
| BM15 headway-safety analogue | PASSED | wide vs tight headway | +0.0803 |
| BM16 mesoscopic distribution | MIXED | low-tail vs high-tail | +0.0011 |
| BM17 Wardrop sector equilibrium | DATA_GATED | sector dispersion states | NaN |

Batch totals:
- PASSED: 7
- MIXED: 1
- FAILED: 6
- DATA_GATED: 3

## Result

The Bright-Mind backlog is now first-pass addressed. The strongest surviving
signals are arousal-fatigue spread, wake-pulse, cycle-stability, router split,
macro persistence, relaxation-gap, and headway-wide states. Several higher-level
macro/context items remain data-gated and require richer sector or macro-state
contracts before promotion.

## Verdict: BATCH_COMPLETED

## Next

- Reconcile queue sections in `live_state.md` so no unresolved backlog items remain.
- Promote durable outcomes and dead-ends into compact memory layers.
