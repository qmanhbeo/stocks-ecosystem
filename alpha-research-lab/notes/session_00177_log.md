# Session 177 Log - Binary-Head Threshold And Split Repair (2026-04-25)

## Objective

Diagnose why the first real `phobert_article_scope` canary looked dead, then
patch the binary-head contract so semantic PhoBERT heads stop inheriting the
wrong operating assumptions from the forward-looking lane.

This session did not change the live alpha branch.
It stayed long-only.

## What changed

### Binary-head training contract

Updated the shared binary-head trainer so it now:
- calibrates a positive decision threshold on the validation split instead of
  assuming a hard `0.5` cutoff
- stores that calibrated threshold in the candidate result and winner contract
- can enable positive class weighting per head during training

### Binary-head stage contract

Updated the shared binary-head stage builder so it now:
- supports head-specific split strategies
- records the effective split strategy and split label distribution in the
  stage manifest

Current default posture after this repair:
- `article_scope`:
  - `stratified_random` article-level split
  - positive class weighting enabled
- `source_type`:
  - `stratified_random` article-level split
  - class weighting still disabled by default

### Binary-head publish contract

Updated binary-head publish so it now:
- reads the saved winner threshold
- reapplies the threshold when building article-level boolean labels from the
  stored positive probability
- writes metadata that makes the chosen threshold visible to later sessions

This closes the bug where training/evaluation could be calibrated one way while
publish silently fell back to the old binary decision rule.

## Verified diagnosis

The saved `article_scope` checkpoint was not actually devoid of signal.
The first canary looked broken because the operator contract was wrong:

- the stage split reused the forward-looking date split even though
  `article_scope` is a semantic classifier, not a market-prediction task
- the train / val / test positive rates drifted sharply across that time split
- evaluation then forced a hard `0.5` cutoff

The direct threshold probe on the completed winner showed:
- old test F1 at `0.5` threshold:
  - `0.0009`
- same checkpoint at calibrated threshold `0.04`:
  - test F1 about `0.5794`

So the initial headline result overstated how bad the checkpoint really was.

## Verification

Completed during this pass:
- `python -m py_compile research_pipelines/news_features/config.py research_pipelines/news_features/core/phobert_binary_head_teacher_stage.py research_pipelines/news_features/core/phobert_binary_head_train.py research_pipelines/news_features/core/phobert_binary_head_publish.py research_pipelines/news_features/tests/test_feature_builders.py`
- `python -m pytest research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `42 passed`

What was not executed:
- no fresh real `article_scope` retrain after the contract repair
- no fresh `source_type` canary
- no downstream alpha usefulness audit for the recalibrated `article_scope`
  surface

## Next step

Rerun `article_scope` under the repaired contract first, then publish it, then
start `source_type`:

- `python -m research_pipelines.news_features.core.train_phobert_article_scope --candidate-name phobert_base`
- `python -m research_pipelines.news_features.core.build_phobert_article_scope_features`
- `python -m research_pipelines.news_features.core.train_phobert_source_type --candidate-name phobert_base`
- `python -m research_pipelines.news_features.core.build_phobert_source_type_features`
