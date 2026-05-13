# Session 208 Log - Resume Ollama Backfill Watchdog (2026-04-29)

## Objective

Resume the guarded Ollama residual backfill and check it twice at 5-minute
intervals under the local hardware contract:
- one heavy local-model job at a time
- `3GB VRAM / 10GB RAM` planning budget
- checkpointed/restart-safe backfill only

## Preflight

Read the current workspace and alpha-lab notes before launch. Live state said
the Session 207 manual stop left no active heavy job, with the last checkpoint
at `755 / 7344` batches and `15,100` processed input rows.

Checks before resume:
- no matching `build_ollama_guarded_features` process was visible
- no `ollama_guarded_backfill` tmux session existed
- `ollama ps` was empty
- `ollama list` included `qwen2.5-coder:3b`
- GPU was idle at `0MiB / 4096MiB`
- RAM/swap were safe
- checkpoint manifest was `in_progress` at `755 / 7344`

## Action

Started:

`tmux new-session -d -s ollama_guarded_backfill -c /home/manh/stocks-ecosystem/alpha-research-lab '/home/manh/miniforge3/envs/stocks/bin/python -m research_pipelines.news_features.core.build_ollama_guarded_features >> artifacts/logs/ollama_guarded_backfill.log 2>&1'`

Startup check:
- tmux session `ollama_guarded_backfill` existed
- status heartbeat refreshed to `2026-04-29T10:26:45.539189+00:00`
- checkpoint state was still `755 / 7344` while the worker skipped completed
  rows
- Ollama loaded `qwen2.5-coder:3b` with context `512`
- GPU memory was about `2318MiB / 4096MiB`

## Watchdog Checks

First 5-minute check:
- status: `running`
- phase: `score`
- heartbeat: `2026-04-29T10:32:31.834008+00:00`
- completed batches: `768 / 7344`
- processed input rows: `15,360`
- unique article count: `15,360`
- article score rows: `28,321`
- Ollama model still loaded on GPU
- GPU memory about `2318MiB / 4096MiB`
- RAM/swap safe

Second 5-minute check:
- status: `running`
- phase: `score`
- heartbeat: `2026-04-29T10:37:43.425262+00:00`
- completed batches: `780 / 7344`
- processed input rows: `15,600`
- unique article count: `15,600`
- article score rows: `28,841`
- newly scored rows since resume: `500`
- Ollama model still loaded on GPU
- GPU memory about `2318MiB / 4096MiB`
- RAM/swap safe

## Decision

The guarded Ollama residual backfill is healthy and should be left running as
the single active heavy local-model job.

Continue monitoring `artifacts/job_status/ollama_guarded_publish.json`,
`artifacts/logs/ollama_guarded_backfill.log`, and tmux session
`ollama_guarded_backfill`.

After completion, the next local-news step remains:

`python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking ollama_guarded`

## Memory Changes

Updated:
- `notes/live_state.md`
- `notes/sessions_compact.md`

Added:
- `notes/session_00208_log.md`

Durable promotion:
- none; this was an operational watchdog pass, not a research result.

## Verification

Completed:
- `tmux ls`
- process-table inspection
- `ollama ps`
- `ollama list`
- `/usr/lib/wsl/lib/nvidia-smi`
- `free -h`
- status-file inspection
- job-log tail inspection
