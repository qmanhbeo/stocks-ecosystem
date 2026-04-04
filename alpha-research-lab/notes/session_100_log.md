# Session 100 Log

## Objective
Run the exact deterministic follow-through after Session 99's survivor-target pass:
- `H271`: test whether a simple gate built from the `H270` winner score improves the realized observed breakout-survivor sleeve versus the ungated observed-breakout-survivor baseline

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H270` had already passed the breakout-survivor label rewrite audit on the observed `breakout_followthrough` sleeve
- the surviving `H270` contract was:
  - `net_soft_survivor`
  - `5d cycle_return_net > -0.01`
  - `10d cycle_return_net > 0.00`
- the surviving `H270` score was:
  - `entry_prob__intraday_shape_core`
- the branch ceiling was already explicit:
  - `H270` was predictive, not deterministic
  - the best path control still had stronger confirmation top-quintile `10d` economics
- the next honest question was no longer:
  - "does the target rewrite rescue predictive ranking?"
- it was:
  - does a deterministic gate built from the `H270` winner score improve the realized breakout-survivor sleeve versus the ungated survivor baseline?
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## What changed

Used existing runner:
- `analysis/h271_breakout_survivor_gate_integration.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_breakout_survivor_gate_integration.json`
- `artifacts/entry_alpha/20260404_112625_h271_breakout_survivor_gate_integration_results.parquet`
- `artifacts/entry_alpha/20260404_112625_h271_breakout_survivor_gate_integration_best_daily.parquet`
- `artifacts/entry_alpha/20260404_112625_h271_breakout_survivor_gate_integration_baseline_daily.parquet`
- `artifacts/entry_alpha/20260404_112625_h271_breakout_survivor_gate_integration_gate_panel.parquet`

### H271 - Breakout Survivor Gate Integration
**Hypothesis:**
If `H270` is real, a simple high-conviction gate on the observed breakout-survivor sleeve should improve deterministic realized performance versus the ungated observed-breakout-survivor baseline.

**Command / code:**
`conda run -n stocks python analysis/h271_breakout_survivor_gate_integration.py`

**Inputs:**
- `H270` summary and scored panel
- same restarted `2023-2025` protocol as `H270`
- same observed breakout-survivor sleeve:
  - `entry_thesis_family == breakout_followthrough`
  - `can_buy_next_open == True`
  - `entry_prob__intraday_shape_core` observed
  - winner contract from `H270`:
    - `net_soft_survivor`
- predeclared dev-only threshold grid:
  - `dev_q50`
  - `dev_q80`
  - `dev_q90`
- coverage guard:
  - confirmation allowed rows `>= 120`

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_breakout_survivor_gate_integration.json`

| Metric | Value | Note |
|--------|-------|------|
| baseline variant | `observed_breakout_survivor_always_on` | ungated observed breakout-survivor sleeve |
| baseline validation relative return | `-0.1615` | benchmark-relative |
| baseline confirmation relative return | `-0.3327` | benchmark-relative |
| baseline overall relative return | `-0.4499` | full `2023-2025` restarted slice |
| winning gate | `dev_q90` | strongest deterministic gate |
| winning threshold | `0.4572` | dev-phase `90%` quantile of `entry_prob__intraday_shape_core` |
| winning allowed rows | `505` | `207` dev / `140` validation / `158` confirmation |
| winning validation relative return | `+0.0498` | turns validation positive |
| winning confirmation relative return | `-0.2794` | still negative in absolute terms |
| winning overall relative return | `-0.2594` | materially above the ungated sleeve |
| winning validation relative delta | `+0.2113` | vs ungated observed-breakout-survivor baseline |
| winning confirmation relative delta | `+0.0534` | vs ungated observed-breakout-survivor baseline |
| winning validation IR delta | `+1.0527` | vs ungated observed-breakout-survivor baseline |
| winning confirmation IR delta | `+0.5324` | vs ungated observed-breakout-survivor baseline |

**Result:**
`H271` passes on the predeclared deterministic gate contract.

What passed:
- the `H270` survivor rewrite is no longer only a predictive ranking result
- a simple high-conviction gate survives deterministic sleeve integration
- the winning rule remains the high-conviction gate:
  - `dev_q90`
  - threshold `0.4572`
- both validation and confirmation relative deltas are positive against the ungated survivor sleeve

What did **not** pass yet:
- the branch is still not a broad-book or live-ready winner
- confirmation relative return remains negative in absolute terms:
  - `-0.2794`
- the working contract remains narrow:
  - `505` allowed rows overall
  - `158` confirmation rows

So this is a deterministic local pass, not a deployment pass.

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 100 resolves:
- `H271` passes:
  - the breakout-survivor rewrite survives deterministic sleeve integration
  - the best gate is:
    - `dev_q90`
    - threshold `0.4572`
- the result is still offline-only:
  - no broad-book reintegration yet
  - no current-account compatibility claim yet
  - no live promotion

Branch effect:
- keep the original breakout-trust continuation family closed:
  - `H269` still kills that exact line
- promote `H271` as offline evidence only
- the next exact follow-through is:
  - `H272`: breakout-survivor family trust compatibility integration
- if `H272` fails:
  - kill this exact reintegration continuation
  - pivot to:
    - `top-k intraday stress router`
    - or `library-grade intraday shape atoms`

## Validation

Completed before the run:
- `python -m py_compile alpha-research-lab/analysis/h271_breakout_survivor_gate_integration.py alpha-research-lab/src/entry_alpha_research.py alpha-research-lab/tests/test_entry_alpha_research.py`
- `pytest -q alpha-research-lab/tests/test_entry_alpha_research.py alpha-research-lab/tests/test_intraday_exit_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h271_breakout_survivor_gate_integration.py`
- read `artifacts/run_summaries/latest_entry_alpha_breakout_survivor_gate_integration.json`

Verdict:
- `H271`: **PASSED**
