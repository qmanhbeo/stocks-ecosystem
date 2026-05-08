# README for Agents - heuristic-trader

## Overview

Heuristic-trader is a baseline trading system that tests executable trading rules and models based on profit/PnL, not just IC (Information Coefficient). It serves as the bridge between alpha-research-lab (signal discovery) and RL-trading-agent (RL policy learning).

## Current Architecture

```
heuristic-trader/
├── run_backtest.py      # CLI entrypoint with lockbox protection
├── backtest.py          # Core backtest engine (constraint-compliant)
├── signals.py           # Data loaders with lockbox filtering
├── constraints.py       # Vietnam market execution rules
├── cache/               # Pre-computed caches for fast runs
│   ├── price_cache.parquet
│   ├── liquid_lookup.joblib
│   ├── trad_lookup.joblib
│   └── vnindex_baseline.parquet
├── artifacts/           # Output artifacts from runs
│   └── runs/<timestamp>/
│       ├── config.json
│       ├── metrics.json
│       └── daily_equity.parquet
├── notes/               # Session logs and findings
└── session_*.py         # Ad-hoc experiment scripts
```

## Cache Build Workflow

Before running backtests, build caches for fast execution:

```bash
cd /home/manh/stocks-ecosystem/heuristic-trader

# Build price cache (takes ~5 min)
python build_cache.py

# Build tradability lookup (takes ~2 min)
python build_trad_cache.py
```

Caches are stored in `cache/` directory and loaded automatically by `run_backtest.py`.

## Lockbox Rule

**2026 is locked by default** - all data loading functions enforce this:

- Default max end date: `2025-12-31`
- If loaded data contains dates after max_date, the system raises a clear error
- Use `--allow-lockbox` flag to override (only for testing):
  ```bash
  python run_backtest.py --strategy s1_only --end-date 2026-03-31 --allow-lockbox
  ```

This matches the workspace-wide lockbox policy in `alpha-research-lab/src/experiment_contract.py` (`MAX_RESEARCH_YEAR = 2025`).

## Strategy Configuration

Strategies are defined in `strategies/strategies.json`:

```json
{
  "s1_top5_rebal10": {
    "name": "s1_top5_rebal10",
    "signal_type": "s1_only",
    "signal_col": "s1_proba",
    "top_k": 5,
    "rebalance_days": 10,
    "min_hold_days": 3
  }
}
```

### Add a New Strategy

1. Edit `strategies/strategies.json`
2. Add a new entry with required fields: `name`, `signal_type`, `signal_col`, `top_k`, `rebalance_days`, `min_hold_days`

Available signal types: `s1_only`, `c16_only`, `blend_70_30`, `blend_50_50`

## CLI Entrypoint

### Single strategy:
```bash
python run_backtest.py --strategy s1_top5_rebal10 --start-date 2019-01-01 --end-date 2025-12-31
```

### All strategies:
```bash
python run_backtest.py --all-strategies --start-date 2019-01-01 --end-date 2025-12-31
```

This runs all strategies in `strategies.json` and produces a comparison table.

## Artifact Outputs

Each backtest run produces:

```
artifacts/runs/<timestamp>/
├── config.json     # Strategy config and params
├── metrics.json    # Performance metrics
└── daily_equity.parquet  # Daily equity curve (optional)
```

### Multi-Strategy Summary

When running with `--all-strategies`, comparison summaries are also generated:

```
artifacts/summaries/
├── latest_summary.parquet
├── latest_summary.csv
└── <run_id>_summary.parquet
```

Columns: `strategy_name`, `total_return`, `annualized_return`, `sharpe`, `max_drawdown`, `total_trades`, `start_date`, `end_date`

### metrics.json schema:
```json
{
  "strategy_name": "TopK_s1_proba_K5_R10_H3",
  "start_date": "2019-01-01",
  "end_date": "2025-12-31",
  "total_return": 0.8234,
  "annualized_return": 0.0823,
  "sharpe": 1.23,
  "max_drawdown": -0.15,
  "total_trades": 142,
  "n_filtered": 89,
  "per_year": [
    {"year": 2019, "return": 0.12, "days": 250},
    ...
  ]
}
```

## Notes Location

- `notes/live_state.md` - current state, blockers, next actions
- Session logs: `notes/session_*.md`
- Findings: `notes/findings_*.md`
- Dead ends: `notes/dead_ends_*.md`

## Guardrails

1. **Lockbox enforcement**: Default max date is 2025-12-31
2. **Artifact output**: Every run produces traceable metrics
3. **Pre-computed caches**: Fast ~2.5s runs, verified against legacy truth
4. **Benchmark comparison**: VNINDEX baseline included in metrics

## Performance Targets

- Quick run (with pre-computed filters): ~2.5 seconds
- Legacy run (compute on-the-fly): ~5 minutes
- Target: ~100+ return for good strategies

## Smoke Tests

Run safety/audit tests:

```bash
python test_smoke.py
```

Tests verify:
- A: Lockbox blocks 2026 by default
- B: Valid run produces artifacts (config.json, metrics.json, daily_equity.parquet)
- C: Artifact respects --end-date
- D: All loader functions contain lockbox filtering (protects against duplicate-definition regressions)