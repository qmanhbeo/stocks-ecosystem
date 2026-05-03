# News Features

`research_pipelines/news_features/` is the canonical news producer for the workspace. It reads shared raw news from `stocks/data/news/`, tags articles against the shared stock universe, builds daily tabular features, whole-article local PhoBERT sentiment features, separate PhoBERT forward-looking / article-scope / source-type lanes, transformer embeddings, and exports per-ticker parquet files for RL consumption where applicable. A smaller Ollama residual lane now defaults to event-family only, because scope and source-type are covered by PhoBERT heads. The main production path is local-first and encoder-first.

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

Run the active production stages manually:

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

Local-first semantic side lanes with clearer preferred names:

```bash
python -m research_pipelines.news_features.core.train_phobert_forward_looking
python -m research_pipelines.news_features.core.publish_phobert_forward_looking_features
python -m research_pipelines.news_features.core.train_phobert_article_scope
python -m research_pipelines.news_features.core.build_phobert_article_scope_features
python -m research_pipelines.news_features.core.train_phobert_source_type
python -m research_pipelines.news_features.core.build_phobert_source_type_features
python -m research_pipelines.news_features.core.build_ollama_probe_features
```

Compatibility note:
- `build_ollama_guarded_features` still works, but `build_ollama_probe_features` is the preferred operator name
- `publish_phobert_forward_looking_exports` still works, but `publish_phobert_forward_looking_features` is the clearer preferred alias

The default Ollama guarded backfill includes all 2026 data (no cutoff). To run:

```bash
python -m research_pipelines.news_features.core.build_ollama_guarded_features
```

For locked research backfills that must avoid the `2026+` monitor period, pass
the cutoff explicitly:

```bash
python -m research_pipelines.news_features.core.build_ollama_guarded_features --max-published-at 2025-12-31T23:59:59+07:00
```

Hard operating rule:
- publish-only jobs must not route through heavyweight rebuild stages
- if `phobert_ticker_day_sentiment.parquet` already exists, do not rerun
  `build_tabular_features` or the full `research_pipelines.news_features` entrypoint
  just to refresh RL-ready exports

For a lighter PhoBERT-only export refresh after the PhoBERT backfill is already
complete, use the dedicated publish wrapper:

```bash
python -m research_pipelines.news_features.core.publish_phobert_exports
```

For the additive forward-looking PhoBERT head after a winner already exists,
use the dedicated forward-looking publish wrapper:

```bash
python -m research_pipelines.news_features.core.publish_phobert_forward_looking_features
```

Advanced equivalent:

```bash
python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking ollama_guarded
```

Use the full pipeline only when upstream raw/normalized/tagged inputs or the
legacy keyword / embedding contracts actually need to be rebuilt.

PhoBERT whole-article scoring is now checkpointed and resumable by default. The
builder first materializes a tagged-only PhoBERT input cache under
`data/features/news/datasets/phobert_input_articles.parquet`, then writes
per-batch checkpoint shards under `data/features/news/datasets/phobert_checkpoint/`.
It only publishes the final `phobert_article_sentiment.parquet` and
`phobert_ticker_day_sentiment.parquet` after all batches are complete.

The additive guarded local Ollama lane follows the same staged pattern while
staying separate from `data/llm_cache/`. It first materializes a tagged-only
`ollama_guarded_input_articles.parquet` cache, scores one article at a time
with deterministic ticker linkage from tagged rows, writes resumable shards
under `ollama_guarded_checkpoint/`, and only then publishes
`ollama_guarded_article_features.parquet` plus
`ollama_guarded_ticker_day_features.parquet`. This guarded lane is now the
minimal local residual semantic contract:
- default generated field: `event_family`
- default input gate: `phobert_article_scope_prob_positive >= 0.28`
- default checkpoint interval: `20` input rows per shard
- local confidence / coverage / abstention diagnostics
- optional widened fields: `impact_scope`, `source_authority`, `is_rumor`

Expensive Ollama article scores are cached separately under
`ollama_guarded_score_cache/` by article content plus the real scoring
contract: model, prompt version, prompt variant, field set, `num_ctx`,
`num_predict`, temperature, schema mode, and body truncation. `checkpoint_rows`
is intentionally not part of that score key. Changing checkpoint cadence can
rebuild or resume checkpoint shards from cached scores without calling Ollama
again for rows that were already scored under the same scoring contract.

PhoBERT `article_scope` and `source_type` are the preferred local scope/source
proxies. Use `--field-set full5` or `--field-set event_rumor` only when you are
intentionally running a widened diagnostic pass.

Sentiment and forward-looking stay in the separate PhoBERT lanes. The guarded
local daily aggregates now merge into `predictions/*_news_features.parquet`.

Canonical roadmap on the current constrained workstation:
- keep PhoBERT sentiment as the main local production lane
- keep PhoBERT forward-looking as the first separate local head
- if expanding beyond that, add separate PhoBERT heads rather than a broader
  guarded-generator contract
- keep `article_scope` and `source_type` as the default scope/source path
- treat model probability as the first local confidence surface
- keep the Ollama lane event-family-first and residual rather than broad-schema
- keep deterministic ticker linkage outside the model
- use the locally proven best residual model on the `3GB VRAM / 10GB RAM`
  planning box rather than forcing a nominally larger model class

The semantic binary heads now use a slightly different training contract from
the forward-looking lane where that is justified by the task:
- `article_scope` and `source_type` stage datasets can use head-specific split
  strategies instead of inheriting the forward-looking date split blindly
- training calibrates a per-head positive decision threshold on the validation
  split rather than assuming a hard `0.5` cutoff
- heads can also enable train-time positive class weighting when label balance
  is materially skewed

That means the saved winner contract for the binary heads now includes the
calibrated decision threshold, and publish uses that threshold when writing the
article-level boolean label and daily positive-count/share surfaces.

The first encoder-distillation builder is
`python -m research_pipelines.news_features.core.train_phobert_forward_looking`.
It is intentionally sequential: first it reconstructs day-level teacher labels
from `data/llm_cache/` into
`data/features/news/datasets/phobert_forward_looking_teacher_labels.parquet`
plus a matching manifest, then it builds the tagged-only article-text stage at
`data/features/news/datasets/phobert_forward_looking_stage_articles.parquet`
plus a matching manifest, and only then trains one PhoBERT candidate at a time.
Candidate state and winner bundles now land under
`data/model_checkpoints/news/phobert_forward_looking/`, while handoff notes stay
under `alpha-research-lab/artifacts/run_summaries/`. The canonical watchdog heartbeat
for this lane is
`alpha-research-lab/artifacts/job_status/phobert_forward_looking_train.json`.
Once a winner exists, the dedicated publish wrapper scores the full tagged
article universe through that winner, writes additive
`phobert_forward_looking_article_features.parquet` and
`phobert_forward_looking_ticker_day_features.parquet` datasets, and overlays
additive `phobert_forward_looking_*` columns onto
`predictions/*_news_features.parquet` without wiping the other tabular,
sentiment, or embedding lanes.

Forward-looking publish surfaces:
- machine-readable heartbeat:
  - `alpha-research-lab/artifacts/job_status/phobert_forward_looking_publish.json`
- published datasets:
  - `data/features/news/datasets/phobert_forward_looking_article_features.parquet`
  - `data/features/news/datasets/phobert_forward_looking_ticker_day_features.parquet`
- resumable checkpoint state:
  - `data/features/news/datasets/phobert_forward_looking_checkpoint/`
  - `data/features/news/datasets/phobert_forward_looking_checkpoint/phobert_forward_looking_checkpoint_manifest.json`

Canary-first operating rule:
- first real launches should start with one candidate only so the job-status
  surface, manifests, summaries, and hardware behavior can be checked cheaply
- recommended canary:

```bash
python -m research_pipelines.news_features.core.train_phobert_forward_looking \
  --stages teacher,stage,train \
  --candidate-name phobert_base
```

- after the canary writes healthy teacher / stage / training state, rerun
  without `--candidate-name` to expand to the full candidate set

The same canary rule now applies to the two new binary heads:

```bash
python -m research_pipelines.news_features.core.train_phobert_article_scope \
  --candidate-name phobert_base

python -m research_pipelines.news_features.core.build_phobert_article_scope_features

python -m research_pipelines.news_features.core.train_phobert_source_type \
  --candidate-name phobert_base

python -m research_pipelines.news_features.core.build_phobert_source_type_features
```

Operator note:
- these binary heads now mirror the forward-looking lane more closely at the
  trainer/runtime level too
- expect epoch-level training logs and per-epoch status updates instead of a
  long silent gap after model load
- the binary-head publish path now mirrors the forward-looking lane too:
  article scoring is shard-checkpointed under the head-specific checkpoint
  directory and final article / ticker-day outputs are only promoted after
  finalize succeeds
- the CLI wrappers now apply the local offline-transformers defaults
  automatically when the repo is configured for local-file-first PhoBERT loads
- the heavy PhoBERT train/publish paths now also prepend `/usr/lib/wsl/lib`
  into `PATH` and `LD_LIBRARY_PATH` when present
- on this WSL workstation, PhoBERT train/publish now fail fast if CUDA is
  expected but hidden by a sandbox/container; use `NEWS_FEATURES_ALLOW_CPU=1`
  only for an explicit CPU fallback

Resume / watchdog surfaces for this lane:
- machine-readable heartbeat:
  - `alpha-research-lab/artifacts/job_status/phobert_forward_looking_train.json`
  - `alpha-research-lab/artifacts/job_status/phobert_forward_looking_publish.json`
- optional periodic watchdog snapshots:
  - `python src/watchdogs/phobert_forward_looking_watchdog.py --poll-seconds 600`
  - writes:
    - `alpha-research-lab/artifacts/job_status/phobert_forward_looking_watchdog_current.json`
    - `alpha-research-lab/artifacts/job_status/phobert_forward_looking_watchdog_history.jsonl`
- production manifests:
  - `data/features/news/datasets/phobert_forward_looking_teacher_manifest.json`
  - `data/features/news/datasets/phobert_forward_looking_stage_manifest.json`
  - `data/features/news/datasets/phobert_forward_looking_checkpoint/phobert_forward_looking_checkpoint_manifest.json`
  - `data/model_checkpoints/news/phobert_forward_looking/training_manifest.json`
- candidate state:
  - `data/model_checkpoints/news/phobert_forward_looking/runs/<run_id>/<candidate>/candidate_state.json`
- compact latest summaries:
  - `alpha-research-lab/artifacts/run_summaries/latest_news_forward_looking_*.json`

The legacy heavy tabular and embedding builders now follow the same operating
rule without changing their public outputs:
- `build_tabular_features` first refreshes or reuses the internal
  `news_tabular_article_stage.parquet` cache, then rebuilds the published
  `news_tabular_features.parquet` ticker-day dataset from that stage
- `build_embedding_features` first refreshes or reuses the tagged-only
  `embedding_input_articles.parquet` cache, then writes resumable raw-embedding
  shards under `embedding_checkpoint/` before publishing the existing
  `article_embeddings.parquet` and `news_embedding_features.parquet` outputs
- these staged files are internal producer caches, not new consumer contracts

Operational rule:
- if a PhoBERT backfill is interrupted, rerun `python -m research_pipelines.news_features.core.build_phobert_sentiment_features`
- the builder reuses `phobert_input_articles.parquet` when the normalized/tagged
  inputs have not changed, so restarts skip both the full normalized scan and
  completed checkpoint shards
- the builder will skip completed checkpoint batches when the normalized/tagged
  inputs and PhoBERT config signature still match
- on successful finalization, the checkpoint shard files are cleaned up and the
  manifest stays as the resume record
- if the forward-looking PhoBERT publish is interrupted, rerun
  `python -m research_pipelines.news_features.core.publish_phobert_forward_looking_features`
- the publish builder reuses `phobert_input_articles.parquet`, scores one
  checkpoint batch at a time through the latest winner, and only writes the
  public forward-looking datasets after all shards complete successfully

Run the full feature pipeline after raw news already exists:

```bash
python -m research_pipelines.news_features --full-rebuild
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
  - `phobert_forward_looking_article_features.parquet`
  - `phobert_forward_looking_ticker_day_features.parquet`
  - `ollama_guarded_article_features.parquet`
  - `ollama_guarded_ticker_day_features.parquet`
  - `news_tabular_article_stage.parquet`
  - `news_tabular_article_stage_manifest.json`
  - `embedding_input_articles.parquet`
  - `embedding_input_articles_manifest.json`
  - `embedding_checkpoint/`
  - `phobert_input_articles.parquet`
  - `phobert_input_articles_manifest.json`
  - `phobert_checkpoint/` for resumable batch shards and checkpoint metadata
  - `phobert_forward_looking_checkpoint/` for resumable publish shards and checkpoint metadata
  - `ollama_guarded_input_articles.parquet`
  - `ollama_guarded_input_manifest.json`
  - `ollama_guarded_checkpoint_manifest.json`
  - `ollama_guarded_checkpoint/` for resumable batch shards and checkpoint metadata
- Per-ticker RL-ready files: `data/features/news/predictions/`

## RL Integration

RL now consumes these exports through its own adapter layer. The producer-side merge helper remains `research_pipelines.news_features.core.merge_news_features.merge_news_features(...)`.

The additive local lanes are isolated from the hosted LLM stack:
- PhoBERT outputs and guarded Ollama datasets live under `data/features/news/`
- hosted LLM semantic/event extraction remains under `data/llm_cache/` and `data/features/xs_llm_news_*` as a legacy bootstrap surface, not the default production dependency for the local-news path
