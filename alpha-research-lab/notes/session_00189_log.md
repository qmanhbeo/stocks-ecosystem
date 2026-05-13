# Session 189 Log - Official-Disclosure Bridge Source Audit (2026-04-28)

## Objective

Continue the evergreen loop after H349 failed:
- keep the live alpha branch unchanged
- avoid any predictive use of `2026`
- avoid GPU / Ollama / PhoBERT training jobs
- audit whether the newly present HNX official-disclosure surface is ready for
  an official-source bridge experiment

This was a source audit only. It did not compute alpha IC.

## Branch selection

H315 previously skipped the official-disclosure branch because no local
official-disclosure timestamp history existed. The workspace now has
`data/official_disclosures/hnx/`, so the honest next step was to audit source
readiness before attempting any predictive bridge.

The pass treated current `2026` rows as monitor-only and excluded them from
predictive-readiness counts.

## Experiment

### H350 - Official-Disclosure Bridge Source Audit

**Hypothesis:**
The HNX official-disclosure surface may now be ready to support a bridge
experiment if it has enough pre-2026 timestamp history, transaction extracts,
and overlap with the HOSE research matrix.

**Command / code:**
`python analysis/h350_official_disclosure_bridge_source_audit.py`

**Inputs:**
- `data/official_disclosures/hnx/issuer_universe.parquet`
- `data/official_disclosures/hnx/issuer_news.parquet`
- `data/official_disclosures/hnx/issuer_news_attachments.parquet`
- `data/official_disclosures/hnx/issuer_transaction_disclosures.parquet`
- `data/official_disclosures/hnx/issuer_transaction_attachment_extracts.parquet`
- `data/official_disclosures/hnx/manifest.json`
- `data/features/xs_rl_signal_matrix.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_143701_h350_official_disclosure_bridge_source_audit_research_branch_official_disclosure_bridge_source_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `SKIPPED` | source not ready for predictive bridge |
| universe rows / tickers | `1,220 / 1,220` | full HNX / UPCoM universe exists |
| universe market buckets | `listed 387`, `upcom 833` | from official HNX surface |
| HOSE matrix overlap | `1` | not enough for a HOSE bridge |
| current news rows / tickers | `10 / 2` | latest run scoped to AAV and ADC |
| news date range | `2026-04-07` to `2026-04-23` | monitor-only rows |
| pre-2026 news rows / tickers / dates | `0 / 0 / 0` | no predictive history |
| attachment rows | `13` | latest run sample only |
| transaction disclosure rows | `0` | none in current parquet |
| transaction extract rows | `0` | none in current parquet |
| manifest max tickers | `2` | current outputs are sample-scoped |

**Result:**
The HNX official-disclosure fetcher and full issuer universe are real, but the
current local surface is not a historical research surface. The latest parquet
outputs are scoped to two tickers, contain only current monitor-only rows, have
no pre-2026 history, have zero transaction extracts, and do not overlap the
HOSE matrix enough for a bridge.

**Verdict: SKIPPED**

## Branch decision

Do not run official-disclosure alpha IC yet. The branch remains
acquisition-limited, not analytically unresolved.

The only honest continuation is data work:
- build a broader historical HNX / UPCoM acquisition if that market becomes a
  target
- resolve a HOSE / HSX official-disclosure source before trying to bridge the
  current HOSE matrix
- make the disclosure outputs append-safe or history-preserving before treating
  them as a research surface

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-00271-00300.md`

Added:
- `analysis/h350_official_disclosure_bridge_source_audit.py`

Durable finding:
- `F290`

No signal-library update was made because H350 was a source-readiness gate, not
a signal test.

## Verification

Completed:
- `python -m py_compile analysis/h350_official_disclosure_bridge_source_audit.py`
- `python analysis/h350_official_disclosure_bridge_source_audit.py`
- read the saved run summary and details artifacts

The broader test suite was not run.

## Next step

Continue the evergreen loop with a different current-data mechanism. The next
CPU-light branch from the high-value queue is `sector-ownership-pressure`,
unless a data-acquisition pass is explicitly desired.
