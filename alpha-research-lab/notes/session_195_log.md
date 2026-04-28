# Session 195 Log - Ollama Residual Backfill Resume (2026-04-28)

## Objective

Continue the evergreen loop after H355 left the cheap current-data side queue
thin. The highest-value blocked branch is now the combined local-news audit,
which requires the guarded Ollama residual surface to finish.

This session resumed the stopped local Ollama backfill under the existing
hardware/memory constraints:
- one heavy job at a time
- `3GB VRAM / 10GB RAM` planning budget
- checkpointed/resumable processing only
- no `2026` predictive experiment from this job state

## Preflight

Checks before resume:
- `nvidia-smi` showed the RTX 3050 available with no heavy competing GPU job
- `ollama ps` showed no active loaded model before resume
- `ps -ef` showed no active `build_ollama_guarded_features` process
- tmux had no `ollama_guarded_backfill` session
- the status file was stale:
  - `status`: `running`
  - `last_heartbeat`: `2026-04-28T06:43:00.767550+00:00`
  - `completed_batches`: `12 / 7344`
  - `processed_input_rows`: `240`

## Action

Started:

`tmux new-session -d -s ollama_guarded_backfill -c /home/manh/stocks-ecosystem/alpha-research-lab '/home/manh/miniforge3/envs/stocks/bin/python -m research_pipelines.news_features.core.build_ollama_guarded_features'`

The command uses the default guarded path:
- model: `qwen2.5-coder:3b`
- context: `512`
- output tokens: `64`
- prompt variant: `lean_json_bottom_v1`
- field set: `event_only`
- article-scope gate: `phobert_article_scope_prob_positive >= 0.28`
- checkpoint rows: `20`

## First Watchdog Result

The resumed job loaded the cached state and skipped the already processed
prefix:
- input rows: `146,872`
- total batches: `7,344`
- cached score rows: `240`
- completed batches at resume: `12`

After the first watchdog wait:
- `completed_batches`: `14 / 7344`
- `processed_input_rows`: `280`
- `unique_article_count`: `280`
- `article_score_rows`: `468`
- `last_heartbeat`: `2026-04-28T16:16:33.476096+00:00`
- `ollama ps`: `qwen2.5-coder:3b`, `100% GPU`, context `512`
- `nvidia-smi`: about `2.8GB / 4GB` VRAM used

## Later Watchdog Result

The longer watchdog interval confirmed the job continued cleanly:
- `completed_batches`: `100 / 7344`
- `processed_input_rows`: `2,000`
- `unique_article_count`: `2,000`
- `article_score_rows`: `3,642`
- `newly_scored_rows`: `1,760`
- `last_heartbeat`: `2026-04-28T17:00:46.512813+00:00`

This keeps the job in healthy long-running status rather than one-off resume
status.

## Branch Decision

Keep the guarded backfill running as the single heavy job. Do not start any
other local ML or GPU-heavy task while it is active.

The next research experiment after completion is still the bounded combined
local-news audit:

`python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking ollama_guarded`

then a downstream combined-news alpha audit before any promotion.

## Memory Changes

Updated:
- `notes/next_steps.md`

No durable alpha finding was added because this is an operational resume, not
an experiment result.

## Verification

Completed:
- checked GPU state with `nvidia-smi`
- checked active processes with `ps -ef`
- checked `ollama ps`
- checked tmux sessions / panes
- resumed in tmux
- confirmed status file progress from batch `12` to `14`

## Next Step

Continue watchdog monitoring. If the job stalls or exits, inspect the tmux pane
and `artifacts/job_status/ollama_guarded_publish.json` before retrying.
