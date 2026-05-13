# Session 324 Log — H510 Bull Participation State Audit (2026-05-11)

## Objective

Determine whether existing C23/C24/C25/C26-family latent/emission states explain
heuristic-trader's bull-market cash-drag failure.

## Context

heuristic-trader filed an appeal after execution validation found:
- Failure bull years: 2017, 2025
- Success / contrast years: 2021, 2022
- Failure mechanism in heuristic-trader: high cash / under-participation
- Key question: Is this caused by missing latent participation states in the
  alpha lab, or by execution/portfolio construction?

## Method

- Reused H509 clustered panel:
  `artifacts/research_branches/20260510_144827_latent_state_discovery_clustered_panel.parquet`
- Used k=6 latent cluster assignment from H509
- Panel rows: 826,404
- Years: 2015-2025
- No 2026 used
- No target-derived state construction
- No portfolio construction
- No parameter optimization
- Compared:
  - failure bull years: 2017, 2025
  - success contrast years: 2021, 2022
  - secondary years: 2019, 2024

## Artifact Path

`artifacts/h510_bull_participation_state_audit/20260511_174848/`

Files:
- `year_state_summary.csv`
- `yearly_ic_by_state.csv`
- `focus_years_summary.csv`
- `transition_summary.csv`
- `focus_year_comparison.csv`
- `summary.json`
- `README.md`

## Key Results

| Year | Category | C23 Share | All-rows IC |
|------|----------|-----------|-------------|
| 2017 | failure_bull | 5.82% | 0.149 |
| 2025 | failure_bull | 3.28% | 0.109 |
| 2021 | success_contrast | 3.61% | 0.123 |
| 2022 | success_contrast | 4.33% | 0.082 |

- Failure bull avg C23 share: 4.55%
- Success contrast avg C23 share: 3.97%
- C23 active state is NOT missing in failure bull years; it is slightly higher.
- 2017 had stronger IC than 2021/2022, despite being a heuristic-trader
  cash-drag failure year.
- C24 share is lower in failure years than success years, but the difference is
  small and not enough to support a clean export thesis.

## Conclusion

**NEGATIVE FINDING / Case C**

Latent state ecology does NOT explain heuristic-trader bull-market cash drag.

The lab did not find evidence that 2017/2025 failed because C23/C24-style
active participation states were missing.

Instead, the evidence points back toward heuristic-trader execution /
portfolio construction / filter mechanics.

**Interpretation**

- Do NOT export a latent participation regime from H509/H510 yet.
- Do NOT claim C23/C24/C25/C26 solve the cash-drag issue.
- The likely next investigation should move back to heuristic-trader:
  - portfolio construction
  - exposure sizing
  - filter impact
  - why positive IC still leads to low invested %
  - whether filters reject too many candidates
  - whether position sizing leaves residual cash
  - whether top-k construction fails to stay fully invested