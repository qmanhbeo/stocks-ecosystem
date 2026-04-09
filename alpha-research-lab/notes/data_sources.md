# Data Sources & Inventory

Canonical reference for what data exists, where it lives, how it was created,
and how to restore it. Read this before running any experiment or wondering why
a file is missing.

**For a detailed tool-by-tool breakdown see `data_tools/README.md`.**

---

## TL;DR for Agents

All paths below are written as `data/...` because this repo is meant to be run from
inside `alpha-research-lab/`, where `data/` is a symlink to the shared workspace root
`/home/manh/stocks/data`.

For the active timing-data acquisition branch, also read:
- `notes/timing_data_acquisition_plan.md`
- `notes/timing_data_source_scorecard.csv`

| Data | In git? | How to restore if missing |
|------|---------|---------------------------|
| `data/features/*.parquet` | YES | Already in repo; regenerate with scripts below if corrupted |
| `data/stock/` — 394 HOSE OHLCV parquets | YES | `fetch_hose_universe.py` / `fetch_refresh_all.py` |
| `data/fx-commodities/` — 20 global files | YES | `fetch_fx_commodities.py` + `fetch_global_macro.py` |
| `data/insider_cache/` — 394 ticker parquets | YES | `fetch_insider_deals.py` |
| `data/foreign_flow/cafef/` — historical CafeF foreign flow | YES | `fetch_cafef_foreign_flow.py` |
| `data/foreign_flow_forward/` — forward-only VCI board snapshots | YES | `collect_forward_foreign_flow.py` |
| `data/news/cafef/raw/*.jsonl` | NO (3.6 GB) | `python data_tools/fetch_news_archive.py` |
| Full `data/` snapshot (legacy) | NO | `python setup_data.py` (restores the newest `data-snapshot-YYYY-MM-DD-HHMMSS.tar.zst` from the Drive backup remote after SHA256 verification; pass `--snapshot-name` to restore a specific run) |

To create a fresh full-data snapshot backup, run `rclone config` once to create a Google Drive remote, then run:
```bash
python backup_data_snapshot.py
```
This produces `data-snapshot-YYYY-MM-DD-HHMMSS.tar.zst` plus the matching `.sha256`, uploads both via `rclone`, and keeps the newest 7 runs by default.
Repeated runs on the same day stay distinct because the archive name includes the run time.
It uses zstd level 9 by default.
Default Drive destination: `stocks-ecosystem-data-snapshots:project-backup/stock-data-backup/`.

---

## What Is Tracked in Git

In the workspace root repo, everything in shared `data/` **except** `data/news/` is committed
to git. Inside `alpha-research-lab/`, `data/` is only a symlink to that shared location.

### Pre-Generated Feature Files (active)

| File | Description | Signal | Regenerate |
|------|-------------|--------|------------|
| `xs_barrier_vol_1d_hose_full.parquet` | **H93 — primary RL signal** | S1 | See command below |
| `xs_insider_deals_raw.parquet` | Raw insider transaction disclosures | C2 raw | `fetch_insider_deals.py` |
| `xs_insider_features.parquet` | Rolling 5d/30d insider signal matrix | C2 features | `build_insider_features.py` |
| `xs_news_sentiment_daily.parquet` | H89: keyword sentiment per (day, ticker) | C1 raw | `extract_news_sentiment.py` |
| `xs_news_sentiment_rolling.parquet` | H96: 5d/30d rolling news features | C1 rolling | `build_rolling_news_sentiment.py` |
| `sector_classification.parquet` | ICB sector labels, 398 tickers | — | `fetch_sector_classification.py` |
| `xs_dividend_calendar.parquet` | Ex-dividend dates and windows | — | `fetch_dividend_events.py` |
| `macro_regime_daily.parquet` | VIX, yields, global indices regime | — | `build_macro_regime_features.py` |

**H93 regeneration command:**
```bash
conda run -n stocks python cross_sectional_wf.py \
  --use-volume-signals --barrier-pct 0.01 --target-horizon 1 \
  --save-all-probas data/features/xs_barrier_vol_1d_hose_full.parquet
```

---

## What Is NOT Tracked in Git

### `data/news/` — Cafef News Archive (3.6 GB)

- **Contents:** 3,734 daily JSONL files from cafef.vn
- **Format:** `data/news/cafef/raw/YYYY-MM-DD.jsonl`
- **Date range:** 2016–2026
- **Why excluded:** 3.6 GB too large for git
- **GDrive ID:** `1uzE57O1TTb7pMsQuTNtSiTKDgDt723-l`

**To restore:**
```bash
python data_tools/fetch_news_archive.py
```

---

## Raw Data Sources

### vnstock (VCI source) — market data
- **Stock OHLCV:** `Vnstock(source='VCI').stock(symbol).quote.history(...)`
- **Sector classification:** `.company.overview()` → `icb_name2/3/4`
- **Dividend events:** `.company.events()` → ex-dates
- **Foreign flow:** historical per-ticker daily flow is still not available from vnstock; use CafeF `GDKhoiNgoai` for history, or VCI `price_board` for forward-only current-day accumulation.
- **Forward foreign-flow collector:** `stock.trading.price_board(symbols_list=...)`
  exposes current-day accumulated `foreign_buy_volume`,
  `foreign_sell_volume`, `foreign_buy_value`, `foreign_sell_value`,
  `current_room`, and `total_room`. Session 146 `H326` stores these under
  `data/foreign_flow_forward/vci_price_board/`. This is forward-only and not
  backtestable until enough future collection days accrue.
- **Insider deals (vnstock):** KBS endpoint returns `[]` (unpopulated); VCI has no implementation. Use CafeF instead.

### CafeF APIs — financial disclosure data
- **Price history:** `s.cafef.vn/Ajax/PageNew/DataHistory/PriceHistory.ashx`
- **Historical foreign flow (Khối ngoại):**
  `cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDKhoiNgoai.ashx?Symbol=<TICKER>&StartDate=...`
  - public/no auth required
  - full local backfill currently has `404` tickers, `1,353,462` rows, and date range `2001-04-02` through `2026-04-09`
  - live probe confirmed examples back to `2006-12-13` for `FPT`
  - H327 source audit found `98.80%` row coverage versus the 2015-2025 local stock calendar, with `AAA`, `YBM`, and `YEG` missing in that audit window
  - H327/H328 rejected raw and conditioned foreign buy/sell ranks as signal-library candidates; treat this as raw source data unless a different feature thesis passes
  - fields: `KLMua`, `GtMua`, `KLBan`, `GtBan`, `KLGDRong`, `GTDGRong`, `RoomConLai`, `DangSoHuu`, `ThayDoi`
- **Insider + large-shareholder transactions (GDNB):**
  `cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx?Symbol=<TICKER>&StartDate=...`
  - 394/394 HOSE tickers covered, 2010–2026, free/no auth required
  - Fields: `PublishedDate`, `PlanBuyVolume`, `PlanSellVolume`, `RealBuyVolume`, `RealSellVolume`, `ShareHolderCode`
  - `ShareHolderCode` prefix: `CEO_`/`LQ_` = insiders, `CORP_` = large shareholders

### yfinance — global macro / indices
- VIX, S&P500, gold, oil, copper, Asian indices, EM ETFs, yield curve
- Stored in `data/fx-commodities/`

---

## What Is Genuinely Not Available

| Data | Reason |
|------|--------|
| Historical intraday OHLCV / tick data via vnstock | vnstock doesn't provide historical intraday |
| SSC filing text (structured JSON) | SSC portal is HTML-only |

Forward-only acquisition note:
- Session 146 `H326` started `data/foreign_flow_forward/vci_price_board/`
  from current-day VCI board fields.
- First full snapshot:
  - board date `2026-04-09`
  - `404` tickers
  - `0` failed chunks
- This is not a historical source and must not be used for backtests until a
  sufficient forward window exists and passes a source-quality audit.

Open intraday note:
- CafeF does expose a public historical matched-trade endpoint:
  - `https://msh-appdata.cafef.vn/rest-api/api/v1/MatchPrice`
- repo fetcher:
  - `data_tools/fetch_cafef_intraday.py`
- whole-universe wrapper:
  - `data_tools/fetch_cafef_intraday_all.py`
- repo normalization step:
  - `data_tools/adjust_cafef_intraday_to_vci.py`
- this is an open acquisition path, but it is still a source-specific scraper/adapter, not an officially documented bulk research API contract
- output is kept source-specific by default (`*_1H_CAFEF.parquet`) so it can coexist with other intraday attempts
- safe universe command:
  - `python data_tools/fetch_cafef_intraday_all.py`
  - wrapper default range is `2000-01-01` through `2099-12-31`
- current practical warning:
  - CafeF session prices are raw source prices
  - local `1D` VCI prices in this repo are treated as adjusted historical prices
  - use the daily close factor bridge when cross-day continuity matters:
    - `price_factor[t] = vci_daily_close[t] / cafef_raw_intraday_last_close[t]`
    - adjusted intraday `open/high/low/close = raw_cafef_ohlc * price_factor[t]`
  - `volume` should stay raw unless a separate volume-adjustment contract is proven
- operational fetch design:
  - `fetch_cafef_intraday.py` writes complete yearly parts first, then appends them into the final ticker parquet
  - yearly parts now carry a requested-calendar metadata sidecar, so reruns can skip unchanged historical years but still refresh the latest requested year when the daily calendar expands
  - failed CafeF date requests are retried automatically `2` times after the initial pass before a year is accepted as complete
  - empty early-history years are cached as valid empty yearly parts; this avoids refetching source-empty prefixes on later runs
- empirical coverage note from the current workspace:
  - early daily history does not guarantee intraday coverage from CafeF
  - example: `FPT` daily history starts `2006-12-13`, but the first observed CafeF hourly bars currently start on `2014-10-29`

Tried but failed / limited intraday attempts:
- `vnstock` / VCI `1H` fetch:
  - works only from roughly `2023-09-11` onward in current observed behavior
  - not sufficient for deep historical timing research
- SSI FastConnect:
  - official historical intraday endpoint exists
  - repo fetcher: `data_tools/fetch_ssi_intraday.py`
  - operationally blocked for the open-data branch because it requires credentials and service registration

## Timing Research Acquisition Status

Current branch state:
- event surface v1 exists and is published at `data/features/event_surface_daily.parquet`
- it failed the predictive gate for continuation / exit timing
- legacy published local intraday data is only `FPT` 1H, but the newer CafeF `1H` + VCI bridge has now cleared a reduced-shape contract audit on `2023-2025`:
  - `402` raw tickers
  - `93.05%` held-row coverage lower bound
  - `6.87%` missing-session rate
  - universal five-bar completeness still not honest (`67.50%` complete-day share present), so this is a reduced-shape research surface, not a canonical auction-resolution artifact
  - the first reduced-shape exit predictive screen still failed, so the source reopens research but does not yet prove timing alpha
- local order-book / queue history is absent
- Session 145 `H325` refreshed this source gate:
  - `13,637` source-looking local paths scanned
  - `0` true historical queue / order-book candidates
  - `0` true fine-minute candidates
  - local intraday remains reduced hourly OHLCV plus daily summaries, not an
    auction / queue-resolution artifact

Operational consequence:
- do not keep tuning timing rules on the current local data stack
- if timing research continues, follow `notes/timing_data_acquisition_plan.md`

---

## Data Available But Not Fully Fetched

| Data | Current coverage | Full coverage script |
|------|-----------------|---------------------|
| Dividend events | 52 tickers | `fetch_dividend_events.py` on full 394 |
| Fundamentals (quarterly ratios) | 52 tickers | `fetch_all_stock_fundamentals.py` on full 394 |

---

## Notes on Data Quality

- **HOSE only** — HNX/UPCOM not included
- **VCI daily prices adjusted** for splits/dividends by VCI
- **CafeF MatchPrice prices raw** until explicitly normalized onto the VCI daily backbone
- **Insider signal date:** use `published_date` (SSC disclosure date) — `real_end_date` is after-the-fact
- **Ticker identification in news:** parenthetical pattern `(TICKER)` in article titles
