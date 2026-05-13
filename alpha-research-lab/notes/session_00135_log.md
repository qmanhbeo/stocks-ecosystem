# Session 135 Log — Batch 17 BU2 c17_standalone (2026-05-09)

## Objective

Run batch 17 experiments, continuing with BU2: c17_standalone.
Test raw C17 (order_volume_ratio without cross-sectional ranking) vs ranked C16.

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one research script:
- `analysis/h498_c17_standalone.py`

### BU2 - c17_standalone (H498)

**Hypothesis:**
C17 (raw order_volume_ratio without ranking) as standalone signal may preserve
more signal than the ranked C16 (like F414 illiq alone vs C23 combo).

**Command / code:**
`python analysis/h498_c17_standalone.py`

**Inputs:**
- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- C16 features: `data/features/xs_order_pressure_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260509_235542_c17_standalone_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| panel_rows | 810,201 | |
| baseline (all_rows) IC | 0.1299 | |
| c17_raw_top20 IC | 0.1623 | +0.0324 lift, 11/11 |
| c16_rank_top20 IC | 0.1670 | +0.0371 lift, 11/11 |
| c17_c16_combo IC | 0.1670 | +0.0371 lift, same as C16 alone |
| c17_only IC | 0.1141 | +0.0289, sparse (15,763 rows) |
| c16_only IC | NaN | too sparse (189 rows) |
| c17_raw_bottom20 IC | 0.1588 | +0.0289, contrarian works |
| c16_rank_bottom20 IC | 0.1648 | +0.0349, contrarian works |

**Result:**
The hypothesis is NOT supported. Raw C17 (IC 0.1623) is WEAKER than ranked C16
(IC 0.1670) by -0.0048. The ranking does NOT strip away useful information;
it actually helps slightly. Both high and low states work (symmetric signal).

**Verdict: FAILED**

---

## Branch decision

BU2 is FAILED:
- Raw C17 is WORSE than ranked C16 by -0.0048 IC
- The blending/normalization in C16 does NOT strip useful information
- Both top and bottom 20% work — signal is symmetric
- Do NOT use raw C17 as standalone signal

Next in batch 17:
- BU3: multi_day_c23_accumulation
- BU4: cross_signal_day_complementarity
- BU5: sector_vol_regime
- BU6: c26_without_vol_expansion_isolation
- BU7: foreign_flow_regime_as_conditioner
- BU8: earnings_quality_regime_interaction