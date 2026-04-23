# News Features

`research_pipelines/news_features/` is the canonical news producer for the workspace. It reads shared raw news from `stocks/data/news/`, tags articles against the shared stock universe, builds daily tabular features, whole-article local PhoBERT sentiment features, transformer embeddings, and exports per-ticker parquet files for RL consumption.

By default the pipeline resolves shared data under `/home/manh/stocks/data`. Override that with `STOCKS_DATA_ROOT` if you need a different workspace data root.

## What It Does

1. Fetch raw news into `data/news/cafef/raw/`.
2. Normalize and deduplicate article text.
   Normalized `published_at` and derived `date` use Hanoi time (`Asia/Ho_Chi_Minh`, GMT+7).
3. Tag articles to one or more tickers.
4. Build daily tabular text features.
5. Build whole-article PhoBERT sentiment datasets from normalized title + summary + body text.
6. Build daily transformer embedding features and compress them with PCA.
7. Export combined RL-ready daily feature files.

## Commands

Fetch raw Cafef news:

```bash
python data_tools/fetch_news.py --source cafef --start-date 2020-01-01 --end-date 2026-03-11
```

Run each stage manually:

```bash
python -m research_pipelines.news_features.core.repair_raw_news_dates
python -m research_pipelines.news_features.core.add_section_to_missing --source cafef --workers 4
python -m research_pipelines.news_features.core.preprocess_news
python -m research_pipelines.news_features.core.tag_articles
python -m research_pipelines.news_features.core.build_tabular_features
python -m research_pipelines.news_features.core.build_phobert_sentiment_features
python -m research_pipelines.news_features.core.build_embedding_features
python -m research_pipelines.news_features.core.aggregate_daily_features
```

PhoBERT whole-article scoring is now checkpointed and resumable by default. The
builder first materializes a tagged-only PhoBERT input cache under
`data/features/news/datasets/phobert_input_articles.parquet`, then writes
per-batch checkpoint shards under `data/features/news/datasets/phobert_checkpoint/`.
It only publishes the final `phobert_article_sentiment.parquet` and
`phobert_ticker_day_sentiment.parquet` after all batches are complete.

Operational rule:
- if a PhoBERT backfill is interrupted, rerun `python -m research_pipelines.news_features.core.build_phobert_sentiment_features`
- the builder reuses `phobert_input_articles.parquet` when the normalized/tagged
  inputs have not changed, so restarts skip both the full normalized scan and
  completed checkpoint shards
- the builder will skip completed checkpoint batches when the normalized/tagged
  inputs and PhoBERT config signature still match
- on successful finalization, the checkpoint shard files are cleaned up and the
  manifest stays as the resume record

Run the full feature pipeline after raw news already exists:

```bash
python -m research_pipelines.news_features
```

## Outputs

- Raw fetched JSONL: `data/news/cafef/raw/`
  Raw records now store `section_name` when CafeF exposes the article category in the header.
- Normalized articles: `data/features/news/normalized/`
- Tagged articles: `data/features/news/tagged/`
- Daily datasets: `data/features/news/datasets/`
  This now includes dedicated local PhoBERT datasets:
  - `phobert_article_sentiment.parquet`
  - `phobert_ticker_day_sentiment.parquet`
  - `phobert_input_articles.parquet`
  - `phobert_input_articles_manifest.json`
  - `phobert_checkpoint/` for resumable batch shards and checkpoint metadata
- Per-ticker RL-ready files: `data/features/news/predictions/`

## RL Integration

RL now consumes these exports through its own adapter layer. The producer-side merge helper remains `research_pipelines.news_features.core.merge_news_features.merge_news_features(...)`.

The PhoBERT lane is additive and isolated from the hosted LLM stack:
- PhoBERT outputs live under `data/features/news/`
- hosted LLM semantic/event extraction remains under `data/llm_cache/` and `data/features/xs_llm_news_*`
