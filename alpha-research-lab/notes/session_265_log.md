# Session 265 Log

Date: 2026-05-04
Focus: H387 insider-down rescue

## Summary

- Ran `insider_down_rescue` as the next ranked hidden-flow branch.
- Implemented reusable script:
  `analysis/h387_insider_down_rescue.py`.
- Tested whether positive C5 insider conviction after visible 1d/3d stock
  weakness becomes a stronger delayed-payoff state when confirmed by high C16.
- Used `2016-2025` rows only. No `2026+` rows were used.

## Experiment Contract

Hypothesis:
- Insider buys after visible stock weakness are different from ordinary insider
  buys, especially when C16 support is high.

Fixed state definitions:
- Positive insider: `c5_signal_present > 0` and `c5_ins_relative_size_5d > 0`.
- Visible stock weakness: `stock_return_1d < 0` and `stock_return_3d < 0`.
- Deep weakness: `stock_return_3d <= -0.02`.
- High C16: `order_volume_ratio_rank >= 0.80` with order-pressure availability.

Primary state:
- `insider_down_high_c16`: positive insider plus visible stock weakness plus
  high C16.

Primary controls:
- `insider_buy`: ordinary positive insider rows.
- `insider_high_c16`: positive insider plus high C16, without requiring stock
  weakness.
- `stock_down_high_c16`: stock weakness plus high C16, without requiring
  insider support.

Pass rule:
- PASS if `insider_down_high_c16` or `insider_deep_down_high_c16` has positive
  mean 5d relative payoff and beats all three primary controls by more than
  `+0.002` on average, with at least `60%` positive 5d-lift years and positive
  2025 lifts.
- MIXED if the broader `insider_down` state clears `insider_buy` and
  `stock_down` controls but the high-C16 primary state does not.
- FAIL otherwise.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h387_insider_down_rescue.py
/home/manh/miniforge3/envs/stocks/bin/python analysis/h387_insider_down_rescue.py
```

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_201913_h387_insider_down_rescue_research_branch_insider_down_rescue.json`
- Fold table:
  `artifacts/insider_down/20260504_201913_h387_insider_down_rescue_folds.parquet`
- State table:
  `artifacts/insider_down/20260504_201913_h387_insider_down_rescue_states.parquet`

## Key Metrics

Panel:
- Rows: `755,312`
- Dates: `2,500`
- Tickers: `394`
- Positive-insider share: `1.305%`
- Stock-down share: `29.457%`
- High-C16 share: `18.246%`

State summaries:

| State | WF years | Mean rows | Mean 5d rel payoff | 2025 5d payoff | Mean C16 IC 5d |
|---|---:|---:|---:|---:|---:|
| `stock_down_high_c16` | `8` | `2965.625` | `+0.012197` | `+0.002174` | `+0.09182` |
| `insider_high_c16` | `8` | `185.500` | `+0.009003` | `+0.000720` | `+0.02113` |
| `insider_down_high_c16` | `6` | `35.833` | `+0.008874` | `-0.002143` | `-0.02240` |
| `insider_deep_down_high_c16` | `7` | `40.571` | `+0.007180` | `-0.002757` | `+0.10747` |
| `insider_down` | `8` | `276.125` | `+0.002712` | `-0.007981` | `+0.11849` |
| `insider_buy` | `8` | `1026.625` | `+0.002508` | `-0.004673` | `+0.08400` |
| `stock_down` | `8` | `23511.000` | `+0.002177` | `-0.004790` | `+0.08489` |

Primary lift diagnostics:
- `insider_down_high_c16` beat ordinary `insider_buy` by mean 5d lift
  `+0.00784`, with `6 / 6` positive years and 2025 lift `+0.00253`.
- It did not beat `insider_high_c16` cleanly: mean 5d lift `+0.00087`,
  `3 / 6` positive years, and 2025 lift `-0.00286`.
- It failed the strongest down-control: versus `stock_down_high_c16`, mean 5d
  lift was `-0.00308`, only `1 / 6` years were positive, and 2025 lift was
  `-0.00432`.
- `insider_deep_down_high_c16` also failed versus `insider_high_c16` and
  `stock_down_high_c16`.

## Verdict

H387 `FAILED`.

Interpretation:
- Insider-after-weakness is not the surviving mechanism under this contract.
- High C16 after stock weakness is the stronger control; adding insider support
  does not improve it and weakens 2025.
- H340-style positive-insider plus order-pressure remains the preferred C5
  robustness path; do not open a separate insider-down rescue overlay from H387.

Durable-promotion status:
- branch kill or reframe for the current insider-down rescue contract
- no live branch change
- no shared matrix or recommendation-contract promotion

Next action:
- Continue the broader ranked queue at `fresh_selection_pulse`.

## Verification

- `py_compile` passed for the new script.
- The H387 script completed and wrote saved artifacts.
- The saved JSON summary, state table, and fold table were read before this
  verdict.
- `2026+` data was avoided; run window was `2016-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
