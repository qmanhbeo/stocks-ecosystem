# Session 64 Log

## Objective
Follow through on the Session 63 winner:
- `H190`: test whether mild sector control helps only after the implementation-pain veto is active
- `H191`: refine the blocked-buy veto family locally
- rerun the live overlay and live scoreboard on the actual new winner

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Starting point

Session 63 had already shown:
- sticky + sector cap did not help
- `blocked3<=q80` improved the sticky champion
- the live overlay on that winner was already `OFF / cash`

So the next honest step was not more generic local creativity.
It was:
1. see whether the veto family itself can be improved
2. then see whether sector control helps only after that stronger veto is active

## H191 — blocked-buy veto refinement

Tested family:
- `blocked3<=q75`
- `blocked3<=q80`
- `blocked3<=q85`
- `blocked3<=q90`
- `blocked5<=q80`
- `blocked5<=q85`
- `blocked3` hysteresis around `q80/q85`

Result:
- **PASS**
- new best pure veto:
  - `impl__blocked5_q80`
  - `+590.23%` relative vs VNINDEX
  - IR `1.0027`
  - avg cash `42.75%`

Reference:
- prior winner `impl__blocked3_q80`
  - `+527.16%` relative
  - IR `0.9471`

Reading:
- the implementation-pain family is real
- the more stable `blocked5` memory is stronger than the shorter `blocked3` version
- hysteresis on the weaker `blocked3` path did not matter

## H190 — implementation-pain + sector-cap combo

After `H191`, the sector-cap combination was rerun against the stronger veto family.

Result:
- **PASS**
- best overall historical system:
  - `impl__blocked5_q80 + sector_cap_3`
  - `+597.09%` relative vs VNINDEX
  - IR `1.0093`
  - avg daily turnover `0.2036`

Reference:
- `impl__blocked5_q80`
  - `+590.23%` relative
  - IR `1.0027`

Reading:
- sector control was not useless
- it only became additive once the stronger blocked-buy veto family was in place

Branch decision:
- current best uncapped long-only system is now:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked5_q80 + sector_cap_3`

## Live reruns on the current winner

The canonical live overlay and live scoreboard were rerun on the new winner.

### Current official live overlay state

- signal date: `2026-03-26`
- execution date: `2026-03-27`
- activation: `OFF`
- held names: none
- cash: `100.00%`

The addition of `sector_cap_3` did not change the live state because the winner is currently fully deactivated.

### Current-year scoreboard

`2026` YTD so far:
- activated current winner:
  - `+5.73%` relative vs VNINDEX
  - IR `1.17`
  - avg cash `100.00%`
- always-on:
  - `-11.22%` relative
  - IR `-1.65`
  - avg cash `5.49%`

Reading:
- the current winner is still improving the forward path
- but it is doing so entirely by staying out

This needs to be tracked carefully. It is good defense, but it is not yet proof of a balanced live offense/defense regime.

## Branch decision

Session 64 outcome:
- `H190`: pass
- `H191`: pass
- current winner updated again

Next queue:
1. `H192`: maintain forward live scoreboard on the current winner
2. `H193`: refine the blocked-buy veto family jointly with `sector_cap_3`
3. `H194`: if the forward branch stays cash too long, test a mild re-entry hysteresis on the `blocked5` veto family

Secondary branches remain parked:
- `H151`
- `H152`
- RL beyond exploratory status

## Artifacts

Run summaries:
- `artifacts/run_summaries/latest_portfolio_activation_impl_pain_sector_combo.json`
- `artifacts/run_summaries/latest_portfolio_activation_blocked_buy_veto_refinement.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_scoreboard.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h190_impl_pain_sector_combo*`
- `artifacts/portfolio_baselines/*h191_blocked_buy_veto_refinement*`
- `artifacts/portfolio_baselines/*h179_live_activation_overlay*`
- `artifacts/portfolio_baselines/*h183_live_activation_scoreboard*`

## Validation

Session 64 hygiene completed:
- `python -m py_compile` passed on changed code
- `git diff --check` passed
