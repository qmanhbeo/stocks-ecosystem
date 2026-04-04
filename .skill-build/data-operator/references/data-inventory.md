# Data Inventory

Use this file when you need a compact map of the canonical root `data/` warehouse and the main maintained artifacts without rereading the full `alpha-research-lab/data_tools/README.md`.

## Root Model

- Canonical warehouse: `/home/manh/stocks-ecosystem/data`
- Lab-local alias: `/home/manh/stocks-ecosystem/alpha-research-lab/data -> ../data`
- Producer code: `/home/manh/stocks-ecosystem/alpha-research-lab/data_tools/`
- Shared published surfaces live under `data/features/`

## Main Root Directories

- `data/stock/`: daily and intraday market data, plus CafeF intraday helper folders
- `data/news/`: raw CafeF news archive and daily crawls
- `data/fx-commodities/`: macro, FX, commodity, and global index time series
- `data/macro/`: FRED-based Vietnam macro pulls when present
- `data/features/`: maintained and historical feature artifacts
- `data/features/execution/`: shared tradability contract
- `data/features/recommendations/`: shared recommendation artifacts
- `data/features/entry_alpha/`: canonical offline entry-alpha artifacts
- `data/labels/`: supervised labels and splits
- `data/dividend_cache/`: per-ticker dividend-event caches
- `data/fundamentals_cache/`: per-ticker fundamentals caches
- `data/insider_cache/`: per-ticker insider disclosure caches
- `data/llm_cache/`: per-day structured LLM news feature cache

## Maintained Shared Artifacts

- `data/features/xs_barrier_vol_1d_hose_full.parquet`
  - historical `S1` probability surface
- `data/features/xs_barrier_vol_1d_hose_live_current.parquet`
  - current-date live extension for `S1`
- `data/features/xs_rl_signal_matrix.parquet`
  - maintained consolidated RL signal matrix
- `data/features/execution/tradability_daily.parquet`
  - shared execution/liquidity flags
- `data/features/activation_state_daily.parquet`
  - date-level activation state surface
- `data/features/activation_meta_daily.parquet`
  - selector-efficacy activation-meta surface
- `data/features/event_surface_daily.parquet`
  - canonical ticker-day corporate-event surface
- `data/features/xs_open_close_asymmetry.parquet`
- `data/features/xs_insider_quality_features.parquet`
- `data/features/xs_sector_rotation_daily.parquet`
- `data/features/xs_price_limit_daily.parquet`
- `data/features/xs_volume_zscore_daily.parquet`
- `data/features/xs_shortterm_reversal.parquet`
- `data/features/xs_dispersion_regime_daily.parquet`
- `data/features/xs_earnings_calendar_daily.parquet`
- `data/features/macro_regime_daily.parquet`
- `data/features/sector_classification.parquet`
- `data/features/xs_llm_news_ticker_day.parquet`
- `data/features/xs_llm_news_market_daily.parquet`
- `data/features/xs_news_sentiment_daily.parquet`
  - active raw-input feature table, but sparse

## Limited-Coverage Or Legacy Surfaces

- `data/features/xs_dividend_calendar.parquet`
  - original 52-ticker dividend artifact
- `data/features/xs_fundamentals_daily.parquet`
  - original 52-ticker fundamentals artifact
- `data/features/xs_earnings_quality_daily.parquet`
  - documented as limited coverage pending broader rebuild
- `data/features/xs_insider_features.parquet`
  - superseded by `xs_insider_quality_features.parquet`
- `data/features/xs_news_sentiment_rolling.parquet`
  - legacy rolling-news artifact kept for reproducibility
- `data/features/xs_foreign_demand_daily.parquet`
  - archive-only rejected feature branch
- `data/features/xs_vn30_rebalancing.parquet`
  - archive-only rejected feature branch

## Important Raw Inputs

- `data/stock/gia_lich_su_<TICKER>_1D.parquet`
  - canonical daily HOSE history
- `data/stock/gia_lich_su_<TICKER>_1H_CAFEF.parquet`
  - raw CafeF hourly bars
- `data/stock/gia_lich_su_<TICKER>_1H_CAFEF_ADJ.parquet`
  - CafeF hourly bars normalized onto the VCI-adjusted daily backbone
- `data/stock/_cafef_intraday_parts/`
  - yearly raw CafeF caching surface
- `data/stock/_cafef_adjustment_factors/`
  - audit tables for intraday normalization factors
- `data/news/cafef/raw/YYYY-MM-DD.jsonl`
  - raw Cafef news archive/live crawl surface
- `data/macro/fred_vietnam_macro.parquet`
  - FRED Vietnam macro pull when fetched

## Ownership Heuristics

- If a file is under `data/stock/`, start with the fetchers.
- If a file is under `data/features/` and looks maintained, start with the matching builder in `alpha-research-lab/data_tools/README.md`.
- If the target is `sector_classification.parquet`, verify whether downstream code expects `symbol` or `ticker` instead of assuming the raw file already matches the consumer schema.
- If a file is under `data/features/recommendations/`, treat it as a shared published recommendation contract, not a lab-private scratch artifact.
- If a file is under `data/features/entry_alpha/`, it is a canonical offline artifact owned by the lab analysis pipeline rather than a generic fetcher.

## Common Dependency Chains

- Stock daily history -> `xs_barrier_vol_1d_hose_live_current.parquet` -> `xs_rl_signal_matrix.parquet` -> `activation_state_daily.parquet` -> `activation_meta_daily.parquet`
- Stock daily history -> `data/features/execution/tradability_daily.parquet`
- Dividend cache + earnings calendar + insider raw + RL matrix -> `event_surface_daily.parquet`
- Raw news JSONL -> `data/llm_cache/*.jsonl` -> LLM news feature tables

## Use The Full Manual When

- you need exact command syntax
- you need fetch/build script status
- you need coverage caveats or failure notes
- you need to confirm whether a file is active, limited, legacy, or archive-only

For those cases, read `/home/manh/stocks-ecosystem/alpha-research-lab/data_tools/README.md`.
