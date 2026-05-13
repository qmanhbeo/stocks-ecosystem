# Session 145 Log — Queueing / Open-Fill Source Gate (2026-04-09)

## Objective

Formalize and test the next acquisition queue item after `H324`:
- `H325` queueing-open-fill-source

Question:
- does the canonical warehouse contain any historical auction, order-book,
  opening-queue, or fine-minute source that can honestly test queue imbalance
  / open-fill pain?

This session did not change the live branch.
It stayed long-only.
It did not use `2026+` alpha labels.

---

## What changed

Added one bounded source-gate script:
- `analysis/h325_queueing_open_fill_source.py`

The first implementation pass produced false positives because broad substring
matching treated `ticker`, ticker `BID`, `order_date`, and `insider` as
microstructure evidence. The gate was tightened to use token-level path and
column matching, and `barrier_depth` prediction files are now explicitly
classified as non-order-book artifacts.

### H325 - Queueing / Open-Fill Source Gate
**Hypothesis:**
The queueing / open-fill branch should advance only if the local warehouse has
true auction, order-book, opening-queue, or fine-minute data. Reduced hourly
OHLCV, adjustment factors, daily intraday-shape summaries, and price-limit
blocked-buy proxies are not sufficient to test the mechanism.

**Command / code:**
`python analysis/h325_queueing_open_fill_source.py`

**Inputs:**
- canonical root `data/` file inventory
- `data/stock/gia_lich_su_<TICKER>_1H_CAFEF.parquet`
- `data/stock/gia_lich_su_<TICKER>_1H_CAFEF_ADJ.parquet`
- `data/stock/_cafef_intraday_parts/1H_CAFEF/`
- `data/stock/_cafef_adjustment_factors/`
- `data/features/fpt_intraday_daily.parquet`
- legacy `data/stock/gia_lich_su_<TICKER>_1H.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_162953_h325_queueing_open_fill_source_research_branch_queueing_open_fill_source.json`

| Metric | Value | Note |
|--------|-------|------|
| source-looking paths scanned | `13,637` | root `data/` inventory excluding raw news / LLM cache |
| true queue / order-book candidates | `0` | no bid/ask/depth/order/queue historical table |
| true fine-minute candidates | `0` | no `1m/5m/15m/30m` or equivalent local source |
| reduced hourly source paths | `12,813` | CafeF raw/adjusted, yearly parts, and legacy `1H` |
| CafeF hourly yearly parts | `11,996` | source cache under `_cafef_intraday_parts/1H_CAFEF/` |
| CafeF raw hourly files | `404` | `*_1H_CAFEF.parquet` |
| CafeF adjusted hourly files | `404` | `*_1H_CAFEF_ADJ.parquet` |
| legacy hourly files | `9` | shallow `*_1H.parquet`, starts around 2023 in samples |
| adjustment factor files | `810` | audit/normalization tables, not microstructure |
| derived daily intraday files | `1` | `fpt_intraday_daily.parquet` |
| sampled median bars/day | `4.0` | representative hourly files |
| sampled max bars/day | `5` | hourly OHLCV, not auction / queue resolution |

**Result:**
The branch is source-blocked. The local warehouse has broad reduced hourly
coverage, but the schemas are OHLCV-only (`time/open/high/low/close/volume`) or
daily derived summaries. There are no historical bid/ask depth fields, opening
queue fields, order-book snapshots, matched-order tape fields, or fine-minute
bars fine enough to test queue imbalance / fill pain honestly.

**Verdict: SKIP**

---

## Branch decision

`H325` does not run an alpha test:
- no valid historical queue / order-book / auction / fine-minute source exists
  locally
- do **not** convert hourly OHLCV or price-limit blocked-buy proxies into fake
  queue imbalance evidence
- keep queue/open-fill alpha blocked until an explicit microstructure source is
  acquired

Next honest acquisition queue item:
- `forward-foreign-flow-collector`
  - H324 showed historical foreign flow is unavailable
  - the cheap path is a forward-only current-day board collector, not a
    backtestable historical feature yet

Separate acquisition note:
- if queue/open-fill is reopened, first acquire an external order-book /
  auction / fine-minute contract and validate it as a source before any alpha
  pilot.

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h325_queueing_open_fill_source.py`
- ran `python analysis/h325_queueing_open_fill_source.py`
- read `artifacts/run_summaries/latest_research_branch_queueing_open_fill_source.json`
- read the saved details artifact and sampled inventory classifications

The broader test suite was not run.
