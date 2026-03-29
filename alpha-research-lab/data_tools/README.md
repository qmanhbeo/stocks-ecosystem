# data_tools — Scripts, Sources, and Data Inventory

This is the canonical reference for every data tool, what it fetches, and the current
state of each data source. Read this before running experiments or wondering why a file is missing.

---

## Quick Status Table

| Data | In git? | In repo now? | Restore command |
|------|---------|-------------|----------------|
| HOSE stock OHLCV (394 tickers) | YES | YES | `fetch_stock.py` / `fetch_hose_universe.py` |
| VNINDEX + VN30 daily | YES | YES | included in stock fetch |
| FX + global indices + commodities (20 files) | YES | YES | `fetch_fx_commodities.py` + `fetch_global_macro.py` |
| Sector classification (ICB) | YES | YES | `fetch_sector_classification.py` |
| Dividend event calendar | YES | YES (52 tickers) | `fetch_dividend_events.py` |
| Fundamentals cache | YES | YES (52 tickers) | `fetch_fundamentals.py` / `fetch_all_stock_fundamentals.py` |
| Insider deals raw | YES | YES (394 tickers) | `fetch_insider_deals.py` |
| News archive (cafef, 3.6 GB) | NO | YES (fetched this session) | `fetch_news_archive.py` |
| Historical foreign investor flow | ✗ Not available | — | F59 in findings.md — vnstock only has current-day |
| Intraday tick data | ✗ Not available | — | vnstock doesn't provide historical intraday |

## Critical Refresh Warning

The stock refresh scripts rewrite local parquet files with the requested date window.

- `fetch_stock.py --overwrite` removes the existing file first, then writes only the requested range
- `fetch_refresh_all.py --start <recent-date>` rewrites every existing stock parquet to only that recent window
- many downstream features and live scorers need long lookback history, not just a fresh latest date

Operational rule:
- do **not** use a recent `--start` window on stock refresh scripts if the next step depends on historical feature generation
- if history has been truncated, restore it with a full-range refresh before trying to score live data again
- check `data/stock/gia_lich_su_VNINDEX_1D.parquet` explicitly after any refresh; a truncated benchmark file alone is enough to break live `S1`
- Session 52 fallback note: a local full-history benchmark backup currently exists at `../media-output/signal-xs-momentum/data/stock/gia_lich_su_VNINDEX_1D.parquet`, but that is emergency recovery only, not the canonical data source

Separate live-system warning:
- restoring stock history alone does **not** make the `full_library` branch current
- the shared `full_library` / activation branch also depends on:
  - `data/features/xs_rl_signal_matrix.parquet`
  - `data/features/activation_state_daily.parquet`
  - `data/features/activation_meta_daily.parquet`
- Session 62 resolved the old stale-matrix blocker by rebuilding the live branch through `2026-03-27`
- live refresh chain is now:
  - `build_s1_live_extension.py`
  - `build_rl_signal_matrix.py`
  - `build_activation_state_features.py`
  - `build_activation_meta_features.py`
- if stock data extends beyond the matrix again, rerun that full chain before calling anything “live”

---

## Fetch Scripts

### `fetch_stock.py`
Fetch daily OHLCV for one or more HOSE tickers from VCI via vnstock.
- **Output:** `data/stock/gia_lich_su_<TICKER>_1D.parquet`
- **Usage:** `python data_tools/fetch_stock.py --ticker FPT`
- **Warning:** with `--overwrite`, the old file is deleted first and the replacement file contains only the requested `--start/--end` window

### `fetch_hose_universe.py`
Fetch all HOSE-listed stocks not yet in `data/stock/`. Used to expand the universe.
- **Output:** `data/stock/gia_lich_su_<TICKER>_1D.parquet` for each new ticker
- **Coverage:** 394 HOSE tickers (402 files including indices/ETFs)

### `fetch_refresh_all.py`
Re-fetch all existing tickers to bring data up to the current date.
- **Usage:** `python data_tools/fetch_refresh_all.py`
- Run this at the start of a new session to update `data/stock/`.
- **Warning:** this rewrites each parquet with the exact requested `--start/--end` window; using a recent `--start` is unsafe for long-lookback feature pipelines
- **Safe restore pattern:** `python data_tools/fetch_refresh_all.py --start 2000-01-01 --end 2026-12-31`

### `fetch_fx_commodities.py`
Fetch FX rates, commodity prices, and global indices via yfinance.
- **Output:** `data/fx-commodities/fx_commodities_<NAME>_1D.parquet`
- **Available files (20):**
  - `vix_1D` — CBOE VIX (fear index)
  - `sp500_1D` — S&P 500
  - `gold_1D`, `oil_1D`, `hg_f_1D` — Gold, Crude Oil, Copper
  - `hsi_1D`, `shanghai_1D`, `kospi_1D`, `taiex_1D`, `nikkei_1D` — Asian indices
  - `eem_1D`, `ewh_1D`, `vnm_etf_1D` — EM ETFs
  - `hyg_1D`, `tlt_1D` — Credit/bond risk proxies
  - `fx_vnd_usd_1D`, `cny_x_1D` — USD/VND and CNY
  - `us10y_1D`, `us3m_1D` — US yield curve
  - `btc_1D` — Bitcoin

### `fetch_global_macro.py`
Fetch additional global macro indicators via yfinance (supplement to `fetch_fx_commodities.py`).

### `fetch_fred_macro.py`
Fetch Vietnam macroeconomic data from FRED (330+ series). Used for macro regime features.

### `fetch_sector_classification.py`
Fetch ICB sector/sub-sector labels for all HOSE stocks via `vnstock company.overview()`.
- **Output:** `data/features/sector_classification.parquet`
- **Fields:** `ticker`, `icb_name2`, `icb_name3`, `icb_name4` (industry hierarchy)
- **Coverage:** 398 tickers

### `fetch_dividend_events.py`
Fetch ex-dividend dates for all HOSE stocks via `vnstock company.events()`.
- **Output:** `data/dividend_cache/<TICKER>_events.parquet` + `data/features/xs_dividend_calendar.parquet`
- **Coverage:** 52 tickers (original universe; not yet expanded to full 394)
- **Status:** Partially built — only covers 52 tickers, not full HOSE universe

### `fetch_fundamentals.py`
Fetch quarterly EPS, P/E, ROE, margins etc. for FPT only.
- **Output:** `data/features/fpt_fundamentals.parquet`
- **Status:** FPT-only legacy script

### `fetch_all_stock_fundamentals.py`
Fetch quarterly financial ratios for all 52 stocks in original universe.
- **Output:** `data/fundamentals_cache/<TICKER>.parquet` + `data/features/xs_fundamentals_daily.parquet`
- **Coverage:** 52 tickers (not expanded to 394)
- **Status:** Partially built — not run on full HOSE universe

### `fetch_insider_deals.py`
Fetch insider + large-shareholder transaction disclosures for all HOSE tickers.
- **Source:** CafeF GDCoDong API — `cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx`
- **Output:** `data/insider_cache/<TICKER>.parquet` + `data/features/xs_insider_deals_raw.parquet`
- **Coverage:** 394/394 HOSE tickers, date range 2010–2026
- **Rate:** 0.2s/ticker, ~80 seconds for full run
- **No auth required.** Free public API.
- **Usage:** `python data_tools/fetch_insider_deals.py` (use `--force` to re-fetch)

### `fetch_news.py`
Crawl raw news articles from cafef.vn into `data/news/cafef/raw/`.
- **Output:** `data/news/cafef/raw/YYYY-MM-DD.jsonl` (one JSON object per article)
- **Status:** Crawler for live use; the full 2016–2026 archive is in Google Drive

### `fetch_news_archive.py`
Restore the full 2016–2026 cafef news archive from Google Drive.
- **Output:** `data/news/cafef/raw/` — 3,734 JSONL files (~3.6 GB extracted)
- **GDrive ID:** `1uzE57O1TTb7pMsQuTNtSiTKDgDt723-l`
- **Usage:** `python data_tools/fetch_news_archive.py`
- Run this on a fresh clone before any news-related experiments.

### `probe_listing.py`
Probe vnstock Listing API to audit the full Vietnamese stock universe.
- Diagnostic tool; no persistent output.

---

## Build Scripts

### `extract_news_sentiment.py`
Extract per-ticker daily sentiment from cafef JSONL files using a keyword lexicon.
- **Requires:** `data/news/` (run `fetch_news_archive.py` first)
- **Output:** `data/features/xs_news_sentiment_daily.parquet`
- **Coverage:** ~0.8% of (day, ticker) pairs (very sparse — see F62–F65)

### `build_rolling_news_sentiment.py`
Build rolling 5d/30d news sentiment to reduce sparsity (H96).
- **Requires:** `data/news/`
- **Output:** `data/features/xs_news_sentiment_rolling.parquet` (2.5M rows, full grid)
- **Result:** Still 94.9% zeros after 30d window — did not help (F63)

### `build_rolling_news_features.py`
Alternative rolling news feature builder (earlier H96 variant, superseded by above).

### `extract_llm_news_features.py`
Extract structured per-article features from CafeF JSONL with local Ollama (`/api/generate`).
- **Input:** `data/news/cafef/raw/YYYY-MM-DD.jsonl`
- **Output:** `data/llm_cache/YYYY-MM-DD.jsonl` (resume-safe, atomic write)
- **Usage:** `python data_tools/extract_llm_news_features.py --date-from 2023-01-01 --date-to 2023-01-03`
- **Speed knobs:** `--workers`, `--batch-size`, `--num-predict`, `--max-summary-chars`
- **Progress logs:** timestamped day/batch progress, rates, ETA, error counts

### `build_llm_news_features.py`
Build ticker-day and dense market-daily LLM features from `data/llm_cache/`.
- **Outputs:**
  - `data/features/xs_llm_news_ticker_day.parquet`
  - `data/features/xs_llm_news_market_daily.parquet`
- **Usage:** `python data_tools/build_llm_news_features.py`

### `build_open_close_asymmetry_features.py`
Build dense ticker-day open/close asymmetry features from OHLC.
- **Output:** `data/features/xs_open_close_asymmetry.parquet` (full grid)
- **Usage:** `python data_tools/build_open_close_asymmetry_features.py`
- **Session 62 note:** now builds from a dense stock-day grid derived from raw stock files, not from the stale historical `S1` spine

### `build_dispersion_regime_features.py`
Build dense date-level cross-sectional dispersion/breadth regime features.
- **Output:** `data/features/xs_dispersion_regime_daily.parquet`
- **Usage:** `python data_tools/build_dispersion_regime_features.py`
- **Session 62 note:** now builds from a dense stock-day grid derived from raw stock files, not from the stale historical `S1` spine

### `build_return_skewness_features.py`
Build dense ticker-day return skewness/tail-shape features.
- **Output:** `data/features/xs_return_skewness.parquet`
- **Usage:** `python data_tools/build_return_skewness_features.py`

### `build_earnings_calendar_features.py`
Build dense date-level earnings/reporting season calendar features.
- **Output:** `data/features/xs_earnings_calendar_daily.parquet`
- **Usage:** `python data_tools/build_earnings_calendar_features.py`

### `build_insider_features.py`
Build rolling 5d/30d insider signal feature matrix from raw insider deals.
- **Requires:** `data/features/xs_insider_deals_raw.parquet`
- **Output:** `data/features/xs_insider_features.parquet` (826k rows, full grid)
- **Usage:** `python data_tools/build_insider_features.py`

### `build_insider_quality_features.py`
Build dense ticker-day insider quality / relative-size features from the raw insider-deals matrix.
- **Requires:** `data/features/xs_insider_deals_raw.parquet`
- **Output:** `data/features/xs_insider_quality_features.parquet`
- **Usage:** `python data_tools/build_insider_quality_features.py`
- **Session 62 note:** now builds from a dense stock-day grid derived from raw stock files, not from the stale historical `S1` spine

### `build_macro_regime_features.py`
Build composite macro regime features from FX/commodity/news data.
- **Output:** `data/features/macro_regime_daily.parquet`

### `build_activation_state_features.py`
Build the compact date-level activation surface used to test selector timing overlays.
- **Requires:** `xs_rl_signal_matrix.parquet`, `tradability_daily.parquet`, `xs_dispersion_regime_daily.parquet`, `macro_regime_daily.parquet`
- **Output:** `data/features/activation_state_daily.parquet`
- **Usage:** `python data_tools/build_activation_state_features.py`

### `build_activation_meta_features.py`
Build the selector-efficacy activation-meta surface used for learnable/path-dependent activation experiments.
- **Requires:** `activation_state_daily.parquet` plus the frozen always-on selector simulations
- **Output:** `data/features/activation_meta_daily.parquet`
- **Usage:** `python data_tools/build_activation_meta_features.py`

### `build_s1_live_extension.py`
Build the current-year live extension for the canonical `S1` signal without dropping the latest unlabeled rows.
- **Requires:** current raw stock history plus the historical `S1` feature pipeline inputs
- **Output:** `data/features/xs_barrier_vol_1d_hose_live_current.parquet`
- **Usage:** `python data_tools/build_s1_live_extension.py`
- **Operational role:** first step in the current-date `full_library` / activation refresh chain

---

## Feature Files Reference

### Active (used in current experiments)

| File | Signal | Description | Rows |
|------|--------|-------------|------|
| `xs_barrier_vol_1d_hose_full.parquet` | **S1 / H93** | Primary RL signal — XS momentum probas | 826k |
| `xs_insider_deals_raw.parquet` | **C2 raw** | Raw insider transaction disclosures | 32k |
| `xs_insider_features.parquet` | **C2 features** | Rolling 5d/30d insider signal matrix | 826k |
| `xs_llm_news_ticker_day.parquet` | H98 ticker-day | LLM ticker-day event/sentiment features | 826k |
| `xs_llm_news_market_daily.parquet` | H98 market-daily | Dense date-level LLM market narrative features | ~2.7k |
| `xs_open_close_asymmetry.parquet` | H100 | Dense ticker-day open/close asymmetry features | 826k |
| `xs_dispersion_regime_daily.parquet` | H101 | Dense date-level dispersion regime features | ~2.7k |
| `activation_state_daily.parquet` | H157-H162 | Dense date-level selection/activation state surface | ~2.7k |
| `activation_meta_daily.parquet` | H163-H174 | Dense date-level selector-efficacy / activation-meta surface | ~2.7k |
| `xs_return_skewness.parquet` | H103 | Dense ticker-day return skewness/tail-shape features | 826k |
| `xs_earnings_calendar_daily.parquet` | H104 | Dense date-level earnings/reporting calendar features | ~2.7k |
| `xs_news_sentiment_daily.parquet` | **C1 raw** | Daily keyword sentiment (sparse) | ~29k |
| `xs_news_sentiment_rolling.parquet` | C1 rolling | 5d/30d rolling news features | 2.5M |
| `sector_classification.parquet` | — | ICB sector labels for 398 tickers | 398 |
| `xs_dividend_calendar.parquet` | — | Ex-dividend dates and windows | 826k |
| `macro_regime_daily.parquet` | — | Macro regime features (VIX, yields, etc.) | ~2.7k |

### H93 Variant Probas (historical experiments, not active)

| File | Experiment | IC vs H93 | Status |
|------|-----------|-----------|--------|
| `xs_barrier_all_probas_hose_full.parquet` | H54 (old champion) | +0.1515 | PARKED (deployment gap) |
| `xs_barrier_vol_1d_insider_hose_full.parquet` | H97 (+insider) | −0.0007, Sharpe −4.31 | FAIL |
| `xs_barrier_vol_1d_news_rolling_hose_full.parquet` | H96 (+rolling news) | −0.0008 | FAIL |
| `xs_barrier_vol_1d_news_h99_hose_full.parquet` | H99 (+body news) | −0.0128 | FAIL |
| `xs_barrier_vol_1d_news_hose_full.parquet` | H89 (+daily news) | −0.0044 | FAIL |
| `xs_barrier_vol_hose_full.parquet` | H90 (volume only) | baseline | superseded by H93 |
| `xs_barrier_fundamentals_hose_full.parquet` | fundamentals | — | FAIL |
| `xs_blend_h87_alpha0.7.parquet` | H87 ensemble | IC +0.150 | superseded by H93 |

---

## What Is Genuinely Not Available

| Data | Reason | Finding |
|------|--------|---------|
| **Historical foreign investor flow** | vnstock only has current-day; no historical per-ticker breakdown | F59 |
| **Intraday tick/order flow data** | vnstock doesn't provide historical intraday OHLCV | — |
| **Insider data via KBS/VCI vnstock** | KBS endpoint returns empty `[]`; VCI has no implementation | Session 31 |
| **SSC filing text (structured)** | Vietnamese SSC portal is HTML-only; no JSON API found | Session 31 |

---

## Data Not Yet Fetched (available but incomplete)

| Data | Current coverage | Full coverage possible? | Script |
|------|-----------------|------------------------|--------|
| Dividend events | 52 tickers | Yes — 394 tickers | `fetch_dividend_events.py` (rerun on full universe) |
| Fundamentals (quarterly ratios) | 52 tickers | Yes — 394 tickers | `fetch_all_stock_fundamentals.py` (rerun on full universe) |
| News (live update) | 2016–2026 archive restored | Yes — run daily crawler | `fetch_news.py` |

---

## Notes on Data Quality

- **HOSE only** — HNX/UPCOM stocks not included
- **Prices adjusted** for splits/dividends by VCI
- **Insider data:** `published_date` (SSC disclosure date) is the safe signal date; `real_end_date` is after-the-fact
- **News JSONL:** raw titles + bodies; sentiment requires `extract_news_sentiment.py`
- **CafeF GDCoDong API:** returns both insiders (`CEO_` / `LQ_` prefix) and large shareholders (`CORP_`); filter on `is_insider` column for pure insider signal
