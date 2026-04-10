# Session 160 Log - CafeF Order-Stats And Proprietary-Trading Acquisition (2026-04-10)

## Objective

Record the durable outcome of the CafeF page-2 / page-4 acquisition follow-through.

Question:
- after discovering CafeF stock-history page 2 (`ThongKeDL`) and page 4
  (`GDTuDoanh`), what exactly is now data-unblocked?
- does this reopen the previously blocked queue / open-fill branch, or only a
  lower-resolution daily side-channel branch?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added and monitored two new raw historical producers:
- `data_tools/fetch_cafef_order_stats.py`
- `data_tools/fetch_cafef_proprietary_trading.py`

Shared helper:
- `data_tools/cafef_history_common.py`

Matching operator docs were updated in:
- `data_tools/README.md`
- `notes/data_sources.md`
- `notes/timing_data_acquisition_plan.md`
- `notes/timing_data_source_scorecard.csv`

### Operational fixes during the monitored backfill

The first live monitored run found two real fetcher issues and both were fixed:

1. run-level progress tracking was too weak mid-run
- the original manifest only wrote at the end
- fix:
  - manifests now update incrementally during the run
  - status is explicit:
    - `running`
    - `completed`
    - `completed_with_errors`
    - `interrupted`
  - processed / fetched / cached / failed ticker counts are now durable

2. resumed runs misclassified cached tickers as failures
- root cause:
  - cached-path logging used `cached_frame or []`, which is invalid once
    `cached_frame` is a real DataFrame
- fix:
  - cached rows now use `len(cached_frame)` when present
  - resumed runs cleanly skip cached windows again

These fixes were committed separately in:
- commit `e095f56a`
- message: `Improve CafeF fetch progress tracking`

---

## Acquisition state

### `fetch_cafef_proprietary_trading.py`

The first live full-universe backfill completed with source-side holes.

Manifest snapshot:
- status:
  - `completed_with_errors`
- tickers requested:
  - `404`
- tickers fetched:
  - `350`
- tickers cached:
  - `25`
- tickers failed:
  - `29`
- panel rows:
  - `50,918`
- panel tickers:
  - `343`
- manifest timestamp:
  - `2026-04-10T21:08:58Z`

Canonical raw root:
- `data/proprietary_trading/cafef/`

Key source behavior:
- the failures are not local code crashes
- direct endpoint probes reproduced the same CafeF payload:
  - `{"Success": false, "Message": "Input string was not in a correct format."}`
- representative source-failure names:
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

### `fetch_cafef_order_stats.py`

The live full-universe backfill is in progress with durable resume support.

Manifest snapshot at note-promotion time:
- status:
  - `running`
- tickers requested:
  - `404`
- tickers processed:
  - `143`
- tickers fetched:
  - `134`
- tickers cached:
  - `9`
- tickers failed:
  - `0`
- current ticker:
  - `HDB`
- manifest timestamp:
  - `2026-04-10T21:13:27Z`

Canonical raw root:
- `data/order_stats/cafef/`

Important note:
- this count is only a snapshot from note-promotion time
- the live source of truth for current run status is:
  - `data/order_stats/cafef/manifest.json`

---

## What this newly unblocks

These two surfaces reopen a **daily summary** branch that the workspace did not
have before.

Specifically, they now support honest tests of:

1. daily order-pressure / implementation-pain states
- posted buy vs sell order count imbalance
- posted volume imbalance
- average order size asymmetry
- interaction with blocked-buy / limit-hit / next-open strain proxies

2. daily proprietary-flow regime states
- proprietary buy / sell / net volume
- proprietary buy / sell / net value
- interaction with market-wide momentum, event follow-through, and crowding

3. cross-surface conflict states
- foreign flow vs proprietary flow
- foreign flow vs posted-order imbalance
- proprietary flow vs posted-order imbalance
- possible transfer / crowding / absorption regimes

So some earlier low-resolution “execution strain / crowding / pressure” ideas
are no longer source-blocked.

---

## What remains blocked

The older `H325` conclusion still stands in the strict microstructure sense.

These new surfaces do **not** provide:
- opening-auction queue state
- bid / ask depth
- order-book ladders
- actual fill position
- fine-minute sequence data
- time-of-day order arrival dynamics

So this session does **not** reopen:
- queue imbalance research
- opening-fill pain research
- auction-resolution timing work

Those branches still need a real auction / order-book / fine-minute source.

---

## Branch decision

Promote this as an acquisition-side **offline evidence / source unlock**, not
as resolution of the queue/open-fill branch.

New honest low-cost follow-through is:
- daily order-pressure side-channel audit
- proprietary-flow side-channel audit
- cross-flow conflict / divergence audit

Do **not** relabel this as:
- “queue data acquired”
- “order-book branch solved”
- “auction-resolution timing unlocked”

---

## Validation

Completed during the pass:
- `python -m py_compile alpha-research-lab/data_tools/cafef_history_common.py alpha-research-lab/data_tools/fetch_cafef_order_stats.py alpha-research-lab/data_tools/fetch_cafef_proprietary_trading.py`
- `pytest -q tests/test_cafef_history_fetchers.py`
- direct endpoint probes on failing proprietary names confirmed CafeF
  `Success=false` source-side failures rather than local parser bugs
- monitored live resumes confirmed:
  - per-ticker checkpointing works
  - manifests update during the run
  - interrupted runs can resume cleanly from cached windows

The broader test suite was not run.
