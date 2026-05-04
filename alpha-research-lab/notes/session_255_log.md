# Session 255 Log

Date: 2026-05-04
Focus: H379 dynamic candidate thermodynamics walk-forward experiment

## Summary

- Used the `experimentor` protocol: reusable script, TRUE walk-forward years,
  saved artifacts, and judgment from the saved JSON summary rather than terminal
  output.
- Chose `dynamic_breadth_option` / `dynamic_candidate_thermodynamics` as the
  next best currently testable queue item because it is high-ranked, CPU-only,
  independent of the still-running Ollama job, and naturally compares against
  random K-policy baselines rather than S1/C16 baselines.
- Implemented reusable script:
  `analysis/h379_dynamic_candidate_thermodynamics.py`.
- Ran the script through 2025 only; no `2026+` rows were used for training or
  testing.

## Experiment Contract

- Hypothesis: candidate-panel temperature features can choose whether to hold
  cash, top1, top2, top5, or top10 better than random action policies.
- Data:
  - `data/features/entry_alpha/candidate_panel_daily.parquet`
  - `data/features/entry_alpha/entry_labels_cycle5.parquet`
- Date scope: `2019-2025`.
- Walk-forward protocol: for each test year, train only on prior years; require
  at least two train years, producing test years `2021-2025`.
- Model: tiny predeclared date-level decision-stump router. For each train fold,
  split each candidate-temperature feature into three train-quantile bins, learn
  the best action per bin on train data, select the feature with best train
  mean absolute cycle return, and apply unchanged to the next test year.
- Feature set: score spread, score std, score entropy, buyable counts, blocked
  counts, buyable/liquid breadth, candidate count, selector confidence, and
  selector entry-quality combo.
- Primary benchmark: random invested action policy over `top1/top2/top5/top10`
  with `2,000` random trials per test year.
- Secondary benchmark: random action policy including cash.
- No S1 or C16 baseline comparison was used because this branch is a portfolio
  policy hypothesis, not a direct S1/C16 signal variation.

## Command

```bash
/home/manh/miniforge3/envs/stocks/bin/python analysis/h379_dynamic_candidate_thermodynamics.py
```

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_124306_h379_dynamic_candidate_thermodynamics_research_branch_dynamic_candidate_thermodynamics.json`
- Year table:
  `artifacts/entry_alpha/20260504_124306_h379_dynamic_candidate_thermodynamics_years.parquet`
- Daily policy table:
  `artifacts/entry_alpha/20260504_124306_h379_dynamic_candidate_thermodynamics_daily.parquet`

## Key Metrics

| Test year | Selected feature | Policy abs return | Random invested mean | Lift | Random percentile |
|---:|---|---:|---:|---:|---:|
| 2021 | `liq_open_breadth_all` | `+0.01031` | `+0.01256` | `-0.00225` | `0.1845` |
| 2022 | `full_top10_score_entropy` | `+0.00569` | `-0.00012` | `+0.00581` | `0.9870` |
| 2023 | `candidate_count` | `+0.00908` | `+0.00673` | `+0.00235` | `0.9080` |
| 2024 | `candidate_count` | `+0.00294` | `+0.00207` | `+0.00087` | `0.7005` |
| 2025 | `candidate_count` | `+0.00523` | `+0.00415` | `+0.00108` | `0.6920` |

Aggregate:
- Mean policy absolute cycle return: `+0.00665`.
- Mean random invested absolute cycle return: `+0.00508`.
- Mean lift versus random invested policy: `+0.00157` per cycle.
- Years beating random invested mean: `4 / 5`.
- Years beating random invested p95: `1 / 5`.
- 2025 confirmation lift versus random invested policy: `+0.00108`.
- 2025 confirmation random-invested percentile: `0.6920`.

## Verdict

Verdict: `PASSED`.

Durable-promotion status: offline evidence only, not live promotion.

Reasoning:
- The predeclared tiny router beat the primary random invested baseline on
  mean lift and in `4 / 5` walk-forward years.
- The result is not strong enough for live promotion because the random
  percentile is modest outside 2022/2023, the 2021 fold failed, and only
  `1 / 5` years beat the random p95.
- The strongest stable clue is `candidate_count`: it was selected in `2023`,
  `2024`, and `2025`, usually mapping crowded candidate universes toward top1
  concentration and thinner/mid-count regimes toward top2/top10.

## Next Action

- Promote H379 as offline evidence that candidate-panel temperature contains
  real policy information.
- Do not change the live branch.
- Next honest step, if this branch is continued: run a narrower full-portfolio
  simulation using a predeclared `candidate_count` router versus random K/cash
  policies, with 2026 still excluded from fitting.
- No `signal_library.md` update: this is a portfolio-policy state, not a new
  standalone RL signal.
