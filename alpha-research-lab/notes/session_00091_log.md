# Session 91 Log

## Objective
Run `H257`, the event-density router audit, to test whether alias-expanded event density can gate `H201` into an information-absorption regime without destroying coverage.

This session did not change the live branch.
It did not read `2026+`.

## Starting point

- `H235` confirmed the alias-expanded event surface is novel but operationally sparse.
- The current live sticky branch still runs `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`, and the non-live priority remains acquisition-first timing work.
- The bright-mind queue suggested gating `H201` by event density (the router idea) before designing another selector branch.

## What changed

Added:
- `analysis/h257_event_density_router_audit.py`

Updated:
- nothing else; helper library already contained the necessary alias-event functions.

Saved artifacts:
- `artifacts/run_summaries/latest_timing_event_density_router_audit.json`
- `artifacts/timing_data/20260331_135127_h257_event_density_router_audit_expanded_daily_flags.parquet`
- `artifacts/timing_data/20260331_135127_h257_event_density_router_audit_alias_map.parquet`
- `artifacts/timing_data/20260331_135127_h257_event_density_router_audit_gate.parquet`

## H257 outcome

### Contract audited

- source:
  - alias-expanded event rows from the passed CafeF news archive (H235)
- analysis window:
  - `2023-01-01` through `2025-12-31`
- gate:
  - event density measured as the 5-day rolling sum of `has_company_event_article`
  - threshold: at least 2 alias events over the 5-day window per ticker
- benchmark:
  - the continuation held-position panel
- decision rule:
  - `PASS` if gated coverage ≥ 40%
  - `MIXED` if gated coverage ≥ 25%
  - otherwise `FAIL`

### What happened

- alias density gate coverage:
  - candidate rows: `2,261`
  - gated rows: `14`
  - gating coverage: `0.62%`
  - gating share: `0.62%`
- the routing threshold only fires on a vanishingly small subset; even with a strict gate the router cannot cover the held rows required for `H201`.

### Branch consequence

**Result:** `H257` is **FAILED**.

**Implication:** the event-density router idea is closed on the current stack. The richer event source stays parked, event-surface publication is postponed, and active non-live effort returns to the provisional intraday branch (`H232`) or live monitoring.

## Validation

Completed before the run:
- `python -m py_compile analysis/h257_event_density_router_audit.py src/news_event_source_research.py tests/test_news_event_source_research.py`
- `pytest -q tests/test_news_event_source_research.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h257_event_density_router_audit.py`
- read `artifacts/run_summaries/latest_timing_event_density_router_audit.json`

Verdict:
- `H257`: **FAILED**
