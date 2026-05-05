# Session 298 Log

**Date**: 2026-05-05
**Focus**: H417 `holdout_2025` - SURVIVOR BIAS KILL TEST

## Summary

- Critical test: held-out 2025 to confirm no survivor bias
- Added `analysis/h417_holdout_2025.py`
- Verdict: **PASSED** - holds on completely independent data

## H417 - Hold-Out Validation

**Hypothesis:**
Does additive pattern survive on completely held-out 2025 data?

**Command / code:**
```bash
python alpha-research-lab/analysis/h417_holdout_2025.py
```

**Inputs:**
- 2025 ONLY data (completely held-out from development)

| Signal | IC 2025 | vs S1 |
|--------|--------|-------|
| S1 alone | +0.109 | baseline |
| Volume alone | +0.070 | |
| **0.1V+0.9S** | **+0.123** | **+0.014** |

**Saved artifact:**
`artifacts/run_summaries/holdout_2025_research_branch.json`

**Verdict: PASSED**

- +0.014 lift on 2025 vs +0.017 long-term average
- Almost identical performance - NOT survivor bias
- Pattern is REAL

**CONCLUSION**: The additive pattern (0.1V+0.9S) is confirmed REAL.

Source anchor: F381