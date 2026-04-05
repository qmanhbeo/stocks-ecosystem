# Session 115 Log

## Objective
Check whether the current signal-library ranking stays roughly the same if the contract moves from the canonical 1d label to a 5d forward excess-return label.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added:
- `analysis/h285_5d_label_contract_audit.py`

Saved artifacts:
- `artifacts/run_summaries/20260405_223611_h285_5d_label_contract_audit_standalone_signal.json`

### H285 - 5d Label Contract Audit
**Hypothesis:**
The current C4-C14 library and the upward-W family should keep roughly the same ranking under a 5d excess-return contract.

**Command / code:**
`python analysis/h285_5d_label_contract_audit.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/stock/`

**Saved artifact:**
`artifacts/run_summaries/20260405_223611_h285_5d_label_contract_audit_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| merged rows | `826,404` | full 2015-2025 panel |
| tickers | `394` | cross-sectional support |
| dates | `2,748` | 2015-01-05 through 2025-12-31 |
| top1 under 1d | `c13_compress_blowoff_2` | current contract champion |
| top1 under 5d | `c6_contrarian_intra_5d` | new horizon champion |
| top3 overlap | `1 / 3` | low rank stability |
| rank Spearman | `+0.5786` | materially below “same ordering” |
| 1d IC for `c13_compress_blowoff_2` | `+0.0350` | still strong, but no longer top-ranked |
| 5d IC for `c6_contrarian_intra_5d` | `+0.0393` | strongest 5d row in the library |
| 5d IC for `c4_oc_asym_5d` | `+0.0269` | also stronger on 5d than on 1d |
| 5d IC for `xs_upward_w_reclaim_12d` | `+0.0100` | reclaim evidence survives on the slower horizon |
| material change | `True` | the contract shift changes the ranking enough to matter |

**Result:**
The 5d contract is not just a relabel of the 1d contract. The top of the ranking changes, the top-3 overlap is only `1 / 3`, and the W-style reclaim features become more relevant on the slower horizon.

**Verdict: PASSED**

## Branch decision

Park the assumption that the current 1d ordering should be reused unchanged.
The next step is a 5d WF pass on the horizon-specific ordering.

## Validation

Completed before the run:
- `python -m py_compile analysis/h285_5d_label_contract_audit.py`

Completed for the experiment:
- `python analysis/h285_5d_label_contract_audit.py`
- read `artifacts/run_summaries/20260405_223611_h285_5d_label_contract_audit_standalone_signal.json`

Verdict:
- `H285`: **PASSED**
