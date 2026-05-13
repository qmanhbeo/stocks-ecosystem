# Session 301 Log

**Date**: 2026-05-06
**Focus**: H420-H421 experiments

## Summary

- H420 (Rank-Based Weight): FAILED - uniform H413 is best
- H421 (Time-Varying Weights): MIXED - marginal improvement (+0.002)

## H420 - Rank-Based Weight Adjustment

**Hypothesis:**
Top stocks get more S1 weight, bottom get more Volume.

**Command / code:**
```bash
python alpha-research-lab/analysis/h420_rank_based_weight.py
```

| Signal | IC |
|--------|-----|
| S1 alone | +0.118 |
| H413 (uniform 0.1V+0.9S) | +0.135 |
| Top-heavy | +0.131 |
| Top-light | +0.134 |

**Delta (vs H413)**: -0.004 (top-heavy), -0.0003 (top-light)

**Verdict: FAILED** - No position-dependent weighting helps.

---

## H421 - Time-Varying Additive

**Hypothesis:**
Optimal weights changed over years.

**Command / code:**
```bash
python alpha-research-lab/analysis/h421_time_varying_weights.py
```

| Year | Best Weights | IC |
|------|---------------|-----|
| 2018 | 0.10V+0.90S | +0.149 |
| 2019 | 0.10V+0.90S | +0.158 |
| 2020 | 0.20V+0.80S | +0.138 |
| 2021 | 0.15V+0.85S | +0.150 |
| 2022 | 0.25V+0.75S | +0.114 |
| 2023 | 0.10V+0.90S | +0.133 |
| 2024 | 0.10V+0.90S | +0.141 |
| 2025 | 0.10V+0.90S | +0.123 |

| Strategy | IC |
|----------|-----|
| Uniform (0.1V+0.9S) | +0.135 |
| Year-optimized | +0.137 |
| **Delta** | **+0.002** |

**Verdict: MIXED** - marginal improvement (+0.002 noise-level)

- 2020-2022 show different preferences
- But gains are within noise
- Uniform 0.1V+0.9S remains the robust standard

## Key Files

- H420 Script: `alpha-research-lab/analysis/h420_rank_based_weight.py`
- H421 Script: `alpha-research-lab/analysis/h421_time_varying_weights.py`
- Artifacts: `artifacts/run_summaries/rank_based_weight_research_branch.json`, `artifacts/run_summaries/time_varying_weights_research_branch.json`

## Notes

- B46 (rank-based): KILLED
- B47 (time-varying): MIXED
- Standard 0.1V+0.9S holds across all tests