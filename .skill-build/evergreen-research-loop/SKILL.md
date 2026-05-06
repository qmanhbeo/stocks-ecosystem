---
name: evergreen-research-loop
description: Autonomous VN stock-lab research loop that recovers repo memory, selects a branch, ideates, runs the smallest honest test, watches at most one heavy job, writes results back, and repeats.
---

# Evergreen Research Loop

Purpose: run a recoverable one-job-at-a-time alpha research loop without
loading every specialist skill up front.

## Core Contract

- Do not load downstream skills by default. Follow the phase contracts below;
  load a specialist skill only when its escalation trigger is hit.
- Keep the loop externally stoppable and memory-backed through
  `alpha-research-lab/notes/live_state.md`, session logs, findings, and dead
  ends.
- Run at most one heavy experiment or builder at a time.
- Never touch 2026 data unless Manh explicitly allows it.
- Keep the lab long-only. Do not weaken the protocol to rescue a branch.
- Never erase failed branches. Park uncertain failures with reopening
  conditions; kill only when evidence is strong.
- Optimize for deployable money-making signals, not just leaderboard movement.

## Recover State

Read only the active frontier:
- repo workflow docs and `live_state.md`
- active findings/dead-ends chunks
- latest relevant session log
- latest saved run summaries for active branches

Identify active branch, frontier, parked/killed/promoted branches, current
champion, benchmark, blockers, and next action.

## Phase Contracts

1. Select or create branch.
- Rank by money relevance, surprise, novelty, uncertainty, feasibility,
  resource cost, and protocol honesty.
- Prefer the smallest branch move that could change deployability.

2. Ideate.
- Ground ideas in live state, findings, failures, and available data.
- Each idea needs mechanism, why prior work does not kill it, required data,
  first honest test, and pass/mixed/fail next steps.
- Load `bright-mind` only for a serious new hypothesis set or when branch
  generation quality matters more than token cost.

3. Experiment.
- Define the smallest honest test and pass/mixed/fail/skip rule before running.
- Read saved summary artifacts before judging terminal output.
- Load `experimentor` only for a non-trivial experiment ladder, branch contract,
  or note-promotion decision.

4. Watch jobs and data.
- For heavy work, read structured status first, check CPU/RAM/VRAM headroom,
  and restart only when resumable or restart-safe.
- Load `job-watchdog` only when starting, monitoring, repairing, or optimizing a
  heavy job.
- Load `low-resource-data-pipeline` only when changing fetch/build/publish
  logic or shared data contracts.

5. Interpret and write memory.
- Classify result as `PROMISING`, `SURPRISING`, `MIXED`, `WEAK`, `FAILED`, or
  `BLOCKED`.
- Decide continue, fork, create sibling, narrow, park, kill, or promote.
- Write session notes, live-state changes, durable findings/dead ends, signal
  library updates, or operator docs only when those surfaces changed.
- Load `manh-memory-system` only for memory bootstrap, reconciliation, or
  ambiguous write-back.

## Closeout Checklist

Every material loop iteration must answer:
- Was the saved artifact read before the verdict?
- What branch status changed, if any?
- What is the exact next action?
- Was memory write-back done, or explicitly skipped because nothing changed?
- Was 2026 data avoided unless allowed?
- Was the protocol kept honest?
- Is there still no more than one heavy job active?
