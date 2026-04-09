# Session 126 Log — Big-Name Cohort Audit (2026-04-08)

## Objective

Formalize the user-proposed "go through the big HOSE names" idea as the smallest honest pre-LLM-cache audit and test whether a frozen big-name cohort preserves enough of the canonical cross-sectional signal to justify reopening stock-local work.

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded audit script:
- `analysis/h295_big_name_cohort_audit.py`

Saved outputs:
- `artifacts/portfolio_baselines/20260408_175426_h295_big_name_cohort_metrics.parquet`
- `artifacts/portfolio_baselines/20260408_175426_h295_big_name_stock_edges.parquet`
- `artifacts/run_summaries/20260408_175426_h295_big_name_cohort_audit_details.json`

### H295 - Big-Name Cohort Audit
**Hypothesis:**
If stock-local work is still alive anywhere, a frozen big-name HOSE proxy should retain most of the S1/H93 signal and show stable stock-level response ordering across dev and validation.

**Command / code:**
`python analysis/h295_big_name_cohort_audit.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- frozen big-name proxy: current `VN30` constituents

**Saved artifact:**
`artifacts/run_summaries/20260408_175426_h295_big_name_cohort_audit_details.json`

| Metric | Value | Note |
|--------|-------|------|
| signal surface | `S1 / H93` | canonical frozen cross-sectional prior |
| years | `2015-2025` | no `2026+` used |
| big-name proxy size | `30` | frozen `VN30` constituent set |
| full-universe IC | `+0.1491` | benchmark |
| big-name cohort IC | `+0.0823` | only `55.2%` of full IC |
| big-name q5-q1 spread | `+10.84%` | only `51.9%` of full spread |
| big-name top-5 edge | `+5.72%` | only `23.7%` of full top-5 edge |
| rest-of-universe IC | `+0.1553` | slightly above full benchmark |
| rest-of-universe top-5 edge | `+24.00%` | effectively all of the full-universe edge |
| dev->val stock-edge rank rho | `+0.0701` | stock ranking inside big names is not stable |
| stable positive dev+val names | `26 / 30` | positive response exists, but ordering is weak |
| strongest recurring names | `VJC`, `PDR`, `CTG`, `MBB`, `HDB`, `STB` | bounded recipient list, not a broad branch |

**Result:**
The big-name cohort keeps some real signal, but it loses too much of the canonical cross-sectional edge to justify a generic "revert to big names" branch. The remaining universe retains essentially all of the edge. Inside the big-name proxy there is stock-level response heterogeneity, but the dev-to-validation rank ordering is almost flat (`rho +0.0701`), so the broad stock-local ranking is not stable enough to support a new recipient-by-recipient search.

**Verdict: MIXED**

---

## Branch decision

Do **not** reopen a generic big-name / single-stock HOSE branch while the LLM cache is blocked.

Narrowed follow-through only:
- keep `llm-cache-fill` first
- if an interim branch is intentionally opened anyway, restrict it to:
  - execution / liquidity routing on top of the frozen XS prior, or
  - a very small recurrent-recipient audit around the strongest big-name responders

Do not treat H295 as permission to restart broad OHLCV stock-local mining.

---

## Validation

Completed during the pass:
- ran `python analysis/h295_big_name_cohort_audit.py`
- read the saved run summary at `artifacts/run_summaries/20260408_175426_h295_big_name_cohort_audit_details.json`

Verdict:
- `H295 big-name cohort audit`: **MIXED**
