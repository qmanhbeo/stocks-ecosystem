# Session 78 Log

## Objective
Run `H247` and test whether sharpening the small-book entry-alpha label can rescue the parked compact-model branch without touching the `2026+` lockbox.

This session did not try to change the live branch.
It kept the branch explicitly small-book (`top1/top2`) and treated label-sharpening as the smallest honest follow-through after `H246`.

## Starting point

Coming in:
- Session 76 had already shown that the branch behaves more like a historical `top1/top2` contract than a `top5` timing overlay
- Session 77 had already closed the local confirmation-overlay sub-branch
- the next honest question was whether the current compact model was learning the wrong target rather than the wrong features

## What changed

Added:
- `analysis/h247_entry_alpha_label_sharpen_audit.py`

Regression coverage added:
- `tests/test_entry_alpha.py`

Branch-local cached artifacts added under `artifacts/entry_alpha/`:
- `h247_candidate_panel_2019_2025.parquet`
- `h247_base_labels_2019_2025.parquet`

Why branch-local caches were used:
- the canonical entry-alpha artifacts in `data/features/entry_alpha/` currently extend into `2026`
- this pass intentionally stayed on `2019-2025`
- the branch-local cache keeps the no-`2026` rule honest without rewriting the canonical published artifacts

## H247 outcome

### Contract audited

`H247` stayed branch-local and did **not** touch `2026+`:
- date range used:
  - `2019-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no forward lockbox read

Carried anchors from `H245/H246`:
- `top_k = 1`
  - `topk1__topm5__score_0p6__gap_none`
- `top_k = 2`
  - `topk2__topm5__score_0p65__gap_0p03`

Compact-model family audited:
- `implementation_context`
- `price_state`
- `blend`

Label buffers audited:
- `0.00`
- `0.01`
- `0.02`
- `0.03`

Thresholds audited:
- `0.55`
- `0.60`
- `0.65`
- `0.70`

Observed label positive-rate compression:
- `buffer = 0.00`
  - overall `48.63%`
  - dev `49.11%`
  - validation `48.53%`
  - confirmation `46.80%`
- `buffer = 0.01`
  - overall `40.58%`
  - dev `42.11%`
  - validation `39.16%`
  - confirmation `37.09%`
- `buffer = 0.02`
  - overall `33.70%`
  - dev `35.91%`
  - validation `31.18%`
  - confirmation `29.65%`
- `buffer = 0.03`
  - overall `28.13%`
  - dev `30.66%`
  - validation `25.18%`
  - confirmation `23.63%`

### `top_k = 1`

Best sharpened candidate:
- `topk1__blend__label_0p03__threshold_0p55`

Metrics vs the `H245` `top1` anchor:
- validation AUC `0.549`
- confirmation AUC `0.574`
- validation delta `+38.16%`
- confirmation delta `-96.68%`

Interpretation:
- this is not a rescue
- sharper labels can improve ranking metrics locally
- but the resulting `top1` contract collapses in `2025`

### `top_k = 2`

Best sharpened candidate:
- `topk2__blend__label_0p03__threshold_0p55`

Metrics vs the `H245` `top2` anchor:
- validation AUC `0.549`
- confirmation AUC `0.574`
- validation delta `+85.80%`
- confirmation delta `-33.94%`

Interpretation:
- again, this is a clean validation overfit
- sharpening the label did not survive the `2025` gate

Best overall `top2` candidate in the run:
- `topk2__price_state__label_0__threshold_0p55`

Metrics vs the `H245` `top2` anchor:
- validation AUC `0.514`
- confirmation AUC `0.528`
- validation relative `+93.79%`
- validation delta `+73.52%`
- confirmation relative `-12.12%`
- confirmation delta `+2.47%`

Interpretation:
- the only promoted candidate in this run used the **original** label contract, not a sharpened one
- that makes it useful offline evidence about the `top2` compact-model contract
- it does **not** validate the sharpened-label thesis that `H247` was designed to test

## Branch decision

Do **not** promote entry alpha into the live branch.

What `H247` resolves:
- the current label-sharpening path does **not** rescue the branch on `2019-2025`
- no `label_edge_buffer > 0` candidate cleared the validation-plus-`2025` gate
- `H248` should **not** be opened from this result alone

What survives as offline evidence:
- the branch still looks more like a small-book problem than a `top5` timing overlay
- inside that branch, the unsharpened `top2` `price_state` compact model is now the strongest contract-level side result against the `H245` `top2` anchor on `2019-2025`
- because `2026+` was intentionally not touched, that side result is still **not** an honest promoted winner

Best next branch if this architecture is intentionally continued later:
- none under the current no-`2026` rule
- if the branch is ever intentionally reopened after the lockbox can be read, the only narrow leftover is a forward check on the unsharpened `top2` compact-model survivor

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h247_entry_alpha_label_sharpen_audit.py tests/test_entry_alpha.py`
- `pytest -q tests/test_entry_alpha.py tests/test_entry_alpha_research.py`
- full `python analysis/h247_entry_alpha_label_sharpen_audit.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_label_sharpen_audit.json`
- `artifacts/entry_alpha/20260331_100109_h247_entry_alpha_label_sharpen_audit_results.parquet`
- `artifacts/entry_alpha/20260331_100109_h247_entry_alpha_label_sharpen_audit_contract_winners.parquet`
- `artifacts/entry_alpha/20260331_100109_h247_entry_alpha_label_sharpen_audit_label_stats.parquet`
