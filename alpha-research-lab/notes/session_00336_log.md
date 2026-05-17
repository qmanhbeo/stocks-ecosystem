# Session 336 Log — Cross-Sectional Relative State Encoding (2026-05-17)

## Objective

Test the second Eureka hypothesis from the carry-branch completion:
- **H523: Cross-Sectional Relative State Encoding**

Question:
- Does relative state encoding (vs market, vs sector) capture info that absolute encoding loses?
- H510 showed C23 active higher in failure years (2017, 2025) than success (2021, 2022)
- Relative encoding might capture participation pressure better

This session does not read `2026+`.
It does not optimize portfolio construction.

---

## What changed

Added one structural script:
- `analysis/h523_cross_sectional_relative_state.py`

### H523 - cross_sectional_relative_state

**Hypothesis:**
Relative state encoding (vs market, vs sector) captures info that absolute encoding loses.

**Command / code:**
`python analysis/h523_cross_sectional_relative_state.py`

**Inputs:**
- Same panel as H507 (2015-2025, 826,404 rows)
- Sector classification from `data/features/sector_classification.parquet`

**Relative features computed:**
- `market_percentile`: cross-sectional percentile of high_illiq on each day
- `sector_percentile`: percentile within ICB sector on each day
- `relative_active_market_top20`: top 20% market-relative activity (42,238 rows)
- `relative_active_market_top10`: top 10% market-relative activity (41,251 rows)
- `relative_active_sector_top20`: top 20% sector-relative activity (43,323 rows)
- `relative_active_sector_top10`: top 10% sector-relative activity (41,595 rows)
- `high_market_relative_low_absolute`: relative high but absolute low (1,824 rows)
- `high_sector_relative_low_absolute`: sector-relative high but absolute low (2,913 rows)

**Saved artifact:**
`artifacts/run_summaries/20260517_140345_cross_sectional_relative_state_research_branch.json`

| State | IC | Rows | Positive Years |
|-------|----|------|----------------|
| state_router (absolute) | 0.2258 | 12,983 | 11/11 |
| state_onset (absolute) | 0.2222 | 35,103 | 11/11 |
| relative_active_market_top20 | 0.2176 | 42,238 | 11/11 |
| relative_active_market_top10 | 0.2156 | 41,251 | 11/11 |
| relative_active_sector_top10 | 0.2152 | 41,595 | 11/11 |
| relative_active_sector_top20 | 0.2150 | 43,323 | 11/11 |
| absolute_active | 0.2126 | 75,492 | 11/11 |
| state_amplified (absolute) | 0.2061 | 17,228 | 11/11 |
| state_carry (absolute) | 0.2018 | 35,078 | 11/11 |
| all_rows (baseline) | 0.1302 | 826,404 | 11/11 |
| high_market_relative_low_absolute | NaN | 1,824 | 0/11 (too sparse) |
| high_sector_relative_low_absolute | NaN | 2,913 | 0/11 (too sparse) |

**Key comparisons:**
- Baseline IC: 0.1302
- Absolute best IC: 0.2258 (`state_router`)
- Relative market best IC: 0.2176 (`relative_active_market_top20`)
- Relative sector best IC: 0.2152 (`relative_active_sector_top10`)
- **Relative vs Absolute lift: -0.0082** (negative!)

**Result:**
Relative encoding does NOT capture info beyond absolute binary labeling.
- Relative market top20 (0.2176) vs state_router (0.2258) = -0.0082 lift
- Relative sector top10 (0.2152) vs state_router (0.2258) = -0.0106 lift
- The cross states (high relative, low absolute) are too sparse to evaluate

**Verdict: FAILED**

---

## Branch decision

**H523 is a negative finding**: Relative encoding (percentile rank within market/sector) does not outperform absolute binary labeling (active vs quiet).

Key insight: The specific router state (`low C16 × C23`) captures unique information that percentile-rank features do not recover. Participation pressure is captured by the specific mechanism (low C16), not by relative ranking.

Next best action:
- Move to hypothesis 3 in the Eureka queue: **State Duration as Hidden Variable**
- Test if duration features capture regime maturity that static labels lose

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h523_cross_sectional_relative_state.py`
- ran `python analysis/h523_cross_sectional_relative_state.py`
- read saved run summary
- confirmed protocol guardrails: 2015-2025 only, no target-derived states