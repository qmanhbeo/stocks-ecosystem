# Session 162 Log - C5 Order-Pressure Split (2026-04-22)

## Objective

Take the first honest research pass on the newly unlocked CafeF page-2
order-statistics surface:
- `H340` C5 order-pressure split

Question:
- does same-day posted buy-side order pressure on the positive side of `C5`
  act as a robustness rewrite of bullish insider conviction?
- if it helps, is the useful mechanism volume pressure, count pressure, both,
  or just a lagged carryover effect?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h340_c5_order_pressure_split.py`

### H340 - C5 Order-Pressure Split
**Hypothesis:**
Same-day posted buy-side order pressure from CafeF page 2 may be a stronger
conditioner on the positive side of `C5` than raw insider conviction alone.
If the mechanism is real, positive `C5` rows should be materially cleaner when
same-day posted buy-volume pressure is supportive.

**Command / code:**
`python analysis/h340_c5_order_pressure_split.py`

**Inputs:**
- `data/features/xs_insider_quality_features.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/stock/gia_lich_su_*_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260422_204509_h340_c5_order_pressure_split_research_branch_c5_order_pressure_split.json`

| Metric | Value | Note |
|--------|-------|------|
| target contract | `H108 fwd_rel_5d` | same daily `C5` target used in `H306` |
| dev volume support threshold | `0.1149` | median positive same-day buy-volume ratio on dev positive-`C5` rows |
| baseline C5 avg IC | `+0.0374` | `10 / 11` positive years |
| baseline validation / 2025 pooled IC | `+0.0808 / +0.0028` | current reference line |
| best candidate | `c5_scale_pos_buy_vol_ratio_cap_dev_median` | soft same-day buy-volume-pressure scaling |
| best avg IC | `+0.0693` | `185.5%` of baseline avg IC |
| best positive years | `11 / 11` | consistency lift over raw `C5` |
| best validation / 2025 pooled IC | `+0.0980 / +0.0576` | materially stronger than baseline in both phases |
| best 2025 uplift vs baseline | `+0.0548` | major confirmation robustness gain |
| other pass rows | `3` | same-day buy-volume gate, dual same-day pressure gate, lagged buy-volume gate |
| failed row | `c5_gate_pos_buy_count_ratio_gt_0` | count-only buy pressure flipped negative in `2025` |

**Result:**
The branch passes cleanly as a stronger positive-side rewrite of `C5`.
Same-day posted **buy-volume** pressure sharply improves bullish insider
conviction on the original daily contract. A soft same-day volume rewrite is
the best row, a hard same-day volume gate also passes, a dual same-day
volume-plus-count gate still passes, and a lagged volume gate remains positive
but weaker. Count-only pressure does not survive confirmation, so the surviving
mechanism is not generic order-count crowding.

**Verdict: PASSED**

---

## Branch decision

`H340` says daily order-pressure belongs inside the bullish side of `C5`:
- do **not** treat page-2 order stats as reopened queue / open-fill evidence
- do treat same-day posted buy-volume pressure as a stronger positive-side
  robustness rewrite of raw `C5`
- do **not** promote count-only pressure as the same mechanism

Current preferred rewrite:
- `c5_scale_pos_buy_vol_ratio_cap_dev_median`

If the branch continues, move to:
- `c5-pressure-exec-stack`
  - test whether `H340` and `H306` stack additively or mostly duplicate the
    same positive-side quality mechanism

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h340_c5_order_pressure_split.py`
- ran `python analysis/h340_c5_order_pressure_split.py`
- read the saved run summary and result artifact before promoting the result
