# Session 303 Log

**Date**: 2026-05-06
**Focus**: Safe-first artifact hardening follow-up

## Summary

Continued the targeted hardening pass without changing published RL matrix,
activation, or research-result schemas.

Implemented:
- C11-C14 durable RL component caches alongside the existing C10 cache under
  `data/features/_rl_signal_matrix_parts/`
- manifest schema v2 for C10-C14 with requested date window, actual date
  window, build timestamp, source fingerprint, input fingerprint, row count,
  column count, producer, and upstream input metadata
- `--component-cache-only`, `--start-date`, `--end-date`, and
  `--verify-component-parity` options in `data_tools/build_rl_signal_matrix.py`
- exact old-inline vs cached parity checks for C10-C14
- batched activation-meta derived-column creation to remove pandas
  fragmentation warnings
- lightweight `src/check_artifact_integrity.py` CLI for key published artifacts
  and RL component caches
- H413 migration onto `src/additive_signal_research.py`, preserving legacy
  summary field names and static legacy pointer

## Verification

Commands run:
- `python data_tools/build_rl_signal_matrix.py --component-cache-only --end-date 2025-12-31 --verify-component-parity`
- `python data_tools/build_rl_signal_matrix.py --component-cache-only --end-date 2025-12-31`
- `python analysis/h413_triple_signal_additive.py --start-year 2025 --end-year 2025`
- old-inline H413 recomputation parity check against
  `artifacts/run_summaries/triple_signal_additive_research_branch.json`
- `python src/check_artifact_integrity.py --artifact rl_matrix`
- `python src/check_artifact_integrity.py --all --summary`
- activation state/meta smoke into `/tmp`, then immediate manifest reuse

Results:
- C10-C14 parity passed with identical row counts, identical key coverage, and
  max absolute numeric difference `0`
- bounded C10-C14 cache manifests all have `end_date=2025-12-31`
- immediate component-cache reuse passed
- H413 2025 migrated output matched old-inline recomputation within `1e-14`
- activation smoke built `(249, 75)` state and `(249, 151)` meta, then reloaded
  both as `artifact`; no pandas fragmentation warnings appeared
- artifact integrity CLI passed for RL matrix, activation surfaces, and C10-C14
  caches

## Artifacts

Created or refreshed:
- `data/features/_rl_signal_matrix_parts/c10_illiq.parquet`
- `data/features/_rl_signal_matrix_parts/c10_illiq_manifest.json`
- `data/features/_rl_signal_matrix_parts/c11_3m_continuation.parquet`
- `data/features/_rl_signal_matrix_parts/c11_3m_continuation_manifest.json`
- `data/features/_rl_signal_matrix_parts/c12_gap_absorption.parquet`
- `data/features/_rl_signal_matrix_parts/c12_gap_absorption_manifest.json`
- `data/features/_rl_signal_matrix_parts/c13_compress_blowoff.parquet`
- `data/features/_rl_signal_matrix_parts/c13_compress_blowoff_manifest.json`
- `data/features/_rl_signal_matrix_parts/c14_clv_resid.parquet`
- `data/features/_rl_signal_matrix_parts/c14_clv_resid_manifest.json`
- `alpha-research-lab/artifacts/cache/triple_signal_additive_2025_2025.parquet`
- `alpha-research-lab/artifacts/cache/triple_signal_additive_2025_2025_manifest.json`
- `alpha-research-lab/artifacts/run_summaries/20260506_125509_triple_signal_additive_research_branch.json`
- `alpha-research-lab/artifacts/run_summaries/triple_signal_additive_research_branch.json`

## Remaining Risk

- Date-window fingerprints are conservative: if a source parquet receives new
  post-window rows, bounded caches rebuild even when pre-window values are
  unchanged. This favors safety over avoiding every rebuild.
- Full `data_tools/build_rl_signal_matrix.py` publishing was not run; only
  component-cache and parity paths were exercised.
