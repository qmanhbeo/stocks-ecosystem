# Session 154 Log — Exit Oracle Upper-Bound Audit (2026-04-10)

## Objective

Take the first smart-exit ML queue item after the outcome-contract discussion:
- `H334` exit-oracle upper-bound

Question:
- before training an exit model, is there enough legal exit-timing capacity in
  predeclared horizons to justify ML at all?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h334_exit_oracle_upper_bound.py`

### H334 - Exit Oracle Upper-Bound
**Hypothesis:**
A sequential exit target is worth learning only if a constrained legal oracle
can materially beat fixed exits under costs, sellability, and drawdown penalty.

**Command / code:**
`python analysis/h334_exit_oracle_upper_bound.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/stock/`
- `data/stock/gia_lich_su_VNINDEX_1D.parquet`
- frozen `full_library` top-5 / rebalance-5 backbone

**Saved artifact:**
`artifacts/run_summaries/20260410_134038_h334_exit_oracle_upper_bound_research_branch_exit_oracle_upper_bound.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `PASSED` | upper-bound gate only |
| entries | `2,578` | executed buy entries, `2015-2025` |
| horizon rows | `10,295` | legal `3d / 5d / 10d / 15d` outcomes |
| tickers / entry dates | `359 / 548` | full-library backbone |
| round-trip cost | `0.30%` | same cost scale as prior cycle labels |
| drawdown penalty | `0.25 * open-path MAE` | path-aware utility penalty |
| max exit year | `2025` | sell-blocked exits cannot roll into 2026 |
| best fixed horizon | `3d` | best in dev, validation, and confirmation |
| validation entries | `477` | `2023-2024` |
| validation best fixed utility | `-0.0018` | per-entry mean, best fixed `3d` |
| validation oracle utility | `+0.0382` | constrained hindsight oracle |
| validation uplift vs best fixed | `+0.0400` | material upper-bound capacity |
| validation non-best-fixed oracle choice rate | `64.78%` | horizon choice is not degenerate |
| confirmation entries | `227` | `2025` |
| confirmation best fixed utility | `-0.0068` | per-entry mean, best fixed `3d` |
| confirmation oracle utility | `+0.0372` | constrained hindsight oracle |
| confirmation uplift vs best fixed | `+0.0440` | material upper-bound capacity |
| confirmation non-best-fixed oracle choice rate | `53.74%` | still diversified in confirmation |

**Result:**
The constrained oracle clears the first smart-exit ML gate. Fixed exits are
best at `3d` under the utility contract, but the oracle chooses longer legal
horizons often enough that the exit problem is not just "always shorten the
hold." This does not create a tradable rule because the oracle uses future
path outcomes to choose the best horizon. It only proves the upper-bound gap is
large enough to justify one distillation attempt.

**Verdict: PASSED**

---

## Branch decision

`H334` advances the smart-exit branch as offline evidence only:
- do **not** deploy the oracle
- do **not** treat this as a live branch change
- do **not** jump to neural/offline RL yet
- next honest step:
  - `exit-mdp-lite`
  - or `discrete-exit-hazard`

The next pass must train only on information available at entry or at the
current hold day, and it must recover a material share of the oracle uplift
strictly walk-forward.

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h334_exit_oracle_upper_bound.py`
- ran `python analysis/h334_exit_oracle_upper_bound.py`
- read the saved run summary artifact

The broader test suite was not run.
