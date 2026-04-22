# Local Vietnamese Encoder Roadmap

Purpose:
- keep the current hosted LLM extractor as the canonical rich semantic/event source
- add a practical local Vietnamese encoder lane where it is honest and cheap enough
- tailor future text-source acquisition to concrete local-model tasks instead of assuming one BERT can replace everything

## Locked Decisions

### 1. Immediate local-model lane

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

### 2. What PhoBERT should not pretend to do

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
- `forward_looking` vs `backward_looking`

Park these until label quality is audited:
- `rumor`
- `causal_impact_label`
- `expectation_alignment`
- `macro_theme`

Preferred supervision source:
- weak labels from the current `data/llm_cache/` contract
- one head or classifier per task family

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
