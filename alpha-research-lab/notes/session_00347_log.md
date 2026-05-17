# Session 347 - H535 Triple-Intersection Alpha

## Hypothesis
Test tight_capacity + low_breadth + active (C16<0.2) three-way intersection. 
H531 (tight+low, 0.1979) + H528 (active+low, 0.2013) suggest triple could exceed 0.21.

## Command
```bash
cd alpha-research-lab && conda run -n stocks python analysis/h535_triple_intersection_alpha.py
```

## Inputs
- S1 panel: xs_barrier_vol_1d_hose_full.parquet (2015-2025)
- C16: xs_order_pressure_daily.parquet
- Active state: C16 rank <= 0.20
- Tight capacity: bottom 20% by order_volume_ratio within each date
- Low breadth: bottom 20% by active count within each date

## Saved Artifact
`artifacts/run_summaries/20260517_150242_triple_intersection_alpha_research_branch.json`

## Results

| State | Avg IC | Lift vs Baseline | Rows |
|-------|--------|------------------|------|
| triple_intersection | 0.1956 | +0.0653 | 19,886 |
| active_low_breadth | 0.1956 | +0.0653 | 19,886 |
| tight_low_breadth | 0.1890 | +0.0588 | 30,821 |
| is_active | 0.1648 | +0.0346 | 127,566 |
| tight_active | 0.1647 | +0.0345 | 127,530 |
| tight_capacity | 0.1588 | +0.0285 | 163,147 |
| low_breadth | 0.1423 | +0.0121 | 168,151 |
| all_rows | 0.1302 | — | 826,404 |

## Result
**MIXED** - triple_intersection beats baseline by +0.0653 (> +0.01) but is IDENTICAL to active_low_breadth (same rows, same IC).

## Key Finding
**tight_capacity is redundant when combined with active+low_breadth**. The three-way intersection produces exactly the same rows as the two-way active+low_breadth filter. The active state (C16<=0.2) already captures the relevant signal, and adding tight_capacity (low raw order volume) adds nothing.

This is consistent with H528 finding that active+low_breadth is the strongest combo (IC=0.2013). The tight_capacity component from H531 doesn't generalize when combined with the active filter.

## Verdict: MIXED