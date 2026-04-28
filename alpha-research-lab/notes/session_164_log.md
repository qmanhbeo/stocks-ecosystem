# Session 164 Log - Ollama Probe Documentation (2026-04-23)

## Objective

Consolidate every local Ollama model comparison completed so far into one
durable note so future sessions do not need to re-probe the same small-model
space on the current workstation.

This session did not change the live branch.
It stayed long-only.
It did not change the hosted LLM contract.

---

## What changed

Added one durable note:
- `notes/ollama_model_probe_log.md`

Linked that note from the main local-model entry points:
- `README.md`
- `notes/local_bert_roadmap.md`
- `notes/live_state.md`

No extractor behavior changed in this session.
No model default was switched in code during this pass.

---

## Durable conclusions captured

- all completed small-model Ollama probes on the current workstation are now
  documented in one place
- the current cheapest all-round local winner for single-article schema
  extraction is `qwen2.5-coder:3b`
- `phi4-mini` had the strongest lower-level judgment behavior, but made a bad
  ticker extraction miss and is not safe as a direct replacement
- no tested cheap local Ollama model is trustworthy enough to replace the
  hosted extractor end to end
- future work should not repeat the rejected small-model comparisons unless the
  prompt contract, guardrails, or hardware budget changes materially

---

## Validation

Documentation-only pass:
- no tests run
- no data rebuilds run
