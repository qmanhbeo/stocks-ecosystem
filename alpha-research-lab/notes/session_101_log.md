# Session 101 Log

## Objective
Run the exact family-local reintegration follow-through after Session 100's survivor-gate pass:
- `H272`: test whether the `H271` breakout-survivor gate still helps when applied only to `breakout_followthrough` rows inside the carried broader entry book, while non-breakout families remain unchanged

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H270` had already passed the breakout-survivor label rewrite on the observed `breakout_followthrough` sleeve
- `H271` had already passed deterministic survivor-sleeve integration with:
  - `entry_prob__intraday_shape_core >= 0.4572`
  - `dev_q90`
- the unresolved question was structural again:
  - was that only a survivor-sleeve artifact?
  - or could the survivor gate survive reintegration into a broader mixed-family deterministic book?
- the honest broader baseline remained the carried sparse-breadth contract from the older entry-alpha branch:
  - `top_m=5`
  - `min_selection_score=0.65`
  - `min_score_gap=0.03`
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## What changed

Added:
- `analysis/h272_breakout_survivor_family_trust_compatibility_integration.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_breakout_survivor_family_trust_compatibility_integration.json`
- `artifacts/entry_alpha/20260404_113609_h272_breakout_survivor_family_trust_compatibility_integration_results.parquet`
- `artifacts/entry_alpha/20260404_113609_h272_breakout_survivor_family_trust_compatibility_integration_best_daily.parquet`
- `artifacts/entry_alpha/20260404_113609_h272_breakout_survivor_family_trust_compatibility_integration_baseline_daily.parquet`
- `artifacts/entry_alpha/20260404_113609_h272_breakout_survivor_family_trust_compatibility_integration_panel.parquet`

### H272 - Breakout Survivor Family Trust Compatibility Integration
**Hypothesis:**
If the `H271` breakout-survivor gate is real, it should still help when applied only to breakout-family rows inside the carried sparse-breadth entry book, while non-breakout families remain unchanged.

**Command / code:**
`conda run -n stocks python analysis/h272_breakout_survivor_family_trust_compatibility_integration.py`

**Inputs:**
- `H271` summary:
  - score column `entry_prob__intraday_shape_core`
  - threshold `0.4572`
- `H270` scored panel:
  - winner survivor contract `net_soft_survivor`
- carried broader contract:
  - `top_m=5`
  - `min_selection_score=0.65`
  - `min_score_gap=0.03`
- two missing-score policies on breakout rows:
  - `survivor_dev_q90_keep_missing`
  - `survivor_dev_q90_block_missing`
- coverage guard:
  - total allowed rows `>= 150`
  - validation allowed rows `>= 75`
  - confirmation allowed rows `>= 70`
  - confirmation cash-weight increase `<= +0.15` vs the carried sparse baseline

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_breakout_survivor_family_trust_compatibility_integration.json`

| Metric | Value | Note |
|--------|-------|------|
| baseline variant | `carried_sparse_contract` | broader mixed-family carried book |
| baseline validation relative return | `-0.1218` | benchmark-relative |
| baseline confirmation relative return | `-0.2142` | benchmark-relative |
| baseline overall relative return | `-0.2796` | full `2023-2025` restarted slice |
| best variant | `survivor_dev_q90_keep_missing` | selected compatibility winner |
| best variant missing policy | `keep_missing` | leave missing-score breakout rows unchanged |
| best variant winner survivor contract | `net_soft_survivor` | inherited `H270` winner contract |
| best variant allowed rows | `219` | `54` dev / `81` validation / `84` confirmation |
| best variant observed breakout rows kept | `8` | only high-conviction observed breakout rows survive |
| best variant validation relative return | `-0.1148` | still negative in absolute terms |
| best variant confirmation relative return | `-0.0447` | still negative in absolute terms |
| best variant overall relative return | `+0.1548` | stitched restarted-window book turns positive |
| best variant validation relative delta | `+0.0070` | vs carried sparse baseline |
| best variant confirmation relative delta | `+0.1696` | vs carried sparse baseline |
| best variant overall relative delta | `+0.4344` | vs carried sparse baseline |
| best variant validation IR delta | `+0.0641` | vs carried sparse baseline |
| best variant confirmation IR delta | `+0.7411` | vs carried sparse baseline |
| best variant overall IR delta | `+0.6110` | vs carried sparse baseline |

**Result:**
`H272` passes on the predeclared reintegration contract.

What passed:
- the `H271` survivor gate is not only a survivor-sleeve artifact
- it can improve the carried sparse-breadth mixed-family book on the restarted `2023-2025` contract
- the useful reintegration winner is:
  - `survivor_dev_q90_keep_missing`

What did **not** pass yet:
- the branch is still not a broad-book or live-ready winner
- validation and confirmation relative returns remain negative in absolute terms:
  - validation `-0.1148`
  - confirmation `-0.0447`
- the carrying shape remains narrow:
  - only `8` observed breakout rows survive inside the carried contract

So this is a compatibility pass, not a broad-book deployment pass.

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 101 resolves:
- `H272` passes:
  - the `H271` survivor gate is not only a local sleeve artifact
  - it can still improve the carried sparse-breadth mixed-family book
- but the pass stays narrow:
  - the reintegrated book is still benchmark-negative in validation and confirmation
  - the useful effect is compatibility / damage reduction, not broad-book dominance

Branch effect:
- keep the original breakout-trust continuation family closed:
  - `H269` still kills that exact line
- promote `H272` as offline evidence only
- do **not** treat `H272` as a new entry-alpha champion
- if this exact branch continues, the next honest follow-through is:
  - `H273`: narrow breakout-survivor current-account compatibility audit
- if `H273` is not pursued or fails:
  - kill this exact reintegration continuation
  - pivot to:
    - `top-k intraday stress router`
    - or `library-grade intraday shape atoms`

## Validation

Completed before the run:
- `python -m py_compile alpha-research-lab/analysis/h272_breakout_survivor_family_trust_compatibility_integration.py alpha-research-lab/analysis/h271_breakout_survivor_gate_integration.py alpha-research-lab/src/entry_alpha_research.py`
- `pytest -q alpha-research-lab/tests/test_entry_alpha_research.py alpha-research-lab/tests/test_intraday_exit_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h272_breakout_survivor_family_trust_compatibility_integration.py`
- read `artifacts/run_summaries/latest_entry_alpha_breakout_survivor_family_trust_compatibility_integration.json`

Verdict:
- `H272`: **PASSED**
