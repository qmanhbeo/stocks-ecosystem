# Session 346 - H534 Active State Duration Sweet Spot

## Hypothesis
Test if time-since-entry into active state (duration bucket) predicts IC decay differently. H526 tested fresh vs sustained, not duration buckets. Sweet spot may exist before decay.

## Command
```bash
cd alpha-research-lab && conda run -n stocks python analysis/h534_active_state_duration_sweet_spot.py
```

## Inputs
- S1 panel: xs_barrier_vol_1d_hose_full.parquet (2015-2025)
- C16: xs_order_pressure_daily.parquet
- Active state: C16 rank <= 0.20

## Saved Artifact
`artifacts/run_summaries/20260517_150058_active_state_duration_sweet_spot_research_branch.json`

## Results

| State | Avg IC | Lift vs Baseline | Positive Years |
|-------|--------|------------------|----------------|
| duration_8pl | 0.1832 | **+0.0530** | 4/4 |
| duration_4_7d | 0.1812 | **+0.0510** | 11/11 |
| duration_2_3d | 0.1722 | **+0.0420** | 11/11 |
| duration_1d | 0.1569 | +0.0267 | 11/11 |
| active_any | 0.1648 | +0.0346 | 11/11 |
| all_rows | 0.1302 | — | 11/11 |

## Result
**PASSED** - duration_8pl beats baseline by +0.0530 (> +0.01 threshold).

## Key Finding
**Longer duration in active state predicts STRONGER signal quality**, not decay. This is the OPPOSITE of expected decay from H526/D046. Sustained presence in the C16<=0.2 regime indicates persistent hidden demand, not signal exhaustion.

## Verdict: PASSED