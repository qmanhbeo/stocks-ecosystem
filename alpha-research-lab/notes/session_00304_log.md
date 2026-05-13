# Session 304 Log

**Date**: 2026-05-06
**Focus**: H426 forced-seller detector queue pass

## Summary

Activated hidden-flow queue item 15, `forced_seller_detector`, as H426. The
pass used a reusable script and the entry-alpha cycle-label contract, with
walk-forward K selection and random-policy baselines only.

The queue memo suggested "next-day C16 turns positive and tradability
releases." Under the current T close -> T+1 open entry-label contract,
next-day C16 is not decision-time observable, so this first honest pass did
not use it. A delayed-entry protocol is required before testing that clause.

### H426 - Forced Seller Detector

**Hypothesis:**
Margin-cascade / forced-seller states should be visible from observable
negative return, volume spike, sell-order pressure, rising or high average sell
size, floor-limit proximity, and absence of active bad news. If the state is
real, fixed buyable forced-seller candidates should beat random same-support
and random-all candidate policies in walk-forward evaluation.

**Command / code:**
- `python analysis/h426_forced_seller_detector.py`
- Script: `analysis/h426_forced_seller_detector.py`

**Inputs:**
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/news/datasets/news_daily_features.parquet`
- Window: `2019-2025`; `2026+` blocked by the script

**Saved artifact:**
- `artifacts/run_summaries/20260506_141722_h426_forced_seller_detector_research_branch_forced_seller_detector.json`
- `artifacts/entry_alpha/20260506_141722_h426_forced_seller_detector_years.parquet`
- `artifacts/entry_alpha/20260506_141722_h426_forced_seller_detector_daily.parquet`

| Metric | Value | Note |
|--------|-------|------|
| Verdict | `FAILED` | No state cleared both random-policy gates |
| WF years | `2021-2025` | Prior-year K choice, `min_train_years=2` |
| Random trials | `5000` | Same-support and random-all policies |
| `forced_seller_core_buyable` rows | `1,588` | `1,049` active dates |
| Core mean lift vs random-state | `+0.000230` | Only `1 / 5` WF years positive |
| Core mean lift vs random-all | `-0.002047` | 2025 lift `-0.000759` |
| `forced_seller_large_down_buyable` rows | `1,228` | `883` active dates |
| Large-down lift vs random-state | `-0.000481` | `1 / 5` WF years positive |
| Large-down lift vs random-all | `-0.003646` | `0 / 5` WF years positive |
| `forced_seller_floor_buyable` rows | `443` | `355` active dates |
| Floor lift vs random-state | `+0.000023` | Too small and inconsistent |
| Floor lift vs random-all | `-0.003408` | 2025 lift `-0.004654` |
| `forced_seller_hard_release` rows | `7` | Literal release support too sparse |

**Result:**
The broad core and floor variants were not superior allocators. The broad core
had tiny positive average same-support lift but failed consistency and random-all
confirmation. Large-down and literal-release forms were weaker; the literal
release state had effectively no support after 2021.

**Verdict: FAILED**

## Interpretation

The current order-stat / entry-candidate representation does not support a
forced-seller buy pulse. Forced-seller-like sell pressure may still describe
distress or liquidity, but it does not select better candidates than random
same-support or random-all rows under this cycle-label consumer.

Do not reopen by tuning thresholds around the same daily state. Reopen only
with a materially different delayed-entry protocol that can honestly observe a
post-sell-pressure C16 turn before execution, or with intraday / queue data
that captures actual absorption and release timing.

## Verification

Commands run:
- `python -m py_compile alpha-research-lab/analysis/h426_forced_seller_detector.py`
- `python analysis/h426_forced_seller_detector.py`
- saved-summary readback from
  `artifacts/run_summaries/20260506_141722_h426_forced_seller_detector_research_branch_forced_seller_detector.json`
- parquet shape/schema readback for the yearly and daily artifacts
- temp-file check under `artifacts/entry_alpha` and `artifacts/run_summaries`

Results:
- py_compile passed
- script completed with saved summary verdict `FAILED`
- yearly artifact shape `(20, 22)`
- daily artifact shape `(4960, 12)`
- no `.tmp` artifact files remained in the checked output directories

## Next Action

Advance the hidden-flow queue to item 16,
`candidate_decision_boundary_curvature`, unless a higher-priority operator
request supersedes it.
