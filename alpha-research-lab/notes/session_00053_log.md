# Session 53 Log

## Objective
Close the ADV / capacity argument for the current-account branch and set the next active research
direction without rewriting the existing evidence.

Hard rules remained unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions

## Decision

### ADV / capacity status
- ADV / capacity is now **parked** for the current-account branch.
- That is a prioritization change, not a scientific reversal.
- The repo still treats ADV / capacity as unresolved for scale and deployability.

### Why the repo is changing direction
- Sessions 48-51 already showed the full shape of the problem:
  - uncapped long-only construction is strong
  - explicit ADV caps break deployability
  - more local liquidity-gate tuning is not generating new information
- For the current account size, the next useful unknown is not another capacity sweep.
- The next useful unknown is whether a long-only RL policy can extract more from the current signal
  library than the fixed deterministic construction.

### New active branch
- keep the current deterministic paper trade running:
  - `full_library + k5_r5_eq`
  - current paper-trade book after the `2026-03-27` close:
    - `ANV`
    - `PTB`
    - `PTL`
    - `VSI`
    - cash `19.57%`
- move the main research queue to **benchmark-first long-only portfolio-choice RL**

## New queue

1. `H153`: same-universe deterministic benchmark for portfolio-choice RL
2. `H154`: controlled long-only RL pilot ladder
3. `H155`: multi-seed robustness and evaluation

Parked, not deleted:
- `H151`: narrow tradability-conditioned composite
- `H152`: tradability-conditioned alpha search

## Required documentation change
The docs must now say all of these explicitly:
- ADV / capacity is parked, not solved
- RL is no longer deferred behind capacity work for the current-account branch
- RL must still be benchmarked honestly against same-universe deterministic comparators
- the old equal-weight-universe RL comparator is obsolete

## Next steps
1. Record the next market-session result against the current paper-trade book
2. If a new live recommendation is needed, restore full canonical benchmark continuity and rerun the official live scorer
3. Start `H153` before any new RL interpretation
