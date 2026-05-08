# Session 00006 — 2026-05-08

## Task

Phase 1: Make heuristic-trader safer and more auditable without large refactors.

## Actions

1. **signals.py** — Added lockbox protection:
   - Added `MAX_RESEARCH_YEAR = 2025` constant
   - Added `_apply_lockbox_filter()` function
   - Added `allow_2026` param to all loader functions
   - Raises clear error if 2026+ included without `--allow-lockbox`

2. **run_backtest.py** (new) — CLI entrypoint:
   - `--strategy`, `--start-date`, `--end-date`, `--top-k`, `--rebalance-days`, `--min-hold-days`
   - `--allow-lockbox` flag for 2026+ testing
   - Auto-generates `artifacts/runs/<timestamp>/config.json`, `metrics.json`, `daily_equity.parquet`
   - Per-year breakdown in metrics.json

3. **README_for_AGENTS.md** — Updated with:
   - Architecture diagram
   - Cache build workflow
   - Lockbox rule
   - CLI usage + artifact schemas

## Verification Results

| Test | Command | Result |
|------|---------|--------|
| Valid run | `--end-date 2025-12-31` | ✅ +41.57%, 416tr, 2.2s |
| Lockbox reject | `--end-date 2026-03-31` | ✅ Error + exit 1 |
| Allow-lockbox | `--end-date 2026-03-31 --allow-lockbox` | ✅ -33.34% |

## Next (queue)

- Phase 2: Import deterministic_portfolio.py from alpha-research-lab
- Add more baseline strategies (not yet implemented)