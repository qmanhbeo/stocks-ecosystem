# Data Playbooks

Use this file when the user asks for an actual data operation instead of just a directory or ownership audit.

Run commands from `/home/manh/stocks-ecosystem/alpha-research-lab/`.

## Safe Defaults

- Prefer `conda run -n stocks python ...`
- Prefer incremental append/update modes over rewrite modes
- Avoid recent `--start` windows on stock refreshes unless the user explicitly wants a truncated local slice
- Verify the produced output after every fetch or rebuild
- Do not assume there is a one-shot full feature refresh script; compose the needed rebuild chain explicitly

## Inspect A Target

1. Inspect the target path under `/home/manh/stocks-ecosystem/data`.
2. Find the owning script in `/home/manh/stocks-ecosystem/alpha-research-lab/data_tools/README.md`.
3. Confirm whether the target is active, limited coverage, legacy, or archive-only.
4. If the request is a contract change rather than a refresh, update docs and consumers together.

## Refresh Daily Stock History

### Small or named ticker set

```bash
conda run -n stocks python data_tools/fetch_stock.py --tickers FPT,ACB
```

### Current-universe incremental top-up

```bash
conda run -n stocks python data_tools/fetch_refresh_all.py
```

### Full-history restore after truncation or suspected damage

```bash
conda run -n stocks python data_tools/fetch_refresh_all.py --start 2000-01-01 --end 2026-12-31
```

Verification:

- check the affected ticker parquet(s)
- check `data/stock/gia_lich_su_VNINDEX_1D.parquet`
- if current dates moved, treat stock-derived maintained features as stale until rebuilt

## Expand The HOSE Universe

```bash
conda run -n stocks python data_tools/fetch_hose_universe.py --delay 0.3
```

Use this when the request is about adding missing HOSE names, not just topping up known files.

## Refresh FX, Macro, And Sector Inputs

```bash
conda run -n stocks python data_tools/fetch_fx_commodities.py
conda run -n stocks python data_tools/fetch_fred_macro.py
conda run -n stocks python data_tools/fetch_sector_classification.py
```

Use the sector-classification refresh when sector-derived features or sector caps depend on current labels.
Check the produced schema before downstream use because the raw fetch path may use `symbol` and some consumers normalize to `ticker`.

## Refresh Insider, Dividend, And Fundamentals Inputs

```bash
conda run -n stocks python data_tools/fetch_insider_deals.py
conda run -n stocks python data_tools/fetch_dividend_events.py
conda run -n stocks python data_tools/fetch_all_stock_fundamentals.py
```

Notes:

- insider raw is active and whole-universe
- dividend and fundamentals are documented as limited-coverage workflows today; confirm whether the user wants a full-universe rerun or just a repair

## Restore Or Update News

### Fresh clone or missing archive

```bash
conda run -n stocks python data_tools/fetch_news_archive.py
```

Notes:

- the archive is not kept in git
- the restore path may need `gdown`

### Daily incremental crawl

```bash
conda run -n stocks python data_tools/fetch_news.py
```

### Structured LLM extraction and build

```bash
conda run -n stocks python data_tools/extract_llm_news_features.py --date-from 2026-03-01 --date-to 2026-03-31
conda run -n stocks python data_tools/build_llm_news_features.py
```

Use `extract_news_sentiment.py` if the request is specifically about the keyword-based sentiment base table instead of the LLM pipeline.

## Acquire Intraday Data

### Preferred open-source path

```bash
conda run -n stocks python data_tools/fetch_cafef_intraday_all.py --start 2000-01-01 --end 2026-12-31 --workers 16
conda run -n stocks python data_tools/adjust_cafef_intraday_to_vci.py
```

Interpretation:

- `*_1H_CAFEF.parquet` is the raw CafeF tape
- `*_1H_CAFEF_ADJ.parquet` is the repo-aligned cross-day intraday surface

### SSI fallback when credentials are available

```bash
conda run -n stocks python data_tools/fetch_ssi_intraday.py --resolution 60 --start 2019-01-01 --end 2025-12-31
```

Use only when the request explicitly accepts the credentialed path or the CafeF path is inadequate.

## Rebuild Maintained Feature Surfaces

### Stock-derived maintained features

```bash
conda run -n stocks python data_tools/build_open_close_asymmetry_features.py
conda run -n stocks python data_tools/build_dispersion_regime_features.py
conda run -n stocks python data_tools/build_return_skewness_features.py
conda run -n stocks python data_tools/build_earnings_calendar_features.py
conda run -n stocks python data_tools/build_insider_quality_features.py
conda run -n stocks python data_tools/build_sector_rotation_features.py
conda run -n stocks python data_tools/build_price_limit_features.py
conda run -n stocks python data_tools/build_volume_zscore_features.py
conda run -n stocks python data_tools/build_shortterm_reversal_features.py
conda run -n stocks python data_tools/build_macro_regime_features.py
conda run -n stocks python data_tools/build_tradability_flags.py
```

Run only the subset required by the user’s task unless the request is a full maintained-surface rebuild.

### Live/current-date shared chain

Use this when stock history changed and the user needs current shared maintained surfaces:

```bash
conda run -n stocks python data_tools/build_s1_live_extension.py
conda run -n stocks python data_tools/build_tradability_flags.py
conda run -n stocks python data_tools/build_rl_signal_matrix.py
conda run -n stocks python data_tools/build_activation_state_features.py
conda run -n stocks python data_tools/build_activation_meta_features.py
```

Reason:

- `build_s1_live_extension.py` refreshes the current-date `S1` extension
- `build_tradability_flags.py` keeps the shared execution surface current with the stock history
- `build_rl_signal_matrix.py` republishes the maintained consolidated matrix
- `build_activation_state_features.py` and `build_activation_meta_features.py` repair the activation surfaces that depend on the maintained matrix and tradability inputs

## Rebuild Event Surface

```bash
conda run -n stocks python data_tools/build_event_surface_daily.py
```

Upstream requirements:

- `data/features/xs_rl_signal_matrix.parquet`
- `data/dividend_cache/*.parquet`
- `data/features/xs_earnings_calendar_daily.parquet`
- `data/features/xs_insider_deals_raw.parquet`

If the event surface is stale, confirm those upstreams first instead of blindly rerunning only the final builder.

## Repair Patterns

### Truncated stock history

1. run the full-history restore
2. verify `VNINDEX`
3. rerun the live/current-date shared chain or the narrower downstream builders the user actually needs

### Missing maintained parquet

1. identify the owner builder
2. verify upstream inputs exist and are current
3. rerun the builder
4. verify the output file was recreated

### Limited-coverage artifact surprise

1. confirm the artifact is documented as limited coverage
2. decide whether the request is for repair or for a full-universe expansion
3. if expanding, treat it as a producer-behavior change and update docs if the published contract changes

## Verification Checklist

- output path exists
- file size and modification time changed as expected
- upstream dependencies are not older or obviously truncated
- `VNINDEX` is intact when stock data was touched
- if a shared published surface changed, note downstream consumers that rely on it
