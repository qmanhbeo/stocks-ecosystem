# Session 76 Log

## Objective
Run `H245` and decide whether the stock-specific entry-alpha branch is really a small-book `top1/top2` contract rather than a `top5` contract with sparse thresholds.

This session did not try to change the live branch.
It audited the contract shape of the parked entry-alpha branch under the same locked protocol used in `H244`.

## Starting point

Coming in:
- Session 75 had already established that `H239` sparse breadth was real enough to keep as offline evidence
- `H244` then showed the dev-selected sparse-breadth winner for the `top5` contract did not survive validation cleanly enough to promote
- the next honest question was not "another top5 threshold" but "does this branch actually want a small-book contract?"

## What changed

Added:
- `analysis/h245_entry_alpha_topk_contract_audit.py`

The first run exposed one implementation bug:
- the script reused the H244-style forward gate but forgot to add `forward_relative_delta` / `forward_ir_delta`
- patched before the final run

## H245 outcome

### Contract winners by audited `top_k`

#### `top_k = 1`
Winner:
- `topk1__topm5__score_0p6__gap_none`

Metrics:
- dev relative `+1125.92%`
- validation relative `+67.91%`
- confirmation (`2025`) relative `+48.14%`
- forward (`2026+`) relative `-15.20%`

Matched fixed-`top1` baseline:
- validation relative `-73.98%`
- confirmation relative `-29.34%`
- forward relative `-14.56%`

Interpretation:
- this is the strongest historical contract in validation and `2025`
- but the forward result is still bad
- the forward relative delta vs its own baseline is only `-0.64%`, but the forward IR deteriorates sharply, so the honest gate still fails

#### `top_k = 2`
Winner:
- `topk2__topm5__score_0p65__gap_0p03`

Metrics:
- validation relative `+20.27%`
- confirmation relative `-14.60%`
- forward relative `-3.30%`

Interpretation:
- weaker than the `top1` contract historically
- not better than its own fixed-`top2` baseline on validation / confirmation

#### `top_k = 3`
Winner:
- `topk3__topm5__score_0p7__gap_0p03`

Metrics:
- validation relative `+2.21%`
- confirmation relative `-4.79%`
- forward relative `+11.44%`

Interpretation:
- best forward result of the audited contracts
- but too weak on validation to count as the right historical contract

#### `top_k = 5`
Winner:
- `topk5__topm5__score_0p65__gap_0p03`

Metrics:
- validation relative `+28.04%`
- confirmation relative `-22.13%`
- forward relative `-2.75%`

Interpretation:
- reproduces the Session 75 `H244` conclusion
- still not an honest promoted winner

### Contract-level interpretation

Validation-ranked contract winner:
- `top_k = 1`
- winner `topk1__topm5__score_0p6__gap_none`

Against the `top5` audited winner:
- validation delta `+39.87%`
- confirmation delta `+70.27%`
- forward delta `-12.44%`

Interpretation:
- the branch really does look more like a **small-book historical contract** than a `top5` timing overlay
- but that strength does **not** survive cleanly enough into `2026+`
- no audited `top_k` contract is honestly promotable

## Branch decision

Do **not** promote entry alpha into the live branch.

What `H245` changes:
- it strengthens the offline thesis that the branch wants `top1/top2` style contracts, not `top5`
- it does **not** produce a live-ready contract
- the branch remains **offline evidence only**

Best next branch if this architecture is intentionally continued:
- `H246`
  - keep the branch small-book
  - test a light confirmation / calibration overlay on top of the `top1/top2` contract
  - do **not** go back to generic `top5` timing overlays

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h245_entry_alpha_topk_contract_audit.py`
- full `python analysis/h245_entry_alpha_topk_contract_audit.py` run completed
- `git diff --check` passed after the note/doc updates
