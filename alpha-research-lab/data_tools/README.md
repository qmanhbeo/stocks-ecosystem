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
| Intraday tick data | Partial | YES (`FPT` 1H legacy + open CafeF fetch path) | `fetch_cafef_intraday_all.py` + `adjust_cafef_intraday_to_vci.py`; authenticated fallback is `fetch_ssi_intraday.py` |

## Critical Refresh Warning

The stock refresh scripts now append incrementally by default, but a forced full refresh
still rewrites local parquet files with the requested date window.

- `fetch_stock.py` now reads the existing parquet, fetches only the missing tail, merges on `time`, and atomically replaces the old file
- `fetch_refresh_all.py` now does the same for the full current universe
- `fetch_stock.py --overwrite` or `fetch_refresh_all.py --full-refresh` still rewrites the target parquet(s) to only the requested `--start/--end` window
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

Status guide:
- `Active` = preferred path for new work
- `Legacy` = narrow/original-universe/debug path kept for compatibility
- `Archive-only` = kept for reproducibility after a failed research branch
- `Utility` = diagnostic helper, not a canonical producer

### Active Fetchers

### `fetch_stock.py`
Fetch daily OHLCV for one or more HOSE tickers from VCI via vnstock.
- **Status:** Active
- **Output:** `data/stock/gia_lich_su_<TICKER>_1D.parquet`
- **Usage:** `python data_tools/fetch_stock.py --tickers FPT`
- **Default behavior:** if the target parquet already exists, fetch only the missing tail, merge on `time`, and atomically replace the old file
- **Probe cache:** no-change and partial-advance VCI probes are now persisted under `data/stock/_refresh_metadata/`, so reruns can skip recently rechecked stale tails instead of burning requests again
- **Probe cache control:** `--probe-cache-ttl-hours` defaults to `24`; set it to `0` to disable probe-cache reads and writes
- **Full rewrite:** use `--overwrite` to rewrite from the requested `--start/--end` window
- **Reliability:** failed tickers now get `2` automatic retry rounds after the initial pass by default

### `fetch_hose_universe.py`
Fetch all HOSE-listed stocks not yet in `data/stock/`. Used to expand the universe.
- **Status:** Active
- **Output:** `data/stock/gia_lich_su_<TICKER>_1D.parquet` for each new ticker
- **Coverage:** 394 HOSE tickers (402 files including indices/ETFs)
- **Reliability:** failed tickers now get `2` automatic retry rounds after the initial pass by default

### `fetch_refresh_all.py`
Re-fetch the current stock universe to bring data up to the current date.
- **Status:** Active
- **Usage:** `python data_tools/fetch_refresh_all.py`
- **Usage:** `python data_tools/fetch_refresh_all.py --workers 2 --delay 0.5`
- **Usage:** `python data_tools/fetch_refresh_all.py --check-workers 12`
- **Usage:** `python data_tools/fetch_refresh_all.py --probe-cache-ttl-hours 24`
- **Usage:** `python data_tools/fetch_refresh_all.py --interval 1H --start 2023-09-01`
- Run this at the start of a new session to update `data/stock/`.
- Ticker discovery comes from the existing `*_1D.parquet` universe files, even when writing another interval such as `1H`.
- **Output:** `data/stock/gia_lich_su_<TICKER>_<INTERVAL>.parquet`
- **Default behavior:** if a parquet already exists, fetch only the missing tail, merge on `time`, and atomically replace the old file
- **Precheck stage:** a separate local parquet-tail scan now runs before any API calls; it uses `--check-workers` so the script can quickly classify which tickers are already current
- **Probe cache:** no-change and partial-advance probes are now persisted under `data/stock/_refresh_metadata/`; if the same parquet tail is rechecked against the same or earlier `--end` within the cache TTL, the script skips the API call locally instead of spending rate-limit budget again
- **Probe cache control:** `--probe-cache-ttl-hours` defaults to `24`; set it to `0` to disable the cache and force every stale tail to be re-probed
- **Parallelism:** defaults are now tuned to the observed VCI rate limit at about `2` workers plus `0.5s` submission delay, roughly `20` requests/minute; use `--workers 1` for serial behavior or override both flags explicitly if the upstream limit changes
- **Intraday overlap rule:** non-`1D` intervals refetch the last stored trading date as an overlap window, then dedupe on `time`
- **Full rewrite:** use `--full-refresh` to rewrite each parquet with the exact requested `--start/--end` window
- **Reliability:** failed tickers now get `2` automatic retry rounds after the initial pass by default
- **Safe restore pattern:** `python data_tools/fetch_refresh_all.py --start 2000-01-01 --end 2026-12-31`

### `fetch_ssi_intraday.py`
Fetch historical intraday OHLCV from SSI FastConnect via the official `IntradayOhlc` API.
- **Status:** Active fallback
- **Output:** `data/stock/gia_lich_su_<TICKER>_<INTERVAL>.parquet`
- **Default output label:** `1H` when `--resolution 60`
- **Usage:** `python data_tools/fetch_ssi_intraday.py --resolution 60 --start 2019-01-01 --end 2025-12-31`
- **Usage:** `python data_tools/fetch_ssi_intraday.py --tickers FPT,ACB --resolution 60 --start 2019-01-01 --end 2025-12-31`
- **Credentials:** set `SSI_FC_CONSUMER_ID` and `SSI_FC_CONSUMER_SECRET`, or pass `--consumer-id` and `--consumer-secret`
- **Notes:**
  - uses the existing `*_1D.parquet` universe when `--tickers` is omitted
  - chunks long date ranges automatically to stay inside SSI page limits
  - reruns now refetch from the last stored trading date and append new bars atomically instead of freezing after the first successful write
  - no-change and partial-advance SSI probes now persist under `data/stock/_refresh_metadata/`, so reruns can skip recently rechecked stale tails instead of replaying the same chunk windows
  - `--probe-cache-ttl-hours` defaults to `24`; set it to `0` to disable the probe cache entirely
  - `--overwrite` still forces a full rebuild, but the old parquet is kept until the replacement file is written successfully
  - intended for the acquisition-first intraday branch; coverage still needs to be validated honestly after fetch

### `fetch_cafef_intraday.py`
Fetch open historical matched-trade data from CafeF and aggregate it into repo-style hourly OHLCV bars.
- **Status:** Active
- **Source:** `https://msh-appdata.cafef.vn/rest-api/api/v1/MatchPrice`
- **Output:** `data/stock/gia_lich_su_<TICKER>_1H_CAFEF.parquet` by default
- **Usage:** `python data_tools/fetch_cafef_intraday.py --tickers FPT,ACB --start 2019-01-01 --end 2025-12-31`
- **Usage:** `python data_tools/fetch_cafef_intraday.py --tickers FPT,ACB --start 2000-01-01 --end 2026-12-31 --workers 8`
- **Usage:** `python data_tools/fetch_cafef_intraday.py --start 2000-01-01 --end 2026-12-31 --workers 16` (implicit whole universe)
- **Usage:** `python data_tools/fetch_cafef_intraday.py --dry-run`
- **Notes:**
  - no auth required
  - uses the existing `*_1D.parquet` files as the trading calendar, so it only requests dates that already exist in the daily stock data
  - fetches dates in parallel within each ticker-year; tune with `--workers`
  - writes complete yearly raw parts first under `data/stock/_cafef_intraday_parts/<INTERVAL_LABEL>/<TICKER>/`, then rebuilds the final ticker parquet by concatenating those yearly parts
  - each yearly part now carries a sidecar metadata file with the requested trading-date signature, so reruns can skip unchanged historical years but still refresh the latest requested year when the daily calendar expands
  - unresolved request failures are retried automatically `2` times after the initial pass, at the date level, before a year is allowed to become a saved part
  - normalizes CafeF's legacy early-history timestamp offset before aggregation, including older rows where the source encoded the shifted session time as a naive timestamp
  - keeps a source-specific output suffix by default so it does not overwrite vnstock / SSI intraday files
  - prices are source-raw CafeF session prices; do not assume they numerically match the locally adjusted daily/vnstock price levels without an explicit normalization step
  - old yearly parts created before the metadata upgrade are still reused as historical cache; run once with `--overwrite` if you want to seed metadata for every existing year immediately

### `fetch_cafef_intraday_all.py`
Fetch CafeF intraday bars for the full current universe in one explicit command.
- **Status:** Active convenience wrapper
- **Universe source:** existing `data/stock/gia_lich_su_*_1D.parquet` files, excluding `VNINDEX` and `VN30`
- **Default range:** `2000-01-01` through `2099-12-31` when no `--start/--end` is passed
- **Usage:** `python data_tools/fetch_cafef_intraday_all.py --start 2000-01-01 --end 2026-12-31 --workers 16`
- **Usage:** `python data_tools/fetch_cafef_intraday_all.py`
- **Usage:** `python data_tools/fetch_cafef_intraday_all.py --dry-run`
- **Notes:**
  - thin wrapper around `fetch_cafef_intraday.py`
  - does not accept `--tickers`; it always uses the full current universe

### `adjust_cafef_intraday_to_vci.py`
Normalize raw CafeF intraday prices onto the local VCI-adjusted daily price backbone.
- **Status:** Active
- **Raw input:** `data/stock/gia_lich_su_<TICKER>_1H_CAFEF.parquet`
- **Daily anchor:** `data/stock/gia_lich_su_<TICKER>_1D.parquet`
- **Adjusted output:** `data/stock/gia_lich_su_<TICKER>_1H_CAFEF_ADJ.parquet`
- **Audit output:** `data/stock/_cafef_adjustment_factors/gia_lich_su_<TICKER>_1H_CAFEF_to_1H_CAFEF_ADJ.parquet`
- **Usage:** `python data_tools/adjust_cafef_intraday_to_vci.py --tickers FPT,ACB`
- **Formula:**
  - `price_factor[t] = vci_daily_close[t] / cafef_raw_intraday_last_close[t]`
  - adjusted intraday `open/high/low/close = raw_cafef_ohlc * price_factor[t]`
  - `volume` is left unchanged
- **Why this works:**
  - the factor is constant within a day, so all same-day returns and bar-shape features are preserved
  - the adjusted last intraday close is forced onto the local VCI daily close, which restores cross-day continuity against the repo's daily backbone
- **Why volume is not scaled:**
  - the local VCI daily files appear price-adjusted but not volume-adjusted
  - scaling volume by the price factor would be a different economic assumption and is not supported by the observed local files
- **Audit fields:** the factor parquet stores raw CafeF daily OHLCV, adjusted-from-CafeF daily OHLC, VCI daily OHLCV, `price_factor`, daily OHLC gaps, and raw-vs-VCI volume ratio
- **Refresh behavior:** reruns now skip only when the current raw CafeF and VCI-overlap state matches the last adjustment metadata; if raw intraday bars or daily anchors changed, the adjusted output is rebuilt automatically
- **Migration note:** adjusted outputs written before the metadata upgrade will refresh once on the next run so the new freshness metadata can be seeded

### CafeF Intraday Normalization Chain
Use the open intraday path in two explicit steps:
1. `python data_tools/fetch_cafef_intraday_all.py`
2. `python data_tools/adjust_cafef_intraday_to_vci.py`

Operational interpretation:
- `*_1H_CAFEF.parquet` is the raw open-source tape
- `*_1H_CAFEF_ADJ.parquet` is the repo-aligned intraday price surface for cross-day research
- if you only need same-day structure features, the raw file is often enough
- if you need gap / overnight joins or any merge onto adjusted daily prices, use the adjusted file
- the whole-universe wrapper defaults to `2000-01-01` through `2099-12-31` and reuses unchanged yearly parts, so bare `python data_tools/fetch_cafef_intraday_all.py` is the safe full-history command

## Tried But Failed Intraday Attempts

- `fetch_refresh_all.py --interval 1H` via `vnstock` / VCI works only as a shallow intraday source; current observed history starts around `2023-09-11`, so it does not solve deep historical intraday acquisition.
- `fetch_ssi_intraday.py` uses an official historical endpoint and may still be useful later, but it failed the “completely open” requirement because SSI FastConnect requires credentials and service registration.

### `fetch_fx_commodities.py`
Fetch FX rates, commodity prices, and global indices via yfinance.
- **Status:** Active
- **Output:** `data/fx-commodities/fx_commodities_<NAME>_1D.parquet`
- **Default behavior:** running without `--tickers` now fetches the canonical shared macro basket directly
- **Refresh behavior:** reruns append missing dates and rewrite atomically; `--overwrite` forces a full rebuild without deleting the last good file first
- **Probe cache:** no-change and partial-advance yfinance probes now persist under `data/fx-commodities/_refresh_metadata/`
- **Probe cache control:** `--probe-cache-ttl-hours` defaults to `24`; set it to `0` to disable the probe cache entirely
- **Available files (21):**
  - `vix_1D` — CBOE VIX (fear index)
  - `sp500_1D` — S&P 500
  - `gold_1D`, `oil_1D`, `hg_f_1D` — Gold, Crude Oil, Copper
  - `hsi_1D`, `shanghai_1D`, `kospi_1D`, `taiex_1D`, `nikkei_1D` — Asian indices
  - `eem_1D`, `ewh_1D`, `vnm_etf_1D` — EM ETFs
  - `hyg_1D`, `tlt_1D` — Credit/bond risk proxies
  - `fx_vnd_usd_1D`, `cny_x_1D` — USD/VND and CNY
  - `us10y_1D`, `us3m_1D` — US yield curve
  - `btc_1D` — Bitcoin
  - `dxy_1D` — US Dollar Index

### `fetch_fred_macro.py`
Fetch Vietnam macroeconomic data from FRED (330+ series). Used for macro regime features.
- **Status:** Active
- **Output:** `data/macro/fred_vietnam_macro.parquet`
- **Refresh behavior:** reruns now reuse the existing daily parquet, fetch only a buffered tail window by default, forward-fill only through the requested `--end`, and atomically replace the merged output
- **Full rewrite:** use `--overwrite` to rebuild from the requested `--start/--end` window
- **Credentials:** set `FRED_API_KEY` or pass `--api-key`

### `fetch_sector_classification.py`
Fetch ICB sector/sub-sector labels for all HOSE stocks via `vnstock company.overview()`.
- **Status:** Active
- **Output:** `data/features/sector_classification.parquet`
- **Fields:** `symbol`, `icb_name2`, `icb_name3`, `icb_name4` (industry hierarchy)
- **Coverage:** 398 tickers
- **Refresh behavior:** reruns now reuse existing rows and fetch only missing symbols or rows with blank sector fields; `--dry-run` no longer writes a sample file
- **Negative cache:** blank or incomplete sector rows now persist a probe-cache record under `data/features/_refresh_metadata/`, so unchanged failures are not retried every run
- **Probe cache control:** `--probe-cache-ttl-hours` defaults to `168` hours; set it to `0` to disable the negative cache
- **Full refetch:** use `--refresh-existing` to refetch all covered symbols

### `fetch_insider_deals.py`
Fetch insider + large-shareholder transaction disclosures for all HOSE tickers.
- **Status:** Active
- **Source:** CafeF GDCoDong API — `cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx`
- **Output:** `data/insider_cache/<TICKER>.parquet` + `data/features/xs_insider_deals_raw.parquet`
- **Coverage:** 394/394 HOSE tickers, date range 2010–2026
- **Rate:** 0.2s/ticker, ~80 seconds for full run
- **No auth required.** Free public API.
- **Refresh behavior:** reruns now reuse tickers already current through the requested `--end-date`; stale caches refresh only a bounded lookback window and merge/dedupe atomically before the combined raw matrix is republished
- **Probe cache:** no-change and partial-advance per-ticker probes now persist under `data/insider_cache/_refresh_metadata/`, so reruns can skip recently rechecked stale ticker tails
- **Probe cache control:** `--probe-cache-ttl-hours` defaults to `24`; set it to `0` to disable the probe cache entirely
- **Usage:** `python data_tools/fetch_insider_deals.py`
- **Full rewrite:** use `--force` to refetch the full requested window for every ticker

### `fetch_news.py`
Crawl raw news articles from cafef.vn into `data/news/cafef/raw/`.
- **Status:** Active
- **Output:** `data/news/cafef/raw/YYYY-MM-DD.jsonl` (one JSON object per article)
- **Role:** live/incremental crawler; use alongside the archive restore on fresh clones

### `fetch_news_archive.py`
Restore the full 2016–2026 cafef news archive from Google Drive.
- **Status:** Active
- **Output:** `data/news/cafef/raw/` — 3,734 JSONL files (~3.6 GB extracted)
- **GDrive ID:** `1uzE57O1TTb7pMsQuTNtSiTKDgDt723-l`
- **Usage:** `python data_tools/fetch_news_archive.py`
- Run this on a fresh clone before any news-related experiments.

### Legacy / Narrow Fetchers

### `fetch_global_macro.py`
Fetch additional global macro indicators via yfinance.
- **Status:** Legacy convenience wrapper
- **Reason:** fully replaceable by the generic `fetch_fx_commodities.py` ticker/alias interface; kept as a fixed-list shortcut for the original macro basket
- **Refresh behavior:** reruns now append missing dates instead of permanently skipping any existing output
- **Probe cache:** no-change and partial-advance yfinance probes now persist under `data/fx-commodities/_refresh_metadata/`
- **Probe cache control:** `--probe-cache-ttl-hours` defaults to `24`; set it to `0` to disable the probe cache entirely

### `fetch_dividend_events.py`
Fetch ex-dividend dates for all HOSE stocks via `vnstock company.events()`.
- **Status:** Legacy original-universe fetcher
- **Output:** `data/dividend_cache/<TICKER>_events.parquet` + `data/features/xs_dividend_calendar.parquet`
- **Coverage:** 52 tickers (original universe; not yet expanded to full 394)
- **Current limitation:** only covers 52 tickers, not the full HOSE universe
- **Refresh behavior:** reruns now reuse per-ticker caches already covering the requested `--end`; stale or missing ticker caches are refreshed and merged atomically, and the published calendar rebuilds only a rolling tail unless `--force` is used
- **Probe cache:** no-change and partial-advance per-ticker probes now persist under `data/dividend_cache/_refresh_metadata/`, so reruns can skip recently rechecked stale ticker tails
- **Probe cache control:** `--probe-cache-ttl-hours` defaults to `24`; set it to `0` to disable the probe cache entirely
- **Window control:** `--start` / `--end` now bound the calendar build instead of hard-coding the old 2026 cap

### `fetch_fundamentals.py`
Fetch quarterly EPS, P/E, ROE, margins etc. for FPT only.
- **Status:** Legacy single-name path
- **Output:** `data/features/fpt_fundamentals.parquet`
- **Current limitation:** FPT-only legacy script

### `fetch_all_stock_fundamentals.py`
Fetch quarterly financial ratios for all 52 stocks in original universe.
- **Status:** Legacy original-universe fetcher
- **Output:** `data/fundamentals_cache/<TICKER>.parquet` + `data/features/xs_fundamentals_daily.parquet`
- **Coverage:** 52 tickers (not expanded to 394)
- **Current limitation:** not yet run on the full HOSE universe
- **Refresh behavior:** reruns now refresh only ticker caches that appear stale for the current quarter, merge/dedupe them atomically, and extend the daily artifact tail when caches are unchanged
- **Rebuild rule:** if any ticker cache changes, the published daily cross-sectional fundamentals surface is rebuilt from cache to keep historical ranks coherent
- **Flags:** use `--skip-fetch` to trust the current caches, or `--force` to refresh every ticker cache

### Utility Fetchers

### `probe_listing.py`
Probe vnstock Listing API to audit the full Vietnamese stock universe.
- **Status:** Utility
- Diagnostic tool; no persistent output.

---

## Build Scripts

Status guide:
- `Active` = preferred current producer
- `Legacy` = limited-coverage, narrow, or superseded path kept for compatibility or historical rebuilds
- `Archive-only` = retained only to reproduce a rejected research branch

### Active Builders

### `extract_news_sentiment.py`
Extract per-ticker daily sentiment from cafef JSONL files using a keyword lexicon.
- **Status:** Active raw input builder
- **Requires:** `data/news/` (run `fetch_news_archive.py` first)
- **Output:** `data/features/xs_news_sentiment_daily.parquet`
- **Coverage:** ~0.8% of (day, ticker) pairs (very sparse; this is the raw base table, not a dense feature surface)

### `extract_llm_news_features.py`
Extract structured per-article features from CafeF JSONL using Google Gemini models only.
- **Status:** Active canonical extractor
- **Input:** `data/news/cafef/raw/YYYY-MM-DD.jsonl`
- **Output:** `data/llm_cache/YYYY-MM-DD.jsonl` (resume-safe, atomic write; one JSON object per filtered article)
- **Usage:** `python data_tools/extract_llm_news_features.py --date-from 2023-01-01 --date-to 2023-01-03`
- **Typical Google-only run:** `python data_tools/extract_llm_news_features.py --workers 8`
- **Typical single-model smoke test:** `python data_tools/extract_llm_news_features.py --model gemini-2.5-flash-lite --workers 1 --date-from 2016-01-01 --date-to 2016-01-03`
- **Provider notes:** the canonical script is pinned to the Google/Gemini model pool; model overrides accept comma-separated Google model names via `--model`
- **Credentials:** canonical runs read `GOOGLE_API_KEY`, `GOOGLE_API_KEY_2`, `GOOGLE_API_KEY_3`, or `GOOGLE_API_KEYS` from the shell or `.env`
- **Rotation:** Google keys are consumed in order and failed keys are cooled down before the next request retries on another key
- **Runtime stats:** observed Google-model latency / failure ranking persists to `alpha-research-lab/artifacts/llm_runtime/hosted_model_stats.json` and is reused on later runs
- **Speed knobs:** `--workers`, `--batch-size`, `--num-predict`, `--max-summary-chars`
- **Concurrency note:** `--workers` is same-day batch concurrency. Days are processed serially so cancellation stops before later days start.
- **Progress logs:** timestamped day/batch progress, rates, ETA, error counts
- **Reliability:** auto-retries failed or partial batches with smaller slices, falls through to alternate hosted models on single-item failures, and reprocesses existing error-only cache days automatically
- **Cache schema:** each cache row keeps the LLM semantic fields plus deterministic CafeF metadata. LLM fields are `id`, `tickers`, `related_tickers`, `sentiment`, `confidence`, `event_type`, `magnitude`, `is_forward_looking`, `market_tone`, `is_rumor`, `surprise_direction`, `impact_scope`, `named_persons`, `expectation_alignment`, `information_novelty`, `macro_theme`, `source_authority`, and `causal_impact_label`.
- **Deterministic enrichments:** the extractor also adds `published_at`, `source_domain`, `event_time_type`, `article_text_length`, `article_has_numbers`, and `article_mentions_percent` in Python, not via the LLM.
- **Schema rules:** invalid enum values are normalized to null/empty-compatible values in code, and historical cache files without the newer fields remain valid inputs to the builder.

### `extract_llm_news_features_legacy.py`
Legacy multi-provider extractor retained for historical rebuilds and debugging.
- **Status:** Legacy compatibility copy
- **Behavior:** keeps the older hosted-provider pool, `auto` routing, and local Ollama path
- **Use when:** you need to reproduce an older multi-provider run or inspect provider-pool behavior directly

### `test_model_pool.py`
Probe hosted model pools without writing cache outputs.
- **Status:** Utility
- **Usage:** `python data_tools/test_model_pool.py --provider auto --max-models 6`
- **Stats mode:** add `--record-stats` to update `alpha-research-lab/artifacts/llm_runtime/hosted_model_stats.json`

### `build_llm_news_features.py`
Build ticker-day and dense market-daily LLM features from `data/llm_cache/`.
- **Status:** Active
- **Outputs:**
  - `data/features/xs_llm_news_ticker_day.parquet`
  - `data/features/xs_llm_news_market_daily.parquet`
- **Usage:** `python data_tools/build_llm_news_features.py`
- **Compatibility:** historical cache files are safe; missing fields are filled with nulls or zeros where appropriate.
- **Ticker-day outputs:** the dense ticker-day surface includes the base sentiment fields plus these rolling 5d features:
  - `llm_expectation_beats_5d`
  - `llm_expectation_misses_5d`
  - `llm_new_info_5d`
  - `llm_followup_info_5d`
  - `llm_official_source_5d`
  - `llm_rumor_source_5d`
  - `llm_causal_rev_pos_5d`
  - `llm_causal_rev_neg_5d`
  - `llm_causal_financing_neg_5d`
  - `llm_theme_real_estate_5d`
  - `llm_theme_banking_5d`
  - `llm_theme_regulation_5d`
- **Market-daily outputs:** the dense market surface includes these daily fractions:
  - `frac_expectation_beats`
  - `frac_expectation_misses`
  - `frac_new_information`
  - `frac_official_source`
  - `frac_rumor_source`
  - `frac_regulation_theme`
  - `frac_real_estate_theme`
  - `frac_banking_theme`
  - `frac_causal_financing_negative`

### `build_open_close_asymmetry_features.py`
Build dense ticker-day open/close asymmetry features from OHLC.
- **Status:** Active
- **Output:** `data/features/xs_open_close_asymmetry.parquet`
- **Usage:** `python data_tools/build_open_close_asymmetry_features.py`
- **Session 62 note:** now builds from a dense stock-day grid derived from raw stock files, not from the stale historical `S1` spine

### `build_dispersion_regime_features.py`
Build dense date-level cross-sectional dispersion/breadth regime features.
- **Status:** Active
- **Output:** `data/features/xs_dispersion_regime_daily.parquet`
- **Usage:** `python data_tools/build_dispersion_regime_features.py`
- **Session 62 note:** now builds from a dense stock-day grid derived from raw stock files, not from the stale historical `S1` spine

### `build_return_skewness_features.py`
Build dense ticker-day return skewness/tail-shape features.
- **Status:** Active
- **Output:** `data/features/xs_return_skewness.parquet`
- **Usage:** `python data_tools/build_return_skewness_features.py`

### `build_earnings_calendar_features.py`
Build dense date-level earnings/reporting season calendar features.
- **Status:** Active
- **Output:** `data/features/xs_earnings_calendar_daily.parquet`
- **Usage:** `python data_tools/build_earnings_calendar_features.py`

### `build_insider_quality_features.py`
Build dense ticker-day insider quality / relative-size features from the raw insider-deals matrix.
- **Status:** Active
- **Requires:** `data/features/xs_insider_deals_raw.parquet`
- **Output:** `data/features/xs_insider_quality_features.parquet`
- **Usage:** `python data_tools/build_insider_quality_features.py`
- **Session 62 note:** now builds from a dense stock-day grid derived from raw stock files, not from the stale historical `S1` spine

### `build_sector_rotation_features.py`
Build sector breadth / sector momentum / intra-sector rank features from stock OHLC plus sector labels.
- **Status:** Active
- **Output:** `data/features/xs_sector_rotation_daily.parquet`
- **Usage:** `python data_tools/build_sector_rotation_features.py`
- **Research note:** H111's original `xs_sector_rotation_signal` failed, but this artifact is still actively used because it feeds the promoted contrarian intra-sector signal (`C6`) in `xs_rl_signal_matrix.parquet`

### `build_price_limit_features.py`
Build dense price-limit-touch features from daily OHLC.
- **Status:** Active
- **Output:** `data/features/xs_price_limit_daily.parquet`
- **Usage:** `python data_tools/build_price_limit_features.py`
- **Research note:** feeds promoted signal `C7`

### `build_volume_zscore_features.py`
Build dense abnormal-volume features relative to each stock's own trailing baseline.
- **Status:** Active
- **Output:** `data/features/xs_volume_zscore_daily.parquet`
- **Usage:** `python data_tools/build_volume_zscore_features.py`
- **Research note:** feeds promoted signal `C8`

### `build_shortterm_reversal_features.py`
Build dense short-term reversal features from daily OHLC.
- **Status:** Active
- **Output:** `data/features/xs_shortterm_reversal.parquet`
- **Usage:** `python data_tools/build_shortterm_reversal_features.py`
- **Research note:** feeds promoted signal `C9`

### `build_macro_regime_features.py`
Build composite macro regime features from FX/commodity/news data.
- **Status:** Active
- **Output:** `data/features/macro_regime_daily.parquet`

### `build_tradability_flags.py`
Build dense execution tradability flags from the daily stock history.
- **Status:** Active
- **Output:** `data/features/execution/tradability_daily.parquet`
- **Usage:** `python data_tools/build_tradability_flags.py`
- **Tests:** `tests/test_tradability_flags.py`

### `build_rl_signal_matrix.py`
Build the consolidated RL signal surface from `S1` plus the current maintained candidate-signal library.
- **Status:** Active
- **Output:** `data/features/xs_rl_signal_matrix.parquet`
- **Inputs:** `xs_barrier_vol_1d_hose_full.parquet`, `xs_barrier_vol_1d_hose_live_current.parquet`, `xs_open_close_asymmetry.parquet`, `xs_insider_quality_features.parquet`, `xs_sector_rotation_daily.parquet`, `xs_price_limit_daily.parquet`, `xs_volume_zscore_daily.parquet`, `xs_shortterm_reversal.parquet`
- **Usage:** `python data_tools/build_rl_signal_matrix.py`

### `build_activation_state_features.py`
Build the compact date-level activation surface used to test selector timing overlays.
- **Status:** Active
- **Requires:** `xs_rl_signal_matrix.parquet`, `data/features/execution/tradability_daily.parquet`, `xs_dispersion_regime_daily.parquet`, `macro_regime_daily.parquet`
- **Output:** `data/features/activation_state_daily.parquet`
- **Usage:** `python data_tools/build_activation_state_features.py`

### `build_activation_meta_features.py`
Build the selector-efficacy activation-meta surface used for learnable/path-dependent activation experiments.
- **Status:** Active
- **Requires:** `activation_state_daily.parquet` plus the frozen always-on selector simulations
- **Output:** `data/features/activation_meta_daily.parquet`
- **Usage:** `python data_tools/build_activation_meta_features.py`

### `build_event_surface_daily.py`
Build the canonical corporate-event surface for the new-data exit ladder.
- **Status:** Active
- **Requires:** `xs_rl_signal_matrix.parquet`, `data/dividend_cache/*.parquet`, `xs_earnings_calendar_daily.parquet`, `xs_insider_deals_raw.parquet`
- **Output:** `data/features/event_surface_daily.parquet`
- **Usage:** `python data_tools/build_event_surface_daily.py`
- **Session 73 note:** the artifact has strong local coverage, but the first event-driven continuation/exit branch still failed at the predictive gate

### `build_s1_live_extension.py`
Build the current-year live extension for the canonical `S1` signal without dropping the latest unlabeled rows.
- **Status:** Active
- **Requires:** current raw stock history plus the historical `S1` feature pipeline inputs
- **Output:** `data/features/xs_barrier_vol_1d_hose_live_current.parquet`
- **Usage:** `python data_tools/build_s1_live_extension.py`
- **Operational role:** first step in the current-date `full_library` / activation refresh chain

### Legacy / Limited / Superseded Builders

### `build_rolling_news_sentiment.py`
Build rolling 5d/30d news sentiment to reduce sparsity (H96).
- **Status:** Legacy historical experiment builder
- **Requires:** `data/news/`
- **Output:** `data/features/xs_news_sentiment_rolling.parquet` (2.5M rows, full grid)
- **Result:** Still 94.9% zeros after 30d window — did not help (F63)

### `build_rolling_news_features.py`
Build the earlier H96 rolling-news variant.
- **Status:** Legacy superseded builder
- **Reason:** earlier H96 variant; superseded by `build_rolling_news_sentiment.py`

### `build_insider_features.py`
Build rolling 5d/30d insider signal feature matrix from raw insider deals.
- **Status:** Legacy superseded builder
- **Requires:** `data/features/xs_insider_deals_raw.parquet`
- **Output:** `data/features/xs_insider_features.parquet`
- **Usage:** `python data_tools/build_insider_features.py`
- **Reason:** raw C2 insider features were superseded by the denser C5 quality artifact in `xs_insider_quality_features.parquet`

### `build_earnings_quality_features.py`
Build earnings-quality factors from the local fundamentals cache.
- **Status:** Legacy limited-coverage builder
- **Output:** `data/features/xs_earnings_quality_daily.parquet`
- **Usage:** `python data_tools/build_earnings_quality_features.py`
- **Current limitation:** the documented artifact is still a 52-ticker subset pending a full-universe fundamentals rebuild

### Archive-only / Rejected Builders

### `build_foreign_demand_features.py`
Build the VNM-ETF-affinity foreign-demand proxy surface.
- **Status:** Archive-only
- **Output:** `data/features/xs_foreign_demand_daily.parquet`
- **Reason:** H110 failed the predictive gate; kept only for reproducibility

### `build_vn30_rebalancing_features.py`
Build VN30 proximity / rebalancing-pressure features.
- **Status:** Archive-only
- **Output:** `data/features/xs_vn30_rebalancing.parquet`
- **Reason:** H114 failed the predictive gate; kept only for reproducibility

---

## Feature Files Reference

### Active / Maintained Artifacts

| File | Status | Description |
|------|--------|-------------|
| `xs_barrier_vol_1d_hose_full.parquet` | Active | Historical `S1` cross-sectional momentum probability surface |
| `xs_barrier_vol_1d_hose_live_current.parquet` | Active | Current-date live extension for `S1` |
| `xs_rl_signal_matrix.parquet` | Active | Consolidated `S1` + maintained candidate-signal matrix used by RL and activation research |
| `xs_insider_deals_raw.parquet` | Active | Raw insider + large-shareholder transaction disclosures |
| `xs_llm_news_ticker_day.parquet` | Active | Structured LLM ticker-day event/sentiment features plus rolling semantic news states |
| `xs_llm_news_market_daily.parquet` | Active | Dense date-level LLM market narrative features and daily fractions |
| `xs_open_close_asymmetry.parquet` | Active | Dense ticker-day open/close asymmetry features (`C4`) |
| `xs_insider_quality_features.parquet` | Active | Dense insider quality / relative-size features (`C5`) |
| `xs_sector_rotation_daily.parquet` | Active | Sector breadth / intra-sector artifact that still feeds contrarian `C6` |
| `xs_price_limit_daily.parquet` | Active | Price-limit-touch feature surface (`C7`) |
| `xs_volume_zscore_daily.parquet` | Active | Abnormal-volume feature surface (`C8`) |
| `xs_shortterm_reversal.parquet` | Active | Short-term reversal feature surface (`C9`) |
| `data/features/execution/tradability_daily.parquet` | Active | Execution/liquidity flags used across portfolio, activation, and exit research |
| `xs_dispersion_regime_daily.parquet` | Active | Dense date-level dispersion regime features |
| `activation_state_daily.parquet` | Active | Dense date-level selection/activation state surface |
| `activation_meta_daily.parquet` | Active | Dense date-level selector-efficacy / activation-meta surface |
| `event_surface_daily.parquet` | Active | Dense ticker-day corporate-event surface for exit-side new-data research |
| `xs_return_skewness.parquet` | Active | Dense ticker-day return skewness / tail-shape features |
| `xs_earnings_calendar_daily.parquet` | Active | Dense date-level earnings/reporting calendar features |
| `xs_news_sentiment_daily.parquet` | Active raw input | Daily keyword-news sentiment base table (sparse) |
| `sector_classification.parquet` | Active | ICB sector labels for the current HOSE universe |
| `macro_regime_daily.parquet` | Active | Macro regime features (VIX, yields, macro proxies, news inputs) |

### Legacy / Limited / Superseded Artifacts

| File | Status | Description |
|------|--------|-------------|
| `xs_insider_features.parquet` | Superseded | Original rolling insider `C2` matrix; superseded by `xs_insider_quality_features.parquet` |
| `xs_news_sentiment_rolling.parquet` | Legacy historical | Canonical rolling-news artifact for H96; kept for reproducibility after the rolling-news branch failed |
| `xs_earnings_quality_daily.parquet` | Limited coverage | Earnings-quality artifact still documented as a 52-ticker subset pending full-universe rebuild |
| `xs_dividend_calendar.parquet` | Limited coverage | Ex-dividend calendar artifact from the original 52-ticker universe |
| `xs_fundamentals_daily.parquet` | Limited coverage | Fundamentals artifact from the original 52-ticker universe |
| `fpt_fundamentals.parquet` | Legacy single-name | FPT-only fundamentals cache kept for the original one-name workflow |

### Archive-only / Rejected Feature Artifacts

| File | Status | Description |
|------|--------|-------------|
| `xs_foreign_demand_daily.parquet` | Archive-only | H110 foreign-demand proxy failed the predictive gate |
| `xs_vn30_rebalancing.parquet` | Archive-only | H114 VN30 rebalancing proximity failed the predictive gate |

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
- **VCI daily prices adjusted** for splits/dividends by VCI
- **CafeF MatchPrice prices raw** until explicitly normalized by `adjust_cafef_intraday_to_vci.py`
- **Insider data:** `published_date` (SSC disclosure date) is the safe signal date; `real_end_date` is after-the-fact
- **News JSONL:** raw titles + bodies; sentiment requires `extract_news_sentiment.py`
- **CafeF GDCoDong API:** returns both insiders (`CEO_` / `LQ_` prefix) and large shareholders (`CORP_`); filter on `is_insider` column for pure insider signal
