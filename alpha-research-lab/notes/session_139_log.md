# Session 139 Log — Ownership-Network Contagion (2026-04-09)

## Objective

Formalize and test the next current-data branch after `H318`:
- `H319` ownership-network contagion

Question:
- do pre-2023 insider / holder links create a pure cross-ticker spillover state,
  where a ticker with no own direct event or insider shock still benefits when a
  linked neighbor gets one?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h319_ownership_network_contagion.py`

### H319 - Ownership-Network Contagion
**Hypothesis:**
A pre-2023 ownership graph built from shared `ShareHolderCode`,
`TransactionMan`, and a small issuer-family alias layer should carry a real
pure-spillover state on `2023-2025`. If the branch is real, target rows with no
own direct event-v2 or `C5` shock should still outperform when linked
neighbors have same-day event or insider shocks.

**Command / code:**
`python analysis/h319_ownership_network_contagion.py`

**Inputs:**
- `data/features/xs_insider_deals_raw.parquet`
- `data/features/xs_insider_quality_features.parquet`
- `artifacts/run_summaries/latest_research_branch_issuer_lexicon_event_surface.json`
- `artifacts/run_summaries/latest_research_branch_event_v2_predictive_rescreen.json`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_151416_research_branch_ownership_network_contagion.json`

| Metric | Value | Note |
|--------|-------|------|
| union-graph tickers | `358` | shared code + shared name + family alias layer |
| union-panel rows | `229,421` | pure target rows only; own direct shocks excluded |
| primary failed row | `nbr_event` | neighbor same-day event shock does not survive |
| `nbr_event` validation / confirmation actual lift | `-0.0053 / -0.0106` | union graph |
| best mixed row | `nbr_c5` | neighbor positive `C5` shock |
| `nbr_c5` validation / confirmation actual lift | `+0.0031 / +0.0127` | broad but weak |
| `nbr_c5` validation / confirmation `fwd5` lift | `+0.0001 / +0.0011` | positive both, still small |

**Result:**
The broad ownership-network branch did not pass. Same-day neighbor event-v2
shock failed cleanly on the union graph. The only surviving line was weak
neighbor insider contagion: linked tickers with neighbor positive `C5` activity
showed small positive actual lift in validation and stronger confirmation, with
positive but tiny `5d` lift. That is enough for offline evidence, not enough
for a promotable graph router.

**Verdict: MIXED**

---

## Branch decision

`H319` does not justify a broad ownership-network branch on the current stack:
- keep only a weak offline hint that neighbor `C5` activity may matter
- keep neighbor event-v2 contagion closed on the current contract
- do **not** open a graph-based router or additive branch from this result

Next honest current-data queue item:
- `criticality-order-parameter`
  - the network line is now narrowed
  - the next creative current-data branch is the complex-systems activation
    state idea

Next honest acquisition queue remains:
- `historical-foreign-flow-source`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h319_ownership_network_contagion.py`
- ran `python analysis/h319_ownership_network_contagion.py`
- fixed the best-row summary ordering and reran the script
- read the saved run summary and detailed results artifacts
