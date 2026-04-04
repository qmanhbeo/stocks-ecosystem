# Session 107 Log

## Objective
Run a user-forced exploratory audit of an explicit close-only `upward W / double-bottom reclaim` idea without reopening the dead daily-synthesis queue by default:
- `H278`: formalize the visually identified two-trough reclaim pattern as a small daily price-shape family
- test it first on the canonical next-day standalone signal gate
- only treat it as structurally interesting if it also shows a cleaner slower-horizon diagnostic

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- the repo already treated the current daily-data synthesis queue as exhausted on the current contract
- nearby daily reversal / rebound work already existed:
  - `C12` gap absorption
  - `C13` compression blow-off reversal
  - `H199` second-wave tradability-conditioned rebound states
- but there was no explicit detector for:
  - two distinct troughs
  - a higher second low
  - a neckline reclaim
- so the honest first pass was not portfolio integration:
  - it was a standalone shape audit with a strict canonical gate

## What changed

Added:
- `src/price_shape_research.py`
- `analysis/h278_upward_w_price_shape_audit.py`
- `tests/test_price_shape_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_standalone_signal_upward_w_price_shape.json`
- `artifacts/portfolio_baselines/20260404_161051_h278_upward_w_price_shape_audit_results.parquet`
- `artifacts/portfolio_baselines/20260404_161051_h278_upward_w_price_shape_audit_panel.parquet`

### H278 - Upward-W Daily Price Shape Audit
**Hypothesis:**
If a stock sells off, forms a higher-low double bottom, and then reclaims the interim high, that explicit close-only `upward W` geometry may mark a real dip worth buying.

**Command / code:**
`python analysis/h278_upward_w_price_shape_audit.py`

**Inputs:**
- daily close only
- evaluation window:
  - `2015-2025`
- no `2026+` research rows
- canonical target:
  - next-day `actual` from the standalone signal library contract
- slower diagnostic target:
  - forward `5`-day stock excess return vs `VNINDEX`
- tested variants:
  - `xs_upward_w_base_12d`
  - `xs_upward_w_moderate_12d`
  - `xs_upward_w_reclaim_12d`
  - `xs_upward_w_reclaim_15d`
- decision rule:
  - `PASS` only if a feature survives the canonical next-day standalone gate
  - `MIXED` if no feature survives that gate but at least one feature passes the `5`-day excess-return diagnostic with the same IC / consistency / orthogonality thresholds
  - `FAIL` otherwise

**Saved artifact:**
`artifacts/run_summaries/latest_standalone_signal_upward_w_price_shape.json`

| Metric | Value | Note |
|--------|-------|------|
| tested features | `4` | explicit close-only upward-W variants |
| canonical passers | `0` | no next-day standalone signal survived |
| `5d` support passers | `3` | reclaim / moderate variants passed the slower diagnostic |
| best canonical feature | `xs_upward_w_reclaim_12d` | still failed the canonical gate |
| best canonical feature next-day IC | `-0.0003` | effectively no next-day edge |
| best canonical feature next-day positive years | `5 / 11` | inconsistent for the library contract |
| best slower-horizon feature | `xs_upward_w_reclaim_12d` | strongest `5d` reclaim variant |
| best slower-horizon `5d` IC | `+0.0171` | above the lab's weak-signal threshold |
| best slower-horizon `5d` positive years | `11 / 11` | fully consistent on `2015-2025` |
| best slower-horizon corr vs `S1` | `+0.0248` | low overlap with the main signal |
| best slower-horizon max candidate corr | `0.2960` | under the `0.30` redundancy bar |
| nearest overlap candidate | `C8` | max corr was with `c8_vol_zscore_5d` |

**Result:**
`H278` is mixed.

What failed:
- the explicit `upward W` family does **not** survive as a canonical next-day signal
- even the best variant, `xs_upward_w_reclaim_12d`, had:
  - next-day IC `-0.0003`
  - only `5 / 11` positive years
- the naive monotonic version was actively wrong:
  - `xs_upward_w_base_12d`
  - next-day IC `-0.0060`
  - `5d` IC `-0.0104`

What survived:
- the reclaim-style interpretation is real on a slower horizon
- three variants passed the `5d` forward excess-return diagnostic:
  - `xs_upward_w_reclaim_12d`
  - `xs_upward_w_reclaim_15d`
  - `xs_upward_w_moderate_12d`
- strongest survivor:
  - `xs_upward_w_reclaim_12d`
  - `5d` IC `+0.0171`
  - `11 / 11` positive years
  - corr vs `S1` `+0.0248`
  - max candidate corr `0.2960`

So the eyeballed pattern was not purely imagined, but the contract matters:
- it is **not** a `T+1` library-grade daily alpha atom
- it behaves more like a short swing-horizon reclaim effect

**Verdict: MIXED**

## Branch decision

Do **not** change the live branch.

What Session 107 resolves:
- explicit daily `upward W / double-bottom reclaim` geometry is not enough to reopen the current daily next-day synthesis queue
- the surviving information, if any, belongs to:
  - alternative-horizon offline label work
  - or a future swing / entry contract
- it does **not** belong to:
  - the current next-day signal library
  - the frozen live branch
  - a new portfolio backtest on the current contract

## Validation

Completed before the run:
- `python -m py_compile alpha-research-lab/src/price_shape_research.py alpha-research-lab/analysis/h278_upward_w_price_shape_audit.py alpha-research-lab/tests/test_price_shape_research.py`

Completed for the implementation:
- `pytest -q alpha-research-lab/tests/test_price_shape_research.py`
  - `2 passed`

Completed for the experiment:
- `python analysis/h278_upward_w_price_shape_audit.py`
- read:
  - `artifacts/run_summaries/latest_standalone_signal_upward_w_price_shape.json`

Completed after the note update:
- `pytest -q alpha-research-lab/tests/test_price_shape_research.py alpha-research-lab/tests/test_entry_alpha_research.py`
  - `15 passed`
  - `2` existing pandas `FutureWarning`s

Verdict:
- `H278`: **MIXED**
