# Session 354 — H546 Capacity Direction as Signal Weight

## Hypothesis

H538 found tight_expanding > tight_contracting by +0.0144. Now test using capacity direction as continuous weight modifier.

## Command / Code

```bash
python analysis/h546_capacity_weight.py --start-year 2015 --end-year 2025
```

## Inputs

- S1 decision panel (2015-2025)
- Order stats for capacity (order count proxy via total_volume)
- Capacity direction: 5d change in order count (expanding vs contracting)

## Saved Artifact

`artifacts/run_summaries/20260517_152031_capacity_direction_as_signal_weight_research_branch.json`

## Results

| State | IC | Lift vs Baseline | Rows | Positive Years |
|-------|-----|-----------------|------|----------------|
| all_rows (baseline) | 0.1299 | — | 810,201 | 11/11 |
| tight_capacity | 0.1851 | +0.0552 | 160,942 | 11/11 |
| tight_expanding | 0.1828 | +0.0529 | 63,743 | 11/11 |
| tight_contracting | 0.1853 | +0.0554 | 96,455 | 11/11 |
| weighted (S1 × (1+change)) | 0.1833 | — | tight only | — |

## Key Findings

1. **Weighting FAILS**: Weighted IC=0.1833 < binary best (0.1853). Similar to H544 (duration weighting failed).

2. **OPPOSITE finding**: tight_contracting (0.1853) > tight_expanding (0.1828), opposite of H538's +0.0144 finding. Possible explanation: small sample difference or different capacity proxy.

## Verdict: MIXED

- Weighting as continuous modifier FAILS (like H544)
- But tight capacity signals are all strong (+0.055 lift)
- OPPOSITE finding on direction needs further investigation