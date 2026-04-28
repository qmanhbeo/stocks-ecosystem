# Session 190 Log - Sector Ownership-Pressure Audit (2026-04-28)

## Objective

Continue the evergreen loop after the official-disclosure source gate skipped:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid GPU / Ollama / PhoBERT training jobs
- test the last current-data H95 reopening condition: sector-level ownership
  pressure rather than ticker-level foreign-flow ranks

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Branch selection

H327/H328/H333/H345 failed the standalone foreign-flow path, H347 failed to
beat H340 as a C5 interaction, and H348 failed proprietary-flow
agreement/conflict. The only remaining current-data flow thesis in the queue
was sector-specific ownership pressure.

The H351 pass deliberately avoided raw ticker-level foreign-flow rank tuning.
It built a small predeclared sector-level feature set from:
- sector foreign net pressure
- sector foreign participation
- sector foreign ownership level and change
- pressure interacted with sector heat and ownership level

The pass also compared features against existing sector anchors so a pass
could not just rediscover C6 / sector breadth.

## Experiment

### H351 - Sector Ownership Pressure

**Hypothesis:**
Foreign ownership pressure may matter at the sector level even though
ticker-level foreign-flow ranks failed. Sector foreign pressure combined with
room scarcity or sector heat should produce a cross-sectional signal that
survives the H95 gate and is not just C6 / breadth.

**Command / code:**
`python analysis/h351_sector_ownership_pressure.py`

**Inputs:**
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- daily stock panels under `data/stock/`
- `data/features/sector_classification.parquet`
- `data/features/xs_sector_rotation_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_rl_signal_matrix.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_144103_h351_sector_ownership_pressure_research_branch_sector_ownership_pressure.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | no sector ownership-pressure feature clears the gate |
| merged rows | `814,353` | 2015-2025 predictive panel |
| merged tickers / dates | `390 / 2,741` | excludes 2026 |
| features tested | `7` | predeclared sector-level pressure / ownership states |
| passing features | `0` | no candidate gate |
| redundant candidates | `0` | failure is not sector-anchor redundancy |
| best feature | `xs_sector_ff_participation_20d_rank` | least-bad validation line |
| best dev IC | `-0.0007` | far below standalone gate |
| best validation IC | `-0.0051` | directionally aligned with negative dev sign |
| best confirmation IC | `+0.0015` | fails the negative dev direction |
| best S1 corr | `-0.0048` | orthogonal but not predictive |
| best sector-anchor corr | `0.0022` | not a C6 / breadth duplicate |

**Result:**
Sector-level ownership pressure fails. The tested features are not redundant
with S1 or the sector anchors, but they also have essentially no dev signal.
The best feature has dev IC near zero and fails confirmation direction.

**Verdict: FAILED**

## Branch decision

The current-data H95 / flow branch is now closed under the present target:
- do not tune standalone foreign-flow windows
- do not tune foreign support around C5
- do not tune proprietary-flow agreement/conflict ranks
- do not tune sector ownership-pressure variants

Reopen only with a materially different data source, target, or market
contract.

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h351_sector_ownership_pressure.py`

Durable finding:
- `F291`

No promoted signal was added.

## Verification

Completed:
- `python -m py_compile analysis/h351_sector_ownership_pressure.py`
- `python analysis/h351_sector_ownership_pressure.py`
- read the saved run summary and details artifacts

The broader test suite was not run.

## Next step

Continue the evergreen loop with a non-flow branch. The remaining current-data
queue item is `event-v2-optionality-payoff`, unless the loop shifts back to
news/Ollama or data acquisition.
