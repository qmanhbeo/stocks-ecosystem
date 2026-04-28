# Session 171 Log - Local-First News Residual Refactor (2026-04-24)

## Objective

Implement the planned local-first news split:

- keep PhoBERT as the main local production lane
- keep PhoBERT `forward_looking` as the first separate local head
- narrow the Ollama lane to the minimal residual semantic contract
- remove the old hosted teacher cache as the default blocker for the local-news branch

This session did not change the live alpha branch.
It stayed long-only.

## What changed

### Local residual contract

Expanded the local Ollama article and ticker-day datasets away from the older
coarse probe fields and into a smaller explicit residual taxonomy:

- `event_family`
- `impact_scope`
- `source_authority`
- `is_rumor`
- local confidence / abstain / parse diagnostics

Ticker extraction stayed deterministic and outside the model.

### News aggregate / export contract

Updated the canonical aggregate exporter so the Ollama residual daily features
now flow into the combined news dataset and per-ticker
`predictions/*_news_features.parquet` exports.

### Local-news operating docs

Updated:

- `research_pipelines/news_features/README.md`
- `notes/local_bert_roadmap.md`
- `notes/live_state.md`

The local-news branch is now documented as:

- PhoBERT sentiment
- PhoBERT forward-looking
- minimal Ollama residual semantics
- legacy hosted labels as bootstrap material only, not the default production
  dependency

## Verification

Completed during this pass:

- `python -m py_compile alpha-research-lab/research_pipelines/news_features/config.py alpha-research-lab/research_pipelines/news_features/schemas.py alpha-research-lab/research_pipelines/news_features/core/aggregate_daily_features.py alpha-research-lab/research_pipelines/news_features/core/build_ollama_guarded_features.py`
- `python -m pytest alpha-research-lab/research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `28 passed`

What was not executed:

- no real Ollama runtime call against the local daemon
- no end-to-end rebuild over the shared production news warehouse
- no new PhoBERT head training beyond the existing sentiment / forward-looking lanes

## Results

- worked:
  - the local residual semantic lane now has a smaller explicit taxonomy
  - the aggregate exporter now includes the residual daily features in the
    published per-ticker news exports
  - the repo docs and live-state notes no longer describe hosted cache fill as
    the default next step for the local-news branch
- unresolved:
  - PhoBERT still owns only sentiment and forward-looking in code; additional
    local heads such as routing / source-type remain future follow-through
  - the narrowed residual taxonomy still needs downstream alpha usefulness
    audits before further expansion

## Durable Promotion Status

- promoted findings:
  - `F274`
- promoted dead ends:
  - none

## Pointers

- live state:
  - `notes/live_state.md`
- durable findings touched:
  - `notes/findings-271-300.md#f274`
