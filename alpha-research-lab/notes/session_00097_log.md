# Session 97 Log

## Objective
Run the smallest honest reintegration follow-through after Session 96's breakout-sleeve gate pass:
- `H268`: test whether the `H267` breakout trust gate still helps when applied only to `breakout_followthrough` rows inside the carried broader entry book, while leaving the other families unchanged

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H266` had already passed on the observed breakout sleeve
- `H267` had already passed on the same sleeve with the dev-calibrated gate:
  - `entry_prob__intraday_shape_core >= 0.5198`
- the unresolved question was structural:
  - was that only a breakout-sleeve artifact?
  - or could the gate survive reintegration into a broader mixed-family deterministic book?
- the honest broader baseline was the carried sparse-breadth contract from the older entry-alpha branch:
  - `top_m=5`
  - `min_selection_score=0.65`
  - `min_score_gap=0.03`
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## What changed

Added:
- `analysis/h268_breakout_family_trust_compatibility_integration.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_breakout_family_trust_compatibility_integration.json`
- `artifacts/entry_alpha/20260403_124630_h268_breakout_family_trust_compatibility_integration_results.parquet`
- `artifacts/entry_alpha/20260403_124630_h268_breakout_family_trust_compatibility_integration_best_daily.parquet`
- `artifacts/entry_alpha/20260403_124630_h268_breakout_family_trust_compatibility_integration_baseline_daily.parquet`
- `artifacts/entry_alpha/20260403_124630_h268_breakout_family_trust_compatibility_integration_panel.parquet`

### H268 - Breakout Family Trust Compatibility Integration
**Hypothesis:**
If the `H267` breakout trust gate is real, it should still help when applied only to breakout-family rows inside the carried sparse-breadth entry book, while non-breakout families remain unchanged.

**Command / code:**
`conda run -n stocks python analysis/h268_breakout_family_trust_compatibility_integration.py`

**Inputs:**
- `H267` summary:
  - score column `entry_prob__intraday_shape_core`
  - threshold `0.5198`
- `H266` scored panel
- carried broader contract:
  - `top_m=5`
  - `min_selection_score=0.65`
  - `min_score_gap=0.03`
- two missing-score policies on breakout rows:
  - `breakout_dev_q90_keep_missing`
  - `breakout_dev_q90_block_missing`
- coverage guard:
  - total allowed rows `>= 150`
  - validation allowed rows `>= 75`
  - confirmation allowed rows `>= 70`
  - confirmation cash-weight increase `<= +0.15` vs the carried sparse baseline

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_breakout_family_trust_compatibility_integration.json`

| Metric | Value | Note |
|--------|-------|------|
| baseline variant | `carried_sparse_contract` | broader mixed-family carried book |
| baseline validation relative return | `-0.1218` | benchmark-relative |
| baseline confirmation relative return | `-0.2142` | benchmark-relative |
| baseline overall relative return | `-0.2796` | full `2023-2025` restarted slice |
| best variant | `breakout_dev_q90_keep_missing` | selected compatibility winner |
| best variant missing policy | `keep_missing` | leave missing-score breakout rows unchanged |
| best variant allowed rows | `219` | `56` dev / `82` validation / `81` confirmation |
| best variant observed breakout rows kept | `8` | only high-conviction observed breakout rows survive |
| best variant validation relative return | `-0.1148` | still negative in absolute terms |
| best variant confirmation relative return | `-0.0447` | still negative in absolute terms |
| best variant overall relative return | `+0.1518` | stitched restarted-window book turns positive |
| best variant validation relative delta | `+0.0070` | vs carried sparse baseline |
| best variant confirmation relative delta | `+0.1696` | vs carried sparse baseline |
| best variant overall relative delta | `+0.4314` | vs carried sparse baseline |
| best variant validation IR delta | `+0.0641` | vs carried sparse baseline |
| best variant confirmation IR delta | `+0.7411` | vs carried sparse baseline |
| best variant overall IR delta | `+0.6031` | vs carried sparse baseline |

**Result:**
`H268` passes on the predeclared reintegration contract.

The pass is real but narrow:
- the breakout trust overlay survives reintegration into the carried sparse-breadth book
- the gain is mostly in confirmation and stitched overall behavior
- the best variant keeps only `8` observed breakout rows inside the carried contract

The branch is still **not** a live-ready entry winner:
- validation relative return remains negative:
  - `-0.1148`
- confirmation relative return remains negative:
  - `-0.0447`
- so this is a compatibility pass, not a broad-book absolute success

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 97 resolves:
- `H268` passes:
  - the `H267` breakout trust gate is not only a breakout-sleeve artifact
  - it can improve the carried sparse-breadth mixed-family book on the restarted `2023-2025` contract
- but the pass stays narrow:
  - the best reintegrated book is still benchmark-negative in validation and confirmation
  - the useful effect is compatibility / damage reduction, not broad-book dominance

Branch effect:
- keep all continuation-veto follow-through closed:
  - `H260/H261` remain closed
  - `H264/H265` remain closed
- keep the live sticky branch unchanged
- promote the reintegration result as offline evidence only
- do **not** treat `H268` as a new entry-alpha champion
- if this exact branch continues, the next honest follow-through is:
  - `H269`: narrow breakout-trust current-account compatibility audit
- if `H269` is not pursued or fails, the next fallback should be:
  - breakout survivor label rewrite
  - or selector-state / top-k intraday stress routing

## Validation

Completed before the run:
- `python -m py_compile analysis/h268_breakout_family_trust_compatibility_integration.py`
- `pytest -q tests/test_entry_alpha_research.py tests/test_intraday_exit_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h268_breakout_family_trust_compatibility_integration.py`
- read `artifacts/run_summaries/latest_entry_alpha_breakout_family_trust_compatibility_integration.json`

Verdict:
- `H268`: **PASSED**
