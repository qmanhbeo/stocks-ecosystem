# Session 350 - H542 Breadth Transition Momentum

## Hypothesis
Direction of breadth change (contracting vs expanding) may matter more than absolute level. Test if breadth_contracting (high→low) has stronger IC than steady_low.

## Command
```bash
cd alpha-research-lab && conda run -n stocks python analysis/h542_breadth_transition_momentum.py
```

## Inputs
- S1 panel: xs_barrier_vol_1d_hose_full.parquet (2015-2025)
- C16: xs_order_pressure_daily.parquet
- Breadth: active stock count per date
- Change: 5-day delta of active count

## Saved Artifact
`artifacts/run_summaries/20260517_150617_breadth_transition_momentum_research_branch.json`

## Results

| State | Avg IC | Lift vs Baseline | Rows |
|-------|--------|------------------|------|
| contracting_to_low | 0.1467 | +0.0165 | 52,834 |
| steady_low | 0.1463 | +0.0161 | 101,138 |
| low_breadth | 0.1423 | +0.0121 | 168,151 |
| all_rows | 0.1302 | — | 826,404 |
| expanding_to_high | 0.1152 | -0.0150 | 33,043 |
| high_breadth | 0.1192 | -0.0110 | 137,143 |

## Result
**MIXED** - contracting_to_low beats baseline (+0.0165) but is essentially tied with steady_low (+0.0004, below +0.01 threshold).

## Key Finding
The transition direction adds almost NOTHING over static low breadth. Both contracting_to_low and steady_low achieve the same IC (~0.146). The "crowd dispersing" mechanism doesn't add predictive value beyond just being in low breadth.

This confirms the earlier H525 finding: low breadth is the regime marker, not the path to it.

## Verdict: MIXED