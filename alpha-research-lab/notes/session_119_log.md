# Session 119 Log

## Objective
Test whether the active-book marginal slot label is actually better separated by existing entry-alpha features than the current label contract.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added the H289 marginal-slot label audit script.

Saved artifacts:
- `artifacts/run_summaries/20260405_230116_h289_marginal_slot_label_audit_details.json`
- `artifacts/run_summaries/20260405_230116_h289_marginal_slot_label_audit_standalone_signal.json`

### H289 - Marginal-Slot Label Audit
**Hypothesis:**
The candidate return minus the weakest held return on the same date should be monotone against existing entry-alpha score-gap features.

**Command / code:**
`conda run -n stocks python analysis/h289_marginal_slot_label_audit.py`

**Inputs:**
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260405_230116_h289_marginal_slot_label_audit_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | monotone but weak |
| best feature | `selection_score_gap_to_next_candidate` | strongest existing proxy |
| mean daily IC | `+0.0090` | positive, but small |
| positive years | `5 / 7` | not stable enough |
| q1 label mean | `+0.0300` | lower feature bucket |
| q5 label mean | `+0.0343` | higher feature bucket |
| label mean | `+0.0308` | overall marginal label level |
| label positive rate | `0.6226` | over the filtered 2019-2025 panel |

**Result:**
The marginal-slot label is directionally sensible and monotone, but the existing entry-alpha proxies only separate it weakly. That is not enough to replace the current contract on its own.

**Verdict: MIXED**

## Branch decision

Park the marginal-slot label as a weak evidence line.
The next queue item is `news-marginal-slot`.

## Validation

Completed before the run:
- `conda run -n stocks python analysis/h289_marginal_slot_label_audit.py`

Completed for the experiment:
- read `artifacts/run_summaries/20260405_230116_h289_marginal_slot_label_audit_standalone_signal.json`

Verdict:
- `H289`: **MIXED**
