# Session 132 Log — Insider Follow-Through Split (2026-04-09)

## Objective

Take the next honest current-data branch after `H305`:
- `H306` insider follow-through split

Question:
- is low execution follow-through on the positive side of `C5` a pollutant that
  should be gated or downweighted, rather than treated as part of the same
  bullish insider-conviction signal?

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h306_insider_followthrough_split.py`

### H306 - Insider Follow-Through Split
**Hypothesis:**
`xs_ins_exec_rate_5d` is not standalone alpha, but it may still matter as a
conditioning variable on the positive side of `C5`. Weak bullish follow-through
may dilute the real insider-buy conviction signal.

**Command / code:**
`python analysis/h306_insider_followthrough_split.py`

**Inputs:**
- `data/features/xs_insider_quality_features.parquet`
- `data/features/event_surface_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/stock/gia_lich_su_*_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_103000_h306_insider_followthrough_split_research_branch_insider_followthrough_split.json`

| Metric | Value | Note |
|--------|-------|------|
| target contract | `H108 fwd_rel_5d` | original `C5` standalone target |
| dev exec-rate threshold | `0.20` | median positive-buy exec rate in `2015-2022` dev |
| baseline C5 avg IC | `+0.0374` | `10 / 11` positive years |
| baseline validation / 2025 pooled IC | `+0.0808 / +0.0028` | current reference line |
| best candidate | `c5_scale_pos_exec_cap_dev_median` | positive side scaled by clipped `exec_rate / 0.20` |
| best avg IC | `+0.0379` | `101.3%` of baseline avg IC |
| best positive years | `11 / 11` | improves consistency over raw `C5` |
| best validation / 2025 pooled IC | `+0.0740 / +0.0119` | slightly lower validation, materially better 2025 |
| best 2025 uplift vs baseline | `+0.0091` | confirmation robustness gain |
| second pass row | `c5_gate_pos_exec_gt_0` | zero bullish rows with no follow-through |
| second pass avg IC | `+0.0368` | `98.6%` retention, `11 / 11` positive years |
| pass rows / mixed rows | `2 / 0` | branch passes cleanly |

**Result:**
The branch passes as a robustness rewrite, not as a brand-new signal family.
Two predeclared rewrites improved `C5` consistency from `10 / 11` to `11 / 11`
positive years and lifted `2025` confirmation IC while retaining essentially all
of the baseline average IC. The better rewrite is the soft version:
`c5_scale_pos_exec_cap_dev_median`.

**Verdict: PASSED**

---

## Branch decision

`H306` says execution follow-through belongs inside the bullish side of `C5`:
- do **not** treat `xs_ins_exec_rate_5d` as standalone alpha
- do treat weak positive-side follow-through as a pollutant on raw `C5`
- prefer the soft rewrite:
  - `c5_scale_pos_exec_cap_dev_median`
- keep the hard gate
  - `c5_gate_pos_exec_gt_0`
  as a simpler fallback

If the current-data queue continues, move to:
- `event-novelty-half-life-without-llm`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h306_insider_followthrough_split.py`
- ran `python analysis/h306_insider_followthrough_split.py`
- read the saved run summary and details artifact
