# Session 163 Log - C5 Pressure-Exec Stack (2026-04-22)

## Objective

Take the exact narrow follow-through after `H340`:
- `H341` C5 pressure-exec stack

Question:
- does layering `H306` exec-rate follow-through on top of the new `H340`
  same-day buy-volume rewrite materially improve positive-side `C5`?
- or does the new buy-volume rewrite already capture the usable daily-state
  quality on the current contract?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h341_c5_pressure_exec_stack.py`

### H341 - C5 Pressure-Exec Stack
**Hypothesis:**
If `H306` and `H340` capture different positive-side quality mechanisms, then a
soft stacked rewrite or a conservative intersection gate should beat the `H340`
buy-volume baseline cleanly enough to become the new preferred form of bullish
`C5`.

**Command / code:**
`python analysis/h341_c5_pressure_exec_stack.py`

**Inputs:**
- `data/features/xs_insider_quality_features.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/stock/gia_lich_su_*_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260422_205307_h341_c5_pressure_exec_stack_research_branch_c5_pressure_exec_stack.json`

| Metric | Value | Note |
|--------|-------|------|
| target contract | `H108 fwd_rel_5d` | same daily `C5` contract used in `H306/H340` |
| branch baseline | `c5_scale_pos_buy_vol_ratio_cap_dev_median` | exact `H340` best row |
| dev exec threshold | `0.20` | inherited from positive dev `exec_rate` rows |
| dev volume support threshold | `0.1149` | inherited from positive dev buy-volume-support rows |
| best stacked row | `c5_scale_pos_exec_x_buy_vol_min_cap_dev_medians` | soft stack using the weaker clipped support score |
| best stacked avg IC | `+0.0654` | below the `H340` baseline `+0.0693` |
| best stacked validation / 2025 pooled IC | `+0.0935 / +0.0548` | both below the `H340` baseline |
| best stacked retention vs baseline | `94.3%` | below the predeclared mixed bar |
| hard intersection row | `c5_gate_pos_buy_vol_gt_0_exec_gt_0` | also below baseline in both validation and confirmation |
| old `H306` context row | `c5_scale_pos_exec_cap_dev_median` | materially weaker than the `H340` baseline head-to-head |

**Result:**
The branch fails cleanly. Neither the soft stacked rewrite nor the hard
intersection gate beat the `H340` baseline on the locked `2015-2025` daily
contract. The best stacked row preserved `11 / 11` positive years, but still
missed the `H340` baseline on avg IC retention, validation pooled IC, and
confirmation pooled IC. This means `H340` already captures the usable
daily-state quality, and layering `H306` on top does not buy enough to justify
more complexity.

**Verdict: FAILED**

---

## Branch decision

`H341` closes the stack question on the current daily contract:
- keep `H340` as the preferred daily-state rewrite of bullish `C5`
- keep `H306` only as the fallback when order-stats data is unavailable
- do **not** stack exec-rate and buy-volume pressure by default

If this family continues, move away from more same-contract daily stacking.
The next honest non-LLM continuation is back on the official-source line:
- `hsx-official-bridge`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h341_c5_pressure_exec_stack.py`
- ran `python analysis/h341_c5_pressure_exec_stack.py`
- read the saved run summary and result artifact before promoting the result
