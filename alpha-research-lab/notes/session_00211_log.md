# Session 211 Log

Date: 2026-04-30

## Request

Manh asked to continue the guarded Ollama residual backfill and keep the
evergreen research loop running until interrupted.

Later in the same session, Manh asked to check progress, stop Ollama for the
day, commit and push the branch, and run the data backup.

## Recovery

- Read the active repo docs, `live_state.md`, compact findings/dead ends, and
  the previous Ollama status.
- Confirmed no `ollama_guarded_backfill` process was active, `ollama ps` was
  empty, and the GPU was idle.
- Checked the existing guarded Ollama input cache before restart. It had
  `146,872` rows and a max timestamp of `2026-03-31T21:01:39+07:00`, so the
  default restart would have eventually scored `2026+` monitor rows.

## Intervention

- Added `ollama_guarded_max_published_at` plus CLI flag `--max-published-at` to
  the guarded Ollama builder.
- Included the cutoff in the input-cache source signature so changing it
  rebuilds the producer-side input cache and invalidates only incompatible
  checkpoint state.
- Added a targeted regression test covering cutoff filtering.
- Found and corrected a queued command issue: the combined local-news aggregate
  needs `phobert_article_scope` and `phobert_source_type`, not only sentiment,
  forward-looking, and Ollama.
- Added `analysis/h364_combined_local_news_audit.py` as the fixed downstream
  audit to run after the guarded Ollama residual completes and the local-news
  surfaces are aggregated.
- Verification:
  - `python -m py_compile analysis/h364_combined_local_news_audit.py research_pipelines/news_features/config.py research_pipelines/news_features/core/build_ollama_guarded_features.py research_pipelines/news_features/tests/test_feature_builders.py`
  - `python -m pytest research_pipelines/news_features/tests/test_feature_builders.py -k "ollama_guarded_exports_filters_input_cache_by_max_published_at or ollama_guarded_exports_materialize_tagged_only_input_cache_and_reuse_it"`

## Relaunch

Started the backfill in tmux:

```bash
tmux new-session -d -s ollama_guarded_backfill -c /home/manh/stocks-ecosystem/alpha-research-lab '/home/manh/miniforge3/envs/stocks/bin/python -m research_pipelines.news_features.core.build_ollama_guarded_features --max-published-at 2025-12-31T23:59:59+07:00 >> artifacts/logs/ollama_guarded_backfill.log 2>&1'
```

The input cache rebuilt to:

- `input_rows`: `142,296`
- `max published_at`: `2025-12-31T20:40:05+07:00`
- `date_filtered_article_count`: `4,576`
- `total_batches`: `7,115`

Latest checked status before stop: phase `score`, `3,638 / 7,115` checkpoint
batches, `72,760 / 142,296` processed input rows, `45,620` reused from the
existing row-level score cache and `27,140` newly scored after the cache
boundary.

## Stop For Today

- Sent `C-c` to the `ollama_guarded_backfill` tmux session at the user's
  request.
- Confirmed the tmux session closed and no
  `build_ollama_guarded_features` process remained.
- Stopped `qwen2.5-coder:3b` with `ollama stop qwen2.5-coder:3b`.
- Confirmed `ollama ps` is empty and the GPU is idle.
- Marked `artifacts/job_status/ollama_guarded_publish.json` as
  `stopped_by_user` with `stopped_at=2026-04-30T21:23:43+00:00`.

## Next

Keep the guarded Ollama residual backfill stopped unless Manh asks to resume.
When restarted, reuse the checkpoint-safe cutoff command:

```bash
python -m research_pipelines.news_features.core.build_ollama_guarded_features --max-published-at 2025-12-31T23:59:59+07:00
```

After it completes, aggregate the local news surfaces:

```bash
python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking phobert_article_scope phobert_source_type ollama_guarded
```

Then run one bounded downstream audit of the combined local-news surface before
promoting any news feature.

```bash
python analysis/h364_combined_local_news_audit.py
```
