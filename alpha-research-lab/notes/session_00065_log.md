# Session 65 Log

## Objective
Solve the activation defense-vs-overfit problem rigorously.

The concrete question was:
- is the current historical winner
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked5_q80 + sector_cap_3`
  actually the right live branch,
- or is it only the strongest full-window backtest stack?

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Starting point

Session 64 left the branch in an ambiguous state:
- strongest historical system was `blocked5<=q80 + sector_cap_3`
- live state on that winner was `OFF / cash`
- the forward edge was positive only because it was staying out

That left three possibilities:
1. valid defensive alpha
2. overfit threshold stack
3. historical/live runner drift

So Session 65 had to answer those in order.

## H192A — champion parity audit

First fix:
- introduce one canonical champion spec
- use the same gate-construction logic for:
  - direct historical simulation
  - `H179` live overlay
  - `H183` live scoreboard

Result:
- **PASS**
- the historical `2019-2025` reproduction of the complex winner matched the archived Session 64 reference exactly
- the refreshed live overlay and live scoreboard matched the direct runner exactly on overlapping dates

Practical read:
- the branch problem was not a hidden runner mismatch
- the complex winner is genuinely reproducible on the current artifact surface

## H192B — forward monitor diagnostic

Recent live monitor window:
- last `30` execution days
- current complex winner:
  - `h175__rel2_gt0 + sticky_bonus_0p015 + blocked5<=q80 + sector_cap_3`

Result:
- classification: `mixed_not_extreme`
- activation-on rate: `30.0%`
- avg cash: `59.55%`
- blocked-extreme rate: `36.67%`
- top-5 buyable mean: `4.77`
- `2026` YTD relative return: `+3.75%`
- delta vs always-on: `+14.97%`

Practical read:
- the complex winner is not “always off”
- the problem is not a trivially broken live branch
- but that still does not make it the right live branch

## H193 — pseudo-live robustness ladder

This was the real decision step.

Protocol:
- train-only threshold calibration
- expanding train windows
- next-year test years:
  - `2023`
  - `2024`
  - `2025`

Candidates:
1. `sticky_bonus_0p015`
2. `impl__blocked3_q80`
3. `impl__blocked5_q80`
4. `impl__blocked5_q80 + sector_cap_3`

Aggregate ranking:
- `sticky_bonus_0p015`
  - mean relative return `+14.91%`
  - mean IR `0.5856`
  - mean cash `37.87%`
- `impl__blocked5_q80 + sector_cap_3`
  - mean relative `+14.04%`
  - mean IR `0.4275`
  - mean cash `41.55%`
- `impl__blocked5_q80`
  - mean relative `+14.04%`
  - mean IR `0.4275`
- `impl__blocked3_q80`
  - mean relative `+13.18%`
  - mean IR `0.3912`

Result:
- **ROLLBACK**
- the complex winner failed the pseudo-live frontier
- sticky is the correct live branch

This was the key branch change.

## Live reruns after rollback

The canonical live overlay and scoreboard were rerun on:
- `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

Latest live state (`2026-03-26` signal / `2026-03-27` execution):
- activation `ON`
- holdings:
  - `ANV`
  - `PGV`
  - `PTB`
  - `PTL`
  - `VSI`

`2026` YTD scoreboard:
- activated sticky:
  - `-3.33%` relative vs VNINDEX
  - IR `-0.36`
- sticky always-on:
  - `-11.22%` relative
  - IR `-1.65`

Practical read:
- rollback sticky is not benchmark-beating yet in this short forward slice
- but it is clearly better than sticky always-on
- and it is more credible as an active live branch than the pseudo-live-rejected blocked-buy stack

## Branch decision

Session 65 outcome:
- `H192A`: pass
- `H192B`: mixed, not extreme
- `H193`: rollback to sticky

This means:
- the complex `blocked5 + sector_cap_3` system stays as the strongest historical full-window result
- the **active live branch** is now:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

### What was implemented but not run

Implemented for future use:
- `H194`: blocked-buy + sector-cap recalibration
- `H195`: blocked-buy hysteresis

They were **not** run after `H193`, because the decision tree said not to keep tuning a family that had already failed the pseudo-live gate.

## Next queue

1. Maintain the live scoreboard on sticky.
2. If sticky keeps beating sticky always-on for at least `2` additional completed rebalance cycles:
   - keep monitoring only
3. If sticky falls behind sticky always-on for `>= 2` completed cycles:
   - rerun parity first
   - then choose one branch:
     - reopen `H194/H195`
     - or stop local activation tuning and move to `H151/H152`

## Artifacts

Session 65 summaries:
- `artifacts/run_summaries/latest_portfolio_activation_champion_parity_audit.json`
- `artifacts/run_summaries/latest_portfolio_activation_forward_monitor_diagnostic.json`
- `artifacts/run_summaries/latest_portfolio_activation_pseudo_live_robustness_ladder.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_scoreboard.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h192a_champion_parity_audit*`
- `artifacts/portfolio_baselines/*h192b_forward_monitor_diagnostic*`
- `artifacts/portfolio_baselines/*h193_pseudo_live_robustness_ladder*`
- `artifacts/portfolio_baselines/*h179_live_activation_overlay*`
- `artifacts/portfolio_baselines/*h183_live_activation_scoreboard*`

## Validation

Session 65 hygiene completed:
- `python -m py_compile` passed on changed code
- focused tests passed:
  - `tests/test_champion_branch_utils.py`
  - `tests/test_activation_meta.py`
- `git diff --check` passed
