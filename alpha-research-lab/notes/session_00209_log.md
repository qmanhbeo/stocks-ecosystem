# Session 209 Log - H363 Vietnam Holiday Timing Payoff (2026-04-29)

## Objective

Implement and run the legal-major Vietnam public-holiday timing branch as a
sparse before/after market-state audit, not as dense calendar model features.

Predeclared holiday set:
- New Year Jan 1
- Tet
- Hung Kings Commemoration Day
- Reunification Day Apr 30 / Labor Day May 1
- National Day Sep 2 plus adjacent official day

Protocol:
- `2015-2022` dev
- `2023-2024` validation
- `2025` confirmation
- `2026+` excluded

## Implementation

Added:
- `src/vietnam_holiday_calendar.py`
- `analysis/h363_vietnam_holiday_timing_payoff.py`
- `tests/test_vietnam_holiday_calendar.py`

Calendar construction:
- hard-coded 2015-2025 Tet first-day and Hung Kings Gregorian anchors
- fixed-date anchors for New Year, Apr30/May1, and Sep2
- inferred actual exchange closure clusters from
  `data/stock/gia_lich_su_VNINDEX_1D.parquet`
- generated only trading-day states:
  `pre_1`, `pre_2`, `pre_3`, `pre_5`,
  `post_1`, `post_2`, `post_3`, `post_5`
- reported family states, grouped states (`tet`, `civil_holidays`,
  `all_holidays`), and diagnostic closure-length states

Audit outcomes:
- 1d relative return
- 5d relative return
- S1 actual
- full-library top-book 5d relative return
- tradability/liquidity flags

Controls:
- non-holiday rows only
- matched by research phase, S1 bucket, and full-library bucket, with fallback
  levels inside the same phase

## Command / Artifacts

Command:

`python analysis/h363_vietnam_holiday_timing_payoff.py`

Saved summary:

`artifacts/run_summaries/20260429_204602_h363_vietnam_holiday_timing_payoff_research_branch_vietnam_holiday_timing_payoff.json`

Core artifacts:
- `artifacts/timing_data/20260429_204602_h363_vietnam_holiday_timing_calendar.parquet`
- `artifacts/timing_data/20260429_204602_h363_vietnam_holiday_timing_clusters.parquet`
- `artifacts/timing_data/20260429_204602_h363_vietnam_holiday_timing_audit_states.parquet`
- `artifacts/portfolio_baselines/20260429_204602_h363_vietnam_holiday_timing_state_results.parquet`
- `artifacts/portfolio_baselines/20260429_204602_h363_vietnam_holiday_timing_payoff_results.parquet`
- `artifacts/portfolio_baselines/20260429_204602_h363_vietnam_holiday_sparse_clock_portfolio_results.parquet`

## Data Checks

| Check | Value |
|-------|-------|
| holiday state rows / dates | `436 / 408` |
| closure clusters | `53` |
| min / max state date | `2015-01-05 / 2025-09-09` |
| every state date in VNINDEX calendar | `true` |
| rows outside requested years | `0` |
| rows in 2026+ | `0` |

## Results

The matched payoff audit found one passing state:

| State | Validation top-book lift | Confirmation top-book lift | Validation dates | Confirmation dates | Year support |
|-------|--------------------------|-----------------------------|------------------|--------------------|--------------|
| `all_holidays__post_5` | `+0.00405` | `+0.01579` | `9` | `5` | `3` positive years, max share `0.6534` |

Risk diagnostics for that state:
- validation q10 / bad-tail lift: `+0.01672 / -0.09008`
- confirmation q10 / bad-tail lift: `+0.03633 / -0.13245`
- validation S1 actual lift: `+0.05724`
- confirmation S1 actual lift: `+0.00423`

The conditional fixed portfolio audit then ran exactly one rule:
- state: `all_holidays__post_5`
- direction: `bonus`
- bonus: `+0.015`
- only when full-library score was already in the daily top quintile
- only when `can_buy_next_open` was true

Portfolio result:

| Metric | Value |
|--------|-------|
| eligible bonus rows | `3,109` |
| portfolio gate | `false` |
| execution-health gate | `true` |
| downside-tail gate | `true` |
| validation relative delta | `0.00%` |
| confirmation relative delta | `0.00%` |

## Decision

The payoff hint is real enough to keep as offline timing evidence, but it does
not transfer to the executable full-library sparse-clock portfolio. The branch
is not promotable under the current selector contract.

Verdict: `MIXED` as research evidence, `FAILED` as a portfolio promotion.

## Next Actions

- Do not tune more legal-holiday pre/post offsets, bonus sizes, or veto variants
  under the current top-5 executable selector.
- Keep `all_holidays__post_5` as offline payoff evidence only.
- Keep `holiday_news_silence_break` parked until the local-news aggregate
  finishes; that is a different data-conditioned thesis, not another generic
  holiday-clock overlay.
- Keep `2026+` monitor-only unless the user explicitly authorizes predictive
  research on forward data.

## Verification

Completed:
- `python -m py_compile src/vietnam_holiday_calendar.py analysis/h363_vietnam_holiday_timing_payoff.py`
- `python -m pytest tests/test_vietnam_holiday_calendar.py -q`
- `python analysis/h363_vietnam_holiday_timing_payoff.py`
- saved-artifact inspection for data checks, state decisions, and portfolio
  gate outputs
