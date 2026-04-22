# News Features

News feature generation moved to `alpha-research-lab`.

`RL-trading-agent` only consumes exported parquet files from shared `stocks/data/features/news/predictions/`.

Those per-ticker exports can now include three additive news families:
- deterministic tabular / keyword features
- embedding features
- whole-article local PhoBERT sentiment features (`phobert_*`)

The PhoBERT columns are additive only. They do not change the separate hosted
LLM contracts under `data/llm_cache/` or `data/features/xs_llm_news_*`.

Current default RL news-column bundles stay unchanged in this pass. The new
`phobert_*` columns are available in the exported per-ticker parquet files and
can be selected explicitly when a training or evaluation run wants them.
