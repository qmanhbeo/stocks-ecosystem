# Session 26: Lab-to-Trader Promotion Contract Bridge (MVP)

**Date:** 2026-05-22  
**Status:** IMPLEMENTED + VERIFIED

## Purpose
Implement the MVP bridge so lab promotion/readiness signals and heuristic-trader execution gates use a shared contract instead of drifting independently.

## What Was Implemented

1. Lab-side contract publish in readiness audit
- Updated `alpha-research-lab/analysis/audit_signal_execution_readiness.py`.
- Added proxy execution score + proxy gate and contract fields:
  - `proxy_execution_score`
  - `proxy_gate_pass`
  - `execution_readiness_verdict`
  - `lab_promotion_status`
- Added publish flags:
  - `--publish-contract`
  - `--contract-csv-path`
  - `--contract-json-path`
  - `--contract-as-of-date`
- Audit now writes:
  - `signal_promotion_contract.csv/json` in audit artifact dir
  - shared publish targets when enabled.

2. Heuristic strict upstream gating
- Updated `heuristic-trader/risk_policy.py` and `heuristic-trader/signal_sweep.py`.
- `signal_sweep.py` now consumes:
  - `data/features/recommendations/signal_promotion_contract_latest.csv`
- Added CLI flags:
  - `--promotion-contract-csv`
  - `--require-promotion-contract`
  - `--publish-feedback-csv`
- Non-control strategies are blocked from promotion if upstream status is below `LAB_PROMOTED_PENDING_EXECUTION`.
- Controls remain evaluable as comparators (not hard-blocked by missing signal-contract rows).

3. Feedback writeback loop
- `signal_sweep.py` now emits:
  - run-local: `signal_promotion_feedback.csv`
  - shared: `data/features/recommendations/signal_promotion_feedback_latest.csv`
- Feedback is keyed by `signal_id` and includes decision counts and failure-cohort execution metrics.

## Verification

1. Unit tests
- `pytest -q heuristic-trader/test_risk_policy.py heuristic-trader/test_signal_sweep.py heuristic-trader/test_select_challenge_set.py`
- Result: `15 passed`

2. Compile checks
- `python -m py_compile alpha-research-lab/analysis/audit_signal_execution_readiness.py heuristic-trader/risk_policy.py heuristic-trader/signal_sweep.py`
- Result: pass

3. Contract publish run
- Command:
  - `python analysis/audit_signal_execution_readiness.py --signals s1,c4,c5,c8,c16,c17,c18 --start-year 2015 --end-year 2025 --publish-contract`
- Artifact:
  - `alpha-research-lab/artifacts/audits/20260522_132432_signal_execution_readiness/`
- Shared outputs created:
  - `data/features/recommendations/signal_promotion_contract_latest.csv`
  - `data/features/recommendations/signal_promotion_contract_latest.json`

4. Strict sweep run with contract required
- Command:
  - `python signal_sweep.py --strategy-limit 2 --skip-autopsy --require-promotion-contract`
- Artifact:
  - `heuristic-trader/artifacts/signal_sweeps/20260522_132635/`
- Confirmed new decision columns and contract metadata in manifest.
- Confirmed feedback export:
  - run-local `signal_promotion_feedback.csv`
  - shared `data/features/recommendations/signal_promotion_feedback_latest.csv`

## Notes Audit Gate
- `python alpha-research-lab/tools/validate_notes_consistency.py --notes-dir heuristic-trader/notes`
- Result: expected FAIL for heuristic note-stack naming mismatch (validator is alpha-note-stack-specific).
- Manual checks passed:
  - session link added to compact index
  - no duplicate new IDs introduced in this session note
