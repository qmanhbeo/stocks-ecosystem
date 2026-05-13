# Session 182 Log - Evergreen Queue Pass During Ollama Backfill (2026-04-28)

## Objective

Use the evergreen loop while the guarded Ollama residual builder is running:
- respect the one-heavy-job local hardware constraint
- avoid starting a second GPU/local-model job
- resolve existing saved hypotheses from artifacts before proposing new work
- update the note stack so the next loop starts from the solved queue state

This session did not change the live alpha branch.
It stayed long-only.
It did not use `2026` data for predictive tuning.

## Watchdog state

The guarded Ollama residual backfill is the active heavy job:
- command observed from the status contract:
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features --checkpoint-batch-limit 100`
- status file:
  `artifacts/job_status/ollama_guarded_publish.json`
- model:
  `qwen2.5-coder:3b`
- runtime shape:
  `num_ctx=512`, `field_set=event_only`, `max_body_words=300`
- gate:
  `phobert_article_scope_prob_positive >= 0.28`
- input universe:
  `146872` BERT-gated article rows

Observed safe hardware state during the pass:
- Ollama reported `qwen2.5-coder:3b` loaded on `100% GPU`
- `nvidia-smi` showed about `2604 MiB / 4096 MiB` VRAM and `55C`

Observed resume/cache state:
- checkpoint progress had advanced to completed batch `12 / 7344`
- status showed `skipped_completed_rows=200`
- the next status interval scored only the new `40` rows
- this is consistent with the Session 181 cache/checkpoint repair: completed
  rows are skipped and checkpoint cadence is bookkeeping, not a scoring key

Decision:
- leave the Ollama job running
- do not launch another heavy model train, large backfill, or full research
  rebuild beside it
- use saved artifacts for the evergreen pass

## Existing hypotheses resolved

### H340 - C5 Order-Pressure Split

Saved artifact:
- `artifacts/run_summaries/latest_research_branch_c5_order_pressure_split.json`

Resolved state:
- passed
- best row:
  `c5_scale_pos_buy_vol_ratio_cap_dev_median`
- avg IC:
  `+0.0693`
- validation / confirmation pooled IC:
  `+0.0980 / +0.0576`
- positive years:
  `11 / 11`

Decision:
- same-day posted buy-volume pressure is the preferred daily-state rewrite of
  bullish `C5`
- do not treat count-only pressure as the mechanism

### H341 - C5 Pressure-Exec Stack

Saved artifact:
- `artifacts/run_summaries/latest_research_branch_c5_pressure_exec_stack.json`

Resolved state:
- failed
- best stacked row:
  `c5_scale_pos_exec_x_buy_vol_min_cap_dev_medians`
- avg IC:
  `+0.0654`
- validation / confirmation pooled IC:
  `+0.0935 / +0.0548`
- both are below the H340 baseline

Decision:
- exec-rate stacking does not improve the H340 buy-volume rewrite
- keep H340 as the preferred daily C5 form
- keep H306 only as fallback when order-pressure data is unavailable
- do not spend more cycles stacking the same daily filters

### H342 - PhoBERT Vs Keyword News Gate

Saved artifact:
- `artifacts/run_summaries/latest_research_branch_phobert_news_gate.json`

Resolved state:
- mixed / not promoted
- best PhoBERT row:
  `phobert_sentiment_score_sum`
- avg IC:
  `+0.0082`
- coverage:
  `22.48%`
- gate:
  failed
- sparse keyword `sentiment_cs_z` stayed stronger on its narrow window:
  avg IC `+0.0688`

Decision:
- pooled PhoBERT sentiment alone is not a promoted standalone alpha signal
- this does not kill the local-news branch because the current surface is no
  longer only sentiment
- the next valid test is the combined local surface:
  PhoBERT sentiment, forward-looking, article-scope, source-type, and Ollama
  event-family residual

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-00271-00300.md`
- `notes/signal_library.md`

Key queue corrections:
- removed binary-head training as an immediate queue item because
  `article_scope` and `source_type` are already trained and published
- marked the active heavy job as the guarded Ollama residual backfill
- added a compact evergreen research tree for the current active/solved
  frontier
- recorded H342's standalone PhoBERT sentiment result in the signal library

## Next step

Continue watching the guarded Ollama residual job.
After it finishes, run:

```bash
python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking ollama_guarded
```

Then audit the combined local-news surface before promoting any news feature.

## Verification

No code changed in this session.
Verification was limited to:
- watchdog/status inspection
- saved artifact review
- note-stack consistency updates
