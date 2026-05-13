# Session 277 Log

**Date**: 2026-05-05
**Focus**: H396 `parent_echo_residual_harvester`

## Summary

- Activated the third S272/S273 eureka queue item.
- Added `analysis/h396_parent_echo_residual_harvester.py`.
- Tested whether H395 and its C-library ingredients survive same-date
  residualization against S1/C16, and whether H395 is new beyond its C-vote
  ingredients.
- Verdict: **PASSED as a residual clarification**.

## H396 - Parent Echo Residual Harvester

**Hypothesis:**
Many high-IC filters are parent echoes. A candidate should be treated as
independent evidence only if its residual after same-date parent-rank
residualization keeps stable IC above `+0.01`.

**Command / code:**
```bash
python alpha-research-lab/analysis/h396_parent_echo_residual_harvester.py
```

**Inputs:**
- H395 canonical test-score artifact:
  `artifacts/h395_weak_signal_quorum_sleeve/20260505_171827_h395_weak_signal_quorum_sleeve_test_scores.parquet`
- `data/features/xs_rl_signal_matrix.parquet`

**Protocol:**
- No `2026+` rows.
- Test years `2019-2025`.
- Candidate inventory: H395 `weak_quorum_score` plus C4-C14 vote columns.
- `resid_s1_c16`: same-date cross-sectional residual of each candidate after
  regressing on S1 and C16.
- `resid_c_votes`: same-date residual of H395 after regressing on all C4-C14
  vote columns, used to test whether H395 is a new primitive beyond its
  ingredients.
- Residual survival gate: avg IC `> +0.01` and at least `60%` positive years.

**Saved artifact:**
`artifacts/run_summaries/20260505_172353_h396_parent_echo_residual_harvester_research_branch_parent_echo_residual_harvester.json`

| Candidate / variant | Avg IC | Positive years | Verdict |
|---------------------|--------|----------------|---------|
| H395 raw quorum | `+0.05826` | `7 / 7` | strong composite |
| H395 residual vs S1+C16 | `+0.01669` | `7 / 7` | survives market parents |
| H395 residual vs C votes | `+0.00187` | `5 / 7` | does not survive ingredients |
| C13 residual vs S1+C16 | `+0.01839` | `6 / 7` | survives |
| C10 residual vs S1+C16 | `+0.01278` | `5 / 7` | survives |
| C6 residual vs S1+C16 | `+0.01115` | `7 / 7` | survives |

**Result:**
H395 is not merely an S1/C16 parent echo: its S1/C16-residual score kept avg
IC `+0.01669` with `7 / 7` positive years. But it is not a new primitive beyond
the known C-library ingredients: after residualizing H395 against C4-C14 votes,
avg IC fell to `+0.00187`, below the gate.

The useful primitive residual harvest from this pass is narrower:
`C13`, `C10`, and `C6` retain residual IC above `+0.01` after S1/C16
residualization.

**Verdict: PASSED**

**Next action:**
Continue to `barrier_pop_vs_hold_router`. Use H396's distinction in future
promotion language: H395 is a strong composite RL state, while C13/C10/C6 are
the cleaner residual primitives in this audit.

## Closeout

- Saved artifact was read before the verdict.
- Branch status changed to passed residual clarification.
- No live branch changed.
- Memory write-back done in live state, compact notes, findings, and signal
  library.
- `2026+` data was avoided.
- No heavy job remains active.
