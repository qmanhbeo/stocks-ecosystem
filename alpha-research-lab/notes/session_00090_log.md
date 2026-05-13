# Session 90 Log

## Objective
Run `H235`, the event-source sample audit and coverage gate, and answer the next acquisition question from the passed `H234` source:
- can a careful extraction expansion materially improve the conservative CafeF title-ticker seed?
- do exact first-public timestamps survive that expansion?
- is the richer source now operationally good enough to open `H236`?

This session did not try to build `event_surface_v2_daily.parquet`.
It did not try to prove predictive value.
It did not read `2026+`.

## Starting point

Coming in:
- `H234` had already passed source identification
- the local CafeF company-news archive was confirmed as a real richer company-event source candidate
- the unresolved question was operational, not existential:
  - can the source be expanded without leakage?
  - does that expansion improve useful coverage or information content enough to justify publication work?

The branch contract from the acquisition plan was:
- recover first-public timestamps
- avoid retrospective leakage
- beat the conservative seed on information content or coverage
- only open `H236` if the richer source is operationally better than event surface v1

## What changed

Added:
- `analysis/h235_event_source_sample_audit.py`

Updated:
- `src/news_event_source_research.py`
- `tests/test_news_event_source_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_timing_event_source_sample_audit.json`
- `artifacts/timing_data/20260331_133946_h235_event_source_sample_audit_expanded_articles.parquet`
- `artifacts/timing_data/20260331_133946_h235_event_source_sample_audit_expanded_daily_flags.parquet`
- `artifacts/timing_data/20260331_133946_h235_event_source_sample_audit_alias_map.parquet`
- `artifacts/timing_data/20260331_133946_h235_event_source_sample_audit_alias_holdout.parquet`
- `artifacts/timing_data/20260331_133946_h235_event_source_sample_audit_alias_assignments.parquet`

## H235 outcome

### Contract audited

`H235` stayed strict:
- source:
  - the passed local CafeF company-news archive from `H234`
- analysis window:
  - `2023-01-01` through `2025-12-31`
- train-only alias learning:
  - `2023-01-01` through `2024-12-31`
- holdout alias audit:
  - `2025-01-01` through `2025-12-31`
- expansion mode:
  - conservative title-ticker seed
  - plus one strict multi-word title-alias lexicon
- benchmark:
  - conservative seed from `H234`
  - current `event_surface_daily.parquet`
- no predictive screen
- no `2026+` read

Decision rule used here:
- `PASSED`:
  - alias precision strong enough for publication work
  - and held-row `5d` company-event coverage reaches the operational bar
- `MIXED`:
  - exact timestamps and novelty are real
  - but coverage is still too weak to open `H236`
- `FAILED`:
  - expansion is too noisy or too weak even as acquisition evidence

### What happened

The strict alias audit was much stronger than the conservative expectation on precision:
- learned alias lexicon:
  - `105` aliases
  - `57` tickers
- masked-title holdout on `2025` title-ticker articles:
  - `194` holdout rows
  - `85` assigned rows
  - assigned share `43.81%`
  - assigned precision `98.82%`

The expansion also materially increased article-level information:
- seed:
  - `1,072` unique qualified articles
  - `1,734` exploded article-family rows
  - `190` tickers
- strict alias expansion:
  - `2,861` added alias-linked unique articles
  - `3,958` added alias-linked article-family rows
  - still `190` total tickers overall

And most of the expanded daily rows are genuinely new relative to event surface v1:
- expanded candidate daily rows:
  - `3,429`
- novel versus v1 company-specific proxy rows:
  - `2,554`
  - `74.48%`

But the operational gate still does **not** clear.

Held-row recent-any company-event coverage improves versus the conservative seed, but it remains far below the `H235` promotion bar:
- seed `5d` recent-any coverage:
  - `0.75%`
- expanded `5d` recent-any coverage:
  - `2.30%`
- delta:
  - `+1.55` percentage points

The same pattern holds at longer windows:
- seed `20d` recent-any coverage:
  - `1.15%`
- expanded `20d` recent-any coverage:
  - `3.54%`

Interpretation:
- the richer source is real
- strict title-alias expansion is not leak-prone on the audited holdout
- the source adds a large amount of company-specific novelty beyond event surface v1
- but the operational coverage is still nowhere near the `H235` bar for opening `H236`

## Branch decision

Do **not** change the live branch.

What `H235` resolves:
- the passed CafeF company-news archive remains a valid richer company-event source candidate
- strict expansion can be done with very high holdout precision
- exact first-public timestamps remain intact
- the source is still too sparse operationally to justify event surface v2 publication work on the current archive / mapping contract

Branch effect:
- `H235` is **MIXED**
- keep `H236` closed
- keep the richer source as acquisition evidence only
- do **not** publish event surface v2 yet
- do **not** spend more local timing-model effort on this branch

Next honest move from this result:
- route active non-live effort back to the provisional intraday branch:
  - let the CafeF fetch continue
  - rerun `H232` when coverage materially changes
- keep any pre-completion intraday work reduced-shape only
- if the repo ever reopens the event-source branch, require a cleaner company-identity mapping contract or broader archive support first

## Validation

Completed before the run:
- `python -m py_compile analysis/h235_event_source_sample_audit.py src/news_event_source_research.py tests/test_news_event_source_research.py`
- `pytest -q tests/test_news_event_source_research.py`

Completed for the experiment:
- full `conda run -n stocks python analysis/h235_event_source_sample_audit.py` run completed
- saved result read from `artifacts/run_summaries/latest_timing_event_source_sample_audit.json`

Completed after a non-behavioral warning cleanup:
- `python -m py_compile analysis/h235_event_source_sample_audit.py src/news_event_source_research.py tests/test_news_event_source_research.py`
- `pytest -q tests/test_news_event_source_research.py`

Verdict:
- `H235`: **MIXED**
