# Session 193 Log - Dividend Clock Payoff Audit (2026-04-28)

## Objective

Continue the evergreen loop after H353 showed H340 does not cleanly transfer
to the entry-alpha prior:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid heavyweight local-model jobs
- test whether the old dividend-calendar branch has a direct sparse
  pre/post ex-dividend payoff effect rather than a broad model-feature effect

This session stayed CPU-only.
It did not use `2026` for predictive tuning.

## Branch Selection

Earlier H31 evidence said adding dividend-calendar fields as XS model inputs
adds noise. H298 later used corporate-action windows only as conditioners for
fundamentals / earnings quality, not as direct dividend-clock payoff states.

The smallest remaining honest question was whether a dividend clock by itself
has sparse pre/post ex-date payoff behavior after matching against same-universe
non-dividend-window controls.

## Experiment

### H354 - Dividend Clock Payoff

**Hypothesis:**
Dividend calendar states may matter as sparse payoff or risk-filter clocks even
though broad dividend-calendar model features failed. Active pre/post
ex-dividend rows should show positive validation and confirmation 5d matched
return lifts without worse downside tail or tradability.

**Command / code:**
`python analysis/h354_dividend_clock_payoff.py`

**Inputs:**
- `data/features/xs_dividend_calendar.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`
- `data/features/execution/tradability_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_160134_h354_dividend_clock_payoff_research_branch_dividend_clock_payoff.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | local pre-ex payoff hint, no clean gate pass |
| panel rows / tickers / dates | `131,330 / 51 / 2,748` | same dividend-calendar universe, 2015-2025 |
| dividend-window rows / dates | `8,573 / 2,540` | pre/post union |
| best state | `pre_ex_20d` | 20 trading days before ex date |
| validation active rows / dates | `1,039 / 414` | enough coverage |
| validation mean / q10 / q90 lift | `+0.0007 / -0.0005 / +0.0068` | small positive mean, tail okay |
| validation bad-tail / hit-rate lift | `-0.0297 / +0.0419` | risk and hit rate favorable |
| confirmation active rows / dates | `555 / 224` | enough coverage |
| confirmation mean / q10 / q90 lift | `+0.0002 / -0.0030 / +0.0093` | positive mean, but q10 misses gate |
| confirmation bad-tail / hit-rate lift | `-0.0324 / +0.0240` | bad-tail rate favorable, hit rate positive |

**Result:**
The 20-day pre-ex window has a real-looking but small local payoff hint: both
validation and confirmation mean lifts are positive, hit-rate lifts are
positive, and bad-tail rates improve. It still misses the predeclared clean
gate because the confirmation q10 lift is slightly worse than allowed
(`-0.0030` versus the `-0.0025` floor) and the mean lifts are too small for a
promoted sparse clock.

Post-ex windows failed directly. The clustered dividend-count state also failed.

**Verdict: MIXED**

## Branch Decision

Keep dividend-clock behavior as offline calendar evidence only:
- do not reopen H31-style dividend-calendar model features
- do not promote a dividend-clock signal
- do not tune more pre/post dividend windows under the current contract
- reopen only if a stricter portfolio-level sparse-clock or risk-filter
  contract explicitly needs a calendar side channel

## Memory Changes

Updated:
- `notes/next_steps.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h354_dividend_clock_payoff.py`

Durable finding:
- `F294`

No promoted signal was added.

## Verification

Completed:
- `python -m py_compile analysis/h354_dividend_clock_payoff.py`
- `python analysis/h354_dividend_clock_payoff.py`
- read the saved run summary and state-result artifacts

The first run reached parquet artifact writing and then failed on a JSON
serialization call. The canonical rerun is timestamp `20260428_160134`; the
earlier `20260428_160116` parquet artifacts are partial non-summary leftovers.

The broader test suite was not run.

## Next Step

Continue the evergreen loop. The remaining cheap current-data branch surface is
thin; the default high-value blocker remains the local-news combined audit,
which needs the Ollama residual backfill to finish unless a new non-news
hypothesis has a distinct mechanism.
