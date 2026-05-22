# Profit Playbook (Heuristic Trader)

## Core Problem

Signals can be predictive in research, but realized PnL fails when execution is cash-heavy or underfilled in key regimes.  
The bottleneck is converting signal edge into benchmark-beating, constraint-compliant returns.

## Profit Goal

Promote only strategies that pass canonical walk-forward and execution-health gates:

- positive fold consistency
- benchmark-relative excess return
- controlled drawdown
- no catastrophic worst-fold behavior
- acceptable participation (cash/underfill/filter friction)

## Decision Workflow

1. Build or refresh canonical walk-forward outputs (`artifacts/canonical_wfv/`).
2. Run profit-readiness + autopsy:

```bash
cd /home/manh/stocks-ecosystem/heuristic-trader
python cli.py profit
```

For fixed-scope new signal testing with automatic decision labels:

```bash
python cli.py sweep -- --require-promotion-contract
```
This enforces upstream lab contract alignment from `data/features/recommendations/signal_promotion_contract_latest.csv`.

Freeze a baseline/challenger pair from the latest sweep:

```bash
python cli.py challenge
```

Default is strict challenger selection (`PROMOTE_CANDIDATE` only). If none exist, the command fails and records `ready_for_shadow=false` in `challenge_set.json`.
Use relaxed fallback modes only for diagnostic comparison:
```bash
python cli.py challenge -- --selection-mode research
python cli.py challenge -- --selection-mode any
```

Run frozen shadow comparison (no retuning):

```bash
python cli.py shadow -- --start-date 2025-01-01 --end-date 2025-12-31
```

Shadow phase now fails fast when the challenge set is not strict-ready.

When failure diagnosis is ambiguous (signal vs execution translation), run:

```bash
python cli.py disambiguate -- --top-n 3
```

For tail-first downside control, enable strategy-level exposure gate fields
(`gate_enabled`, `gate_profile=tail_first_v1`, floors/kill thresholds) and rerun
the same canonical validation workflow.

3. Read outputs in `artifacts/profit_pipeline/<timestamp>/`:
- `profit_readiness.csv`
- `profit_readiness_summary.json`
- `autopsy_yearly.csv`
- `autopsy_cohort_summary.csv`
- `autopsy_failure_minus_success.csv` (when both cohorts exist)
- `report.md`

## Promotion Rule

Do not promote a strategy based on headline return alone.  
A strategy is promotion-eligible only if it passes readiness gates and has no unresolved failure-cohort execution pathology.
