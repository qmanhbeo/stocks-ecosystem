# Session 161 Log - Timing Data Wrap-Up, Source Split, And Vendor Escalation Path (2026-04-10)

## Objective

Close the `2026-04-10` timing-data acquisition pass with one clean handoff.

Questions to answer:
- what exactly was completed today?
- what genuinely succeeded versus what stayed blocked?
- which missing timing data is still realistically collectable?
- which paths are only forward-collectable?
- which paths now require paid / credentialed vendor escalation?
- what should the next operator do in the smallest honest order?

This session did not change the live branch.
It stayed long-only.
It did not tune on `2026+`.

---

## What completed today

### 1. CafeF page-2 / page-4 historical acquisition is now operational

New raw producers added and documented:
- `data_tools/fetch_cafef_order_stats.py`
- `data_tools/fetch_cafef_proprietary_trading.py`
- shared helper: `data_tools/cafef_history_common.py`

The monitored live run also fixed two real operator defects:
- manifests now update incrementally during the run instead of only at the end
- resumed runs no longer misclassify cached tickers as failures

These fixes were already committed in:
- commit `e095f56a`
- message: `Improve CafeF fetch progress tracking`

### 2. Order-stats backfill completed cleanly

Canonical raw root:
- `data/order_stats/cafef/`

Final manifest status:
- `completed`
- requested:
  - `404`
- processed:
  - `404`
- fetched:
  - `395`
- cached:
  - `9`
- failed:
  - `0`

Combined panel snapshot:
- rows:
  - `1,340,619`
- tickers:
  - `404`
- date range:
  - `2007-07-02` through `2026-04-10`

### 3. Proprietary-trading backfill completed with source-side holes

Canonical raw root:
- `data/proprietary_trading/cafef/`

Final manifest status:
- `completed_with_errors`
- requested:
  - `404`
- processed:
  - `404`
- fetched:
  - `350`
- cached:
  - `25`
- failed:
  - `29`

Combined panel snapshot:
- rows:
  - `50,918`
- tickers:
  - `343`
- date range:
  - `2022-11-01` through `2026-04-09`

Direct endpoint probes confirmed the main failures are source-side CafeF
responses rather than local parser bugs:
- representative names:
  - `ANV`
  - `BVH`
  - `DGC`
  - `GVR`
  - `HDB`
  - `HPG`
  - `KDH`
  - `LPB`
  - `MSB`
  - `NLG`
  - `OCB`
- representative payload:
  - `{"Success": false, "Message": "Input string was not in a correct format."}`

---

## What genuinely succeeded

The workspace now owns new real **daily summary** timing-adjacent surfaces:
- posted buy / sell order counts
- posted buy / sell order volume
- average buy / sell order size
- buy-sell posted-volume imbalance
- proprietary buy / sell / net volume
- proprietary buy / sell / net value

That means the following branches are no longer source-blocked:
- daily order-pressure / implementation-pain side-channel tests
- daily proprietary-flow regime tests
- daily cross-flow divergence tests:
  - foreign vs proprietary
  - foreign vs posted-order imbalance
  - proprietary vs posted-order imbalance

This is a real offline-evidence acquisition win.

---

## What stayed blocked

The older `H325` blockage still stands in the strict microstructure sense.

Open-source data in the current workspace still does **not** provide:
- historical order-book ladders
- historical queue position
- historical opening-auction state
- historical closing-auction state
- actual fill position / open-fill pain
- fine-minute order-arrival dynamics

So this session did **not** reopen:
- queue/open-fill research
- auction-resolution timing work
- true historical depth / order-book branches

---

## Practical source split after today's audit

### Collectable now from the current stack

1. open-source historical data already in hand or already wired:
- CafeF `MatchPrice` reduced-shape intraday (`1H` path)
- CafeF page 2 daily order stats
- CafeF page 4 daily proprietary trading
- CafeF historical foreign flow
- CafeF raw company news archive

2. nearby open-source expansion still feasible:
- HNX / UPCOM daily price expansion if a broader universe branch is reopened

### Collectable only if we start recording forward from now

- CafeF Liveboard board-depth / queue-pressure snapshots
- board-state snapshots near open / close / ATC
- any higher-frequency current-board state that is only shown live
- VCI current-day board accumulations beyond the existing forward foreign-flow collector

These are feasible operationally, but they are **not** historically
backfillable for dates we did not record.

### Collectable only through paid or credentialed vendor escalation

1. `FiinQuant`
- vendor docs show historical `1m/5m/15m/30m/1h/2h/4h/1d` retrieval and
  foreign buy/sell/net value fields
- vendor docs also show `3/10`-level order-book websocket coverage
- best use:
  - historical intraday + foreign-flow-like fields
- unknown from today's audit:
  - exact Vietnam entitlement
  - historical depth archive availability
  - date coverage and price

2. `SSI FastConnect`
- docs already support the repo's authenticated historical intraday fallback
- docs also show streaming board / best-bid-ask style data
- best use:
  - authenticated intraday fallback
  - live board if credentials are acceptable
- unknown from today's audit:
  - whether historical depth / auction-state archives are sold

3. `ICE` HOSE market-data products
- vendor catalog advertises HOSE level-1 / level-2 pricing
- vendor history docs advertise historical tick-by-tick level `1/2/3`
  availability
- best use:
  - enterprise path if true historical depth is worth paying for
- likely constraint:
  - this is an enterprise-cost path, not an open-data continuation

### Genuinely undoable from the current open/local stack

- reconstructing past liveboard depth for dates we never collected
- reconstructing historical queue position from daily summary tabs
- reconstructing historical auction-book state from the current CafeF pages
- turning page-2 / page-4 daily summaries into true minute-level microstructure

---

## Recommended next actions

Do these in order:

1. run the first honest daily side-channel research pass
- build order-pressure / proprietary-flow / cross-flow divergence features
- test them as daily implementation-pain / crowding / transfer states
- do **not** market them as queue/depth evidence

2. if timing research still needs more than daily side channels, escalate the vendor question directly
- ask `FiinQuant`, `SSI`, and `ICE` one exact question:
  - do you provide historical HOSE/HNX/UPCOM order-book depth or auction-state
    data?
  - at what granularity?
  - for what date range?
  - at what cost?

3. only build new forward collectors if the vendor route fails or is too expensive
- if a future liveboard collector is built, treat it as forward-only raw
  acquisition, not as a historical solution

4. keep the source taxonomy honest in future notes
- daily side channels:
  - unlocked
- reduced-shape intraday:
  - unlocked
- historical queue / depth / auction state:
  - still blocked unless a paid vendor or new live collection path is accepted

---

## Handoff summary

If someone resumes from here, the clean branch state is:
- `page 2 / page 4` acquisition:
  - success
- order-stats backfill:
  - complete
- proprietary-trading backfill:
  - complete with source-side holes
- daily pressure / flow side-channel branch:
  - now honestly testable
- true queue/open-fill branch:
  - still blocked on richer data
- next external decision:
  - vendor escalation vs staying inside the daily-side-channel branch

## Validation

Completed during the wrap-up pass:
- `git diff --check`
- direct manifest inspection for final acquisition status
- direct panel count snapshots for rows / tickers / date ranges
- earlier direct endpoint probes on failed proprietary names confirming
  source-side CafeF failures

No broader experiment suite was run in this session.
