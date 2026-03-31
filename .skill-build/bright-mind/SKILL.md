---
name: bright-mind
description: Research-ideation skill for the VN stock lab that inspects hypotheses, findings, branch outcomes, next steps, and available data to produce unusually creative, high-upside new hypotheses. Use when asked to generate bold alpha ideas, new research branches, branch continuations, data-driven thesis proposals, or breakthrough experiments grounded in alpha-research-lab history, failures, successes, and current data availability.
---

# Bright Mind

## Overview

Generate hypotheses that are both ambitious and disciplined. Mine the lab's full memory, not just the latest winner, then propose ideas that could produce step-change improvements in performance, robustness, or deployability.

## Read Order

Read the smallest set that gives a faithful picture of the lab before proposing ideas.

1. Read workspace state.
- `README.md`
- `alpha-research-lab/README.md`
- `alpha-research-lab/notes/next_steps.md`

2. Read durable research memory.
- `alpha-research-lab/notes/signal_library.md`
- `alpha-research-lab/notes/findings.md`
- the relevant findings chunks that match the branch or idea family

3. Read the branch-local evidence.
- recent session logs tied to the active branch
- the logs for the strongest successful branch in the same family
- the logs for the strongest failure in the same family

4. Inspect the available data surface.
- shared `data/`
- current published feature artifacts
- current labels, activation, event, recommendation, and entry-alpha surfaces when relevant

## Hypothesis Generation Workflow

1. Reconstruct the lab's state.
- Identify the active live branch, active research branch, parked branches, and known dead ends.
- Separate evidence into `live-promotable`, `offline evidence`, and `killed or parked`.
- Note what the lab currently believes is true, false, fragile, or unknown.

2. Mine the failures.
- Treat failed branches as information, not waste.
- Ask what they killed exactly:
  - a mechanism
  - a contract
  - a data regime
  - a label
  - a sizing rule
  - a deployment assumption
- Search for overfit patterns, wrong objective choices, missing state variables, or hidden contract mismatches.

3. Search for structural blind spots.
- Look for spaces the lab has under-explored:
  - interactions between selection, activation, exit, and entry
  - alternative targets or labels
  - conditional or state-scoped alpha
  - cross-sectional vs stock-local reformulations
  - capacity, tradability, and implementation pain as alpha inputs instead of vetoes
  - event, intraday, sector, breadth, and market-structure effects
  - data the lab has but is not yet using well
  - data the lab lacks but that would unlock a new branch

4. Push for novelty without breaking honesty.
- Prefer hypotheses that are not just local parameter tweaks.
- Favor ideas that change representation, target, state definition, branch framing, or data source.
- Do not resurrect a dead branch unless new data, a new label, or a changed contract makes it materially different.

5. Convert ideas into falsifiable branches.
- For each promising idea, define:
  - mechanism
  - why prior work does not already kill it
  - what data it needs
  - the cheapest honest first test
  - what result would advance, narrow, or kill the branch

6. Record the ideas in the repo immediately.
- After producing a non-trivial hypothesis set, update `alpha-research-lab/notes/next_steps.md`.
- Add a concise queue, not the full dossier:
  - short branch names
  - one-line claim or connection
  - the smallest honest next test
- Keep the new queue subordinate to the repo's active priorities.
- Do **not** assign `H` numbers unless the branch is intentionally being activated.
- Skip this only if the user explicitly asks for a dry ideation pass with no file changes.

## Idea Standards

Prefer ideas with these properties:

- high upside if true
- low overlap with already-confirmed signals or branches
- clear mechanism rather than vague optimism
- compatible with long-only Vietnam reality
- testable with an honest minimal ladder
- able to exploit information the current system likely leaves on the table

Avoid:

- parameter fiddling presented as a new thesis
- ideas already falsified by stronger evidence
- hypotheses that only work by silently weakening the protocol
- branches that require unrealistic shorting or unrealistic execution

## Curiosity Heuristics

Use these prompts to force originality:

- What if the current winner is right for the wrong reason?
- What if the branch failed because the label was wrong, not the feature?
- What if a veto variable should be a signal variable?
- What if a global gate should be local, or a local rule should be global?
- What if the true edge is in when a signal should be ignored rather than followed?
- What if breadth, concentration, or replacement pressure is the hidden state variable?
- What if event timing matters more as a state transition than as a raw feature?
- What if the data weakness itself implies the next research frontier?

## Output Format

Produce a compact hypothesis dossier.

For each idea include:

- `name`: short branch-worthy title
- `claim`: what the hypothesis says
- `mechanism`: why it could work
- `evidence from history`: which findings, sessions, or failures motivated it
- `why not already killed`: what makes it materially different from past failures
- `required data`: existing artifacts or missing data needed
- `first honest test`: smallest valid experiment
- `branch ladder`: next step if pass, next step if mixed, kill condition if fail
- `upside`: why this could matter materially

Then rank ideas by:

- expected upside
- novelty
- feasibility with current data
- honesty of the test path

After presenting the dossier, leave a condensed version in `alpha-research-lab/notes/next_steps.md` unless the user explicitly asked not to modify files.

## Working Style

- Stay curious, but do not become hand-wavy.
- Be willing to propose strange ideas if the mechanism is coherent.
- Use negative evidence aggressively; the lab's failures are part of the search engine.
- Optimize for ideas that could genuinely change the frontier, not just improve a leaderboard by noise.
