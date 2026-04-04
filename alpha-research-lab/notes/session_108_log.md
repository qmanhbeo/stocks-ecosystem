# Session 108 Log

## Objective
Audit whether the intraday `upward-W` proxies (fade + repair) become a live-worthy continuation filter when paired with sector breadth gaps, turning the leftover disagreement branch into a controlled router.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added:
- `analysis/h279_shape_breadth_disagreement_router.py`

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_router_shape_breadth.json`
- `artifacts/run_summaries/20260404_151950_h279_shape_breadth_router_summary.json`
- `artifacts/portfolio_baselines/20260404_151950_h279_shape_breadth_router_results.parquet`
- `artifacts/portfolio_baselines/20260404_151950_h279_shape_breadth_router_panel.parquet`

### H279 – Shape + Breadth Router Audit
**Hypothesis:** An intraday `fade/repair` “W shape” signal only works when breadth is collapsing; gating on the shape score plus a nonnegative breadth gap (5-day lag) should raise the 5-day hold advantage and the top quintile hit rate.

**Command / code:**
`python analysis/h279_shape_breadth_disagreement_router.py`

**Inputs:**
- `H258` reduced-shape intraday panel plus the `add_intraday_shape_atoms` proxies
- `data/features/xs_sector_rotation_daily.parquet`
- `data/features/xs_rl_signal_matrix.parquet` via the `load_ohlcv_wide` helper (for returns/backtest)
- gate: shape score above the 90th percentile and `breadth_gap >= 0.0`

**Saved artifact:** `artifacts/run_summaries/latest_portfolio_router_shape_breadth.json`

| Metric | Value | Note |
|--------|-------|------|
| router rows | `13,356` | gate rows on 2023-2025 observed coverage |
| router mean 5d hold adv | `+0.000398` | net positive vs VNINDEX |
| router positive rate | `46.6%` | vs `45.2%` baseline |
| shape-only mean adv | `-0.000120` | shape score alone is slightly negative |
| baseline mean adv | `+0.000278` | raw set, no gate |
| shape threshold | `0.02066` | 90th percentile of the proxy score |
| best gate row | shape score `0.552`, breadth gap `0.125`, 5d adv `+0.06696` |

**Result:** `H279` is mixed.

What failed:
- the raw shape score alone is not live-friendly (`shape_only` mean adv negative)

What survived:
- gating on both the intraday proxies and breadth gap produces a measurable 5-day hold advantage and higher hit rate than the baseline

**Verdict: MIXED**

## Branch decision

Do **not** change the live branch.

What Session 108 resolves:
- gating the shape proxies with breadth gap is promising but not yet canonical; keep it as offline timing evidence and use the saved panel/results for future router work
- do **not** open a new live continuation branch until this gate proves stable in confirmation-level tests

## Validation

Completed before the run:
- `python -m py_compile alpha-research-lab/analysis/h279_shape_breadth_disagreement_router.py`

Completed for the experiment:
- `python analysis/h279_shape_breadth_disagreement_router.py`
- reviewed `artifacts/run_summaries/latest_portfolio_router_shape_breadth.json`

Verdict:
- `H279`: **MIXED**
