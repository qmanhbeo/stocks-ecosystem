---
name: experimentor
description: Hypothesis-testing workflow for the VN stock lab that turns a proposed research idea into the smallest valid honest experiment, runs it inside alpha-research-lab conventions, reads the saved summary artifact, and records every pass in the repo note stack. Use when asked to test a lab hypothesis, continue a research branch, run or design an HNN ladder, validate a signal or portfolio idea, inspect whether current data can support a branch, or take a bright-mind idea through disciplined experimentation.
---

# Experimentor

## Overview

Run experiments the way the lab expects: pick the smallest valid mode, define the branch ladder before running, read the saved artifact first, and leave permanent notes after every material pass.

## Read Order

1. Read workspace and lab state.
- `README.md`
- `README_for_AGENTS.md` when changing shared or root-owned skill behavior
- `alpha-research-lab/README.md`
- `alpha-research-lab/README_for_AGENTS.md`
- `alpha-research-lab/notes/live_state.md`

2. Read durable branch memory.
- `alpha-research-lab/notes/signal_library.md`
- `alpha-research-lab/notes/findings.md`
- the relevant `alpha-research-lab/notes/findings-*.md` chunk

3. Read branch-local history only when needed.
- the current `alpha-research-lab/notes/session_NN_log.md`
- the strongest prior pass in the same family
- the strongest clean failure in the same family

4. Read the data inventory before promising a new branch.
- `alpha-research-lab/notes/data_sources.md`
- branch-specific data docs such as `alpha-research-lab/notes/timing_data_acquisition_plan.md`
- `alpha-research-lab/notes/timing_data_source_scorecard.csv` when timing-data acquisition is active

## Experiment Workflow

1. Reconstruct the branch contract.
- Identify the active champion, honest benchmark, branch thesis, and current branch bucket:
  - `live promotion`
  - `offline evidence promotion`
  - `branch kill / park`
- State exactly what the next pass is trying to prove, narrow, or kill.
- Keep the live branch frozen when the repo says it is frozen.

2. Choose the smallest valid mode.
- Prefer the cheapest honest runner that can answer the question.
- Use the existing experiment entrypoints and compact-summary writers.
- For new lightweight signal/state/context audits, start from
  `alpha-research-lab/analysis/_template_research_branch.py` and
  `alpha-research-lab/src/experiment_contract.py` instead of hand-rolling a
  script.
- Use `load_s1_decision_panel` from `src/experiment_contract.py` when reading
  the S1 parquet. It renames raw `actual` to `s1_barrier_hit_1d`, a future
  target label; do not use it, raw `actual`, future returns, or same-date
  target aggregates to define states or regimes.
- The scaffold blocks `2026+` by default, checks target/state overlap,
  computes pooled/yearly/phase IC summaries, and writes standard artifacts.
- Do not jump to broad sweeps when a one-shot, audit, ablation, or branch-local comparison can falsify the idea faster.
- If the hypothesis depends on missing data, stop and record the data constraint instead of faking an experiment.

3. Define the ladder before running.
- Give the pass an `HNN` identifier and short name when the repo uses that convention.
- Write the decision rule up front: what counts as `pass`, `mixed`, `fail`, or `skip`.
- Name the next step for each outcome before touching code.
- Prefer sequential ladders over unordered search bags.

4. Run and read the saved artifact.
- Execute from the repo structure the project expects.
- Read the compact saved summary under `alpha-research-lab/artifacts/run_summaries/` before relying on terminal output.
- Use terminal output only as debugging support.
- Interpret the result against the honest benchmark, not a locally tuned best case.

5. Record the pass immediately.
- After each material run, update the current `alpha-research-lab/notes/session_NN_log.md`.
- Keep failed and mixed outcomes; do not erase dead ends.
- If the pass changes live state, branch priority, or branch closure, update `alpha-research-lab/notes/live_state.md`.
- If the pass confirms, promotes, or sharply constrains a signal, update `alpha-research-lab/notes/signal_library.md`.
- Promote durable conclusions into the current `alpha-research-lab/notes/findings-*.md` chunk and update `alpha-research-lab/notes/findings.md` if needed.

## Pass Documentation Standard

Every material pass should leave behind:

- a command or script path
- a compact saved result artifact
- a session-log entry in repo format
- a verdict: `PASSED`, `FAILED`, `NEUTRAL`, or `MIXED`

Use this session-log block shape:

```md
### HNN - [Experiment Name]
**Hypothesis:**
**Command / code:**
**Inputs:**
**Saved artifact:**

| Metric | Value | Note |
|--------|-------|------|
| ... | ... | ... |

**Result:**
**Verdict: PASSED / FAILED / NEUTRAL / MIXED**
```

## Guardrails

- Keep the lab permanently long-only.
- Do not weaken the protocol to rescue a branch.
- Do not treat terminal output as the permanent record.
- Do not let `next_steps.md` become a narrative dump; keep detail in session logs and findings.
- Do not reopen killed branches unless new data, a new label, or a changed contract makes them materially different.
- Do not touch 2026 data until the user explicitly says so.
- Treat root `data/` as the canonical shared data surface.
- Treat `alpha-research-lab/artifacts/` as the canonical lab artifact root.
- If a pass changes a producer-consumer contract across repos, update the affected docs and notes on both sides.

## Working Style

- Convert a `bright-mind` idea into a falsifiable branch, not a vague research wish.
- Be empirical and branch-conscious, not leaderboard-chasing.
- Separate `design`, `run`, `artifact read`, and `note promotion` clearly.
- End every pass by naming the next action: advance, narrow, park, or kill.
