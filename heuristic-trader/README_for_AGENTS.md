# README for Agents - heuristic-trader

## Overview

Heuristic-trader is a baseline trading system that tests executable trading rules and models based on profit/PnL, not just IC (Information Coefficient). It serves as the bridge between alpha-research-lab (signal discovery) and RL-trading-agent (RL policy learning).

## Promotion Contract (Lab -> Heuristic)

Shared status vocabulary across lab and heuristic-trader:
- `RESEARCH_CANDIDATE`
- `LAB_PROMOTED_PENDING_EXECUTION`
- `EXECUTION_VALIDATED`
- `FINAL_PROMOTED`
- `OVERRIDE_PROMOTED`

Contract:
- alpha-research-lab can promote up to `LAB_PROMOTED_PENDING_EXECUTION` using
  signal-quality + light execution-readiness evidence.
- heuristic-trader owns execution validation (`risk_policy.py` and canonical
  WFV/profit artifacts).
- `FINAL_PROMOTED` requires explicit post-validation decision logging.
- `OVERRIDE_PROMOTED` is allowed only with an explicit note justification
  (reason, owner, date, rollback trigger, review date).

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
├── artifacts/           # Outputs (scratch + canonical)
│   ├── runs/<timestamp>/        # scratch single-run outputs
│   ├── walk_forward/<timestamp>/ # scratch walk-forward outputs
│   └── canonical_wfv/           # decision-grade deterministic WFV outputs
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

## Data Horizon Rule

- Default start rule: use the earliest available date supported by the loaded signal surfaces and execution tradability contract.
- Do not hard-code `2015` starts in loaders/backtests.
- Use narrower windows only when an experiment explicitly requires them (for example, a holdout comparability run).

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

Available signal types: `s1_only`, `c16_only`, `c17_only`, `c17_active_boost`, `c18_only`, `s1_low_breadth`, `s1_active_low_breadth`, `blend_70_30`, `blend_50_50`, `blend_70_30_low_breadth`

Optional risk-gate fields (tail-first exposure scaling):
- `gate_enabled` (bool)
- `gate_profile` (string, e.g. `tail_first_v1`)
- `exposure_floor` (float, e.g. `0.20`)
- `exposure_ceiling` (float, e.g. `1.00`)
- `kill_switch_thresholds` (object with optional keys: `drawdown`, `volatility`, `underfill_ratio`, `reject_ratio`)
- `cooldown_rebalances` (int)

## CLI Entrypoint

### Single strategy:
```bash
python run_backtest.py --strategy s1_top5_rebal10 --start-date 2007-01-02 --end-date 2025-12-31
```

### All strategies:
```bash
python run_backtest.py --all-strategies --start-date 2007-01-02 --end-date 2025-12-31
```

This runs all strategies in `strategies.json` and produces a comparison table.

## Artifact Outputs

### Artifact Policy (Important)

- Timestamped artifacts are **scratch/legacy clues**, not decision-grade truth.
- Decision-grade truth should come from `artifacts/canonical_wfv/` only.
- Old timestamped artifacts must not drive new decisions without fresh patched canonical revalidation.
- 2026 lockbox policy remains unchanged (`max end date = 2025-12-31` by default).

### Scratch Backtest Outputs

Each scratch backtest run produces:

```
artifacts/runs/<timestamp>/
├── config.json     # Strategy config and params
├── metrics.json    # Performance metrics
└── daily_equity.parquet  # Daily equity curve (optional)
```

### Scratch Multi-Strategy Summary

When running with `--all-strategies`, comparison summaries are also generated:

```
artifacts/summaries/
└── <run_id>_summary.parquet/csv
```

`latest_summary.*` is only updated when `run_backtest.py` is called with `--update-latest`.

Columns: `strategy_name`, `total_return`, `annualized_return`, `sharpe`, `max_drawdown`, `total_trades`, `start_date`, `end_date`

### Canonical Walk-Forward Outputs (Decision-Grade)

Use `walk_forward_validate.py --canonical-output artifacts/canonical_wfv` to write stable deterministic outputs:

```
artifacts/canonical_wfv/
├── manifest.json
├── leaderboard.csv
└── strategies/
    └── <strategy_name>/
        ├── config_effective.json
        ├── strategy_summary.csv
        ├── fold_metrics.csv
        └── metadata.json
```

Canonical files are CSV/JSON only, strategy-separated, overwrite-in-place, and exclude volatile fields like timestamps and `elapsed_seconds`.

## Profit Decision Pipeline

Use a single canonical command to decide whether a strategy is profit-ready and to diagnose execution conversion failures:

```bash
python profit_pipeline.py
```

This writes `artifacts/profit_pipeline/<timestamp>/` with:
- `profit_readiness.csv`: strategy gate results from canonical WFV
- `profit_readiness_summary.json`: top candidate + profit-ready count
- `autopsy_yearly.csv`: year-level execution/PnL diagnostics for the selected strategy
- `autopsy_cohort_summary.csv`: failure-vs-success cohort means
- `autopsy_failure_minus_success.csv`: failure minus success delta table
- `report.md`: compact operator summary

`profit_readiness.csv` now includes machine-checkable execution status fields:
- `execution_validation_status`
- `execution_status_warning`

Defaults follow current live-state priority:
- failure years: `2016,2018,2024`
- success years: `2017,2020,2021,2022,2025`
- strategy: `blend_70_30_top5`

## Canonical Signal Sweep

For fixed-scope new-signal testing with decision labels:

```bash
python signal_sweep.py
```

Strict upstream alignment (recommended):
```bash
python signal_sweep.py --require-promotion-contract
```
This reads `data/features/recommendations/signal_promotion_contract_latest.csv` and blocks promotion when upstream `lab_promotion_status` is below `LAB_PROMOTED_PENDING_EXECUTION`.

This writes `artifacts/signal_sweeps/<timestamp>/` with:
- `canonical_wfv/` (strategy-separated fold outputs)
- `profit_readiness.csv`
- `autopsy_summary_by_strategy.csv` (unless skipped)
- `signal_sweep_decisions.csv` (`PROMOTE_CANDIDATE` / `RESEARCH_ONLY` / `KILL`)
- `signal_sweep_manifest.json`
- `signal_promotion_feedback.csv`

`signal_sweep_decisions.csv` also carries:
- `promotion_status`
- `promotion_status_warning`

Manual override (hybrid enforcement):
```bash
python signal_sweep.py --promotion-override-strategies strategy_a,strategy_b
```
This marks those rows as `OVERRIDE_PROMOTED`; a note justification is mandatory.

The sweep set is predeclared: controls + standalone matrix signals (`c4..c14`) + fixed S1 blends.

## Challenge Set Freeze

After a sweep run, freeze one baseline + one challenger:

```bash
python select_challenge_set.py
```

Default behavior is strict:
- only `PROMOTE_CANDIDATE` rows are eligible as challenger
- if none exist, command fails after writing an auditable challenge-set record with `ready_for_shadow=false`

Relaxed fallback modes (for diagnostics only):
```bash
python select_challenge_set.py --selection-mode research
python select_challenge_set.py --selection-mode any
```

Outputs:
- `artifacts/challenge_sets/<timestamp>/challenge_set.json`
- `artifacts/challenge_sets/<timestamp>/challenge_strategies.csv`

## Shadow Phase (No Retuning)

Run the frozen baseline/challenger over a fixed window:

```bash
python run_shadow_phase.py --start-date 2025-01-01 --end-date 2025-12-31
```

`run_shadow_phase.py` fails fast when challenge metadata has `ready_for_shadow=false`.

Outputs:
- `artifacts/shadow_phase/<timestamp>/shadow_results.csv`
- `artifacts/shadow_phase/<timestamp>/shadow_summary.json`

## Signal vs Translation Disambiguation

Use this when you need to separate:
- weak signal edge vs weak execution translation
- parameterization effects within the same signal family
- simplistic regime-gating benefit/harm

```bash
python run_signal_vs_translation_disambiguation.py --top-n 3
```

Outputs:
- `artifacts/signal_translation_disambiguation/<timestamp>/exp1_oracle_summary.csv`
- `artifacts/signal_translation_disambiguation/<timestamp>/exp2_translation_summary.csv`
- `artifacts/signal_translation_disambiguation/<timestamp>/exp3_router_summary.csv`
- `artifacts/signal_translation_disambiguation/<timestamp>/summary.json`

## Gate Sweep

For tail-first gate parameter search on candidate strategies:

```bash
python run_gate_sweep.py
```

Optional: override with translation-best configs from disambiguation:

```bash
python run_gate_sweep.py \
  --strategies s1b_c11_ret_60d_lag_rank_70_30_depth5,m_c11_ret_60d_lag_rank_depth5,m_c8_vol_zscore_5d_depth5 \
  --translation-best-csv artifacts/signal_translation_disambiguation/<run>/exp2_translation_best_per_strategy.csv
```

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
