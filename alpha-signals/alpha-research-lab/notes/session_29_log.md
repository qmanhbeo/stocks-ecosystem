# Session 29 Log — 2026-03-24

## Objectives
- Explore news sentiment (H89) and sector sub-models (H92) as alternative alpha signals
- Investigate vnstock data availability: sector classification and foreign investor flow
- Maintain H93 as best RL signal (Sharpe 15.08)

## System State (entering)
- H93: best RL signal, IC +0.1491, edge std 1.60%, Sharpe 15.08
- H54: champion for raw edge (+25.52%) but parked (deployment gap)
- No new production-ready signal since H54

---

## Data Exploration

### vnstock API probe (probe_vnstock2.py)
**Finding F58:** `company.overview()` returns `icb_name2`, `icb_name3`, `icb_name4` — ICB sector classification.
- Fetched for all 398 HOSE tickers with price data → `data/features/sector_classification.parquet`
- Top sectors: Real Estate (58), Construction & Materials (54), Industrial Goods (41), Utilities (37), Banking (20)

**Finding F59:** Historical daily foreign investor flow is NOT available via vnstock.
- `trading_stats()` gives current-day point-in-time data only
- `price_board()` gives current-day intraday accumulated foreign buy/sell
- No historical time series → H95 (foreign flow signal) deferred

---

## Experiment H89: Keyword News Sentiment

### Setup
- `data_tools/extract_news_sentiment.py`: processes 3,733 cafef JSONL files
- Ticker extraction: parenthetical pattern `\(([A-Z]{2,5})\)` in article titles (~10.8% match rate)
- Sentiment: keyword lexicon (26 positive, 25 negative Vietnamese financial terms)
- Output: `xs_news_sentiment_daily.parquet` (6,532 rows, 340 tickers, 2016–2026)

### Results
| System | IC | IC Std |
|---|---|---|
| H93 (baseline) | +0.1405 | 0.0945 |
| H89 (H93 + news) | +0.1361 | 0.1001 |
| Delta | −0.0044 | +0.0056 |

Per-year: mostly negative deltas (2018: −0.0185, 2020: −0.0059, 2022: −0.0103).
Marginal positive in 2024 (+0.0025) and 2025 (+0.0015).

### Root Cause
Extreme sparsity: 6,532 article-ticker pairs over 11 years of data. Coverage = ~0.8% of (day, ticker) pairs.
Model sees 99.2% zeros and learns to ignore news features. Keyword scoring is also noisy.

### Verdict: FAIL (F60)
News sentiment as implemented hurts IC slightly. Path forward: rolling/lagged aggregation (H96)
or LLM-based extraction (H98) to improve quality and density.

---

## Experiment H92: Sector Sub-Models

### Setup
- `data_tools/fetch_sector_classification.py`: fetches ICB codes for 398 tickers via company.overview()
- `cross_sectional_wf.py` enhanced: `--sector` flag with diacritic-normalized matching
  (handles Vietnamese characters like "đ"→"d", "ă"→"a" etc.)
- Ran H93 config within each sector universe

### Results

**Banking (20 tickers: ACB, BID, CTG, EIB, HDB, KLB, LPB, MBB, MSB, NAB, OCB, SHB, SSB, STB, TCB, TPB, VAB, VCB, VIB, VPB)**

| Year | Sub-model IC | Pooled IC | Delta |
|------|-------------|-----------|-------|
| 2015 | 0.1302 | 0.1844 | −0.054 |
| 2018 | 0.0469 | 0.0890 | −0.042 |
| 2020 | 0.0621 | 0.1022 | −0.040 |
| Overall | 0.1077 | 0.1238 | −0.016 |

**Real Estate (57 tickers)**

| Year | Sub-model IC | Pooled IC | Delta |
|------|-------------|-----------|-------|
| 2015 | 0.1538 | 0.1902 | −0.036 |
| 2021 | 0.1133 | 0.1131 | +0.000 |
| 2022 | 0.0837 | 0.0802 | +0.004 |
| Overall | 0.1308 | 0.1393 | −0.009 |

### Root Cause
Pooled model wins due to volume: banking has ~4,400 training rows/year vs pooled ~87,000.
Even real estate (57 stocks) benefits from the full universe during training.

### Verdict: NEUTRAL/FAIL (F61)
Sector-specific sub-models don't beat the pooled model. The cross-sectional momentum signal
is sector-agnostic. This is consistent with H80 and H94 findings.

---

## Infrastructure Created This Session

| Asset | Purpose |
|-------|---------|
| `data_tools/fetch_sector_classification.py` | Fetches ICB sector codes from vnstock |
| `data/features/sector_classification.parquet` | 398 tickers × {symbol, icb_name2/3/4} |
| `data_tools/extract_news_sentiment.py` | Keyword sentiment from cafef JSONL |
| `data/features/xs_news_sentiment_daily.parquet` | 6,532 (day, ticker) sentiment pairs |
| `--sector` flag in `cross_sectional_wf.py` | Unicode/diacritic-normalized sector filter |
| `data/features/xs_barrier_vol_1d_banking_hose.parquet` | H92a banking sub-model probas |
| `data/features/xs_barrier_vol_1d_realestate_hose.parquet` | H92b real estate sub-model probas |
| `data/features/xs_barrier_vol_1d_news_hose_full.parquet` | H89 with news features |

---

## Session Conclusions

1. **H93 unchanged** — no new signal beats it (Sharpe 15.08, IC +0.1491 remain best RL signal)
2. **News path not dead, just needs better approach** — rolling aggregation (H96) or LLM (H98)
3. **Sector sub-models confirmed ineffective** — this now has 3 replication points (H80, H94, H92)
4. **Foreign flow deferred** — vnstock doesn't expose historical daily data

---

## Next Session Priority (Session 30)

| Experiment | Hypothesis | Effort | Notes |
|---|---|---|---|
| H96 | Rolling 5d/30d news sentiment reduces sparsity | Low | Fix for H89 |
| H97 | Insider trading net flow predicts outperformance | Medium | New data source |
| H98 | LLM-based news scoring (OpenAI $4 credit) | High | Higher quality but costly |
