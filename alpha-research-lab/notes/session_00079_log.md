# Session 79 Log

## Objective
Run `H248` and test whether the parked small-book entry-alpha branch only works on catalyst-dense dates rather than on all dates.

This session did not try to change the live branch.
It kept the branch explicitly small-book and tested only date-level catalyst gating on carried contracts, not another new model family.

## Starting point

Coming in:
- Session 78 had already rejected the sharpened-label path in `H247`
- the only surviving side result was the unsharpened `top2` `price_state` compact model on `2019-2025`
- the next queued question was whether small-book structure matters only when top candidates are backed by sparse catalysts

## What changed

Added:
- `analysis/h248_entry_alpha_catalyst_concentrated_small_book.py`

Shared support added:
- `apply_date_gate_to_entry_allowed_matrix()` in `src/entry_alpha_research.py`

Regression coverage added:
- `tests/test_entry_alpha_research.py`

Branch-local cached artifacts added under `artifacts/entry_alpha/`:
- `h248_candidate_panel_2019_2025.parquet`
- `h248_base_labels_2019_2025.parquet`

## H248 outcome

### Contract audited

`H248` stayed branch-local and did **not** touch `2026+`:
- date range used:
  - `2019-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no forward lockbox read

Carried contracts:
- `h245_top1_anchor`
  - `topk1__topm5__score_0p6__gap_none`
- `h245_top2_anchor`
  - `topk2__topm5__score_0p65__gap_0p03`
- `h247_top2_price_state_side`
  - `topk2__price_state__label_0__threshold_0p55`

Catalyst families used:
- rolling news:
  - `data/features/xs_news_sentiment_rolling.parquet`
  - row flag = `has_news_5d > 0`
- insider conviction:
  - `c5_ins_relative_size_5d > 0`
- event / filing surface:
  - `data/features/event_surface_daily.parquet`
  - row flags:
    - `recent_any_filing_5d > 0`
    - `dividend_window_pre_20d > 0`
    - `issuance_window_pre_20d > 0`

Date gates tested on the top-5 candidate pool:
- `highconv_ge1`
  - at least `1` top-5 candidate has insider / filing / corp-action support
  - overall gate rate `71.13%`
- `highconv_ge2`
  - at least `2` top-5 candidates have insider / filing / corp-action support
  - overall gate rate `35.33%`
- `multisource_ge1`
  - at least `1` top-5 candidate has `2+` catalyst families
  - overall gate rate `50.54%`
- `news_or_insider_ge1`
  - at least `1` top-5 candidate has news or insider support
  - overall gate rate `61.52%`

### `h245_top1_anchor`

Best gate:
- `highconv_ge1`

Metrics vs the always-on `top1` anchor:
- validation relative delta `+332.33%`
- validation IR delta `+0.90`
- confirmation relative delta `-81.90%`
- confirmation IR delta `-1.28`

Interpretation:
- this is a large validation overfit, not a usable catalyst-conditioned contract

### `h245_top2_anchor`

Best gate:
- `highconv_ge2`

Metrics vs the always-on `top2` anchor:
- validation relative delta `+38.82%`
- confirmation relative delta `-16.22%`

Near-miss:
- `multisource_ge1`
  - validation relative delta `+38.31%`
  - confirmation relative delta `-34.25%`

Interpretation:
- catalyst concentration helps validation somewhat on the `top2` anchor
- but no gate survives the `2025` floor cleanly enough to count as honest offline promotion

### `h247_top2_price_state_side`

Best gate:
- `highconv_ge1`

Metrics vs the always-on `top2` `price_state` side result:
- validation relative delta `-89.17%`
- confirmation relative delta `-15.62%`

Interpretation:
- every tested catalyst gate made the `H247` side result worse
- the existing `top2` compact-model side result does **not** want this date-level catalyst filter

## Branch decision

Do **not** promote entry alpha into the live branch.

What `H248` resolves:
- sparse catalyst concentration does **not** rescue the carried small-book contracts on the current `2019-2025` data stack
- no catalyst gate cleared the validation-plus-`2025` offline gate
- the `H247` `top2` compact-model side result gets weaker, not stronger, under these gates

Branch effect:
- close Family A (`H247-H248`) on the current data stack
- do **not** keep tuning small-book catalyst gates locally
- if model-side queue work is intentionally continued later, move to `H249`, not more `H247/H248` variants

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h248_entry_alpha_catalyst_concentrated_small_book.py src/entry_alpha_research.py tests/test_entry_alpha_research.py`
- `pytest -q tests/test_entry_alpha.py tests/test_entry_alpha_research.py`
- full `python analysis/h248_entry_alpha_catalyst_concentrated_small_book.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_catalyst_concentrated_small_book.json`
- `artifacts/entry_alpha/20260331_101447_h248_entry_alpha_catalyst_concentrated_small_book_results.parquet`
- `artifacts/entry_alpha/20260331_101447_h248_entry_alpha_catalyst_concentrated_small_book_contract_winners.parquet`
- `artifacts/entry_alpha/20260331_101447_h248_entry_alpha_catalyst_concentrated_small_book_catalyst_daily.parquet`
