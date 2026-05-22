# Session 24: Profit-Ready Gate Candidate Emerged

**Date:** 2026-05-19  
**Status:** POSITIVE FINDING (first profit-ready gated candidate family)

## Purpose
Continue experimentation after gate-v1 implementation until a profit-ready configuration appears under explicit policy gates.

## Experiments Run
1. Gate sweep on base top candidates (`run_gate_sweep.py`)
   - Artifact: `artifacts/gate_sweeps/20260519_223627/`
   - Result: no profit-ready rows; baseline `off` remained best for base configs.

2. Gate sweep on translation-best configs (from disambiguation exp2 winners)
   - Artifact: `/tmp/gate_sweep_translation_best/`
   - Result: **6 profit-ready rows**, all from `m_c8_vol_zscore_5d` family.
   - Best row:
     - `tail_med_f30_cd2`
     - mean excess `+4.04%`
     - mean annualized `+17.00%`
     - positive folds `8/11`
     - beating benchmark `6/11`
     - worst fold `-24.16%`

3. Focused local refinement on `m_c8` gate neighborhood
   - 17-variant ad-hoc sweep around floor/cooldown/kill thresholds.
   - Best refined variant:
     - `f0.35_cd2_d0.3_v0.6_u0.8_r0.9`
     - mean excess `+4.27%` (improved)
     - mean annualized `+17.23%`
     - positive folds `8/11`
     - beating benchmark `6/11`

## Promotion/Config Actions
- Added promoted strategy configs:
  - `m_c8_vol_zscore_gate_tail_f30_cd2_k3_h2`
  - `m_c8_vol_zscore_gate_tail_f35_cd2_k3_h2`
  in `strategies/strategies.json`.

## Validation
- WFV for `m_c8_vol_zscore_gate_tail_f35_cd2_k3_h2`:
  - output: `/tmp/wfv_m_c8_gate_f35/`
  - mean annualized: `~17.23%`, positive folds `8/11`
- Profit pipeline readiness/autopsy:
  - `/tmp/profit_pipeline_m_c8_gate_f35/`
  - `profit_ready=1`

## Practical Head-to-Head (Recent Windows)
- 2025 only:
  - `blend_70_30_top5`: `-32.34%` (excess `-70.77%`)
  - `m_c8...f30...`: `+30.00%` (excess `-8.44%`)
- 2024-2025:
  - `blend_70_30_top5`: `-16.88%` (excess `-55.32%`)
  - `m_c8...f30...`: `+41.36%` (excess `+2.92%`)

## Conclusion
- Gate-v1 did not rescue base configs, but it **did** produce a profit-ready candidate when combined with translation-optimized C8 configuration.
- Current best family to continue: `m_c8_vol_zscore_gate_tail_f35_cd2_k3_h2`.

## Notes Audit Gate
- `make notes-audit` -> unavailable (no Make target).
- `python tools/validate_notes_consistency.py --notes-dir notes` -> unavailable (script missing).
- Manual checks passed:
  - session links in `sessions_compact.md` resolve,
  - findings/dead-end header IDs are unique.
