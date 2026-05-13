# Session 108 Log

## Objective
Run the next queue item from live_state.md EUREKA batch 5 (AO):
- **AO**: volume_level_vs_direction_divergence - testing if vol DIRECTION + return works better than vol LEVEL + return

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- H448: PASSED - vol_expansion_contrarian combo IC=0.2069 (+0.0771 lift)
- H449: MIXED - vol_contraction_exhaustion negative IC
- H450: MIXED - volume acceleration secondary to level
- H451: PASSED - buy_heavy_expansion NEW SIGNAL (+0.0508 lift)
- Hypothesis: vol DIRECTION + return might work better than vol LEVEL + return

## What changed

Added:
- `analysis/h452_volume_level_vs_direction_divergence.py`

Saved artifacts:
- `artifacts/run_summaries/20260508_175654_volume_level_vs_direction_divergence_research_branch.json`

### H452 - volume_level_vs_direction_divergence

**Hypothesis:**
H447 showed volume LEVEL + return interaction (low_vol works). What about vol DIRECTION 
(expanding vs contracting) + return? High return + vol_expanding = momentum, high return + 
vol_contracting = exhaustion. Test vol_regime × return vs forward IC.

**Command / code:**
`python analysis/h452_volume_level_vs_direction_divergence.py`

**Saved artifact:**
`artifacts/run_summaries/20260508_175654_volume_level_vs_direction_divergence_research_branch.json`

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| low_vol_level_low_return | 0.2045 | +0.0747 | STRONGEST (from H447) |
| low_vol_level | 0.1819 | +0.0522 | |
| vol_expanding | 0.1753 | +0.0455 | (from H446) |
| vol_expanding_high_return | 0.1671 | +0.0373 | |
| vol_expanding_low_return | 0.1632 | +0.0334 | |
| all_rows | 0.1298 | 0.0000 | Baseline |
| vol_contracting_high_return | 0.1043 | -0.0255 | Exhaustion |
| high_vol_level_high_return | 0.1112 | -0.0186 | Negative |

**Key Finding:**
- Direction vs Level (high return): **+0.0559** - vol expanding + high return beats high vol level + high return
- Direction vs Level (low return): **-0.0412** - low vol level still dominates for low return

**Result:**
Hypothesis confirmed: direction beats level for high return (momentum). BUT this is just 
confirming the known components - vol_expanding (+0.0455) and low_vol_level (+0.0522) are 
the real signals. No incremental value beyond the components.

**Verdict: MIXED** - pattern confirmed but no new signal - use components separately.

## Branch decision

Do **not** change the live branch.

What Session 108 resolves:
- H452 MIXED: confirms vol direction × return pattern but no incremental value
- Use vol_expanding and low_vol_level as separate signals, not the combination

The queue continues with remaining items:
- AP: implied_limit_proximity
- AQ: low_vol_low_return_regime

## Validation

Completed for the experiment:
- `python analysis/h452_volume_level_vs_direction_divergence.py`
- Read saved summary artifact

Verdict:
- H452: **MIXED** - pattern confirmed but no new signal