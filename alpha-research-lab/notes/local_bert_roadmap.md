# Local Vietnamese Encoder Roadmap

Purpose:
- keep the current hosted LLM extractor as the canonical rich semantic/event source
- add a practical local Vietnamese encoder lane where it is honest and cheap enough
- tailor future text-source acquisition to concrete local-model tasks instead of assuming one BERT can replace everything

## Locked Decisions

### 1. Canonical local path on the current workstation

Treat constrained local hardware as the roadmap anchor:
- target box: plan against roughly `3GB VRAM` and `10GB RAM` on WSL
- prefer encoder-style classification heads over small local generators for any repeated production inference
- keep small local generators as optional audit / prototyping tools, not as the mainline local semantic stack

Use PhoBERT for whole-article sentiment only.

- first implementation target: `Angelectronic/phobert-base-vietnamese-sentiment`
- input text: normalized `title + summary + body`
- outputs: class probabilities plus derived continuous sentiment features
- artifact namespace: `data/features/news/datasets/phobert_*`
- downstream merge: additive `phobert_*` columns in `data/features/news/predictions/*_news_features.parquet`
- explicit guardrail: this lane does **not** write `data/llm_cache/` and does **not** replace `xs_llm_news_*`

Why:
- encoder classification is a natural fit for article sentiment
- whole-article scoring should dominate title-only or keyword-only sentiment
- the local GPU path is now feasible on the WSL workstation

The first expansion beyond sentiment is now:
- a separate PhoBERT `forward_looking` binary head distilled from `data/llm_cache/`
- trained sequentially through the local winner-selection lane
- published as additive `phobert_forward_looking_*` datasets and merged
  prediction columns
- still not a wider generator prompt
- still not a multi-task checkpoint that tries to absorb unrelated fields

For any future local encoder head, treat confidence like this by default:
- use model probability / calibration as the confidence surface
- do **not** make the first expansion step a separate semantic `0/1/2` confidence head

### 2. What the current sentiment checkpoint should not pretend to do

Do not treat a sentiment-finetuned PhoBERT checkpoint as a drop-in replacement for the full LLM schema.

Fields that remain LLM-only unless separately distilled:
- `event_type`
- `is_rumor`
- `surprise_direction`
- `impact_scope`
- `expectation_alignment`
- `information_novelty`
- `source_authority`
- `causal_impact_label`
- `macro_theme`

Reason:
- these are separate tasks, not hidden outputs of a sentiment model

### 3. Medium-term local distillation lane

If the local encoder branch keeps paying off, expand it with separate task heads rather than one overloaded model.

Best first candidates:
- `market_news` vs `stock_news`
- `official_or_regulatory_source`

Park these until label quality is audited:
- `rumor`
- `causal_impact_label`
- `expectation_alignment`
- `macro_theme`

Preferred supervision source:
- weak labels from the current `data/llm_cache/` contract
- one head or classifier per task family
- date-split evaluation rather than random article splits

## Model Family Notes

### PhoBERT / PhoBERT-v2

Use as the default Vietnamese encoder backbone for classification-style tasks:
- sentiment
- article routing
- forward-looking language classification
- generic stock-news vs market-news classification

### Domain-specific Vietnamese encoders

Use only when the source text actually matches the domain:

- legal/regulatory text may justify a model like `ViLegalBERT`
- official disclosures may justify a specialized filing-stage / source-type head

Do not add a domain model just because it exists; tie it to a concrete source and task.

## Small Local Ollama Generator Note

This roadmap is still encoder-first, but the workspace now also has a durable
record of the cheap local Ollama generator probes:
- see `notes/ollama_model_probe_log.md`

Locked takeaways from that probe ledger:
- cheapest current all-round local winner for single-article schema extraction:
  - `qwen2.5-coder:3b`
- strongest lower-level judgment fields:
  - `phi4-mini`
  - but it made a bad ticker extraction miss and is not safe as a direct
    extractor replacement
- no tested small local Ollama model is trustworthy enough to replace the
  hosted full-schema extractor end to end

Practical consequence:
- keep PhoBERT as the honest local default for the narrow sentiment lane
- if the local lane expands, prefer separate PhoBERT heads before expanding
  the guarded Ollama contract
- use Ollama as a teacher-probe / audit / weak-label-check path only
  unless a later benchmark proves otherwise on the target workstation

### Canonical order of operations

1. Keep hosted LLM extraction as the teacher and canonical rich schema.
2. Keep PhoBERT sentiment as the main local production lane.
3. Add `forward_looking` as the first separate PhoBERT head.
4. Use model probability as the first local confidence surface.
5. Audit weak-label quality before attempting `rumor`.
6. Keep the guarded Ollama lane additive and non-canonical for repeated local inference.

## Source-Acquisition Rule

Future text-source work should be chosen by task fit.

### Good source/task pairings

- CafeF company news archive:
  - article sentiment
  - market-news vs stock-news routing
  - forward-looking vs backward-looking wording

- Official exchange disclosures:
  - official-source detection
  - filing-stage classification
  - insider notice vs result
  - rights / subscription-right routing

- SSC / enforcement / legal text:
  - regulatory / legal event routing
  - enforcement severity or category heads

### Bad acquisition posture

Do not add new text sources under the vague idea that “BERT might find something.”
Every new source should map to a specific local-model contract before the acquisition work starts.
