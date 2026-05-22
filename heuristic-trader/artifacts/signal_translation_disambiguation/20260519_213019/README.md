# Signal vs Translation Disambiguation

- Generated: 2026-05-19T21:31:21
- Source sweep: `/home/manh/stocks-ecosystem/heuristic-trader/artifacts/signal_sweeps/20260519_211758`
- Strategies tested: `s1b_c11_ret_60d_lag_rank_70_30_depth5`

## Experiment 1: Oracle Execution Ablation
- Files: `exp1_oracle_fold_metrics.csv`, `exp1_oracle_summary.csv`
- Question: if filters/execution friction are removed, does benchmark-relative edge turn positive?

## Experiment 2: Translation Sweep
- Files: `exp2_translation_fold_metrics.csv`, `exp2_translation_summary.csv`, `exp2_translation_best_per_strategy.csv`
- Question: can parameterization of the same signal family convert to stable positive excess?

## Experiment 3: Train-Only Regime Router
- Files: `exp3_router_fold_metrics.csv`, `exp3_router_summary.csv`
- Router state: prior-year VNINDEX sign (bull/bear), trained only on earlier folds
- Question: does simple ex-ante regime gating improve mean excess vs always-on canonical?

## Programmatic Summary
- See `summary.json`.