# Session 167 Log - Local Hardware Safety Budget Tightened (2026-04-24)

## Objective

Tighten the repo-local hardware planning assumptions to a more conservative
budget after checking the live workstation and the first PhoBERT canary.

This session did not change the live alpha branch.
It stayed long-only.
It was an infrastructure / workflow-hardening pass, not a research result.

---

## What changed

Updated repo-local workflow and local-model docs so future work plans against a
safer local budget:
- `3GB VRAM`
- `10GB RAM`

Updated these repo-owned surfaces:
- `AGENTS.md`
- `alpha-research-lab/README.md`
- `alpha-research-lab/research_pipelines/news_features/README.md`
- `alpha-research-lab/notes/local_bert_roadmap.md`
- `alpha-research-lab/notes/next_steps.md`

This pass does not claim the machine only exposes those exact totals.
It changes the planning budget so future agents leave the remaining observed
memory as safety headroom for:
- WSL overhead
- background processes
- transient allocation spikes
- recovery / restart slack during watchdog-managed jobs

---

## Validation

Completed during this pass:
- re-searched the repo for stale live references to the older local-ML hardware
  profile
- confirmed the repo-local docs now point to the tighter planning budget

What was not executed:
- no new research runs
- no new data rebuilds
- no change to the active PhoBERT canary command itself

---

## Results

- worked:
  - the repo now documents a tighter and clearer local hardware planning rule
  - future local-ML work is less likely to overfit to the currently visible
    `~4GB` VRAM / `~12GB` RAM totals
- unresolved:
  - none
- next step:
  - keep the current PhoBERT canary sequential and continue treating
    `3GB VRAM / 10GB RAM` as the safe planning budget

## Durable Promotion Status

- promoted findings:
  - `F272`
- promoted dead ends:
  - none

## Pointers

- live state:
  - `notes/next_steps.md`
- durable findings touched:
  - `notes/findings-271-300.md#f272`
- durable dead ends touched:
  - none
