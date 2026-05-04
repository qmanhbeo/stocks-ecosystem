# Session 266 Log

Date: 2026-05-04
Focus: H388 fresh selection pulse

## Summary

- Ran `fresh_selection_pulse` as the next ranked candidate-history branch.
- Implemented reusable script:
  `analysis/h388_fresh_selection_pulse.py`.
- Computed prior top-5 and top-10 candidate-set appearances using only earlier
  panel dates.
- Compared buyable candidate rows that were incumbents, short repeats,
  reappearances after 20+ trading days out, and first-ever appearances.
- Used `2019-2025` rows only. No `2026+` rows were used.

## Experiment Contract

Hypothesis:
- A ticker's first reappearance in the top candidate set after dormancy carries
  more edge than repeated membership or incumbency.

Fixed state definitions:
- `incumbent`: buyable row also in the same top-N set on the previous trading
  day.
- `stale_repeat`: buyable row returning after `2-19` trading days out of the
  same top-N set.
- `fresh20`: buyable row returning after at least `20` trading days out of the
  same top-N set.
- `first_ever`: buyable row with no prior same-top-N appearance in panel
  history.

Pass rule:
- PASS if `top5_fresh20` or `top10_fresh20` has positive mean cycle relative
  return and beats all, incumbent, and stale-repeat controls by more than
  `+0.002` on average, with at least `60%` positive-lift years and positive
  2025 lifts.
- MIXED if only first-ever top-5 appearances clear.
- FAIL otherwise.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h388_fresh_selection_pulse.py
/home/manh/miniforge3/envs/stocks/bin/python analysis/h388_fresh_selection_pulse.py
```

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_202357_h388_fresh_selection_pulse_research_branch_fresh_selection_pulse.json`
- Fold table:
  `artifacts/entry_alpha/20260504_202357_h388_fresh_selection_pulse_folds.parquet`
- State table:
  `artifacts/entry_alpha/20260504_202357_h388_fresh_selection_pulse_states.parquet`

## Key Metrics

State summaries:

| State | WF years | Mean rows | Mean relative return | 2025 relative return | Mean days since |
|---|---:|---:|---:|---:|---:|
| `top5_stale_repeat` | `5` | `364.0` | `+0.002472` | `-0.000650` | `7.29` |
| `top5_fresh20` | `5` | `474.6` | `+0.002309` | `-0.003340` | `145.89` |
| `top10_stale_repeat` | `5` | `853.2` | `+0.002084` | `-0.003336` | `7.07` |
| `top5_all` | `5` | `1169.2` | `+0.001451` | `-0.004788` | `62.44` |
| `top10_fresh20` | `5` | `742.6` | `+0.001401` | `-0.004311` | `103.64` |
| `top10_all` | `5` | `2355.2` | `+0.001314` | `-0.006220` | `35.70` |
| `top10_incumbent` | `5` | `749.8` | `+0.000540` | `-0.010703` | `1.00` |
| `top5_incumbent` | `5` | `315.2` | `-0.000320` | `-0.011265` | `1.00` |
| `top5_first_ever` | `2` | `25.5` | `-0.009024` | `n/a` | `n/a` |

Lift diagnostics:
- `top5_fresh20` beat `top5_all` by mean lift `+0.00086` and `top5_incumbent`
  by `+0.00263`, but failed `top5_stale_repeat` with mean lift `-0.00016` and
  2025 lift `-0.00269`.
- `top10_fresh20` barely beat `top10_all` by `+0.00009` and
  `top10_incumbent` by `+0.00086`, but failed `top10_stale_repeat` with mean
  lift `-0.00068` and 2025 lift `-0.00098`.
- First-ever rows were too sparse and negative.

## Verdict

H388 `FAILED`.

Interpretation:
- Long-dormancy reappearance is not a clean candidate-history edge.
- The stronger candidate-history clue is short repeat after a few days out,
  not first reappearance after long dormancy.
- Do not add a fresh-selection boost or dormancy reappearance policy under the
  current entry-alpha contract.

Durable-promotion status:
- branch kill or reframe for fresh-selection pulse
- no live branch change
- no shared matrix or recommendation-contract promotion

Next action:
- Continue the broader ranked queue at `post_ollama_event_cascade`.

## Verification

- `py_compile` passed for the new script.
- The H388 script completed and wrote saved artifacts.
- The saved JSON summary, state table, and fold table were read before this
  verdict.
- `2026+` data was avoided; run window was `2019-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
