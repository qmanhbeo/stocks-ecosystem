# Session 274 Log

**Date**: 2026-05-05
**Focus**: Reusable research-branch experiment scaffold

## Summary

- Added `src/experiment_contract.py` as the shared base contract for new
  lightweight research experiments.
- Added runnable copy template `analysis/_template_research_branch.py`.
- Updated `README_for_AGENTS.md` and `README.md` so future agents start from
  the template instead of hand-rolling target loading, year guards, state
  validation, IC summaries, and run-summary artifacts.

## Contract

The scaffold provides:
- role-safe S1 loading through `load_s1_decision_panel`, which renames raw
  `actual` to `s1_barrier_hit_1d`
- default blocking of `2026+` research rows
- `ExperimentSpec`, `ExperimentContext`, and `StateSpec`
- target/state overlap validation
- safe pooled/yearly/phase Spearman IC helpers
- reusable run-summary and parquet artifact writes
- a copyable template with only branch-specific TODO sections

## Verification

```bash
python -m py_compile alpha-research-lab/src/experiment_contract.py alpha-research-lab/analysis/_template_research_branch.py
python alpha-research-lab/analysis/_template_research_branch.py --start-year 2024 --end-year 2025 --min-year-rows 100 --min-phase-rows 100
git diff --check
```
