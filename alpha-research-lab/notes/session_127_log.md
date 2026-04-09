# Session 127 Log — Liquidity Router Audit (2026-04-08)

## Objective

Run the next blocked-LLM interim queue item as the smallest honest execution-sleeve audit: test whether a frozen H54 ranker can improve executable economics by routing large-liquidity names to daily `H=1` and mid-liquidity names to weekly `H=5`.

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded execution audit script:
- `analysis/h296_liquidity_router_audit.py`

Saved outputs:
- `artifacts/portfolio_baselines/20260408_180602_h296_liquidity_router_audit_yearly.parquet`
- `artifacts/run_summaries/20260408_180602_h296_liquidity_router_audit_details.json`

### H296 - Liquidity Router Audit
**Hypothesis:**
A frozen H54 ranker may still support a useful execution sleeve if large names run daily `H=1` and mid names run weekly `H=5` under realistic bucket-specific costs.

**Command / code:**
`python analysis/h296_liquidity_router_audit.py`

**Inputs:**
- `data/features/xs_barrier_all_probas_hose_full.parquet`
- rolling liquidity buckets from `data/stock/*.parquet`
- bucket contract:
  - large = top `50` trailing-liquidity ranks
  - mid = ranks `51-200`
  - thin = `>200`
- cost contract:
  - large daily `H=1`: `0.20%` RT
  - mid weekly `H=5`: `0.50%` RT

**Saved artifact:**
`artifacts/run_summaries/20260408_180602_h296_liquidity_router_audit_details.json`

| Metric | Value | Note |
|--------|-------|------|
| raw top-5 thin share | `63.25%` | most raw H54 picks still sit outside the tradable sleeve |
| eligible-all `H=1` avg annual net | `-48.38%` | fill from next eligible large+mid names only |
| eligible-all `H=5` avg annual net | `-23.92%` | same eligible sleeve, weekly only |
| router avg annual net | `-22.26%` | best of the three, but still negative |
| router uplift vs eligible-all `H=1` | `+26.12%` | directionally better allocator |
| router uplift vs eligible-all `H=5` | `+1.66%` | only marginally better than slow-only sleeve |
| router positive years | `4 / 11` | still below a viable continuation bar |
| router eligible slot share | `97.06%` | next-eligible fill works mechanically |
| router executed slot share | `32.86%` | collapses once the slower mid-cap cadence is enforced |

**Result:**
The liquidity router is directionally better than the one-size-fits-all eligible baselines, but it still does not work as a deployable branch. The main problem is structural: raw H54 top-5 requests are still mostly thin (`63.25%`), so once the router respects realistic large/mid sleeves the executed slot share collapses to `32.86%`. The router therefore improves the bad eligible baselines only by acting as a weak allocator over a badly mismatched universe, not by solving the execution problem.

**Verdict: MIXED**

---

## Branch decision

Do **not** continue the liquidity-router branch as an active follow-through.

Branch consequence:
- keep this only as weak execution-allocation evidence
- do not promote it as a real sleeve router
- do not open further blocked-LLM filler branches from this family
- return priority to `llm-cache-fill`

The interim blocked-LLM queue is now exhausted.

---

## Validation

Completed during the pass:
- ran `python analysis/h296_liquidity_router_audit.py`
- read the saved run summary at `artifacts/run_summaries/20260408_180602_h296_liquidity_router_audit_details.json`

Verdict:
- `H296 liquidity router audit`: **MIXED**
