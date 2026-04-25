# Session 178 Log - Binary PhoBERT Train/Publish Completion (2026-04-25)

## Objective

Run the repaired `article_scope` and `source_type` PhoBERT heads sequentially
under watchdog supervision, with safer train-time checkpoints.

This session did not change the live alpha branch.
It stayed long-only.

## Code changes

Updated the binary-head local ML surface so:
- training writes durable mid-epoch checkpoints every
  `phobert_binary_head_training_checkpoint_steps` optimizer steps
- each checkpoint includes model, tokenizer, optimizer, scaler, and trainer
  cursor state
- relaunch resumes from the last in-progress training checkpoint instead of
  restarting the current epoch
- evaluation temporarily disables gradient checkpointing under `no_grad`,
  removing repeated PyTorch checkpoint warnings
- publish invalidates a checkpoint when the top-level stored model id does not
  match the current winner model id, even if the nested run signature matches
- publish scorer progress is less noisy for the 2,000-row checkpoint-batch loop
- the aggregate feature-builder test now uses an isolated temp config instead
  of the real workspace parquet files

## Completed jobs

Executed sequentially on the WSL CUDA runtime:
- `python -m research_pipelines.news_features.core.train_phobert_article_scope --candidate-name phobert_base`
- `python -m research_pipelines.news_features.core.build_phobert_article_scope_features`
- `python -m research_pipelines.news_features.core.train_phobert_source_type --candidate-name phobert_base`
- `python -m research_pipelines.news_features.core.build_phobert_source_type_features`

`article_scope` result:
- winner: `phobert_base`
- model id: `phobert_article_scope::20260425T141320974641+0000::phobert_base`
- threshold: `0.28`
- test F1: `0.3743236596163306`
- test ROC-AUC: `0.7233646025752045`
- publish checkpoint: `172 / 172` complete
- published article rows: `660255`
- published ticker-day rows: `1436996`

`source_type` result:
- winner: `phobert_base`
- model id: `phobert_source_type::20260425T161859367170+0000::phobert_base`
- threshold: `0.81`
- test F1: `0.7869481765834933`
- test ROC-AUC: `0.9136848733161289`
- publish checkpoint: `172 / 172` complete
- published article rows: `660255`
- published ticker-day rows: `1436996`

## Verification

Completed during this pass:
- artifact sanity check confirmed both article-level published parquets contain
  the new trained model ids, not stale fake ids
- `pytest research_pipelines/news_features/tests/test_feature_builders.py`
  - `43 passed`

## Next step

The BERT production surfaces are now built. The next useful experiment is a
downstream news-feature audit: measure whether `article_scope` and
`source_type` add predictive or gating value when joined with the existing
news / RL feature surfaces, without reopening the expensive LLM path.
