# Session 179 Log - Ollama Residual Prompt Optimization And Gated Backfill (2026-04-25)

## Objective

Assess the completed local BERT head metrics, narrow the remaining local
generator task to what BERT still does not cover well, run a low-resource
Ollama prompt grid, and start a checkpointed backfill only if the path is
operationally sane.

This session did not change the live alpha branch.
It stayed long-only.

## BERT assessment

`source_type` is good enough to treat as the production local source-authority
proxy:
- test F1: `0.7869481765834933`
- test ROC-AUC: `0.9136848733161289`

`article_scope` is usable but noisy:
- test F1: `0.3743236596163306`
- test ROC-AUC: `0.7233646025752045`
- calibrated threshold: `0.28`

Decision:
- use `article_scope` as a probability / routing gate, not as a hard truth
- use `source_type` as the preferred local source-type feature
- do not ask Ollama to own those fields by default

## Ollama prompt optimization

Added a reusable low-resource grid probe:
- `research_pipelines.news_features.core.probe_ollama_guarded_prompts`

The useful probe artifact is:
- `artifacts/run_summaries/20260425_190453_ollama_guarded_prompt_probe.json`
- `artifacts/run_summaries/latest_ollama_guarded_prompt_probe.json`

Sample:
- `8` articles
- `4` hand-curated current raw articles
- `4` legacy-cache labels mapped back to raw articles with real event-family
  labels

Main result:
- winner: `lean_event_only_json_512_300_bottom`
- model: `qwen2.5-coder:3b`
- parse OK: `1.0`
- event-family accuracy: `0.625`
- exact event-family rate: `0.625`
- average seconds/article: `1.7357272136250685`
- articles/second: `0.5761273961427952`
- average eval tokens: `29.125`

Rejected or weakened:
- top-schema placement at `num_ctx=512` is unreliable
- raw full-body prompts are slower and not better
- expert header did not help
- XML and CSV are not safe production formats despite CSV speed
- one-shot, fixed anchors, prefill, and `temperature=0.1` did not beat the
  simple bottom-schema event-only JSON path
- no local Q8 / FP16 Ollama tag was available, so quantization was not varied

## Code changes

Updated the guarded Ollama builder so production defaults now match the
optimized minimal residual contract:
- bottom-schema prompt
- `num_ctx=512`
- `num_predict=64`
- `max_body_words=300`
- `field_set=event_only`
- compact Vietnamese taxonomy hints for event-family labels
- `keep_alive=5m`
- no stop after every article by default

Added operator controls:
- `--field-set`
- `--prompt-variant`
- `--num-ctx`
- `--num-predict`
- `--max-body-words`
- `--checkpoint-rows`
- `--checkpoint-batch-limit`
- `--min-article-scope-prob`
- `--min-source-type-prob`

Added a real job-status file for the Ollama builder:
- `artifacts/job_status/ollama_guarded_publish.json`

Fixed status write behavior so a new run does not retain stale progress keys
from a previous canary.

## Canaries

Ungated 20-article canary:
- input rows: `342135`
- checkpoint rows: `20`
- parse OK in shard: `1.0`
- build seconds: `41.1`
- throughput: about `0.486` unique articles/second
- implication: full ungated run would take roughly `8` days

BERT-gated 20-article canary:
- article-scope gate: `phobert_article_scope_prob_positive >= 0.28`
- input rows after gate: `146872`
- checkpoint rows: `20`
- parse OK in shard: `1.0`
- build seconds: `46.8`
- scoring throughput: about `0.428` unique articles/second
- implication: priority gated run is still multi-day, but far smaller than the
  full corpus and safe to checkpoint

## Running job

Started a detached tmux job:
- session: `ollama_guarded_backfill`
- command:
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features --checkpoint-rows 200 --min-article-scope-prob 0.28`

Expected shape:
- input rows: `146872`
- checkpoint batches: `735`
- first durable checkpoint after roughly several minutes
- outputs finalize only after all checkpoints complete

The run is abort-safe at completed checkpoint batches.

Watchdog checks after launch:
- checkpoint `1 / 735`:
  - unique articles: `200`
  - article-ticker rows: `345`
  - observed rate: about `0.325` unique articles/second
  - GPU: about `2472 MiB / 4096 MiB`, safe temperature
- checkpoint `2 / 735`:
  - unique articles: `400`
  - article-ticker rows: `671`
  - shard parse OK: `1.0`
  - observed rate: about `0.284` unique articles/second
  - GPU: about `2452 MiB / 4096 MiB`, `59C`, safe

Decision:
- leave the job running in tmux
- do not restart just to chase small speed changes; completed checkpoints are
  durable and the machine is not under pressure
- do not start another heavy local model job beside it
- an orphaned duplicate process from an earlier detached launch attempt was
  stopped; only the tmux-managed job remains active

## Verification

Completed:
- `python -m py_compile research_pipelines/news_features/config.py research_pipelines/news_features/core/build_ollama_guarded_features.py research_pipelines/news_features/core/probe_ollama_guarded_prompts.py`
- `pytest research_pipelines/news_features/tests/test_feature_builders.py`
  - `43 passed`

## Next step

Watch `artifacts/job_status/ollama_guarded_publish.json`, the checkpoint
manifest under `data/features/news/datasets/ollama_guarded_checkpoint/`, and
the tmux session `ollama_guarded_backfill`. If throughput remains around the
canary rate and hardware stays below pressure limits, leave the gated backfill
running. Do not start a second heavy local model job beside it.
