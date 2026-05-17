# Session 343 — H530 Breadth-Weighted Position Sizing

**Date:** 2026-05-17  
**Experiment:** H530 — Breadth-Weighted Position Sizing Test

## Hypothesis

From queue item #5 after H529:
- H529 showed: binary low_breadth filter = IC 0.1542 vs baseline 0.1277 (+0.0266)
- Question: Does continuous 1/breadth weighting add value beyond binary filter?

## Command

```bash
cd /home/manh/stocks-ecosystem/alpha-research-lab
python3 analysis/h530_breadth_weighted_position_sizing.py
```

## Inputs

- S1 panel: `xs_barrier_vol_1d_hose_full.parquet` (2015-2025)
- C16 panel: `xs_order_pressure_daily.parquet`
- Date breadth: active_count and active_fraction computed per date
- Continuous weight: 1 / (active_fraction + 0.01), normalized to mean=1

## Results

| Signal | IC | Lift vs Baseline | N | Pos Years |
|--------|-----|-------------------|-------|-----------|
| Baseline (all rows) | 0.1277 | — | 821,764 | 11/11 |
| Binary low_breadth filter | 0.1428 | +0.0151 | 178,627 | 11/11 |
| Binary high_breadth filter | 0.1179 | -0.0098 | 233,635 | 11/11 |
| **Weighted score** (S1 × inv_breadth) | 0.1057 | **-0.0220** | 821,764 | — |
| **Weighted rank** (rank of weighted score) | 0.1407 | +0.0130 | 821,764 | — |

## Analysis

1. **Weighted score (S1 × inv_breadth)**: IC=0.1057 is WORSE than baseline by -0.0220!
   - Direct multiplication amplifies low-breadth signals too much, distorting rank
   - This approach FAILS

2. **Weighted rank**: IC=0.1407 (+0.0130) is better than baseline but still slightly below binary filter (0.1428)
   - Using rank within date of weighted scores is better than raw weighted score
   - But still not better than binary filter

3. **Binary filter remains superior**: The discrete low/high breadth filter (IC=0.1428) outperforms continuous weighting approaches.

## Key Finding

**Continuous 1/breadth weighting does NOT beat the binary filter.** The binary approach of simply selecting low-breadth dates as entry days (from H529) remains the best implementation of the breadth timing mechanism.

## Verdict

**FAILED** — continuous weighting does not add value over binary filter.

## Saved Artifact

`artifacts/run_summaries/20260517_144255_breadth_weighted_position_sizing_research_branch.json`

## Next Steps

Queue advances to:
6. **Active-State Regime Amplifier** - use low_breadth as positive filter for active state (next in queue)