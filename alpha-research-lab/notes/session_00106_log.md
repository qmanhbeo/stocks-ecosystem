# Session 106 Log

## Objective
Run the next queue item from live_state.md EUREKA batch 5 (AM):
- **AM**: volume_acceleration_signal - testing volume CHANGE (acceleration) + return vs volume LEVEL + return

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- H448: PASSED - vol_expansion_contrarian combo IC=0.2069 (+0.0771 lift)
- H449: MIXED - vol_contraction_exhaustion has negative IC, pattern confirmed but wrong direction
- Hypothesis: volume CHANGE (acceleration) + return might work better than volume LEVEL + return

## What changed

Added:
- `analysis/h450_volume_acceleration_signal.py`

Saved artifacts:
- `artifacts/run_summaries/20260508_175508_volume_acceleration_signal_research_branch.json`

### H450 - volume_acceleration_signal

**Hypothesis:**
H447 tested volume LEVEL + return. What about volume CHANGE (acceleration) + return?
H446 showed vol CHANGE matters, so volume CHANGE + return might work better than 
volume LEVEL + return. Test vol_delta × return vs forward IC.

**Command / code:**
`python analysis/h450_volume_acceleration_signal.py`

**Inputs:**
- S1 decision panel (2015-2025)
- order_stats: total_volume (computed vol_delta = volume - 5d MA)
- Computed features: vol_delta (volume change), return_rank

**Saved artifact:**
`artifacts/run_summaries/20260508_175508_volume_acceleration_signal_research_branch.json`

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| low_vol | 0.1821 | +0.0522 | STRONGEST - volume LEVEL low |
| low_return | 0.1424 | +0.0125 | |
| vol_accel_high_return | 0.1346 | +0.0047 | Accel + high return |
| all_rows | 0.1299 | 0.0000 | Baseline |
| vol_accelerating | 0.1227 | -0.0072 | |
| high_vol | 0.0872 | -0.0427 | Negative |
| vol_decel_high_return | 0.0974 | -0.0325 | |
| vol_decel_low_return | 0.0989 | -0.0310 | |

**Key Comparison:**
- Accel vs Level (high return): **+0.0474** - acceleration beats level for high return
- Accel vs Level (low return): **-0.0654** - but volume LEVEL dominates for low return

**Result:**
Volume LEVEL (low_vol) is still stronger than volume CHANGE. The combo (vol_accel_high_return) 
has +0.0047 lift, but low_vol alone has +0.0522 lift. Volume acceleration helps for high return 
(+0.0474 vs high_vol), but volume LEVEL (low_vol) is the dominant factor.

**Verdict: MIXED** - acceleration helps for high return but doesn't beat volume LEVEL overall.

## Branch decision

Do **not** change the live branch.

What Session 106 resolves:
- H450 MIXED: acceleration helps for high return (+0.0474 vs level), but low_vol is still 
  stronger overall (+0.0522). Volume LEVEL dominates, acceleration is secondary.
- No new signal - use low_vol (volume LEVEL) as the primary factor

The queue continues with remaining items:
- AN: buy_sell_imbalance_in_stress
- AO: volume_level_vs_direction_divergence
- AP: implied_limit_proximity
- AQ: low_vol_low_return_regime

## Validation

Completed for the experiment:
- `python analysis/h450_volume_acceleration_signal.py`
- Read saved summary artifact

Verdict:
- H450: **MIXED** - acceleration helps for high return, but level dominates overall