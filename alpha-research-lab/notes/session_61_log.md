# Session 61 Log

## Objective
Convert the post-Session-60 idea list into a concrete, ordered experiment queue.

No new backtests were run in Session 61.
This was a branch-definition pass only.

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Starting point

Session 60 had already established three things clearly:
1. `h175__rel2_gt0` is the current activation champion
2. the champion is robust enough to operationalize
3. the live-paper activation overlay runner exists, but the shared `full_library` matrix is stale beyond `2025-12-31`

So the branch no longer needs broad activation creativity.
It needs a concrete operational-and-refinement queue.

## Branch structure

The current system now has four layers:
1. selection alpha
2. activation alpha
3. construction / turnover control
4. live data freshness

The highest-priority unsolved issue is layer 4.
So the next queue deliberately starts with infrastructure and only then returns to small local portfolio refinements.

## Active ordered queue

### H181 — Current-date feature refresh for the activation branch

Purpose:
- make the `full_library` activation stack genuinely current

Required rebuild chain:
1. `data/features/xs_rl_signal_matrix.parquet`
2. `data/features/activation_state_daily.parquet`
3. `data/features/activation_meta_daily.parquet`

Acceptance:
- matrix max date matches the latest stock-data date
- activation artifacts rebuild successfully on top of that matrix
- `H179` no longer reports `stale_signal_matrix = true`

This is the hard prerequisite for all later current-date activation work.

### H182 — Current-date live-paper activation overlay

Purpose:
- rerun the Session 60 overlay on a current matrix and start a dated paper blotter

Expected runner:
- `analysis/h179_live_activation_overlay.py`

Deliverables:
- latest activation state
- requested basket
- held basket after execution rules
- one dated detail blotter
- one dated daily summary

Acceptance:
- latest overlay date equals latest tradable market date
- no stale-matrix warning remains

### H183 — Activated vs always-on live scoreboard

Purpose:
- stop talking about activation in the abstract and compare the two books directly in forward paper trading

Comparison:
- always-on `full_library + k5_r5_eq`
- activated `full_library + k5_r5_eq + h175__rel2_gt0`

Rules:
- compare only overlapping forward dates after the overlay is current
- do not mix stale historical overlays with live-forward dates

Core metrics:
- cumulative return difference
- benchmark-relative difference
- drawdown difference
- cash weight difference
- turnover difference

Acceptance:
- one dated scoreboard artifact exists and can be refreshed forward without changing methodology

### H184 — Sticky holdings / displacement margin

Hypothesis:
- the current selector is right, but churn still leaks edge
- held names should persist unless a challenger is clearly better, not barely better

Construction:
- apply only to the activated `full_library + k5_r5_eq + h175__rel2_gt0` branch
- when activation is ON, retain current holdings unless a non-held stock beats the weakest held stock by a margin

Suggested margin grid:
- `0.00`
- `0.01`
- `0.02`
- `0.03`
- `0.05`

Score domain:
- use the existing normalized cross-sectional composite score directly

Acceptance:
- must improve either:
  - relative return, or
  - IR / drawdown frontier
- without collapsing into trivial low-turnover stagnation

### H185 — Sector concentration cap on the activated selector

Hypothesis:
- some bad cycles come from the book being correct on theme but too concentrated in one sector

Construction:
- keep selector and activation fixed
- limit names per sector in the selected basket
- fill remaining slots with next-ranked eligible names outside the capped sector

Suggested cap grid:
- unlimited
- max `3` names / sector
- max `2`
- max `1`

Sector source:
- use the existing sector classification artifact already in the repo

Acceptance:
- must improve either relative return or drawdown-adjusted performance versus the uncapped activated champion
- if it only reduces drawdown while destroying return, reject it

### H186 — Local exposure control around `rel2_gt0`

Hypothesis:
- the champion is right on direction, but exposure can still be controlled better using the same state variable

Important constraint:
- do not invent a new activation family
- only use the same `recent_rel2` memory state that powers `h175__rel2_gt0`

Permitted local variants:
1. hysteresis
   - turn ON at `rel2 > 0`
   - turn OFF only at `rel2 < -x`
2. small stepped sizing
   - `0 / 50 / 100`
   - `25 / 50 / 100`
   based only on `recent_rel2` thresholds
3. mild protection threshold
   - require `rel2 > tiny_positive_buffer`

Acceptance:
- must beat plain `h175__rel2_gt0`
- if not, the repo should stop spending time on local activation refinements and keep the plain rule

## Secondary backlog only after H181-H186

These are now explicitly secondary, not active:
- `H187`: implementation-pain veto on blocked-buy / cash-drag spikes
- `H188`: basket-coherence / score-dispersion overlay
- `H189`: selector switching between `full_library` and `S1`
- `H190`: calendar / entry-window quality guards
- `H151`: narrow tradability-conditioned composite
- `H152`: tradability-conditioned alpha search

## Branch logic

The branch should now behave like this:
1. make the activation stack current
2. compare activated vs always-on in forward paper mode
3. only then refine construction around the champion
4. only then reopen any broader hypothesis branch

That ordering is important.
Without `H181-H183`, the repo is still optimizing a champion that is not yet truly live on the latest date.
