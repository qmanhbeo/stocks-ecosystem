# Session 95 Log

## Objective
Run the smallest honest entry-side follow-through after Session 94's continuation-veto failure:
- `H266`: test whether the surviving reduced-shape intraday contradiction belongs at breakout entry trust rather than hold-vs-exit continuation handling

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H258` had already passed the reduced-shape CafeF `1H` contract audit on `2023-2025`
- `H259` had already failed as a global continuation / exit predictor on the observed subset
- `H262/H263` had already shown that reduced-shape intraday survives only inside `breakout_followthrough`
- `H264` had already failed deterministic continuation-veto integration:
  - the family-aware router broke on confirmation
  - explicit path-only controls won the ladder
- the surviving structural clue was now narrow:
  - the only family that ever wanted reduced-shape intraday contradiction was `breakout_followthrough`
  - so the honest relocation target was entry trust, not more continuation tuning
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

The honest question was no longer:
- "does reduced-shape intraday rescue continuation?"

It was:
- does signal-day reduced-shape intraday contradiction improve breakout entry selection on the `2023-2025` entry-candidate panel?
- and is the observed breakout subset broad enough that missingness is no longer the main blocker?

## What changed

Added:
- `analysis/h266_breakout_entry_intraday_trust_audit.py`

Updated:
- `src/entry_alpha_research.py`
- `tests/test_entry_alpha_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_entry_alpha_breakout_intraday_trust_audit.json`
- `artifacts/entry_alpha/20260403_121317_h266_breakout_entry_intraday_trust_audit_results.parquet`
- `artifacts/entry_alpha/20260403_121317_h266_breakout_entry_intraday_trust_audit_scored_panel.parquet`
- `artifacts/entry_alpha/20260403_121317_h266_breakout_entry_intraday_trust_audit_subset_panel.parquet`
- `artifacts/entry_alpha/h266_candidate_panel_2023_2025.parquet`
- `artifacts/entry_alpha/h266_base_labels_2023_2025.parquet`

### H266 - Breakout Entry Intraday Trust Audit
**Hypothesis:**
The reduced-shape intraday contradiction that survives only inside `breakout_followthrough` is better interpreted as entry trust: on buyable breakout-like candidate rows, same-day `1H` shape should help decide which next-open entries deserve to be taken.

**Command / code:**
`conda run -n stocks python analysis/h266_breakout_entry_intraday_trust_audit.py`

**Inputs:**
- branch-local `2023-2025` entry candidate / label caches under `artifacts/entry_alpha/`
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_scores_daily.parquet`
- `H258` reduced-shape intraday panel and coverage summary
- thesis-family assignment rebuilt from the existing family components
- breakout-entry subset filters:
  - `entry_thesis_family == breakout_followthrough`
  - `can_buy_next_open == True`
  - observed-subset comparison on rows with reduced-shape intraday available
- model ladder:
  - `selection_baseline`
  - `breakout_path_core`
  - `intraday_shape_core`
  - `intraday_shape_atoms`
  - `intraday_atoms_plus_breakout_path`

**Saved artifact:**
`artifacts/run_summaries/latest_entry_alpha_breakout_intraday_trust_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| breakout buyable rows | `6,216` | full `breakout_followthrough`-like next-open-buyable subset |
| observed breakout rows | `5,869` | rows with reduced-shape intraday observed |
| observed breakout share | `94.42%` | missingness is not the main blocker on this subset |
| best path model | `selection_baseline` | strongest non-intraday control |
| best path validation AUC | `0.5132` | control benchmark |
| best path validation top-quintile cycle return | `-0.00170` | worse than subset mean |
| best path confirmation top-quintile cycle return | `-0.00142` | still negative |
| best intraday model | `intraday_shape_core` | simple reduced-shape winner |
| best intraday validation AUC | `0.5151` | beats the best control |
| best intraday validation top-quintile cycle return | `+0.00233` | positive and above subset mean |
| best intraday confirmation AUC | `0.5593` | stable confirmation ranking |
| best intraday confirmation top-quintile cycle return | `+0.00410` | positive and above subset mean |
| breakout subset mean cycle return | validation `+0.00094`, confirmation `-0.00231` | reference means for the ungated subset |

**Result:**
`H266` passes cleanly on the predeclared entry-trust contract.

The useful interpretation is narrow but real:
- reduced-shape intraday remains family-specific
- the family is still `breakout_followthrough`
- but the information fits better at entry than it did inside deterministic continuation vetoes

This is still not a live-promotion result:
- the test is `2023-2025` only
- the working contract is the observed breakout subset
- and nothing in this session justifies touching the frozen `2026+` branch

What it does justify is one deterministic entry-side follow-through:
- `H267`: test whether a simple breakout-entry gate or downweight built from the `H266` score actually improves the realized small deterministic entry ladder versus the ungated breakout subset

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 95 resolves:
- `H266` passes:
  - breakout-entry trust relocation is a real offline-evidence branch on the current contract
  - reduced-shape intraday does not look globally useful, but it is informative on the observed `breakout_followthrough` entry subset
  - observed coverage is high enough that subset missingness no longer invalidates the branch

Branch effect:
- keep all continuation-veto follow-through closed:
  - `H260/H261` remain closed
  - `H264/H265` remain closed
- promote the breakout-entry trust result as offline evidence only
- keep the live sticky branch unchanged
- the next honest follow-through is:
  - `H267`: deterministic breakout-entry gate integration
- if `H267` fails, the next fallback should be:
  - breakout survivor label rewrite
  - or selector-state / top-k intraday stress routing

## Validation

Completed before the run:
- `python -m py_compile src/entry_alpha_research.py analysis/h266_breakout_entry_intraday_trust_audit.py tests/test_entry_alpha_research.py`
- `pytest -q tests/test_entry_alpha_research.py tests/test_intraday_exit_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h266_breakout_entry_intraday_trust_audit.py`
- read `artifacts/run_summaries/latest_entry_alpha_breakout_intraday_trust_audit.json`

Verdict:
- `H266`: **PASSED**
