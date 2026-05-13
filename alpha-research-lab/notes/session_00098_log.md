# Session 98 Log

## Objective
Run the last narrow compatibility check after Session 97's reintegration pass:
- `H269`: test whether the `H268` breakout-trust overlay helps enough inside the carried current-account / operational framing to justify keeping this exact branch alive

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H266` had passed on the observed breakout sleeve
- `H267` had passed on the same sleeve with `dev_q90`
- `H268` had passed narrowly as a reintegration / compatibility result inside the carried sparse-breadth book
- but the branch still had a clear ceiling:
  - the best reintegrated book remained benchmark-negative in both validation and confirmation
  - only `8` observed breakout rows survived in the best reintegration winner
- the next honest question was therefore final and narrow:
  - if the `H268` winner is applied inside the current-account / operational sticky framing, does any real compatibility value remain?
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## What changed

Added:
- `analysis/h269_breakout_trust_current_account_compatibility.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_breakout_trust_current_account_compatibility.json`
- `artifacts/entry_alpha/20260403_130705_h269_breakout_trust_current_account_compatibility_results.parquet`
- `artifacts/entry_alpha/20260403_130705_h269_breakout_trust_current_account_compatibility_best_daily.parquet`
- `artifacts/entry_alpha/20260403_130705_h269_breakout_trust_current_account_compatibility_baseline_daily.parquet`
- `artifacts/entry_alpha/20260403_130705_h269_breakout_trust_current_account_compatibility_panel.parquet`

### H269 - Narrow Breakout-Trust Current-Account Compatibility Audit
**Hypothesis:**
If the narrow `H268` overlay has real operational value, it should still help once inserted into the current-account / sticky operational framing rather than just the carried sparse entry-alpha book.

**Command / code:**
`conda run -n stocks python analysis/h269_breakout_trust_current_account_compatibility.py`

**Inputs:**
- `H268` winner:
  - `breakout_dev_q90_keep_missing`
  - score `entry_prob__intraday_shape_core`
  - threshold `0.5198`
- `H266` scored panel
- current-account / operational framing:
  - sticky activation from `activation_state`
  - `incumbent_score_bonus = 0.015`
  - no `2026+` read
- variants:
  - `operational_sticky_baseline`
  - `carried_sparse_plus_sticky`
  - `h268_overlay_plus_sticky`
- guards:
  - allowed rows `>= 150`
  - confirmation allowed rows `>= 70`
  - sparse-book rate increase vs operational baseline `<= +0.20`
  - average holdings drop vs operational baseline `<= 1.0`

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_breakout_trust_current_account_compatibility.json`

| Metric | Value | Note |
|--------|-------|------|
| operational baseline validation relative return | `-0.0873` | sticky operational baseline |
| operational baseline confirmation relative return | `+0.1880` | sticky operational baseline |
| operational baseline overall relative return | `+0.4660` | sticky operational baseline |
| sparse control validation relative return | `-0.5346` | carried sparse contract plus sticky |
| sparse control confirmation relative return | `-0.0824` | carried sparse contract plus sticky |
| candidate validation relative return | `-0.5635` | `h268_overlay_plus_sticky` |
| candidate confirmation relative return | `-0.3364` | `h268_overlay_plus_sticky` |
| candidate overall relative return | `-0.5495` | `h268_overlay_plus_sticky` |
| candidate validation delta vs operational | `-0.4762` | much worse than current-account baseline |
| candidate confirmation delta vs operational | `-0.5245` | much worse than current-account baseline |
| candidate overall delta vs operational | `-1.0155` | much worse than current-account baseline |
| candidate confirmation delta vs sparse control | `-0.2540` | worse than the carried sparse control too |
| candidate VC sparse-book rate | `0.9800` | vs operational baseline `0.4910` |
| candidate VC avg num holdings | `0.7014` | vs operational baseline `3.0962` |

**Result:**
`H269` fails cleanly.

Failure mode:
- the overlay loses badly to the unchanged operational sticky baseline
- it also loses to the weaker carried sparse control
- the narrowness cost dominates:
  - near-always sparse
  - much lower average holdings
  - confirmation cash weight materially higher than baseline

So the branch has reached its honest limit:
- the breakout-trust idea is real as offline evidence on narrow local contracts
- but it does **not** survive current-account operational compatibility

**Verdict: FAILED**

## Branch decision

Do **not** change the live branch.

What Session 98 resolves:
- `H269` fails:
  - the narrow breakout-trust overlay does not survive current-account compatibility
  - the branch should not be stretched further inside the same contract family

Branch effect:
- close the breakout-trust continuation family on the current restarted contract:
  - `H266-H268` remain useful offline evidence
  - `H269` kills operational continuation of the family
- keep the live sticky branch unchanged
- do **not** promote any entry-alpha winner from this line
- the next honest fallback branches are:
  - breakout survivor label rewrite
  - selector-state / top-k intraday stress router
  - library-grade intraday state atoms

## Validation

Completed before the run:
- `python -m py_compile analysis/h269_breakout_trust_current_account_compatibility.py`
- `pytest -q tests/test_entry_alpha_research.py tests/test_intraday_exit_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h269_breakout_trust_current_account_compatibility.py`
- read `artifacts/run_summaries/latest_entry_alpha_breakout_trust_current_account_compatibility.json`

Verdict:
- `H269`: **FAILED**
