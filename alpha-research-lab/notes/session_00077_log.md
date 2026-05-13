# Session 77 Log

## Objective
Run `H246` and test whether a light confirmation / calibration overlay can improve the small-book entry-alpha contracts identified by `H245`.

This session did not try to change the live branch.
It kept the branch explicitly small-book (`top1/top2`) and tested only local confirmation overlays, not another broad model family.

## Starting point

Coming in:
- Session 76 had already shown that the entry-alpha branch behaves more like a historical `top1` contract than a `top5` timing overlay
- no audited `top_k` contract was honestly promotable
- the next honest question was whether a **light** overlay could improve the small-book contract without collapsing back into overfitting

## What changed

Added:
- `analysis/h246_entry_alpha_small_book_confirmation.py`

Shared support added:
- `build_entry_row_mask()` in `src/entry_alpha_research.py`
- `build_small_book_confirmation_overlay_frame()` in `src/entry_alpha_research.py`
- `build_small_book_threshold_series()` in `src/entry_alpha_research.py`

Regression coverage added:
- `tests/test_entry_alpha_research.py`

## H246 outcome

### Contract audited

`H246` only tested the small-book contracts carried forward from `H245`:
- `top_k = 1`
  - base sparse contract:
    - `topm5`
    - `min_selection_score = 0.60`
    - no score-gap requirement
- `top_k = 2`
  - base sparse contract:
    - `topm5`
    - `min_selection_score = 0.65`
    - `min_score_gap = 0.03`

Overlays tested:
- `soft_consensus_threshold`
- `soft_reversal_threshold`
- `soft_gap_absorb_threshold`
- `soft_uncrowded_threshold`
- `near_cutoff_no_confirm_veto`
- `soft_consensus_plus_veto`

### `top_k = 1`

Best overlay by validation:
- `topk1__near_cutoff_no_confirm_veto`

Metrics:
- validation relative `+67.91%`
- confirmation relative `+48.14%`
- forward relative `-15.20%`

Delta vs the base sparse `top1` contract:
- validation `+0.00%`
- confirmation `+0.00%`
- forward `+0.00%`

Interpretation:
- every tested top1 overlay collapsed back to the same result as the base sparse contract
- local confirmation features did **not** meaningfully recalibrate the top1 contract

### `top_k = 2`

Validation winner:
- `topk2__soft_consensus_threshold`

Metrics:
- validation relative `+135.26%`
- confirmation relative `-42.25%`
- forward relative `-25.14%`

Delta vs the base sparse `top2` contract:
- validation `+114.99%`
- confirmation `-27.65%`
- forward `-21.84%`

Interpretation:
- this is a classic validation overfit
- the overlay looks spectacular in validation and fails badly afterwards

Near-miss overlays:
- `near_cutoff_no_confirm_veto`
- `soft_consensus_plus_veto`

Metrics for both:
- validation around `+30%`
- confirmation around `-34%`
- forward around `+2.50%`

Interpretation:
- these produce small forward improvements over the base sparse `top2` contract
- but they still degrade confirmation materially and do not clear the honest gate

## Branch decision

Do **not** promote entry alpha into the live branch.

What `H246` adds:
- top1 branch:
  - local confirmation overlays are effectively a no-op
- top2 branch:
  - soft consensus overlays overfit validation
  - lighter veto-style overlays are not strong enough to matter honestly

So the branch remains:
- **offline evidence only**
- stronger as a statement about small-book structure than as a deployable rule

Best next branch if this architecture is intentionally continued:
- `H247`
  - keep the branch small-book
  - stop testing more local confirmation overlays on the current label
  - sharpen the label / target for the compact entry-model branch instead

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h246_entry_alpha_small_book_confirmation.py src/entry_alpha_research.py`
- `pytest -q tests/test_entry_alpha_research.py`
- full `python analysis/h246_entry_alpha_small_book_confirmation.py` run completed
- `git diff --check` passed after the note/doc updates
