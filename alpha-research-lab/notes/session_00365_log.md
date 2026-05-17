# Session 365 - H566 Time-Since-Active as Hidden State

**Date**: 2026-05-17

**Hypothesis**: Test "time since last active state" as continuous hidden variable that modulates signal REGARDLESS of current state. H522 found transitions don't help - now test time-since.

**Command**: `python analysis/h566_time_since_active_hidden.py`

**Saved artifact**: `artifacts/run_summaries/20260517_155638_time_since_active_hidden_state_research_branch.json`

## Results

| State | IC | Positive Years |
|-------|-----|----------------|
| c16_low (currently active) | 0.1648 | 11/11 |
| tsa_0d (just active) | 0.1574 | 11/11 |
| tsa_15plus (dormant 15d+) | 0.1331 | 11/11 |
| tsa_4_7d | 0.0956 | 8/8 |
| tsa_8_14d | 0.0881 | 11/11 |
| tsa_1_3d | 0.0809 | 7/7 |

## Key Finding: FAILED

**TSA does NOT beat current state**:
- Best TSA (tsa_0d) = 0.1574
- Current active = 0.1648
- Difference: **-0.0074** (current wins)

**Non-monotonic pattern**:
- Current active is strongest (0.165)
- 15+ days dormant is second (0.133)
- The middle buckets (1-14d) are all WEAKER
- Neither "recently active" nor "long dormant" captures extra alpha

**H522 confirmed**: transitions are not the path. The current state (C16 level) is the signal, not time-since.

## Verdict: FAILED

- Time-since-active doesn't add value beyond current state
- The current state is the signal, not the history
- Dead-end D071

**Next**: #65 Quiet-to-Active Transition Probability (last item)