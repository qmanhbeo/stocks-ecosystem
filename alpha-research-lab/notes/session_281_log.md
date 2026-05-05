# Session 281 Log

**Date**: 2026-05-05
**Focus**: H400 `calendar_as_weak_prior_not_clock`

## Summary

- Activated the seventh S272/S273 eureka queue item.
- Added `analysis/h400_calendar_as_weak_prior_not_clock.py`.
- Rebuilt the H395 weak-signal quorum with calendar components explicitly
  removed, then added one fixed calendar weak-prior vote.
- Verdict: **FAILED**. The fixed calendar prior degraded the non-calendar
  quorum in every test year.

## H400 - Calendar As Weak Prior Not Clock

**Hypothesis:**
Exact calendar clocks are too sparse for promotion, but a predeclared
calendar-residue vote may add weak incremental context inside the H395 quorum.

**Command / code:**
```bash
python alpha-research-lab/analysis/h400_calendar_as_weak_prior_not_clock.py
```

**Inputs:**
- H395 component panel logic from `analysis/h395_weak_signal_quorum_sleeve.py`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/xs_order_pressure_daily.parquet`
- `data/features/news/datasets/news_daily_features.parquet`

**Protocol:**
- No `2026+` rows.
- Train-before-test folds, test years `2019-2025`.
- Base quorum uses the H395 selection rules but removes the old
  `january_first_10` and `monday` votes.
- Calendar add-on is one fixed weak-prior vote averaging:
  `january_first_10`, `monday`, last five trading days of month, and a
  Wednesday/Friday T+2 weekday residue.
- Primary comparison is `calendar_quorum_score` versus the same
  `non_calendar_quorum_score`; a random extra weak-vote control is also
  recorded.

**Saved artifact:**
`artifacts/run_summaries/20260505_174904_h400_calendar_as_weak_prior_not_clock_research_branch_calendar_as_weak_prior_not_clock.json`

| Metric | Value | Note |
|--------|-------|------|
| Non-calendar quorum avg IC | `+0.05826` | same as H395 without calendar votes |
| Calendar quorum avg IC | `+0.05605` | lower than base |
| Calendar lift vs base | `-0.00221` | `0 / 7` positive lift years |
| Calendar-only avg IC | `-0.00827` | `2 / 7` positive years |
| Random extra mean lift | `-0.00170` | calendar was still worse |
| `vote_t2_weekday_residue_vote` | `+0.00646` | weak diagnostic, below weak gate |
| `vote_month_end5_vote` | `-0.00181` | no stable edge |
| `vote_january_first_10_vote` | `-0.00790` | harmed the pooled fixed prior |
| `vote_monday_vote` | `-0.01282` | harmed the pooled fixed prior |

**Result:**
The fixed calendar weak prior failed the branch contract. The non-calendar
quorum retained H395's strength, but adding the calendar vote reduced average
IC by `-0.00221` and had no positive lift years. The calendar-only score was
negative. The single T+2 weekday residue was mildly positive over the full
panel, but below the weak-candidate IC gate and not enough to rescue the
predeclared pooled prior.

**Verdict: FAILED**

**Next action:**
Continue to `anti_signal_annihilation_veto`. Do not add calendar votes to the
H395 quorum under the current fixed residue contract.

## Closeout

- Saved artifact was read before the verdict.
- Branch status changed to failed / parked.
- No live branch changed.
- Memory write-back done in live state, compact notes, findings, dead ends,
  and signal library.
- `2026+` data was avoided.
- No heavy job remains active.
