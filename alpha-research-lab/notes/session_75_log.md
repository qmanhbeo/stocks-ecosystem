# Session 75 Log

## Objective
Run the first executable stock-specific entry-alpha ladder and decide whether it should graduate from architecture idea to active research branch.

This session did not try to change the live branch.
It tested the parked entry-alpha idea offline from the smallest honest implementation upward.

## Starting point

Coming in:
- the current live branch was still frozen:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- the entry-alpha idea existed only as a parked architecture sketch in the central repo docs
- no canonical candidate-panel / label artifacts existed yet under `data/features/entry_alpha/`

## What changed

### New canonical entry-alpha artifacts

Added and populated:
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/features/entry_alpha/entry_scores_daily.parquet`

Coverage after the final refresh:
- `2019-01-02` to `2026-03-27`
- `1804` unique dates

### New analysis runners

Added:
- `analysis/h238_entry_alpha_candidate_panel.py`
- `analysis/h239_entry_alpha_sparse_breadth_baseline.py`
- `analysis/h240_entry_alpha_single_family_screens.py`
- `analysis/h241_entry_alpha_compact_model.py`
- `analysis/h242_entry_alpha_soft_exposure_prior.py`
- `analysis/h243_entry_alpha_live_compatibility.py`
- `analysis/h244_entry_alpha_sparse_breadth_protocol.py`

### Shared research support

Added:
- `src/entry_alpha.py`
- `src/entry_alpha_research.py`

Also fixed two workflow-level bugs discovered during the runs:

1. `src/run_summary.py` could not serialize numpy arrays / timestamps in summary payloads.
   - this blocked the first `H242` run at artifact write time
   - fixed centrally and covered by `tests/test_run_summary.py`

2. `load_or_build_entry_artifacts()` reused stale cached candidate-panel / label artifacts if rank coverage matched, even when requested dates had extended into a new year.
   - this would have allowed `2026` experiments to silently run on a `2025` candidate panel
   - fixed so requested signal-date coverage must match the cached artifact dates exactly

## Experiment outcomes

### H238: Candidate-panel contract

Result:
- PASS

Artifacts built cleanly:
- `34,980` candidate rows on the first `2019-2025` run
- later refreshed to `2019-2026` coverage
- cycle-aligned labels published successfully

### H239: Variable-breadth threshold baseline

Result:
- PASS offline

Best full-window sparse-breadth scenario:
- `top_m=10`
- `min_selection_score=0.70`
- `min_score_gap=0.02`
- relative return `+481.90%`
- IR `0.91`

Fixed-width baseline:
- relative return `+279.52%`
- IR `0.74`

Interpretation:
- sparse breadth is real enough to justify further testing
- but this was still an ex-post full-window winner, not yet an honest promoted branch result

### H240: Stock-level single-family entry screens

Result:
- FAIL to promote

Best screen:
- `screen__price_reversal_quality`
- validation relative `+51.73%` vs sparse baseline `+34.70%`
- confirmation relative `-24.77%`

Interpretation:
- simple local price-state entry evidence exists
- but not strongly enough in confirmation to become a frozen rule

### H241: Compact entry model

Result:
- FAIL to promote

Best compact model variant:
- `blend__threshold_0p6`
- validation AUC `0.533`
- confirmation AUC `0.556`
- validation relative `+106.07%`
- confirmation relative `-48.54%`

Interpretation:
- candidate-level model scoring can separate validation history somewhat
- current label / feature contract is still too weak or too unstable for promotion

### H242: Soft exposure prior

Result:
- FAIL

Best result:
- `entry_model_only`

Soft threshold and soft breadth variants:
- tied the base entry-model result

Soft weights:
- weaker on validation

Hard veto:
- materially worse on validation

Interpretation:
- current activation alpha did not add value as a soft prior on top of the current entry-model winner
- and the hard gate remains the wrong abstraction for this branch

### H243: Live-compatibility audit

Result:
- FAIL to promote

Refreshed result after fixing `2026` candidate-panel coverage:

Current sticky branch:
- validation relative `+29.65%`
- confirmation relative `+18.80%`
- forward (`2026+`) relative `-2.46%`

Best entry variant:
- validation relative `+106.07%`
- confirmation relative `-48.54%`
- forward relative `+7.74%`
- operationally behaves like a one-name book

Best entry variant + sticky:
- validation relative `-20.03%`
- confirmation relative `-27.75%`
- forward relative `+7.11%`

Interpretation:
- the branch produced interesting sparse-book evidence
- but did not produce a live-compatible replacement or overlay for the frozen sticky branch

### H244: Honest sparse-breadth protocol

Result:
- FAIL to promote honestly

Dev-selected winner:
- `topm5__score_0p65__gap_0p03`

Metrics:
- dev relative `+572.73%`, IR `1.46`
- validation relative `+28.04%`
- confirmation relative `-22.13%`
- forward relative `-2.75%`

Baseline fixed-top-`K`:
- validation relative `+38.69%`
- confirmation relative `-26.11%`
- forward relative `-9.33%`

Interpretation:
- the dev-selected sparse-breadth winner did not hold up cleanly enough on validation to become an honest promoted winner
- however, it was less bad than baseline in confirmation and forward
- this keeps the branch alive as sparse-book structure evidence, not as a promoted deployment rule

## Branch decision

Do **not** promote stock-specific entry alpha into the live branch.
Under the branch-result policy in `README.md` / `README_for_AGENTS.md`, this branch is classified as **offline evidence promotion**, not live promotion.

Current status of the architecture idea:
- H238-H244 now exist as executable offline evidence
- strongest result is still the general sparse-breadth finding from H239
- later model / soft-prior / live-compatibility steps did not justify promotion

Best next branch if this architecture is intentionally continued:
- `H245`
  - test whether the real contract is `top1/top2` sparse-book selection rather than `top5` with timing overlays

Active workspace policy does **not** change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `pytest -q tests/test_entry_alpha.py tests/test_entry_alpha_research.py tests/test_run_summary.py`
- `pytest -q tests/test_live_recommendation.py`
- `python -m py_compile` on the new entry-alpha modules and CLIs
- full H238-H244 experiment runs completed
- `git diff --check` passed
