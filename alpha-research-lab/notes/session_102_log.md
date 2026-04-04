# Session 102 Log

## Objective
Run the last narrow operational follow-through after Session 101's survivor-gate reintegration pass:
- `H273`: test whether the `H272` breakout-survivor overlay helps enough inside the current-account / sticky operational framing to justify keeping this exact branch alive

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H270` had already passed the breakout-survivor label rewrite on the observed `breakout_followthrough` sleeve
- `H271` had already passed deterministic survivor-sleeve integration with:
  - `entry_prob__intraday_shape_core >= 0.4572`
- `H272` had already passed narrowly as a reintegration / compatibility result inside the carried sparse-breadth book
- but the branch still had a clear ceiling:
  - the best reintegrated book remained benchmark-negative in both validation and confirmation
  - only `8` observed breakout rows survived in the best reintegration winner
- the next honest question was therefore final and narrow:
  - if the `H272` winner is applied inside the current-account / operational sticky framing, does any real compatibility value remain?
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## What changed

Added:
- `analysis/h273_breakout_survivor_current_account_compatibility.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_breakout_survivor_current_account_compatibility.json`
- `artifacts/entry_alpha/20260404_114645_h273_breakout_survivor_current_account_compatibility_results.parquet`
- `artifacts/entry_alpha/20260404_114645_h273_breakout_survivor_current_account_compatibility_best_daily.parquet`
- `artifacts/entry_alpha/20260404_114645_h273_breakout_survivor_current_account_compatibility_baseline_daily.parquet`
- `artifacts/entry_alpha/20260404_114645_h273_breakout_survivor_current_account_compatibility_panel.parquet`

### H273 - Narrow Breakout-Survivor Current-Account Compatibility Audit
**Hypothesis:**
If the narrow `H272` overlay has real operational value, it should still help once inserted into the current-account / sticky operational framing rather than just the carried sparse entry book.

**Command / code:**
`conda run -n stocks python analysis/h273_breakout_survivor_current_account_compatibility.py`

**Inputs:**
- `H272` winner:
  - `survivor_dev_q90_keep_missing`
  - score `entry_prob__intraday_shape_core`
  - threshold `0.4572`
  - survivor contract `net_soft_survivor`
- `H270` scored panel
- current-account / operational framing:
  - sticky activation from `activation_state`
  - `incumbent_score_bonus = 0.015`
  - no `2026+` read
- variants:
  - `operational_sticky_baseline`
  - `carried_sparse_plus_sticky`
  - `h272_overlay_plus_sticky`
- guards:
  - allowed rows `>= 150`
  - confirmation allowed rows `>= 70`
  - sparse-book rate increase vs operational baseline `<= +0.20`
  - average holdings drop vs operational baseline `<= 1.0`

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_breakout_survivor_current_account_compatibility.json`

| Metric | Value | Note |
|--------|-------|------|
| operational baseline validation relative return | `-0.0873` | sticky operational baseline |
| operational baseline confirmation relative return | `+0.1880` | sticky operational baseline |
| operational baseline overall relative return | `+0.4660` | sticky operational baseline |
| sparse control validation relative return | `-0.5346` | carried sparse contract plus sticky |
| sparse control confirmation relative return | `-0.0824` | carried sparse contract plus sticky |
| sparse control overall relative return | `-0.2154` | carried sparse contract plus sticky |
| candidate validation relative return | `-0.5635` | `h272_overlay_plus_sticky` |
| candidate confirmation relative return | `-0.1650` | `h272_overlay_plus_sticky` |
| candidate overall relative return | `-0.4340` | `h272_overlay_plus_sticky` |
| candidate validation delta vs operational | `-0.4762` | much worse than current-account baseline |
| candidate confirmation delta vs operational | `-0.3530` | much worse than current-account baseline |
| candidate overall delta vs operational | `-0.8999` | much worse than current-account baseline |
| candidate confirmation delta vs sparse control | `-0.0826` | worse than the carried sparse control too |
| candidate VC sparse-book rate | `0.9800` | vs operational baseline `0.4910` |
| candidate VC avg num holdings | `0.7315` | vs operational baseline `3.0962` |

**Result:**
`H273` fails cleanly.

Failure mode:
- the overlay loses badly to the unchanged operational sticky baseline
- it also loses to the weaker carried sparse control
- the narrowness cost dominates again:
  - near-always sparse
  - much lower average holdings
  - confirmation cash weight materially higher than baseline

So the branch has reached its honest limit:
- the breakout-survivor rewrite is real as offline evidence on narrow local contracts
- but it does **not** survive current-account operational compatibility

**Verdict: FAILED**

## Branch decision

Do **not** change the live branch.

What Session 102 resolves:
- `H273` fails:
  - the narrow breakout-survivor overlay does not survive current-account compatibility
  - the branch should not be stretched further inside the same continuation family

Branch effect:
- close the breakout-survivor continuation family on the current restarted contract:
  - `H270-H272` remain useful offline evidence
  - `H273` kills operational continuation of the family
- keep the live sticky branch unchanged
- do **not** promote any entry-alpha winner from this line
- the next honest fallback branches are:
  - `top-k intraday stress router`
  - `library-grade intraday shape atoms`

## Validation

Completed before the run:
- `python -m py_compile alpha-research-lab/analysis/h273_breakout_survivor_current_account_compatibility.py alpha-research-lab/analysis/h272_breakout_survivor_family_trust_compatibility_integration.py alpha-research-lab/src/entry_alpha_research.py`
- `pytest -q alpha-research-lab/tests/test_entry_alpha_research.py alpha-research-lab/tests/test_intraday_exit_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h273_breakout_survivor_current_account_compatibility.py`
- read `artifacts/run_summaries/latest_entry_alpha_breakout_survivor_current_account_compatibility.json`

Verdict:
- `H273`: **FAILED**
