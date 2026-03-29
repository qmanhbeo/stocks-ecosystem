# Timing Data Acquisition Plan

This file is the active acquisition branch for timing research.

Use it when:
- activation / exit work on current daily data is exhausted
- the live sticky branch is frozen
- the next honest move is to acquire genuinely new timing data rather than invent more threshold rules

Current policy:
- live branch remains frozen while this branch runs
- do not tune timing rules on `2026+`
- sequential hypothesis ladders remain mandatory

## Current branch decision

The current local workspace has already established:
- current daily-data activation branch: exhausted for local tuning
- current daily-data exit branch: exhausted for local tuning
- corporate-event surface v1: good local coverage, failed predictive gate
- local intraday surface: not usable beyond `FPT` 1H
- local order-book / queue data: not available historically

So the active next branch is acquisition-first:

1. acquire a usable multi-ticker intraday / auction surface
2. if that is not feasible, acquire a richer company-event source than the current event surface
3. if that is also not feasible, stop timing research and wait for more forward live evidence or genuinely new data access

## Decision tree

### H230: Intraday source audit
Goal:
- determine whether a real multi-ticker intraday / auction source is obtainable

Candidate source requirements:
- at least `100` tickers preferred; `50` is the hard floor
- at least `2023-01-01` through `2025-12-31`; `2021+` preferred
- OHLCV bar data at `<= 60m` granularity
- timestamps in exchange local time or convertible to exchange local time
- stable identifiers mappable to the 394-ticker daily universe
- historical access, not live-only

Required output:
- source list with exact fields, limits, date coverage, and cost/licensing notes
- one recommended source or a hard fail

Pass:
- at least one source appears operationally acquirable and meets the minimum schema/date requirements

Fail:
- no source meets those requirements

If H230 passes:
- go to H231

If H230 fails:
- go to H234

### H231: Intraday sample pull and normalization pilot
Goal:
- prove that the chosen source can be normalized into a lab-usable intraday panel

Pilot scope:
- `20` representative tickers
- `60` trading sessions minimum
- include liquid banks, industrials, and smaller names

Required normalized columns:
- `time`
- `ticker`
- `open`
- `high`
- `low`
- `close`
- `volume`
- optional but valuable:
  - `value`
  - `vwap`
  - `match_price_ato`
  - `match_price_atc`
  - auction-specific matched volume

Hard checks:
- no duplicated `(time, ticker)` rows
- monotonic timestamps within ticker/day
- session boundaries map correctly to Vietnam market hours
- corporate-action distortions are understood and documented

Current repo normalization bridge:
- raw open-source acquisition path:
  - `data_tools/fetch_cafef_intraday.py`
- repo-aligned adjustment step:
  - `data_tools/adjust_cafef_intraday_to_vci.py`
- current factor rule:
  - `price_factor[t] = vci_daily_close[t] / cafef_raw_intraday_last_close[t]`
  - adjusted intraday `open/high/low/close = raw_cafef_ohlc * price_factor[t]`
  - keep `volume` raw unless a separate volume-adjustment contract is proven

Pass:
- pilot panel builds cleanly and supports derived first-hour / close-auction features

Fail:
- schema is too inconsistent, timestamps are unreliable, or pilot continuity is poor

If H231 passes:
- go to H232

If H231 fails:
- go to H234

### H232: Intraday coverage and continuity gate
Goal:
- decide whether the normalized intraday source is actually sufficient for timing research

Coverage metrics:
- held-row coverage against the continuation panel over `2023-2025`
- ticker coverage across the active research universe
- missing-session rate
- bar-completeness rate per day

Promotion thresholds:
- held-row coverage `>= 50%`
- ticker coverage `>= 50` tickers minimum
- missing-session rate `< 10%`
- enough information to derive:
  - first `30m` return
  - first `60m` return
  - intraday reversal flag
  - close / auction weakness proxy

Pass:
- intraday source is usable

Fail:
- coverage or continuity is too weak

If H232 passes:
- go to H233

If H232 fails:
- go to H234

### H233: Publish intraday surface and reopen timing research
Goal:
- turn the viable intraday source into a canonical lab artifact

Required artifact:
- `data/features/intraday_structure_daily.parquet`

Required per `(time, ticker)` features:
- `open_gap_vs_prev_close`
- `first_30m_return`
- `first_60m_return`
- `first_60m_range_pct`
- `midday_vwap_distance`
- `close_auction_return`
- `close_auction_vs_vwap`
- `intraday_reversal_flag`
- `failed_breakout_intraday`
- `open_drive_then_fade_flag`

Branch effect:
- reopen the intraday timing ladder on the locked protocol
- do not change the live branch yet

### H234: Richer corporate-event source audit
Run this only if the intraday branch fails.

Goal:
- find a richer event source than the current event surface v1

Why the current surface is insufficient:
- current event surface mostly uses:
  - dividend cache (`52` names)
  - issuance / listing-change events
  - insider / major-holder filing timestamps
  - global quarter-phase earnings calendar
- it does not have broad company-specific earnings announcement timestamps
- it does not have a broad board / AGM / rights / issuance event ledger for the full universe

Minimum useful new event source must add at least one of:
- company-specific earnings announcement date/time
- AGM / EGM dates
- rights issue announcement + effective window
- board resolution dates tied to issuance / corporate action
- richer major-holder / insider filing metadata with public timestamps

Pass:
- a richer, timestamped event source is identified and is acquirable for a meaningful subset of the universe

Fail:
- no richer event source is realistically available

If H234 passes:
- go to H235

If H234 fails:
- go to H237

### H235: Event source sample audit and coverage gate
Goal:
- prove the richer event source is operationally better than event surface v1

Pilot requirements:
- at least `100` tickers preferred; `50` minimum
- date range covering `2023-2025`
- first-public timestamps are recoverable
- no leakage from retrospectively known event dates

Coverage thresholds:
- held-row coverage `>= 60%` is ideal
- held-row coverage `>= 40%` can still be useful if the added event fields are genuinely new and company-specific

Pass:
- source materially improves the current event surface on information content or coverage

Fail:
- source is too sparse, too noisy, or too leak-prone

If H235 passes:
- go to H236

If H235 fails:
- go to H237

### H236: Publish event surface v2 and reopen event-driven timing research
Goal:
- publish a richer event artifact and rerun event-driven timing research from the start

Required artifact:
- `data/features/event_surface_v2_daily.parquet` or a promoted replacement for `event_surface_daily.parquet`

Required branch behavior:
- rerun predictive screening before any deterministic integration
- compare against the earlier failed H221/H222 event branch honestly
- do not jump directly to live integration

### H237: Stop timing research on current data access
Goal:
- close the branch cleanly if neither intraday nor richer event data is feasible

Required action:
- keep the live branch frozen
- continue live scoreboard monitoring only
- wait for either:
  - actual data acquisition progress
  - or enough forward live evidence to justify reopening another branch

## Data-family acceptance summary

### Intraday / auction source is usable only if:
- multi-ticker, not single-name legacy data
- historical, not live-only
- enough coverage to hit the held-row gate
- stable timestamps and session structure

### Richer event source is usable only if:
- event timestamps are public and reconstructable
- information is company-specific, not just quarter-phase
- coverage materially improves over event surface v1

### Order-book / queue branch is out of scope until:
- historical depth/imbalance data actually exists locally or is licensable
- timestamps can be mapped into daily summaries without leakage

## Current source scorecard

Read together with:
- `notes/timing_data_source_scorecard.csv`

That scorecard is the compact operational snapshot.
This file is the full branch logic.
