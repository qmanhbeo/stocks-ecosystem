# Session 375 - H585 C27 × Market Activity Interaction

**Date**: 2026-05-17

**Hypothesis**: C27 (blocked stocks) works differently in high vs low market activity regimes (avg order pressure proxy for vol regime).

**Command**: `python analysis/h585_c27_vol_interaction.py`

**Saved artifact**: `artifacts/run_summaries/20260517_164909_c27_market_activity_interaction_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| blocked_high_breadth | 0.2029 | 5,836 | 4/4 |
| blocked_either (C27) | 0.1477 | 15,848 | 10/10 |
| blocked_low_activity | 0.1345 | 4,986 | 2/2 |
| all_rows | 0.1302 | 826,404 | 11/11 |
| blocked_low_breadth | 0.0960 | 1,023 | 1/1 |
| blocked_high_activity | 0.0860 | 4,314 | 3/3 |

## Key Finding: OPPOSITE - C27 is WORSE in high_activity

- C27 × high_activity: IC=0.0860 (-0.0352 vs high_activity baseline, sparse 3/3)
- C27 × low_activity: IC=0.1345 (+0.0073 vs low_activity baseline)
- **diff: -0.0485 — hypothesis FAILS**

**Critical contrast (new insight):**
- C27 × **high_breadth** = 0.2029 (STRONGEST — many signals, low intensity)
- C27 × **high_activity** = 0.0860 (WORST — few signals, high intensity)
- **Breadth and activity level are OPPOSITE regime signals for C27!**
- C27 wants: **many signals active** (high breadth) + **low per-signal intensity** (low activity)
- C27 avoids: **few signals active** (low breadth) + **high per-signal intensity** (high activity)

**Mechanism**: Blocked stocks represent hidden demand that fills the void when many signals fire (many stocks active). When the market has few signals BUT high order activity (concentrated chasing), blocked stocks are less valuable.

## Verdict: FAILED (opposite direction) — Dead-end D078

- high_activity HURTS C27, low_activity helps slightly
- The breadth × activity distinction is a new structural insight, not a usable signal
- Both high_breadth and low_activity are sparse (4/2 years positive)

**Next**: #86 Blocked Duration Sweet Spot (newly blocked vs persistently blocked)