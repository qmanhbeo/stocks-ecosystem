# Session 186 Log - Foreign-Insider Agreement Split (2026-04-28)

## Objective

Continue the evergreen loop with data already available on disk:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid GPU / Ollama / PhoBERT training jobs
- test the first distinct foreign-flow interaction after standalone
  foreign-flow screens failed: foreign buy/sell agreement as a conditioner on
  bullish `C5`

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Branch selection

Recent evidence closed or parked the obvious local paths:
- H344 parked BERT-only sentiment as standalone
- H345 rejected standalone foreign accumulation / ownership-change paths
- H346 closed the stale long-horizon OHLCV residual queue

The remaining honest foreign-flow reopening condition in `live_state.md` was a
distinct interaction contract rather than more standalone window tuning. H347
therefore tested whether foreign-flow support can improve `C5`, with the
current H340 order-pressure rewrite as the hard benchmark.

## Experiment

### H347 - Foreign-Insider Agreement Split

**Hypothesis:**
Standalone CafeF foreign-flow features failed, but foreign buy/sell pressure
may still work as a non-price agreement state for bullish `C5` insider
conviction. A true pass must improve the current H340 buy-volume-pressure
rewrite, not merely raw `C5`.

**Command / code:**
`python analysis/h347_foreign_insider_agreement_split.py`

**Inputs:**
- `data/features/xs_insider_quality_features.parquet`
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`
- daily stock volume panels under `data/stock/`

**Saved artifact:**
`artifacts/run_summaries/20260428_084603_h347_foreign_insider_agreement_split_research_branch_foreign_insider_agreement_split.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | foreign support improves raw C5 but does not beat H340 |
| panel rows | `826,400` | 2015-2025, excludes 2026 |
| panel tickers / dates | `394 / 2,748` | S1-compatible daily panel |
| foreign 5d non-null coverage | `98.87%` | broad enough for the interaction audit |
| raw C5 avg IC | `+0.0374` | `10 / 11` positive years |
| H340 benchmark avg IC | `+0.0693` | `11 / 11` positive years |
| best foreign row | `c5_gate_pos_order_and_ff_net_5d_gt_0` | require both H340 buy pressure and foreign net 5d support |
| best foreign avg IC | `+0.0572` | improves raw C5 by `+0.0199` |
| best foreign validation / confirmation IC | `+0.0942 / +0.0376` | positive both phases |
| best foreign delta vs H340 avg IC | `-0.0121` | below the current benchmark |
| best foreign validation / confirmation delta vs H340 | `-0.0038 / -0.0200` | no pass over H340 |
| best foreign S1 corr | `-0.0258` | orthogonal but not stronger |

**Result:**
Foreign-flow agreement is real enough to improve raw `C5` and make every tested
foreign-conditioned row positive in `11 / 11` years. It does not improve the
stronger H340 buy-volume-pressure rewrite. The best row is the joint
order-pressure plus foreign-support gate, but it still trails H340 in average,
validation, and confirmation IC.

**Verdict: MIXED**

## Branch decision

Keep H347 as offline interaction evidence only:
- do not promote a foreign-conditioned `C5` rewrite
- do not replace H340 as the preferred daily-state form of bullish `C5`
- do not continue with more foreign-insider threshold or lag tuning under the
  same contract

The foreign-flow branch remains weak as a standalone family. If it continues,
the next honest reopening should be a materially different interaction, such
as proprietary-flow conflict/agreement or sector-specific ownership pressure,
not another foreign-net window around `C5`.

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-00271-00300.md`
- `notes/signal_library.md`

Added:
- `analysis/h347_foreign_insider_agreement_split.py`

Durable finding:
- `F287`

No durable dead-end file exists in the current repo note convention, so the
mixed interaction result is recorded in the active findings chunk and signal
library.

## Verification

Completed:
- `python -m py_compile analysis/h347_foreign_insider_agreement_split.py`
- `python analysis/h347_foreign_insider_agreement_split.py`

## Next step

Continue the evergreen loop with a distinct existing-data interaction branch.
The best next CPU-light candidate is a proprietary-flow conflict/agreement
pilot, because it tests a different non-price actor surface rather than
retuning foreign-flow support around `C5`.
