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
| `data/news/cafef/raw/*.jsonl` | NO (3.6 GB) | `python data_tools/fetch_news_archive.py` |
| Full `data/` snapshot (legacy) | NO | `python setup_data.py` (GDrive backup, may be stale) |

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
- **Foreign flow:** NOT available historically (current-day only). See F59.
- **Insider deals (vnstock):** KBS endpoint returns `[]` (unpopulated); VCI has no implementation. Use CafeF instead.

### CafeF APIs — financial disclosure data
- **Price history:** `s.cafef.vn/Ajax/PageNew/DataHistory/PriceHistory.ashx`
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
| Historical foreign investor flow (per-ticker, daily) | vnstock only has current-day. F59. |
| Intraday OHLCV / tick data | vnstock doesn't provide historical intraday |
| SSC filing text (structured JSON) | SSC portal is HTML-only |

## Timing Research Acquisition Status

Current branch state:
- event surface v1 exists and is published at `data/features/event_surface_daily.parquet`
- it failed the predictive gate for continuation / exit timing
- local intraday data is only `FPT` 1H and is not a usable research surface
- local order-book / queue history is absent

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
- **Prices adjusted** for splits/dividends by VCI
- **Insider signal date:** use `published_date` (SSC disclosure date) — `real_end_date` is after-the-fact
- **Ticker identification in news:** parenthetical pattern `(TICKER)` in article titles
