---
name: skeptical-mind
description: Research-audit skill for the VN stock lab that reviews past hypotheses, experiments, findings, and branch decisions to surface what may have been overlooked, overstated, misclassified, or insufficiently tested. Use when asked to challenge a conclusion, revisit a branch, inspect findings for weak assumptions, search for missing controls or contradictory evidence, question whether a kill or promotion was justified, or produce a concrete follow-up plan with exact reasoning.
---

# Skeptical Mind

## Overview

Pressure-test the lab's own story. Read the permanent note stack, identify where conclusions may rest on weak evidence or unchallenged assumptions, explain exactly why the concern is real, and turn that concern into a disciplined correction plan.

## Read Order

1. Read current state first.
- `README.md`
- `alpha-research-lab/README.md`
- `alpha-research-lab/notes/next_steps.md`

2. Read the durable truth layer.
- `alpha-research-lab/notes/signal_library.md`
- `alpha-research-lab/notes/findings.md`
- the relevant `alpha-research-lab/notes/findings-*.md` chunk

3. Read branch-local evidence.
- the current `alpha-research-lab/notes/session_NN_log.md`
- the session logs for the branch under review
- the strongest pass and strongest failure in the same family

4. Read data and artifact context when needed.
- `alpha-research-lab/notes/data_sources.md`
- the relevant compact summary in `alpha-research-lab/artifacts/run_summaries/`
- branch-specific artifacts or published data surfaces tied to the claim

## Skeptical Review Workflow

1. State the claim being challenged.
- Name the exact hypothesis, finding, session conclusion, or branch decision under review.
- Separate:
  - what the repo currently treats as true
  - what evidence actually supports it
  - what evidence would be needed to make the conclusion stronger

2. Reconstruct the evidence chain.
- Trace the path from hypothesis to run to artifact to note promotion.
- Identify whether the conclusion came from:
  - one experiment
  - a sequential ladder
  - a partial pass later treated as a durable truth
  - a failure that may have killed more than it really should
- Prefer saved artifacts and permanent notes over terminal recollection.

3. Search for overlooked weaknesses.
- Look for:
  - contradictory runs that were mentioned but not integrated
  - branch kills that may have been too broad
  - promotions resting on narrow periods, weak baselines, or missing confirmation
  - missing ablations, parity checks, or control comparisons
  - data-coverage holes, stale artifacts, or contract mismatches
  - evidence that a feature, label, or gate worked for a different reason than claimed
  - a branch that failed because of the test design rather than the mechanism

4. Classify the concern precisely.
- Use one of:
  - `credible oversight`
  - `needs evidence`
  - `already resolved`
  - `not actually a concern`
- Do not raise vague doubt. Tie every concern to a concrete gap, contradiction, or inference jump.

5. Explain exactly why the concern matters.
- Name the assumption doing the work.
- Show where the current record stops short.
- Explain whether the risk is:
  - wrong scientific conclusion
  - wrong branch priority
  - overbroad branch kill
  - false promotion
  - hidden data or artifact dependency
  - documentation drift

6. Convert the concern into a fix plan.
- Prefer the smallest honest correction:
  - note correction
  - findings reclassification
  - parity rerun
  - missing control experiment
  - branch reopen with a narrower claim
  - data audit or artifact regeneration
- If an experiment is needed, define the first pass the way `experimentor` would:
  - smallest valid mode
  - honest benchmark
  - pass / mixed / fail rule
  - exact artifact to read

## Skepticism Heuristics

Ask questions like:

- What assumption is carrying the whole conclusion?
- Did the lab prove the mechanism, or only observe a score move?
- Was a branch killed because the idea failed, or because the test contract was wrong?
- Did a result pass only on validation and then quietly weaken later?
- Was a durable conclusion promoted from mixed evidence without enough caveat?
- Is the benchmark honest for the claim being made?
- Is a missing data surface being treated as evidence against the hypothesis?
- Did the repo document a local failure as a family-wide failure?
- Is there a contradictory artifact or session note that weakens the current summary?

## Output Format

Produce a compact skepticism dossier.

For each concern include:

- `target`: branch, finding, hypothesis, or session conclusion being challenged
- `current claim`: what the repo currently implies
- `concern`: what may have been overlooked
- `status`: `credible oversight`, `needs evidence`, `already resolved`, or `not actually a concern`
- `why exactly`: precise reasoning tied to the notes, artifacts, or data contract
- `evidence`: sessions, findings, artifacts, or files that create the concern
- `impact`: what could be wrong if the concern is real
- `fix`: smallest correction or follow-up needed
- `first pass`: exact next check or experiment if a run is required

Then rank concerns by:

- risk to current scientific truth
- risk to branch prioritization
- ease of resolving honestly

## Guardrails

- Do not invent contradictions that the notes do not support.
- Do not treat uncertainty as a bug; show the exact missing evidence.
- Do not recommend weakening long-only, forward-lock, or note-discipline rules.
- Do not reopen a dead branch without naming what makes the new challenge materially different.
- Do not confuse a documentation issue with a model issue.
- When the concern is already resolved in a later session or finding, say so plainly.

## Working Style

- Be skeptical without becoming vague or cynical.
- Cite the exact reason a conclusion may be fragile.
- Optimize for better science, not contrarianism for its own sake.
- End with a concrete correction path, not just criticism.
