# Session 136 Log — 2026-05-09

## BU3: multi_day_c23_accumulation

**Decision: MIXED**

### Hypothesis
C23 (high_illiq × vol_expansion) on consecutive days works better than single-day C23. Sustained illiq × vol expansion represents stronger regime.

### Results

| State | IC | Lift vs Baseline | Rows | Positive Years |
|-------|-----|-----------------|------|----------------|
| all_rows (baseline) | 0.1302 | — | 826,404 | 11/11 |
| single_day_c23 | 0.2007 | +0.0705 | 29,188 | 11/11 |
| consecutive_2d_c23 | 0.2014 | +0.0712 | 20,587 | 11/11 |
| consecutive_3d_c23 | 0.1925 | +0.0623 | 9,478 | 11/11 |

### Key findings

1. **consecutive_2d_c23 is marginally best**: IC=0.2014, +0.0712 lift over baseline
2. **single_day_c23 is nearly as good**: IC=0.2007, +0.0705 lift — only 0.0007 IC below 2d
3. **consecutive_3d_c23 degrades**: IC=0.1925 — MORE accumulation HURTS after 2 days
4. Pattern consistent with **D046**: signals decay at multi-day horizons

### Interpretation

- 2-day consecutive C23 is marginally better than single-day (+0.0007 IC)
- 3-day is WORSE than 2-day — diminishing returns + signal decay
- Confirms D046 finding: signals work best at 1d horizon
- Not worth using consecutive as a filter — single_day_c23 is effectively equivalent

### Verdict: MIXED

- 2d beats single day but only marginally (+0.0007 IC < +0.005 threshold)
- 3d degrades, confirming signal decay pattern
- No actionable edge from consecutive filtering

### Next step
Continue with BU4 (cross_signal_day_complementarity) — test if C23/C24/C25/C26 fire on different days and whether routing between them improves IC.

**Saved artifact:** `artifacts/run_summaries/20260509_235929_multi_day_c23_accumulation_research_branch.json`

**Source anchor:** F420 (from batch 16), D046 (signal decay confirmed)