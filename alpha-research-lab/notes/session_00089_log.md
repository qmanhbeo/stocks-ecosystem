# Session 89 Log

## Objective
Run `H234`, the richer company-event source audit, and answer a narrow acquisition question:
- does the current local workspace already contain a materially richer company-event source than event surface v1?
- can that source recover exact first-public timestamps and company-specific event families for a meaningful subset?

This session did not try to build event surface v2.
It did not try to prove predictive value.
It did not read `2026+`.

## Starting point

Coming in:
- `H231` had kept the intraday branch alive but only as a mixed partial-data result
- the acquisition plan still allowed a parallel richer-event-source branch
- the missing question was whether the local CafeF news archive was merely a text archive or a real event-source candidate

The audit standard from the plan was:
- exact public timestamps
- company-specific event families missing from event surface v1
- meaningful ticker subset

## What changed

Added:
- `analysis/h234_richer_event_source_audit.py`
- `src/news_event_source_research.py`
- `tests/test_news_event_source_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_timing_richer_event_source_audit.json`
- `artifacts/timing_data/20260331_131858_h234_richer_event_source_audit_articles.parquet`
- `artifacts/timing_data/20260331_131858_h234_richer_event_source_audit_daily_flags.parquet`
- `artifacts/timing_data/20260331_131858_h234_richer_event_source_audit_family_summary.parquet`

## H234 outcome

### Contract audited

`H234` stayed conservative:
- source audited:
  - local CafeF company-news archive
- extraction rule:
  - title-ticker seed only
  - exact `published_at` timestamps only
- analysis window:
  - `2023-01-01` through `2025-12-31`
- allowed universe:
  - current matrix tickers only
- no predictive screen
- no `2026+` read

### What happened

The source passes as a richer company-event candidate.

Archive scan:
- total articles scanned:
  - `312,488`
- title-ticker company articles:
  - `1,257`
- timestamp coverage on those title-ticker articles:
  - `100%`
- family-qualified company-event articles:
  - `1,072`
- candidate ticker coverage:
  - `190` tickers

Recovered company-specific families that event surface v1 does not have broadly:
- `earnings_company`
  - `176` tickers
  - `803` unique articles
- `board_management`
  - `120` tickers
  - `410` unique articles
- `shareholder_meeting`
  - `107` tickers
  - `278` unique articles
- `rights_issuance`
  - `97` tickers
  - `222` unique articles
- `buyback`
  - `6` tickers
  - `12` unique articles

Why this counts as a real `H234` pass:
- timestamps are exact article publish times, not quarter-phase proxies
- the recovered families are genuinely company-specific and materially richer than event surface v1
- the subset is well above the `50`-ticker floor and above the `100`-ticker preferred bar

The caution is also clear:
- this conservative seed is still sparse on held rows
- held-row recent coverage from the seed only:
  - any company-event article:
    - `1d` `0.22%`
    - `5d` `0.75%`
    - `20d` `1.15%`
- that does **not** fail `H234`
- it means `H235` must audit whether richer extraction can improve useful coverage or information content without leakage

## Branch decision

Do **not** change the live branch.

What `H234` resolves:
- a richer company-event source is already locally available
- the best current candidate is:
  - `cafef_company_news_archive_title_ticker_seed`
- the next honest step is `H235`, not more source hunting

Branch effect:
- `H234` is **PASSED**
- open `H235`
- do **not** jump directly to event surface v2
- do **not** infer predictive value from source availability alone

`H235` should now test:
- whether a sample event panel from this source is operationally better than v1
- whether first-public timestamps remain recoverable after any extraction expansion
- whether richer extraction improves information novelty or usable coverage without leakage

## Validation

Completed:
- `python -m py_compile analysis/h234_richer_event_source_audit.py src/news_event_source_research.py tests/test_news_event_source_research.py`
- `pytest -q tests/test_news_event_source_research.py tests/test_intraday_acquisition_research.py`
- full `conda run -n stocks python analysis/h234_richer_event_source_audit.py` run completed

Verdict:
- `H234`: **PASSED**
