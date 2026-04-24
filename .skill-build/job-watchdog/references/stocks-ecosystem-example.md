# Stocks Ecosystem Example

What this file is for: concrete examples of how `job-watchdog` should supervise
heavy scripts in `/home/manh/stocks-ecosystem/`.

## Workspace Defaults

Treat these as the default local constraints unless a repo documents a stricter
rule:

- WSL machine
- roughly `10GB RAM` for heavy local work
- roughly `3GB VRAM` for local GPU model work
- one heavy managed job at a time

Read:

- `/home/manh/stocks-ecosystem/AGENTS.md`
- `/home/manh/stocks-ecosystem/README.md`

## Example: PhoBERT Forward-Looking Training

Typical entry surface:

- `python -m research_pipelines.news_features.core.train_phobert_forward_looking`

Recommended canonical status file when this surface is materially touched:

- `alpha-research-lab/artifacts/job_status/phobert_forward_looking_train.json`

Structured progress surfaces:

- `alpha-research-lab/artifacts/news_models/phobert_forward_looking/training_manifest.json`
- `alpha-research-lab/artifacts/run_summaries/latest_news_forward_looking_teacher_labels.json`
- `alpha-research-lab/artifacts/run_summaries/latest_news_forward_looking_stage_build.json`
- `alpha-research-lab/artifacts/run_summaries/latest_news_forward_looking_candidate_train.json`
- `alpha-research-lab/artifacts/run_summaries/latest_news_forward_looking_winner_selection.json`
- candidate state and metrics under
  `alpha-research-lab/artifacts/news_models/phobert_forward_looking/runs/`

Hardware posture:

- treat this as GPU-heavy when CUDA is in use
- do not run another heavy local ML job at the same time
- prefer smaller micro-batches and longer runtime over unsafe VRAM pressure

Restart safety:

- usually resumable because manifests and candidate-state outputs exist
- read the current manifest before killing or relaunching

Progress log expectation:

- phase changes such as teacher, stage, candidate train, and winner selection
- candidate-level completion or failure
- width or device reductions if the run is being made safer for hardware

## Example: Hosted LLM Extraction

Typical entry surface:

- `python -u data_tools/extract_llm_news_features.py`

Recommended canonical status file when this surface is materially touched:

- `alpha-research-lab/artifacts/job_status/llm_news_extract.json`

Structured progress surfaces:

- `alpha-research-lab/artifacts/llm_runtime/hosted_model_stats.json`
- per-day outputs in `data/llm_cache/`
- current pending date range inferred from input raw day files versus completed
  cache days

Log rule:

- use the extractor's progress lines only as fallback when the structured view
  does not explain the current state

Restart safety:

- restart-safe because the day-level cache and partial retry behavior bound the
  repeated work

Progress log expectation:

- completed day count
- pending day count
- throughput in articles or days when meaningful
- retries, provider cooldowns, or worker-width reductions

## Example: CafeF-Style Resumable Backfills

Typical entry surfaces:

- `alpha-research-lab/data_tools/fetch_cafef_order_stats.py`
- `alpha-research-lab/data_tools/fetch_cafef_proprietary_trading.py`
- similar per-source historical fetchers

Recommended canonical status files when these surfaces are materially touched:

- `alpha-research-lab/artifacts/job_status/cafef_order_stats_backfill.json`
- `alpha-research-lab/artifacts/job_status/cafef_proprietary_trading_backfill.json`

Structured progress surfaces:

- `data/order_stats/cafef/manifest.json`
- `data/proprietary_trading/cafef/manifest.json`
- equivalent per-source manifest files
- per-ticker cache files under the source root

Health interpretation:

- use `tickers_processed`, `tickers_remaining`, `current_ticker`, and run status
  first
- use raw logs only if the manifest stops moving or the final status is failed

Restart safety:

- generally resumable because the fetchers write per-ticker caches and a compact
  manifest

Progress log expectation:

- ticker completed
- tickers remaining
- current ticker
- retry or backoff events

## Note Rule In This Workspace

Material watchdog interventions should be written into the managed repo's note
stack:

- `alpha-research-lab/notes/` for alpha-lab jobs
- another child repo's notes if that repo owns the job

If the managed repo lacks a coherent note stack, bootstrap the minimum with
`manh-memory-system` before leaving the intervention undocumented.
