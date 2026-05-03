# Session 214 Log

Date: 2026-05-03

## H365 - Order Standalone Selector (From Ideation Session)

### Hypothesis
Use C16 `order_volume_ratio_rank` as primary selector instead of additive blend.

### Key Finding
H365 was already tested in H358 as the "diagnostic" third leg. Results show:

| Metric | full_library_baseline | order_pressure_only | Delta |
|--------|-------------------|-----------------|-----------------|
| Validation IR | 0.85 | **1.98** | +1.13 |
| Validation relative return | +0.45% | **+1.47%** | +1.02% |
| Cash delta | — | +0.0085 | OK (< 0.02) |
| Turnover | 33.5% | **27.3%** | -6.2% |
| Execution health | PASS | PASS | — |

### Verdict
**PASSED** — C16 standalone beats full_library on validation with higher IR, better relative return, lower turnover, and clean execution health.

### Promotion
Offline evidence only. C16 is now validated as a standalone selector stronger than the full library on execution metrics. Not promoted to live branch (sticky remains active).

### Source
H358 diagnostic run: `artifacts/run_summaries/20260428_212531_h358_order_pressure_portfolio_tradability_audit_research_branch_order_pressure_portfolio_tradability_audit.json`

---

## Next Hypothesis
H366: `order_ceiling_floor_momentum` — C16 + C7 ceiling intersection