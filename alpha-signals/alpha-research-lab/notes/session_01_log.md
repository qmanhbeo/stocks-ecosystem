# Session 01 Log — Framework + Baselines (2026-03-16)

## Objectives
Build the experimental infrastructure from scratch. Establish a working train/val/test pipeline and run first baseline models.

## System State (entering)
No system. Empty repo.

## Work Done

### Infrastructure Built
- `run_experiment.py` — one-shot train/eval script
- `configs/` — JSON experiment config schema
- `src/feature_engineering.py`, `src/data_loader.py`, `src/model_factory.py`, `src/evaluator.py`
- Metric: `dir_acc` (direction accuracy vs naive 50%)

### Baseline Experiments

| Config | Model | Features | Test dir_acc |
|--------|-------|----------|-------------|
| baseline_linear | Logistic Regression | 13 OHLCV features | 48.8% |
| xgboost_v1 | XGBoost defaults | 13 OHLCV features | 54.6% |

## Session Conclusions

The XGBoost baseline appears to show 54.6% accuracy — but this is misleading. The metric is raw
directional accuracy vs a fixed 50% baseline, without accounting for market drift. The val period
(2023-2024) was a bull market where simply predicting "up" scores ~59% for free. The metric needs
to be fixed before results are interpretable.

## Critical Lesson Learned
Comparing to 50% is wrong. Must compare to the actual drift rate in each period (`edge_over_naive`).

## Next Session Priority
Fix metric → rerun baselines → test all OHLCV feature combinations with `edge_over_naive`.
