# Session 143 Log — Policy Beneficiary Graph (2026-04-09)

## Objective

Formalize and test the next creative branch after `H322`:
- `H323` policy-beneficiary-graph

Question:
- can a tiny political-economy beneficiary map turn raw CafeF
  public-investment / infrastructure policy news into a sector-specific
  response, without using the unfinished LLM cache?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h323_policy_beneficiary_graph.py`

### H323 - Policy Beneficiary Graph
**Hypothesis:**
Public-investment and infrastructure policy news should benefit explicitly
mapped listed beneficiaries. The first honest pilot should show that direct
public-works beneficiaries outperform the rest of the market on high
policy-intensity days, not merely that the whole market moved.

**Command / code:**
`python analysis/h323_policy_beneficiary_graph.py`

**Inputs:**
- `data/news/cafef/raw/*.jsonl`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/sector_classification.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_161017_h323_policy_beneficiary_graph_research_branch_policy_beneficiary_graph.json`

| Metric | Value | Note |
|--------|-------|------|
| policy unique articles | `5,964` | local CafeF title/summary keyword corpus |
| policy signal days | `744` | articles assigned to first trading day on or after publication |
| direct beneficiaries | `55` tickers | `icb_name2 == Xây dựng và Vật liệu` |
| second-order beneficiaries | `57` tickers | `icb_name2 == Bất động sản` |
| rest basket | `282` tickers | all other matrix names |
| best state | `policy_total_5d_high` | combined public-investment / infrastructure article count over 5d |
| best state decision | `MIXED` | weak beneficiary-state structure only |
| validation / confirmation active days | `96 / 211` | enough coverage |
| validation / confirmation direct `fwd5` edge | `+0.0010 / +0.0023` | direct public-works vs rest on active days |
| validation / confirmation `fwd5` diff-in-diff | `+0.0032 / +0.0007` | active minus inactive direct edge |
| validation / confirmation actual diff-in-diff | `+0.0027 / -0.0006` | confirmation actual response fails |
| validation / confirmation direct minus real-estate `fwd5` | `+0.0048 / -0.0012` | second-order control beats in confirmation |

**Result:**
The branch is not source-blocked: the local CafeF archive has enough raw
public-investment / infrastructure policy coverage for a pilot. But the
predeclared beneficiary response is too weak and unstable to promote. The best
5d total-policy state showed positive direct-public-works `fwd5` edge in both
validation and confirmation, but confirmation actual response turned negative
and the direct basket did not beat the real-estate second-order control in
confirmation.

**Verdict: MIXED**

---

## Branch decision

`H323` does not justify a promotable policy-beneficiary graph on the current
manual map:
- keep the CafeF public-investment policy corpus as usable offline evidence
- do **not** promote a direct public-works beneficiary router
- do **not** expand this branch without a better policy-event source or a more
  explicit beneficiary graph

Next honest queue item:
- `historical-foreign-flow-source`
  - current-data creative branches have produced useful offline evidence, but
    the next high-upside step is a blocked data-source problem rather than
    another local overlay

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h323_policy_beneficiary_graph.py`
- ran `python analysis/h323_policy_beneficiary_graph.py`
- read the saved run summary and detailed results artifacts

The broader test suite was not run.
