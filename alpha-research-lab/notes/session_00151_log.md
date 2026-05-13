# Session 151 Log — Surrogate Disagreement Residual Audit (2026-04-10)

## Objective

Take the last honest cheap non-API continuation after `H331`:
- `H332` surrogate disagreement residual audit

Question:
- does the remaining short-horizon information in the cheap branch sit in the
  hard tail where the deterministic student disagrees with the teacher or
  routes back to the teacher?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h332_surrogate_disagreement_residual_audit.py`

### H332 - Surrogate Disagreement Residual Audit
**Hypothesis:**
If direct novelty and lexical routers are too lossy, the remaining short-horizon
news reaction may be concentrated in the teacher-fallback / disagreement tail
rather than in the deterministic-safe rows.

**Command / code:**
`python analysis/h332_surrogate_disagreement_residual_audit.py`

**Inputs:**
- `H330` `aggressive_triple` route table
- `H331` teacher-vs-student field disagreement table
- teacher-window market target built from local stock closes vs `VNINDEX`

**Saved artifact:**
`artifacts/run_summaries/20260410_113110_h332_surrogate_disagreement_residual_audit_details.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | disagreement tail does not carry the surviving reaction |
| policy | `aggressive_triple` | predeclared best cost / contract trade-off from `H330` |
| panel rows | `18,640` | ticker-day panel built from article residual states |
| panel dates | `728` | teacher-window dates |
| panel tickers | `2,073` | raw ticker mentions in the teacher window |
| `safe_only_day` activity | `6,209` | deterministic-safe control rows |
| `hard_tail_day` activity | `12,431` | fallback or disagreement residual rows |
| best residual state | `lexical_2plus_day` | smallest failure, still not enough |
| best residual signed uplift vs `safe_only` | `+0.00025 / +0.00062` | `1d / 5d` |
| best residual absolute uplift vs `safe_only` | `-0.00011 / -0.00137` | `1d / 5d`, still negative |
| `hard_tail_day` signed uplift vs `safe_only` | `+0.00017 / +0.00093` | `1d / 5d` |
| `hard_tail_day` absolute uplift vs `safe_only` | `-0.00124 / -0.00303` | `1d / 5d` |

**Result:**
The disagreement tail is not empty. Every residual state had slightly better
signed mean returns than the deterministic-safe control on both `1d` and `5d`.

But that is not the right effect. The disagreement / fallback rows also had
consistently weaker absolute post-news reactions than the `safe_only` rows.
That means the hard tail is not where the surviving reaction lives; if
anything, the deterministic-safe rows are the stronger reaction subset on the
current teacher window.

**Verdict: FAILED**

---

## Branch decision

`H332` closes the cheap non-API surrogate branch on the current contract:
- do **not** continue novelty-only tuning
- do **not** continue direct lexical routing
- do **not** continue disagreement-residual mining on the same teacher window

If this branch is ever revisited, it needs:
- more cache years
- new labels
- or a materially different contract

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h332_surrogate_disagreement_residual_audit.py`
- ran `python analysis/h332_surrogate_disagreement_residual_audit.py`
- read `artifacts/run_summaries/latest_research_branch_surrogate_disagreement_residual_audit.json`
- inspected the saved panel and result parquet artifacts

The broader test suite was not run.
