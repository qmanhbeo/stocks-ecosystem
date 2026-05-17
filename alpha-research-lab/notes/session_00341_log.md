# Session 341 — H528 Quiet-State × Low-Breadth Intersection

**Date:** 2026-05-17  
**Experiment:** H528 — Quiet-State × Low-Breadth Intersection Test

## Hypothesis

Idea #13 from bright-mind queue:
- state_quiet is STRONG (IC=0.1552, 11/11 pos yrs) — discovered in H524
- low_breadth dates have BETTER IC (0.1542 vs high breadth 0.1149) — from H525  
- Both strong independently; intersection is untested

## Command

```bash
cd /home/manh/stocks-ecosystem/alpha-research-lab
python3 analysis/h528_quiet_low_breadth_intersection.py
```

## Inputs

- S1 panel: `xs_barrier_vol_1d_hose_full.parquet` (2015-2025)
- C16 panel: `xs_order_pressure_daily.parquet` (rank column)
- Date breadth: computed from active stock count (< 0.2 threshold)
- Low breadth = bottom 25% of date-level active counts

## Results

| Signal | IC | Lift vs Baseline | N | Pos Years |
|--------|-----|-------------------|-------|-----------|
| Baseline (all rows) | 0.1277 | — | 821,764 | — |
| state_quiet (rank>=0.75) | 0.1552 | +0.0276 | 192,612 | 11/11 |
| is_low_breadth | 0.1542 | +0.0266 | 166,230 | 11/11 |
| state_active (rank<0.2) | 0.1597 | +0.0320 | 127,045 | 11/11 |
| **quiet + low_breadth** | 0.1644 | +0.0367 | 37,649 | 9/9 |
| **active + low_breadth** | 0.2013 | +0.0736 | 20,030 | 7/9 |

## Analysis

1. **Quiet + Low-Breadth Intersection**: IC=0.1644 beats both components (quiet 0.1552, low_breadth 0.1542) by ~+0.009, but does NOT exceed max_single + 0.01 threshold (would need 0.1652). **Verdict: MIXED** — intersection captures some additional signal but not beyond threshold.

2. **Active + Low-Breadth Intersection**: IC=0.2013 beats active alone (0.1597) by +0.0416! This is a significant finding — low_breadth dates strongly amplify the active-state signal.

## Key Finding

**Low-breadth dates act as a regime amplifier for active-state signals.** The intersection of active (rank < 0.2) + low_breadth dates produces IC=0.2013, which is substantially stronger than either component alone:
- Active alone: 0.1597
- Active + low_breadth: 0.2013 (+0.0416, +26% boost)

This aligns with H525's finding that high breadth dates have WORSE IC (0.1149 vs 0.1454 for low breadth). The mechanism: when fewer stocks activate together, there's less crowd noise and the signal quality improves.

## Verdict

- **Quiet + Low-Breadth**: MIXED (0.1644 > min but not > max + 0.01)
- **Active + Low-Breadth**: SIGNIFICANT FINDING — +0.0416 boost over active alone, 7/9 positive years

## Saved Artifact

`artifacts/run_summaries/20260517_143514_quiet_low_breadth_intersection_research_branch.json`

## Next Actions

1. ~~H528~~ — DONE (MIXED for quiet, significant for active)
2. Test Anti-Breadth Entry Signal (idea #19) — explicitly select low-breadth dates as entry days
3. Test Breadth-Weighted Position Sizing (idea #21) — continuous 1/breadth weighting

## Dead-End Candidate

D057: Quiet + Low-Breadth Intersection does NOT exceed threshold — intersection not promotion-worthy.

But Active + Low-Breadth IS a finding — update signal library if confirmed.