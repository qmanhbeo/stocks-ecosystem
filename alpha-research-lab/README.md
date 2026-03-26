# Alpha Signal Research Lab

Research repo for finding statistically valid equity signals in Vietnamese stocks, with an
agent-oriented workflow built around hypothesis → experiment → saved result → findings.

## What This Repo Is For

The **primary goal** is to build a library of learnable, orthogonal alpha signals that can
serve as state features for RL trading agents. Each signal should be independently predictive
and ideally uncorrelated with existing signals.

A secondary goal is tracking which signals combine into tradeable strategies. H54 (+25.52%
edge, Sharpe 9.17) is the current best strategy, but it is **parked** — not yet deployable.

**This is not a race to beat H54. New signals are evaluated on their own merit as independent
information sources, not on whether they improve a combined model.**

## Signal Evaluation Criteria

For a signal to enter the library it must meet:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Standalone IC | > 0.01 | Any reliable predictive content is useful |
| Correlation with primary signal | < 0.30 | Orthogonality = RL diversity value |
| IC positive in ≥ years | 60% of in-sample years | Consistency, not noise |

Note: a signal that "fails" to improve a combined XGBoost model may still be RL-valuable.
XGBoost handles sparse signals poorly. An RL agent can selectively attend to signals.

## Start Here

- `notes/next_steps.md`: live system state, current priorities, session history
- `notes/signal_library.md`: **the registry of confirmed and candidate signals**
- `README_for_AGENTS.md`: exact agent loop, commands, result artifacts, data, note conventions
- `notes/findings.md`: durable scientific conclusions

`README.md` is an overview. The live source of truth is `notes/next_steps.md`.

## Data Contract

- Run research scripts from inside `alpha-research-lab/`
- Canonical data lives in the workspace root at `../data/`
- The repo-local `data/` path is a symlink to that shared root so existing lab scripts can keep using `data/...`
- No research data is duplicated inside `alpha-research-lab/`

## Current Best RL Signal

**H93 — Volume + 1-day label cross-sectional model**

- IC +0.1491, edge std 1.60%, Sharpe 15.08, 11/11 positive years (2015–2025)
- Lowest year-to-year variance of any system tested
- Artifact: `data/features/xs_barrier_vol_1d_hose_full.parquet`

## Current Best Trading Strategy (Parked)

**H54 — Full HOSE Rank Portfolio**

- +25.52% avg edge, Sharpe 9.17, 11/11 positive years
- Parked: deployment gap (real fills unverified, net P&L borderline at 0.30% RT)
- Artifact: `data/features/xs_barrier_all_probas_hose_full.parquet`

Run it with:
```bash
PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_all_probas_hose_full.parquet \
    --no-vix-filter
```

See `notes/next_steps.md` for the live champion, honest benchmark, and next priorities.

## Setup

```bash
conda env create -f environment.yml
conda activate stocks
python setup_data.py
```

All commands above are intended to be run from `alpha-research-lab/`.

## Main Experiment Modes

- `run_experiment.py`: quick one-shot screen on a fixed split. Cheap, not authoritative.
- `walk_forward.py`: default for new FPT-only hypotheses.
- `cross_sectional_wf.py`: default for market-wide hypotheses.
- `ensemble_wf.py`: combine saved FPT probability streams.
- `analysis/*.py`: portfolio, ranking, filter, and meta-analysis scripts on saved outputs.

## Saved Result Artifacts

Main experiment runners write compact JSON summaries to `artifacts/run_summaries/`.

- One-shot: `latest_one_shot.json`
- Walk-forward: `latest_walk_forward.json`
- Cross-sectional: `latest_cross_sectional.json`
- Ensemble: `latest_ensemble.json`
- Portfolio: `latest_portfolio.json`

Permanent logs remain:

- `results_summary.jsonl` for one-shot screens
- `wf_results.jsonl` for walk-forward runs
- `xs_wf_results.jsonl` for cross-sectional and ensemble runs

## Repo Structure

```text
.
├── README.md
├── README_for_AGENTS.md
├── walk_forward.py
├── cross_sectional_wf.py
├── ensemble_wf.py
├── run_experiment.py
├── src/
├── configs/
├── analysis/
├── data_tools/
├── notes/
│   ├── signal_library.md      ← signal registry (primary output)
│   ├── findings.md            ← durable scientific truth
│   ├── next_steps.md          ← live state & queue
│   └── session_NN_log.md      ← per-session records
├── experiments/
├── artifacts/run_summaries/
├── wf_results.jsonl
├── xs_wf_results.jsonl
└── results_summary.jsonl
```

## Notes Policy

The repo treats `notes/` as a permanent scientific record:

- Session logs are the detailed record
- `findings.md` is the durable truth layer
- `signal_library.md` is the signal registry — the primary deliverable
- `next_steps.md` is the active queue
- Failed ideas stay documented instead of being erased

See `README_for_AGENTS.md` for the working convention and agent protocol.
