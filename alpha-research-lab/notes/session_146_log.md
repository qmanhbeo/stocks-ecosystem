# Session 146 Log — Forward Foreign-Flow Collector (2026-04-09)

## Objective

Formalize and implement the next acquisition queue item after `H325`:
- `H326` forward-foreign-flow-collector

Question:
- if real historical per-ticker foreign flow is unavailable, can the workspace
  start collecting current-day board foreign fields forward-only under a clear,
  non-backtestable contract?

This session did not change the live branch.
It stayed long-only.
It did not run an alpha backtest.

---

## What changed

Added one data producer and one contract gate:
- `data_tools/collect_forward_foreign_flow.py`
- `analysis/h326_forward_foreign_flow_collector.py`

New canonical forward-only data root:
- `data/foreign_flow_forward/vci_price_board/`

Written outputs:
- `data/foreign_flow_forward/vci_price_board/snapshots/2026-04-09/vci_price_board_foreign_flow_20260409T164939Z.parquet`
- `data/foreign_flow_forward/vci_price_board/latest_snapshot.parquet`
- `data/foreign_flow_forward/vci_price_board/daily_latest.parquet`
- `data/foreign_flow_forward/vci_price_board/manifest.json`

The contract is explicit:
- source: `vnstock_vci_price_board`
- forward-only: `true`
- not backtestable yet: `true`
- snapshot primary key: `collected_at_utc, ticker`
- daily latest primary key: `trading_date, ticker`
- required board fields:
  - `foreign_buy_volume`
  - `foreign_sell_volume`
  - `foreign_buy_value`
  - `foreign_sell_value`
  - `current_room`
  - `total_room`

### H326 - Forward Foreign-Flow Collector Contract Gate
**Hypothesis:**
The correct response to missing historical foreign flow is to start a
forward-only current-day board collector now, not to retest the failed VNM ETF
proxy or pretend the new data is historical.

**Command / code:**
`python data_tools/collect_forward_foreign_flow.py --chunk-size 50 --delay 0.2`

`python analysis/h326_forward_foreign_flow_collector.py`

**Inputs:**
- local HOSE ticker universe from `data/stock/gia_lich_su_<TICKER>_1D.parquet`
- vnstock/VCI `stock.trading.price_board(symbols_list=...)`

**Saved artifact:**
`artifacts/run_summaries/20260409_165555_h326_forward_foreign_flow_collector_research_branch_forward_foreign_flow_collector.json`

| Metric | Value | Note |
|--------|-------|------|
| fixture contract passed | `true` | synthetic MultiIndex price-board normalizer test |
| live capture ready | `true` | manifest + latest snapshot validated |
| latest rows | `404` | full local HOSE board snapshot |
| latest tickers | `404` | excludes default indices |
| latest trading date | `2026-04-09` | board date from VCI response |
| failed chunks | `0` | full run succeeded |
| daily latest rows | `404` | one latest row per trading-date/ticker |
| biggest positive net foreign value | `HPG +482.15B VND` | current-day board accumulation |
| biggest negative net foreign value | `VPL -3.284T VND` | current-day board accumulation |

**Result:**
The forward collector is implemented and successfully captured a full local
HOSE snapshot for `2026-04-09`. This is a data-acquisition pass, not an alpha
pass. The captured fields are current-day accumulated board fields and must
remain marked forward-only until enough snapshots accrue for honest research.

**Verdict: PASSED**

---

## Branch decision

`H326` advances the data-acquisition branch:
- start running `python data_tools/collect_forward_foreign_flow.py` once per
  trading day, preferably after market close
- do not run a foreign-flow alpha backtest until enough forward history accrues
- do not backfill from VNM ETF or other proxy surfaces into this contract

Next honest follow-up:
- `forward-foreign-flow-daily-runbook`
  - add a simple scheduled-run habit or cron wrapper if desired
  - after enough forward days exist, run the first honest source-quality audit:
    coverage by date, missing tickers, stale board dates, and basic stability of
    foreign net value / room fields

Research can continue on other non-LLM ideas while this surface accumulates.

---

## Validation

Completed during the pass:
- ran `python -m py_compile data_tools/collect_forward_foreign_flow.py analysis/h326_forward_foreign_flow_collector.py`
- ran `python data_tools/collect_forward_foreign_flow.py --tickers FPT,VCB,HPG --dry-run`
- attempted live collector in sandbox and confirmed DNS/network was blocked
- reran live collector with approved network access
- ran full local-HOSE collector: `404` rows, `0` failed chunks
- ran `python analysis/h326_forward_foreign_flow_collector.py`
- read `artifacts/run_summaries/latest_research_branch_forward_foreign_flow_collector.json`
- read the manifest and sampled output rows

The broader test suite was not run.

---

## Addendum - CafeF Historical Foreign Flow Source Correction

After `H326`, a narrower follow-up source probe checked whether CafeF itself
exposes a historical per-ticker foreign-flow endpoint.

It does.

The stock-history `Khối ngoại` tab is backed by:
- `cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDKhoiNgoai.ashx`

Representative live probes confirmed that this is a real historical daily
source, not just a current-day board view:
- `FPT`
  - oldest observed date: `2006-12-13`
  - returned rows: `4,769`
- `VCB`
  - oldest observed date: `2009-06-30`
- `HPG`
  - oldest observed date: `2007-03-01`

New producer added:
- `data_tools/fetch_cafef_foreign_flow.py`

New raw canonical root:
- `data/foreign_flow/cafef/`

Written surfaces:
- `data/foreign_flow/cafef/per_ticker/<TICKER>.parquet`
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- `data/foreign_flow/cafef/manifest.json`

Validation run:
- command:
  - `python data_tools/fetch_cafef_foreign_flow.py --tickers FPT,VCB --start-date 2015-01-01 --end-date 2026-04-09 --force --sleep 0`
- rows:
  - `5,604`
- tickers:
  - `2`
- failures:
  - `0`

This changes the acquisition status of the old foreign-flow branch:
- historical foreign flow is still unavailable from vnstock
- but it is available from CafeF
- `H95` should now move from source-blocked to source-acquired / audit-next
