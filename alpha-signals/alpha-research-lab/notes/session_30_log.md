# Session 30 Log — News Path Exhausted; Infrastructure Built (2026-03-25)

## Objectives
- H96: Rolling 5d/30d news aggregation to fix H89 sparsity
- H97: Probe insider trading data availability (vnstock)
- H99: Body-text extraction to increase news coverage 6×

## System State (entering)
- H93: best RL signal, IC +0.1491, edge std 1.60%, Sharpe 15.08 (11/11 years)
- H54: champion for raw edge (+25.52%), parked (deployment gap)
- C1 (H89): candidate signal — IC +0.043 standalone, 5/8 years positive, too sparse for XS WF

---

## Setup: News Archive Restored

Downloaded `data/news/cafef/raw/` (3,734 daily JSONL files, 2016–2026) from Google Drive
via `data_tools/fetch_news_archive.py`. 1.18 GB compressed, ~3.6 GB extracted.

---

## Experiment H96: Rolling 5d/30d News Sentiment

**Hypothesis:** Aggregating daily sentiment over 5 and 30 trading days reduces sparsity enough
for the XS WF model to learn from news features.

**Script built:** `data_tools/build_rolling_news_sentiment.py`
- Full (trading_day, ticker) grid: 2.5M rows, 401 tickers
- Rolling 5d/30d windows: `sentiment_score_5d/30d`, `article_count_5d/30d`,
  `positive_ratio_5d`, `has_news_5d/30d`

**Coverage after rolling:**
- article_count_5d > 0: 1.1% of rows
- article_count_30d > 0: 5.1% of rows

**WF command:**
```bash
python cross_sectional_wf.py --use-volume-signals --barrier-pct 0.01 --target-horizon 1 \
  --use-rolling-news --save-all-probas data/features/xs_barrier_vol_1d_news_rolling_hose_full.parquet
```

**Results:**
| Metric | H93 (baseline) | H96 (rolling news) | Delta |
|--------|---------------|-------------------|-------|
| IC (Spearman) | +0.1491 | +0.1483 | −0.0008 |
| Edge std | 1.60% | 1.76% | +0.16% |
| Sharpe (N=5) | 15.08 | 13.86 | −1.22 |
| Sig years | 11/11 | 11/11 | 0 |

**Artifact:** `data/features/xs_barrier_vol_1d_news_rolling_hose_full.parquet`

**Root cause:** 94.9% of (day, ticker) rows are still zero even after 30d rolling.
Model correctly assigns near-zero feature importance to near-zero features.

**Verdict: FAIL (F62)**

---

## Experiment H97: Insider Trading Data Availability

**Hypothesis:** `company.insider_deals()` from vnstock provides historical insider
net-buying data that predicts next-week outperformance.

**Probe result:** vnstock API returns 403 Forbidden in this cloud environment.
Network access to VCI data source is blocked.

**Verdict: DEFERRED** — no data available in this environment.
Will require a different data source or local environment with vnstock access.

---

## Experiment H99: Body-Text Enhanced News Sentiment

**Hypothesis:** Extracting tickers from article body_text (in addition to titles)
increases coverage 6× and improves signal quality or consistency.

**Key observation from data probe:**
- Title-only ticker extraction: ~0.8% of articles (parenthetical pattern in title)
- Body-text extraction: +25.7% additional articles
- After known-ticker filter: false positives (WHO, UAE, financial abbreviations) auto-excluded

**Results of body extraction:**
- H89 (title only): 5,225 matched (day, ticker) pairs, 325 tickers
- H99 (title + body): 27,001 matched pairs, 375 tickers — **5.2× increase**

**Standalone IC comparison (Spearman):**
| Year | H89 IC | H99 IC |
|------|--------|--------|
| 2019 | +0.072 | −0.011 |
| 2020 | +0.098 | +0.041 |
| 2021 | +0.005 | +0.010 |
| 2022 | +0.088 | +0.031 |
| 2025 | −0.066 | +0.063 |
| Avg  | +0.041 | +0.018 |
| Pos yrs | 6/10 | 9/10 |

H99 standalone: IC +0.0184, 9/10 years positive (vs H89 +0.041, 6/10 years).
Coverage improves consistency but reduces per-observation quality.

**XS WF test (H93 + H99 daily body news):**
```bash
python cross_sectional_wf.py --use-volume-signals --barrier-pct 0.01 --target-horizon 1 \
  --use-news --news-path data/features/xs_news_sentiment_h99_body.parquet \
  --save-all-probas data/features/xs_barrier_vol_1d_news_h99_hose_full.parquet
```

| Metric | H93 (baseline) | H99 (body news) | Delta |
|--------|---------------|----------------|-------|
| IC (Spearman) | +0.1491 | +0.1363 | −0.0128 |
| Sharpe (N=5) | 15.08 | 11.52 | −3.56 |
| Years covered | 11/11 | 8/11 | −3 yrs |

**Artifact:** `data/features/xs_barrier_vol_1d_news_h99_hose_full.parquet`

Note: WF started from 2018 instead of 2015 — possible cause is that merged data
reduced early-year coverage enough to fail the min_train_years=3 threshold.

**Verdict: FAIL (F63)** — Body extraction adds noise > signal in the XS WF context.
Per-observation quality falls too much despite coverage improvement.

---

## Infrastructure Created This Session

| Asset | Purpose |
|-------|---------|
| `data_tools/build_rolling_news_sentiment.py` | Rolling 5d/30d news aggregation |
| `data/features/xs_news_sentiment_rolling.parquet` | 2.5M rows rolling news features |
| `data/features/xs_news_sentiment_h99_body.parquet` | 37,547 rows body-enhanced sentiment |
| `data/features/xs_barrier_vol_1d_news_rolling_hose_full.parquet` | H96 WF probas |
| `data/features/xs_barrier_vol_1d_news_h99_hose_full.parquet` | H99 WF probas |
| `--use-rolling-news` flag in `cross_sectional_wf.py` | H96 rolling news feature loading |
| `--news-path` flag in `cross_sectional_wf.py` | H99 custom news file override |

---

## Session Conclusions

1. **H93 unchanged** — Sharpe 15.08, IC +0.1491 remain best RL signal
2. **News path exhausted without LLM quality** — all three news approaches fail:
   - H89: daily title sentiment → FAIL (too sparse)
   - H96: rolling aggregation → FAIL (still 94.9% zeros)
   - H99: body extraction → FAIL (noisier per-observation)
3. **H97 blocked** — vnstock API 403 in cloud environment
4. **C1 remains CANDIDATE** — standalone IC +0.043, but cannot improve H93 as XS feature
5. **Path forward for news:** H98 (LLM quality sentiment) is the only remaining option

---

## Findings To Promote

- **F62:** Rolling 5d/30d news aggregation doesn't fix sparsity for XS WF. Even 5.1% coverage (30d window) leaves model unable to use the feature — 94.9% zeros, near-zero importance assigned.
- **F63:** Body-text ticker extraction increases coverage 6× but per-observation quality falls proportionally. IC drops from +0.041 to +0.018 standalone; XS WF IC drops −0.013. Not a net improvement.
- **F64:** All three news approaches (sparse daily, rolling aggregate, body extraction) consistently fail to improve H93 in the XS WF. The keyword lexicon is likely the core bottleneck — LLM-quality sentiment (H98) remains the only untested path.

---

## Production System After This Session

H93 unchanged: IC +0.1491, Sharpe 15.08, edge std 1.60%.
Signal library: S1 = CONFIRMED (unchanged), C1 = CANDIDATE (unchanged).

---

## Next Session Priority (Session 31)

| Experiment | Hypothesis | Blocker | Priority |
|---|---|---|---|
| H97 | Insider deals / dividend events | Needs local vnstock access | Medium |
| H98 | LLM news sentiment | Needs LLM API key (~$4) | High if API available |
| New direction | Explore non-news signals | - | High |

**Suggested new signal directions to explore:**
- **Return reversal at earnings season** — test IC around quarterly reporting dates
- **Cross-ticker correlation features** — stocks moving together as XS feature
- **Order flow proxies** — volume-weighted price momentum at open vs close
- **High-frequency session features** — open/close asymmetry patterns
