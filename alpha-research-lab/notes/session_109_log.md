# Session 109 Log

## Objective
Run the strict confirmation pass for the mixed H279 shape+breadth router without retuning the gate:
- reuse the frozen H279 shape threshold
- split the observed rows into validation `2023-2024` and confirmation `2025`
- test whether the router still beats the baseline on confirmation

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added:
- `analysis/h280_shape_breadth_confirmation_audit.py`

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_router_shape_breadth_confirmation.json`
- `artifacts/run_summaries/20260405_210450_h280_shape_breadth_confirmation_summary.json`
- `artifacts/portfolio_baselines/20260405_210450_h280_shape_breadth_confirmation_results.parquet`
- `artifacts/portfolio_baselines/20260405_210450_h280_shape_breadth_confirmation_panel.parquet`

### H280 - Shape + Breadth Confirmation Audit
**Hypothesis:**
The mixed H279 shape+breadth router should still beat the baseline on a strict confirmation split if the gate is real rather than a full-panel artifact.

**Command / code:**
`conda run -n stocks python analysis/h280_shape_breadth_confirmation_audit.py`

**Inputs:**
- frozen H279 panel artifact:
  - `artifacts/portfolio_baselines/20260404_151950_h279_shape_breadth_router_panel.parquet`
- frozen H279 gate threshold from:
  - `artifacts/run_summaries/latest_portfolio_router_shape_breadth.json`
- split:
  - validation `2023-2024`
  - confirmation `2025`

**Saved artifact:**
`artifacts/run_summaries/latest_portfolio_router_shape_breadth_confirmation.json`

| Metric | Value | Note |
|--------|-------|------|
| validation router mean adv | `+0.002592` | above baseline |
| validation baseline mean adv | `+0.001631` | reference |
| validation lift | `+0.000962` | real validation lift |
| confirmation router mean adv | `-0.004816` | below baseline |
| confirmation baseline mean adv | `-0.002828` | reference |
| confirmation lift | `-0.001988` | negative confirmation delta |
| confirmation shape-only mean adv | `-0.003746` | still negative |
| frozen shape threshold | `0.020657` | reused from H279 |
| frozen breadth gap min | `0.0` | reused from H279 |

**Result:**
The validation lift did not survive confirmation. The raw shape score also stayed negative on the confirmation slice.

**Verdict: FAILED**

## Branch decision

Do not promote `H279` on the current contract.
Keep the router as parked offline evidence only.
If this family is ever revisited, it needs genuinely new data, a materially different label, or a different gate contract.

## Validation

Completed before the run:
- `conda run -n stocks python -m py_compile alpha-research-lab/analysis/h280_shape_breadth_confirmation_audit.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h280_shape_breadth_confirmation_audit.py`
- read `artifacts/run_summaries/latest_portfolio_router_shape_breadth_confirmation.json`

Verdict:
- `H280`: **FAILED**
