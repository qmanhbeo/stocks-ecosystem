# Session 63 Log

## Objective
Complete the next local refinement wave around the Session 62 sticky champion:
- `H187`: combine sticky retention with mild sector concentration control
- `H188`: add an implementation-pain veto to the sticky champion
- `H189`: add a basket-coherence / score-dispersion guard to the sticky champion

Then rerun the live overlay and current-year scoreboard on any new winner.

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Starting point

Session 62 had already established:
- current live branch is current through `2026-03-27`
- sticky holdings improved the historical champion
- local exposure sizing failed
- current live sticky overlay state was:
  - `ANV`, `PGV`, `PTB`, `PTL`, `VSI`
  - activation `ON`

The open question for Session 63 was whether any small local follow-through could improve the sticky champion without reopening broad activation search.

## H187 — sticky holdings + sector cap

Goal:
- test whether the two positive local refinements from Session 62 stack when combined

Result:
- **FAIL**
- best result remained the sticky champion alone:
  - `sticky_bonus_0p015`
  - `+509.76%` relative vs VNINDEX
  - IR `0.9372`

Combined candidate:
- `sticky_bonus_0p015 + sector_cap_3`
- `+498.04%` relative
- IR `0.9280`

Reading:
- mild sector diversification does not compound with sticky retention enough to matter
- sector cap remains secondary, not core

## H188 — implementation-pain veto

Goal:
- test whether the sticky champion should deactivate when recent execution strain is high

Family tested:
- blocked-buy pressure vetoes
- cash-drag vetoes
- combined pain filters
- small composite pain scores

Result:
- **PASS**
- best rule:
  - `impl__blocked3_q80`
  - interpreted as: stay active only when recent blocked-buy pressure is not in the worst `20%`

Historical reference (`2019-2025`, `0.30%` RT):
- sticky baseline:
  - `+509.76%` relative vs VNINDEX
  - IR `0.9372`
  - blocked-buy events `68`
- `impl__blocked3_q80`:
  - `+527.16%` relative
  - IR `0.9471`
  - avg cash `41.47%`
  - blocked-buy events `42`

Reading:
- the next useful refinement is not another confidence or coherence filter
- it is a direct veto on recent implementation strain

Branch decision:
- the new champion is:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked3_q80`

## H189 — basket-coherence / score-dispersion guard

Goal:
- test whether the sticky champion should only stay on when the selected basket is internally coherent

Family tested:
- coherence quantiles
- spread + score-std conjunctions
- spread/overlap and std/overlap conjunctions

Result:
- **FAIL**
- every tested coherence gate gave up too much return and pushed cash too high
- best result was just the sticky baseline itself

Reading:
- the current winner is not about cleaner basket shape
- it is about reducing real implementation pain

## Live reruns on the new H188 winner

After `H188` passed, the canonical live overlay and live scoreboard were rerun with:
- `incumbent_score_bonus = 0.015`
- implementation-pain veto: `blocked3<=q80`

### Current official live overlay state

- signal date: `2026-03-26`
- execution date: `2026-03-27`
- activation: `OFF`
- held names: none
- cash: `100.00%`

Reading:
- the new champion is currently choosing to stay out
- this is a materially different live posture from the Session 62 sticky-only champion

### Current-year scoreboard

`2026` YTD so far:
- activated new champion:
  - `+5.73%` relative vs VNINDEX
  - IR `1.17`
  - avg cash `100.00%`
- always-on:
  - `-11.22%` relative
  - IR `-1.65`
  - avg cash `5.49%`

Reading:
- the new champion is outperforming the always-on book in the short live-forward window
- but it is doing so by being fully defensive
- that needs to be tracked explicitly, not romanticized

## Branch decision

Session 63 outcome:
- `H187`: fail
- `H188`: pass and become new champion
- `H189`: fail

The next queue is now:
1. `H190`: combine the new `H188` winner with `sector_cap_3`
2. `H191`: refine the blocked-buy veto family locally (`q75/q80/q85`, span changes, small hysteresis)
3. `H192`: maintain the forward live scoreboard on the new champion

Secondary branches remain parked:
- `H151`
- `H152`
- RL beyond exploratory status

## Artifacts

Run summaries:
- `artifacts/run_summaries/latest_portfolio_activation_sticky_sector_combo.json`
- `artifacts/run_summaries/latest_portfolio_activation_implementation_pain.json`
- `artifacts/run_summaries/latest_portfolio_activation_basket_coherence.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_scoreboard.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h187_sticky_sector_combo*`
- `artifacts/portfolio_baselines/*h188_implementation_pain_veto*`
- `artifacts/portfolio_baselines/*h189_basket_coherence_guard*`
- `artifacts/portfolio_baselines/*h179_live_activation_overlay*`
- `artifacts/portfolio_baselines/*h183_live_activation_scoreboard*`

## Validation

Session 63 hygiene completed:
- `python -m py_compile` passed on changed code
- `git diff --check` passed

Important note:
- the first `H188/H189` runs were invalid because their raw meta columns were not aligned to the time index of `rel2`
- the valid results are the reruns after that fix
