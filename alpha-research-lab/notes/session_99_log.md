# Session 99 Log

## Objective
Run the next materially different fallback after the `H269` current-account failure:
- `H270`: test whether the breakout-specific reduced-shape intraday branch becomes cleaner if the target is rewritten from generic `buy_now` to breakout-survivor contracts that require avoiding immediate failure and keeping `10d` follow-through alive

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H266-H268` had already shown that reduced-shape intraday contained real breakout-specific offline information
- `H269` then closed the breakout-trust continuation family in the operational sticky framing:
  - the overlay lost badly to both the operational sticky baseline and the carried sparse control
  - narrowness cost dominated
- so the queue pivot was explicit:
  - stop stretching the same gate / compatibility family
  - reopen only with a materially different contract
- the next honest question was therefore target-side:
  - is the surviving intraday information really about a generic `buy_now` label?
  - or is it better framed as whether a breakout entry survives the next `1-2` cycles without immediate failure?
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## What changed

Added:
- `analysis/h270_breakout_survivor_label_rewrite_audit.py`

Shared support added:
- `build_survivor_label_series()` in `src/entry_alpha_research.py`

Regression coverage added:
- `tests/test_entry_alpha_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_breakout_survivor_label_rewrite_audit.json`
- `artifacts/entry_alpha/20260403_132526_h270_breakout_survivor_label_rewrite_results.parquet`
- `artifacts/entry_alpha/20260403_132526_h270_breakout_survivor_label_rewrite_contract_winners.parquet`
- `artifacts/entry_alpha/20260403_132526_h270_breakout_survivor_label_rewrite_label_stats.parquet`
- `artifacts/entry_alpha/20260403_132526_h270_breakout_survivor_label_rewrite_scored_panel.parquet`
- `artifacts/entry_alpha/20260403_132526_h270_breakout_survivor_label_rewrite_subset_panel.parquet`

### H270 - Breakout Survivor Label Rewrite Audit
**Hypothesis:**
The surviving breakout-specific intraday information may be answering the wrong question under the generic `buy_now` contract. A breakout-local survivor target that asks whether the entry avoids immediate failure and still has positive `10d` follow-through may be a better use of the reduced-shape intraday signal.

**Command / code:**
`conda run -n stocks python analysis/h270_breakout_survivor_label_rewrite_audit.py`

**Inputs:**
- same restarted `2023-2025` protocol as `H266-H269`
- same observed breakout universe:
  - `breakout_followthrough`
  - `can_buy_next_open == True`
  - reduced-shape intraday observed rows only
- same reduced-shape intraday surface from `H258`
- survivor horizon:
  - `10` signal steps (`2` cycle lengths)
- fixed survivor contracts:
  - `net_relaxed_survivor`
    - `5d cycle_return_net > -0.02`
    - `10d cycle_return_net > 0.00`
  - `net_soft_survivor`
    - `5d cycle_return_net > -0.01`
    - `10d cycle_return_net > 0.00`
  - `net_strict_survivor`
    - `5d cycle_return_net > 0.00`
    - `10d cycle_return_net > 0.00`
- model ladder:
  - `selection_baseline`
  - `breakout_path_core`
  - `intraday_shape_core`
  - `intraday_atoms_plus_breakout_path`
- pass rule:
  - at least one intraday-aware model beats the best path control on validation AUC
  - and its top-quintile `10d` return is above the breakout-survivor phase mean in both validation and confirmation
  - and confirmation AUC stays `>= 0.52`

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_breakout_survivor_label_rewrite_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| breakout buyable rows | `6216` | same breakout family contract as `H266` |
| observed breakout rows | `5869` | reduced-shape intraday observed subset |
| observed breakout share | `94.42%` | usable overlap remains high |
| winner contract | `net_soft_survivor` | `5d > -1%` and `10d > 0` |
| winner intraday model | `intraday_shape_core` | pure reduced-shape intraday winner |
| winner best path control | `breakout_path_core` | strongest non-intraday control on the winner contract |
| winner validation AUC | `0.5168` | vs path `0.5074` |
| winner confirmation AUC | `0.5344` | still above the `0.52` floor |
| winner validation top-quintile `10d` return | `+0.87%` | vs phase mean `+0.18%` |
| winner confirmation top-quintile `10d` return | `+0.89%` | vs phase mean `+0.59%` |
| winner validation top-quintile delta vs path | `+0.26%` | above the best path control |
| winner confirmation top-quintile delta vs path | `-0.35%` | path control still stronger on `2025` top-quintile economics |
| second passing contract | `net_relaxed_survivor` | hybrid winner `intraday_atoms_plus_breakout_path` |
| mixed contract | `net_strict_survivor` | confirmation `10d` top quintile fell below the phase mean |

**Result:**
`H270` passes.

What passed:
- a materially different breakout-local label contract works
- reduced-shape intraday survives that target rewrite on the observed breakout sleeve
- the best contract is not the loosest or the strictest:
  - `net_soft_survivor` is the clean winner

What did **not** pass yet:
- the branch is still not a deterministic or broad-book winner
- on the winning contract, the best path control still has the stronger confirmation top-quintile `10d` return:
  - `breakout_path_core`
  - `+1.24%` vs `+0.89%` for `intraday_shape_core`

So this is a target-contract pass, not a deployment pass.

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 99 resolves:
- `H270` passes:
  - the breakout-specific intraday branch is not dead after `H269`
  - but it only survives after a materially different label rewrite
- the usable winner is:
  - contract:
    - `net_soft_survivor`
  - score:
    - `entry_prob__intraday_shape_core`
- the branch remains offline-only:
  - no broad-book reintegration
  - no current-account claim
  - no live promotion

Branch effect:
- keep the original breakout-trust continuation family closed:
  - `H269` still kills that exact line
- promote `H270` as offline evidence only
- the next exact follow-through is:
  - `H271`: deterministic breakout-survivor gate integration on the observed breakout sleeve
- if `H271` fails:
  - kill this exact deterministic continuation
  - pivot to:
    - selector-state / top-k intraday stress router
    - or library-grade intraday state atoms

## Validation

Completed before the run:
- `python -m py_compile src/entry_alpha_research.py analysis/h270_breakout_survivor_label_rewrite_audit.py tests/test_entry_alpha_research.py`
- `pytest -q tests/test_entry_alpha_research.py tests/test_intraday_exit_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h270_breakout_survivor_label_rewrite_audit.py`
- read `artifacts/run_summaries/latest_entry_alpha_breakout_survivor_label_rewrite_audit.json`

Verdict:
- `H270`: **PASSED**
