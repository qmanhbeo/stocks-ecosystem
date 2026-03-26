# News Features

`research_pipelines/news_features/` is the canonical news producer for the workspace. It reads shared raw news from `stocks/data/news/`, tags articles against the shared stock universe, builds daily tabular and embedding features, and exports per-ticker parquet files for RL consumption.

## What It Does

1. Fetch raw news into `data/news/cafef/raw/`.
2. Normalize and deduplicate article text.
   Normalized `published_at` and derived `date` use Hanoi time (`Asia/Ho_Chi_Minh`, GMT+7).
3. Tag articles to one or more tickers.
4. Build daily tabular text features.
5. Build daily transformer embedding features and compress them with PCA.
6. Export combined RL-ready daily feature files.

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
python -m research_pipelines.news_features.core.build_embedding_features
python -m research_pipelines.news_features.core.aggregate_daily_features
```

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
- Per-ticker RL-ready files: `data/features/news/predictions/`

## RL Integration

RL now consumes these exports through its own adapter layer. The producer-side merge helper remains `research_pipelines.news_features.core.merge_news_features.merge_news_features(...)`.
