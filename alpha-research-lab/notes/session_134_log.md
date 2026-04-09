# Session 134 Log — Stock-Local Predictability Atlas (2026-04-09)

## Objective

Take the next honest current-data branch after `H307`:
- `H308` stock-local predictability atlas

Question:
- does a full HOSE atlas reveal any non-random stable tail of recipient stocks
  worth deeper interrogation, or does the apparent ticker-level structure stay
  too weak to justify reopening stock-local alpha hunting?

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h308_stock_local_predictability_atlas.py`

### H308 - Stock-Local Predictability Atlas
**Hypothesis:**
The lab may still have a tiny recurrent-recipient tail even though broad
single-stock OHLCV mining is dead. If so, a full-HOSE atlas should show a
stable dev->validation tail after null control and multiple-testing discipline,
with coherent local-structure diagnostics rather than random positive noise.

**Command / code:**
`python analysis/h308_stock_local_predictability_atlas.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/stock/gia_lich_su_*_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_110645_h308_stock_local_predictability_atlas_research_branch_stock_local_predictability_atlas.json`

| Metric | Value | Note |
|--------|-------|------|
| qualified tickers | `45` | predeclared minimum selected-day coverage in all three phases |
| observed dev->validation rank rho | `+0.1018` | ticker ordering stability on recipient edge |
| null `p95` rank rho | `+0.2588` | within-day permutation control |
| empirical rank-stability p | `0.3134` | no global stable ordering |
| FDR survivors (`q <= 0.10`) | `0` | no null-controlled recurrent tail |
| nominal tail (`p <= 0.10`, conf > 0) | `7` | `AAM, VTB, SRF, SHA, VID, TMT, DTA` |
| diagnostic corr: overnight share | `-0.5361` | stronger tail sits in less gap-dominant names |
| diagnostic corr: zero-range rate | `-0.5706` | stronger tail sits in smoother names |
| diagnostic corr: median traded value | `+0.4491` | stronger tail sits in more liquid names |

**Result:**
The broad stock-local branch does **not** survive null control. There are no
FDR survivors and the dev->validation ticker-edge ranking is not stronger than
the permutation null. But the atlas does leave a small nominal tail of
recurrent recipients, and that tail clusters in smoother, less gap-dominant,
more liquid names rather than in obviously noisy random-walk candidates.

**Verdict: MIXED**

---

## Branch decision

`H308` closes the broad stock-local branch again:
- do **not** reopen generic per-stock OHLCV alpha hunting
- do keep the atlas only as a bounded diagnostic line around the nominal tail:
  - `AAM, VTB, SRF, SHA, VID, TMT, DTA`
- interpret that tail as recipient-state evidence, not as standalone stock-local
  alpha
- if the queue continues, move to:
  - `issuer-lexicon-event-surface`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h308_stock_local_predictability_atlas.py`
- ran `python analysis/h308_stock_local_predictability_atlas.py`
- read the saved run summary and details artifact
