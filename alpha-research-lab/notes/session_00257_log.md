# Session 257 Log

Date: 2026-05-04
Focus: H380 candidate-count portfolio-policy router

## Summary

- Continued the H379 / PP5 portfolio-policy branch under the `experimentor`
  protocol: reusable script, TRUE walk-forward years, saved artifacts, and
  judgment from the saved JSON summary.
- Implemented reusable script:
  `analysis/h380_candidate_count_policy_router.py`.
- Tested only candidate-count state and predeclared candidate-count transforms:
  raw level, 1-day change, 5-day change, and distance from 20-day trailing mean.
- Compared against random policy baselines only. No S1 or C16 baseline was used
  because this is a portfolio-policy action router, not a direct signal
  variation.
- Used data through `2025` only; no `2026+` rows were used for fitting or
  testing.

## Experiment Contract

- Hypothesis: candidate-count regimes can choose whether the portfolio should
  use `cash`, `top1`, `top2`, `top5`, or `top10` better than random K/cash
  policies.
- Data:
  - `data/features/entry_alpha/candidate_panel_daily.parquet`
  - `data/features/entry_alpha/entry_labels_cycle5.parquet`
- Date scope: `2019-2025`.
- Walk-forward protocol: for each test year, train only on prior years; require
  at least two train years, producing test years `2021-2025`.
- Model: narrow date-level decision-stump router. For each train fold, learn
  candidate-count bin actions using train-only quantile edges. The only
  candidate transforms are `candidate_count`, `candidate_count_delta_1d`,
  `candidate_count_delta_5d`, and `candidate_count_vs_20d_mean`, with
  predeclared bin counts `2`, `3`, and `4`.
- Primary benchmark: `5,000` random K/cash policies over
  `cash/top1/top2/top5/top10`.
- Secondary benchmark: `5,000` random invested policies over
  `top1/top2/top5/top10`.

Pass rule:
- PASS if mean lift versus random K/cash is positive, at least `60%` of WF years
  beat random K/cash mean, 2025 lift versus random K/cash is positive, and mean
  lift versus random invested policy is also positive.
- MIXED if only partial random-baseline consistency.
- Otherwise FAILED.

## Command

```bash
/home/manh/miniforge3/envs/stocks/bin/python analysis/h380_candidate_count_policy_router.py
```

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_125947_h380_candidate_count_policy_router_research_branch_candidate_count_policy_router.json`
- Year table:
  `artifacts/entry_alpha/20260504_125947_h380_candidate_count_policy_router_years.parquet`
- Daily policy table:
  `artifacts/entry_alpha/20260504_125947_h380_candidate_count_policy_router_daily.parquet`

## Key Metrics

| Test year | Selected transform | Bins | Policy abs return | Random K/cash mean | Lift vs K/cash | Random K/cash percentile | Lift vs invested |
|---:|---|---:|---:|---:|---:|---:|---:|
| 2021 | `candidate_count` | 4 | `+0.00991` | `+0.01010` | `-0.00019` | `0.4726` | `-0.00277` |
| 2022 | `candidate_count` | 4 | `+0.00995` | `-0.00010` | `+0.01005` | `0.9998` | `+0.00999` |
| 2023 | `candidate_count` | 3 | `+0.00894` | `+0.00541` | `+0.00353` | `0.9660` | `+0.00213` |
| 2024 | `candidate_count` | 3 | `+0.00294` | `+0.00161` | `+0.00134` | `0.7826` | `+0.00090` |
| 2025 | `candidate_count` | 2 | `+0.00805` | `+0.00333` | `+0.00472` | `0.9790` | `+0.00381` |

Aggregate:
- Mean policy absolute cycle return: `+0.00796`.
- Mean random K/cash absolute cycle return: `+0.00407`.
- Mean lift versus random K/cash policy: `+0.00389`.
- Mean random invested absolute cycle return: `+0.00515`.
- Mean lift versus random invested policy: `+0.00281`.
- Years beating random K/cash mean: `4 / 5`.
- Years beating random K/cash p95: `3 / 5`.
- Years beating random invested mean: `4 / 5`.
- Years beating random invested p95: `2 / 5`.
- 2025 confirmation lift versus random K/cash: `+0.00472`.
- 2025 confirmation lift versus random invested: `+0.00381`.

## Verdict

Verdict: `PASSED`.

Durable-promotion status: offline policy evidence only, not live promotion.

Reasoning:
- The branch passed the predeclared random-baseline gate and strengthened H379's
  durable clue: every walk-forward fold selected raw `candidate_count`, not the
  delta or 20-day mean transform.
- The rule remains offline because it is still a research action router over
  cycle-label artifacts, not a frozen live branch or published consumer
  contract.
- 2021 still failed both random means, so the result should not be treated as a
  universal always-on K router.

## Next Action

- Record H380 as `PP5` offline policy evidence in
  `portfolio_policy_library.md`.
- Remove `dynamic_breadth_option` / PP5 from the active queue because the
  next recommended candidate-count test has now been addressed.
- Do not update `signal_library.md`; this is portfolio-policy state, not a new
  ticker-level alpha signal.
- Next queue item for the evergreen loop is `silent_order_pressure`, unless the
  user asks to stay inside the portfolio-policy branch.
