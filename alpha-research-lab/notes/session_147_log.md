# Session 147 Log - CafeF Foreign-Flow Source Audit (2026-04-09)

## Objective

Continue the newly acquired CafeF foreign-flow branch after the `GDKhoiNgoai`
source was found:
- backfill the full local ticker universe
- fix early fetcher defects while monitoring the first run
- run the smallest honest source-quality audit
- run one constrained follow-up if the first raw screen was mixed

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## Data Backfill

Producer:
- `data_tools/fetch_cafef_foreign_flow.py`

Canonical raw root:
- `data/foreign_flow/cafef/`

Final backfill:
- rows:
  - `1,353,462`
- tickers:
  - `404`
- date range:
  - `2001-04-02` to `2026-04-09`
- failures:
  - `0`

Written surfaces:
- `data/foreign_flow/cafef/per_ticker/<TICKER>.parquet`
- `data/foreign_flow/cafef/per_ticker/<TICKER>.meta.json`
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- `data/foreign_flow/cafef/manifest.json`

Two fetcher defects were fixed during the monitored run:
- partial probe caches were being treated as complete if they reached the
  requested end date; per-ticker coverage sidecars now track the requested
  coverage window
- subset reruns were clobbering the combined panel; the script now rebuilds
  the combined panel from all per-ticker caches on disk

Important source caveat:
- CafeF coverage is not uniformly deep by ticker
- `AAA`, `YBM`, and `YEG` had local stock history in the 2015-2025 audit window
  but no CafeF foreign-flow rows in that window

---

### H327 - CafeF Foreign-Flow Source Audit

**Hypothesis:**
CafeF `GDKhoiNgoai` is broad enough to reopen `H95`, and simple lagged
foreign-flow ranks may have standalone predictive content.

**Command / code:**
`python analysis/h327_cafef_foreign_flow_source_audit.py`

**Inputs:**
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- `data/stock/gia_lich_su_<TICKER>_1D.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_214416_h327_cafef_foreign_flow_source_audit_research_branch_cafef_foreign_flow_source_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | source pass, raw feature screen not promotable |
| source row coverage | `98.80%` | 2015-2025 stock-calendar rows with CafeF flow |
| tickers with any flow | `399` | 2015-2025 |
| tickers with >=60% coverage | `399` | 2015-2025 |
| duplicates | `0` | ticker-day keys |
| net mismatches | `0 / 0` | volume / value |
| predictive rows | `817,074` | merged with S1 target, 2015-2025 |
| best feature | `xs_ff_room_scarcity_rank` | near-pass only |
| best dev IC | `+0.0117` | `7 / 8` directional years |
| best validation IC | `+0.0074` | passed weak validation gate |
| best confirmation IC | `-0.0048` | failed 2025 confirmation |
| best corr vs S1 | `-0.0028` | orthogonal, but not stable |

**Result:**
The source-quality gate passed. The first raw / lagged feature screen did not.
The only near-pass was room scarcity, which cleared dev and validation but
flipped in `2025`, so it cannot be promoted.

**Verdict: MIXED**

---

### H328 - CafeF Foreign-Flow Conditioned Screen

**Hypothesis:**
The raw flow signal may only work in high foreign-participation or high
room-scarcity states.

**Command / code:**
`python analysis/h328_cafef_foreign_flow_conditioned_screen.py`

**Inputs:**
- same CafeF foreign-flow and S1 target inputs as `H327`
- predeclared state families:
  - high rolling foreign participation
  - high room scarcity

**Saved artifact:**
`artifacts/run_summaries/20260409_215607_h328_cafef_foreign_flow_conditioned_screen_research_branch_cafef_foreign_flow_conditioned_screen.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | no conditioned flow feature survived |
| merged rows | `817,074` | same predictive universe as H327 |
| best state | `foreign_participation_top30` | best validation absolute IC |
| best feature | `xs_ff_buy_share_5d_rank` | negative orientation |
| best dev IC | `-0.0088` | below standalone gate |
| best validation IC | `-0.0147` | would be interesting alone |
| best confirmation IC | `+0.0079` | sign flipped |
| best corr vs S1 | `-0.0398` | orthogonal but unstable |

**Result:**
Conditioning on high foreign participation or high room scarcity did not rescue
raw buy/sell/net flow ranks. The 2025 confirmation sign flips on the strongest
conditioned rows are enough to close this simple path.

**Verdict: FAILED**

---

## Branch Decision

`H95` is no longer source-blocked:
- real historical CafeF foreign-flow data exists
- full local-universe backfill is complete
- source coverage is good enough for research

But the first two honest predictive screens reject raw flow ranks:
- do not promote `foreign_net_buy`, `buy_share`, `sell_share`, room scarcity, or
  high-participation conditioned variants into the signal library
- do not keep thresholding the same raw ranks to rescue the branch

If the branch continues, it needs a materially different thesis:
- room-change events
- ownership-regime transitions
- foreign-room near-limit discontinuities
- sector-specific foreign ownership pressure

Otherwise, move back to the non-LLM queue.

---

## Validation

Completed during the pass:
- ran `python -m py_compile data_tools/fetch_cafef_foreign_flow.py`
- ran the full CafeF foreign-flow backfill
- ran `python data_tools/fetch_cafef_foreign_flow.py --start-date 2000-01-01 --end-date 2026-04-09 --sleep 0` after metadata was complete and verified `404` cache reuses
- ran `python -m py_compile analysis/h327_cafef_foreign_flow_source_audit.py`
- ran `python analysis/h327_cafef_foreign_flow_source_audit.py`
- read `artifacts/run_summaries/latest_research_branch_cafef_foreign_flow_source_audit.json`
- ran `python -m py_compile analysis/h328_cafef_foreign_flow_conditioned_screen.py`
- ran `python analysis/h328_cafef_foreign_flow_conditioned_screen.py`
- read `artifacts/run_summaries/latest_research_branch_cafef_foreign_flow_conditioned_screen.json`

The broader test suite was not run.
