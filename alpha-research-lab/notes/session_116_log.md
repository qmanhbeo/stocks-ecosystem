# Session 116 Log

## Objective
Run the next honest 5d walk-forward proxy after the H285 label-contract audit to see whether the slower horizon improves the canonical cross-sectional workflow.

This session did not change the live branch.
It did not read `2026+`.

## What changed

No new research script was added. The existing cross-sectional WF runner was used directly.

Saved artifacts:
- `artifacts/run_summaries/20260405_224257_X10_xs_barrier0.01_cross_sectional.json`

### H286 - 5d Barrier WF Proxy
**Hypothesis:**
A 5d triple-barrier label should keep the cross-sectional WF at least competitive, and ideally improve focal edge relative to the current contract.

**Command / code:**
`python cross_sectional_wf.py --start-date 2015-01-01 --min-train-years 3 --target-horizon 5 --barrier-pct 0.01 --model extra_trees`

**Inputs:**
- `data/stock/`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/stock/gia_lich_su_VNINDEX_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260405_224257_X10_xs_barrier0.01_cross_sectional.json`

| Metric | Value | Note |
|--------|-------|------|
| model backend | `extra_trees_classifier` | `xgboost` and `lightgbm` were unavailable in this runtime |
| target | `future_rel_barrier_5d` | 5d relative triple barrier |
| start date | `2015-01-01` | matches the H285 audit window |
| total years | `8` | 2018-2025 test years under min-train-years=3 |
| avg overall acc | `0.5416` | usable but not strong |
| focal avg edge | `-0.0218` | below zero |
| focal sig years | `4 / 8` | not stable enough to promote |
| focal std edge | `0.1267` | very noisy |

**Result:**
The 5d WF proxy does not improve the label contract in a promotable way. The classification accuracy is acceptable, but the focal edge is negative and noisy, so this is not a clean upgrade over the current contract.

**Verdict: FAILED**

## Branch decision

Park the 5d barrier WF proxy under the available tree backend.
If this branch is revisited, use a supported gradient-boosted backend or a different 5d contract formulation.
The next queue item is `breadth-activation-gate`.

## Validation

Completed before the run:
- `python /home/manh/stocks-ecosystem/alpha-research-lab/cross_sectional_wf.py --start-date 2015-01-01 --min-train-years 3 --target-horizon 5 --barrier-pct 0.01 --model extra_trees`

Completed for the experiment:
- read `artifacts/run_summaries/20260405_224257_X10_xs_barrier0.01_cross_sectional.json`

Verdict:
- `H286`: **FAILED**
