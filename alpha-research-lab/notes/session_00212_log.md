# Session 212 Log

Date: 2026-05-03

## Request

Manh asked to run the evergreen research loop indefinitely while the guarded
Ollama residual backfill is running.

## Recovery

- Read the evergreen loop, watchdog, data-operator, and memory-system
  instructions plus the root, data, and alpha-lab workflow docs.
- Recovered current state from `live_state.md`, compact notes, and
  `session_00211_log.md`.
- Found `live_state.md` still described the guarded Ollama backfill as stopped,
  but a tmux session named `ollama_guarded_backfill` was active.

## Backfill Intervention

- The active job status showed an unsafe non-lockbox run:
  - `max_published_at`: empty
  - `ollama_guarded_input_rows`: `146,872`
  - `total_batches`: `7,344`
  - latest unsafe status before stop: `5,188 / 7,344` batches,
    `103,760 / 146,872` processed input rows, and `120` newly scored rows.
- Stopped that tmux run before it could continue into the known post-2025 tail.
- Verified the `120` newly appended score-cache rows in shards
  `score_shard_005183.parquet` through `score_shard_005188.parquet` had
  published timestamps from `2023-12-22` through `2023-12-26`; `0` rows were
  after the 2025 lockbox cutoff.
- Relaunched the checkpoint-safe command in tmux:

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m research_pipelines.news_features.core.build_ollama_guarded_features --max-published-at 2025-12-31T23:59:59+07:00
```

- The rebuilt input manifest is lockbox-safe:
  - `input_rows`: `142,296`
  - `date_filtered_article_count`: `4,576`
  - `max_published_at`: `2025-12-31T23:59:59+07:00`
- Latest status during write-back:
  - status `running`, phase `score`
  - `4,833 / 7,115` checkpoint batches
  - `96,660 / 142,296` processed input rows
  - current safe restart had reused cached rows only so far

## H364 Readiness Pass

- Confirmed H364 is the next bounded audit after the guarded residual surface
  completes.
- Checked required PhoBERT-side ticker-day inputs:
  - sentiment, forward-looking, article-scope, and source-type parquets all
    exist with `1,436,996` rows each and the required columns.
- Confirmed the expected blocker:
  - `data/features/news/datasets/ollama_guarded_ticker_day_features.parquet`
    is still missing until the guarded backfill finalizes.
- Ran `python analysis/h364_combined_local_news_audit.py` as a readiness probe;
  it exited early by design because the checkpoint was incomplete and the final
  Ollama ticker-day dataset was missing.

## Code Guard

- Tightened `analysis/h364_combined_local_news_audit.py` so H364 now blocks if
  the Ollama input manifest is missing the required 2025 lockbox cutoff instead
  of treating an empty cutoff as acceptable.
- Verification:

```bash
python -m py_compile analysis/h364_combined_local_news_audit.py
python -c "import analysis.h364_combined_local_news_audit as h; assert h._max_published_at_exceeds_lockbox('2026-01-01T00:00:00+07:00'); assert not h._max_published_at_exceeds_lockbox('2025-12-31T23:59:59+07:00')"
```

## Next

- Keep exactly one heavy job active: the lockbox-safe
  `ollama_guarded_backfill` tmux job.
- Watch `artifacts/job_status/ollama_guarded_publish.json` and the checkpoint
  manifest until status is complete.
- After completion, aggregate the default local-first news features:

```bash
python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking phobert_article_scope phobert_source_type ollama_guarded
```

- Then run:

```bash
python analysis/h364_combined_local_news_audit.py
```

## Closeout

- Saved artifact read before verdict: no terminal-only verdict; status,
  manifests, schema metadata, and H364's readiness gate were inspected.
- Branch status changed: no alpha branch verdict; operational status changed
  from stale stopped / unsafe resumed run to running lockbox-safe backfill.
- Memory write-back: this session log, `sessions_compact.md`, and
  `live_state.md`.
- Durable findings/dead ends: skipped; this was an operational repair and
  readiness pass, not a new alpha result.
- 2026 data: avoided. The unsafe non-cutoff run was stopped, score-cache residue
  was checked, and the restarted manifest filters out `4,576` post-2025 rows.
- Protocol: long-only and locked 2026 monitor-only posture preserved.
- Heavy-job count: one active heavy job.
