# Session 144 Log — Historical Foreign-Flow Source Gate (2026-04-09)

## Objective

Formalize and test the acquisition queue item after `H323`:
- `H324` historical-foreign-flow-source

Question:
- is there any real historical per-ticker foreign buy/sell or foreign-room
  table available locally that can support a pilot IC audit?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+` alpha labels.

---

## What changed

Added one bounded source-gate script:
- `analysis/h324_historical_foreign_flow_source.py`

### H324 - Historical Foreign-Flow Source Gate
**Hypothesis:**
The next high-value acquisition branch should proceed only if a real historical
per-ticker foreign-flow table exists. The known VNM ETF proxy should not be
retested as if it were the blocked H95 data source.

**Command / code:**
`python analysis/h324_historical_foreign_flow_source.py`

**Inputs:**
- canonical root `data/` file inventory
- `data/features/xs_foreign_demand_daily.parquet`
- `data/fx-commodities/fx_commodities_vnm_etf_1D.parquet`
- existing `vnstock` API probe evidence

**Saved artifact:**
`artifacts/run_summaries/20260409_161835_h324_historical_foreign_flow_source_research_branch_historical_foreign_flow_source.json`

| Metric | Value | Note |
|--------|-------|------|
| local candidate paths | `2` | path/schema scan under root `data/` |
| real foreign-flow candidates | `0` | no `time+ticker+foreign_buy/sell/room` historical table |
| schema fragments | `0` | no unmapped historical flow fragments |
| VNM ETF proxy rows | `826,404` | `xs_foreign_demand_daily`, archive-only failed H110 proxy |
| VNM ETF proxy tickers | `394` | cross-sectional affinity proxy, not real buy/sell |
| VNM ETF price rows | `4,182` | date-level ETF price, not per-ticker flow |
| vnstock live probe | no historical method | installed `vnstock 3.5.0`; no `quote.history_foreign_ownership`; `price_board` is current-day only |

**Result:**
The branch remains source-blocked. The local warehouse contains only the known
archive-only VNM ETF foreign-demand proxy and the raw VNM ETF price surface.
Neither is a real historical per-ticker foreign buy/sell or foreign-room table,
and H110 already killed the proxy mechanism. A live vnstock probe with network
permission again found no historical foreign-ownership/flow method in the
installed package; current-day board fields are not backtestable.

**Verdict: SKIP**

---

## Branch decision

`H324` does not run an alpha test:
- no valid historical foreign-flow source exists locally
- do **not** retest the VNM ETF proxy
- keep H95 / historical foreign-flow alpha blocked until a real data source is
  acquired or a forward-only collector is started

Next honest acquisition queue item:
- `queueing-open-fill-source`
  - the next missing surface with high expected value is auction / order-book /
    opening-queue data, not another proxy surface

---

## Validation

Completed during the pass:
- ran `python analysis/probe_vnstock.py` with network permission
- ran `python -m py_compile analysis/h324_historical_foreign_flow_source.py`
- ran `python analysis/h324_historical_foreign_flow_source.py`
- read the saved source-gate summary and inventory artifact

The broader test suite was not run.
