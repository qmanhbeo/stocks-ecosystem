# Session 25: Strict Gate Fail-Fast Enforcement

**Date:** 2026-05-22  
**Status:** NEGATIVE FINDING + INFRA FIX

## Purpose
Execute the strict promotion workflow and stop progression when no strategy clears readiness gates.

## Experiments Run
1. Canonical sweep run:
   - `python signal_sweep.py`
   - Artifact: `artifacts/signal_sweeps/20260522_130306/`
2. Challenge selection from that sweep:
   - `python select_challenge_set.py --sweep-dir artifacts/signal_sweeps/20260522_130306`
   - Existing artifact (pre-fix behavior): `artifacts/challenge_sets/20260522_130713/`
   - Selected challenger via fallback despite all `KILL`.

## Strict-Gate Outcome (Sweep 20260522_130306)
- Strategies evaluated: `28`
- Decision labels: `KILL=28`, `PROMOTE_CANDIDATE=0`
- Strict-ready candidates (`EXECUTION_VALIDATED` and `is_profit_ready=true`): `0`
- Baseline `ctrl_blend_70_30_depth5`:
  - `mean_excess_return=-6.67%`
  - `worst_fold_return=-38.58%`
- Fallback challenger `s1b_c11_ret_60d_lag_rank_70_30_depth5`:
  - `mean_excess_return=-4.72%`
  - `worst_fold_return=-43.86%`

## Fundamental Flaw Found
- `select_challenge_set.py` previously allowed fallback challenger selection even when no strict-eligible candidate existed (all rows `KILL`).
- This could allow shadow-phase progression on non-promotable strategies.

## Fix Implemented
- `select_challenge_set.py` now defaults to strict mode:
  - challenger must be `PROMOTE_CANDIDATE`
  - otherwise emits `challenger_strategy=null`, `ready_for_shadow=false`, and exits with error unless `--allow-empty-challenge` is set.
- Added explicit modes:
  - `--selection-mode strict|research|any`
- `run_shadow_phase.py` now fails fast when `challenge_set.json` has `ready_for_shadow=false`.

## Verification
- Unit tests:
  - `pytest -q heuristic-trader/test_select_challenge_set.py` -> `4 passed`
- Strict selection behavior after fix:
  - Command now fails as expected with no strict candidate.
  - Artifact: `artifacts/challenge_sets/20260522_131032/`
  - Metadata confirms:
    - `strict_candidate_count=0`
    - `ready_for_shadow=false`
- Shadow guard behavior:
  - `run_shadow_phase.py` correctly aborts on this challenge set.

## Conclusion
- Current strict branch is not promotion-ready.
- Pipeline now enforces fail-fast behavior and prevents silent fallback progression into shadow phase when strict gates fail.

## Notes Audit Gate
- `python alpha-research-lab/tools/validate_notes_consistency.py --notes-dir heuristic-trader/notes`
- Result: FAIL (validator is alpha-note-stack-specific; expects `findings-xxxxx-xxxxx.md` / `deadends-xxxxx-xxxxx.md` + index files not used in heuristic-trader note stack)
- Manual checks passed:
  - `session_00025.md` exists and is linked from `sessions_compact.md`
  - finding IDs unique in chunk (`F00001..F00015`)
  - dead-end IDs unique in chunk (`D00001..D00003`)
  - compact files include new anchors (`F00015`, `D00003`)
