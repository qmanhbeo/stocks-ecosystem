# Ollama Model Probe Log

Purpose:
- record every local Ollama comparison run completed so far on the current WSL workstation
- avoid re-probing already-rejected small models under the same extraction contract
- separate machine-fit, JSON/schema obedience, and semantic trustworthiness

Date of last update:
- `2026-04-25`

## Locked Scope

This note is about cheap local Ollama models on the current workstation, not
about PhoBERT. PhoBERT remains the honest local default for the narrow
sentiment lane. These probes only ask whether a small local generator is good
enough to help with LLM-style article extraction.

## Machine And Runtime

- host shape observed during probing:
  - about `11 GiB` RAM visible to WSL
  - about `3 GiB` swap
  - NVIDIA RTX 3050 Laptop GPU with `4096 MiB` VRAM
- all substantive comparison runs used:
  - one model loaded at a time
  - one article per call
  - no batch probing
  - `think:false`
  - `keep_alive:"0s"`
  - `num_ctx=2048`
  - immediate `ollama stop <model>` after each response
- final safety check after the sweeps:
  - `ollama ps` empty

Patch status tied to these probes:
- the legacy Ollama caller now explicitly sends `think:false`
- regression coverage exists in `tests/test_extract_llm_news_features.py`

Important contract caveat:
- the normal legacy extractor path in `data_tools/extract_llm_news_features_legacy.py`
  still builds prompts from `title + summary`, not full body text
- the real-article ranking probes below intentionally used `title + summary +
  body_text`
- do not assume current production-path quality equals these full-body probe
  results

## Articles Used

The probes below used real CafeF dataset rows, not made-up articles.

### A1 - IPA debt issue
- file: `data/news/cafef/raw/2026-01-01.jsonl`
- article id: `8002e4554e3b25a6`
- title: `IPA muốn huy động tối đa 608 tỷ đồng từ trái phiếu để làm gì?`
- expected core interpretation:
  - main ticker `IPA`
  - `event_type=debt_issue`
  - `impact_scope=stock`
  - `source_authority=official`
  - `is_forward_looking=true`
  - `is_rumor=false`

### A2 - bank policy / multi-ticker stress article
- file: `data/news/cafef/raw/2026-01-09.jsonl`
- article id: `140b663d010812f9`
- title: `Nghị quyết 79 tác động đến VietinBank, BIDV và Vietcombank thế nào?`
- used as a hard qualitative stress case for:
  - multi-ticker extraction
  - policy/event typing
  - scope judgment

### A3 - IDP dividend
- file: `data/news/cafef/raw/2026-01-06.jsonl`
- article id: `899a7c579aaf8b49`
- title: `Sữa Quốc tế Lof chốt ngày chia cổ tức bằng tiền mặt tỷ lệ 25%`
- expected core interpretation:
  - main ticker `IDP`
  - `event_type=dividend_announce`
  - `impact_scope=stock`
  - `source_authority=official`
  - `is_forward_looking=true`
  - `is_rumor=false`

### A4 - VGC 2026 guidance
- file: `data/news/cafef/raw/2026-01-01.jsonl`
- article id: `775ab17877b04e18`
- title: `Viglacera lên kế hoạch 2026: doanh thu đi ngang, lợi nhuận tăng nhẹ 4,4%`
- expected core interpretation:
  - main ticker `VGC`
  - `event_type=guidance_raise`
  - `impact_scope=stock`
  - `source_authority=official`
  - `is_forward_looking=true`
  - `is_rumor=false`

## Methodology Note - One Rejected Early Pass

An early comparison reused the current extractor prompt builder and therefore
fed only `title + summary`. That pass was rejected as a model-selection method
because it did not test full article comprehension. The user correctly called
that out.

Durable rule from now on:
- if the question is model selection for article understanding, use full body
- only use title+summary-only comparisons when evaluating the actual production
  prompt contract

## Round 1 - Machine-Fit Smoke Test

Goal:
- confirm that tiny local models can load and answer on this box without
  immediately overloading it

Prompt style:
- trivial single reply check
- no semantic scoring

Recorded metrics:
- GPU residency and approximate VRAM only
- no comparable schema-quality scoring yet

| Model | Result | Processor | Approx VRAM | Takeaway |
|---|---|---:|---:|---|
| `qwen2.5:0.5b` | replied `OK` | `100% GPU` | `~832 MiB` | safe to load |
| `gemma3:1b` | replied `OK` | `100% GPU` | `~994 MiB` | safe to load |
| `qwen2.5:1.5b` | replied `OK` | `100% GPU` | `~1436 MiB` | safe to load |

What this round proved:
- tiny models do fit on the workstation
- it did not prove extraction quality

## Round 2 - Tiny-Model Full-Body Single-Article Probe

Goal:
- compare the smallest practical models on one real full-body company article

Article:
- `A1` only

Prompt style:
- single-call full-body extraction
- not yet a schema-enforced structured-output test

Metrics captured:
- latency only
- RAM/VRAM were not sampled systematically in this early pass

| Model | Elapsed | Main behavior | Verdict |
|---|---:|---|---|
| `qwen2.5:0.5b` | `2.664s` | invented extra ticker `IPAM`; emitted invalid enum labels such as custom financing phrases | reject except as a last-ditch toy fallback |
| `gemma3:1b` | `2.507s` | effectively returned only the article id; normalized result collapsed to null | reject |
| `qwen2.5:1.5b` | `3.741s` | kept main ticker `IPA`, but still produced invalid event/scope judgments | least-bad tiny model |

Takeaway from the tiny rung:
- if forced below the `3B` class, `qwen2.5:1.5b` was the only remotely usable
  option
- even that model was not trustworthy enough to replace the hosted extractor

## Round 3 - Raw JSON 3B-4B Sweep

Goal:
- test the next cheap rung with real full-body articles and live RAM/VRAM
  measurement

Articles:
- `A1`
- `A2`

Prompt style:
- strict JSON instruction prompt
- not schema-enforced through Ollama `format`

Metrics:
- average elapsed time across the two articles
- peak system RAM during any call in the round
- peak VRAM during any call in the round
- parse failures when the output could not be normalized into the expected JSON

| Model | Avg sec | Peak RAM | Peak VRAM | Parse failures | Result |
|---|---:|---:|---:|---:|---|
| `qwen2.5:3b` | `7.36s` | `1629.5 MiB` | `2470 MiB` | `2` | reject |
| `qwen3:4b` | `10.54s` | `1910.7 MiB` | `3046 MiB` | `2` | reject |
| `llama3.2:3b` | `7.81s` | `1672.9 MiB` | `2692 MiB` | `0` | best practical result in this round |
| `gemma3:4b` | `20.50s` | `3574.8 MiB` | `2554 MiB` | `0` | slightly stronger than expected, but too heavy |

### Per-model notes

#### `qwen2.5:3b`
- both responses failed parse
- one malformed the object shape
- one emitted an array-like key/value structure rather than a usable object
- this ruled it out immediately for extraction work under the raw JSON prompt

#### `qwen3:4b`
- both responses ignored the strict JSON instruction
- emitted prose / reasoning-style text despite `think:false`
- this directly conflicted with the user's "no thinking mode" requirement in
  practice, even if the flag was disabled

#### `llama3.2:3b`
- valid JSON both times
- on `A1`:
  - kept ticker `IPA`
  - got `impact_scope=stock`
  - got `source_authority=official`
  - but mislabeled the event as `merger_acquisition`
  - and failed `is_forward_looking`
- on `A2`:
  - kept the response parseable
  - but produced a bad ticker mapping and wrong event typing
- verdict in this round:
  - cheapest practical raw-prompt choice
  - still not trustworthy enough

#### `gemma3:4b`
- valid JSON both times
- one observed `ollama ps` sample showed mixed CPU/GPU loading, which explains
  why VRAM stayed lower while RAM spiked
- on `A1`:
  - kept `IPA`
  - hallucinated related tickers tied to the downstream entities
  - wrong event type and wrong authority
- on `A2`:
  - sector/macro judgment was somewhat better
  - event typing and source judgment were still wrong
- verdict in this round:
  - more coherent than the raw Qwen models
  - not worth the RAM and speed trade on this machine

### Conclusion from Round 3

- `qwen2.5:3b` and `qwen3:4b` should not be re-probed under the same raw JSON
  contract
- `llama3.2:3b` became the temporary cheap baseline to beat
- `gemma3:4b` was not cheap enough to justify continued interest

## Round 4 - Extraction-Oriented Structured-Output Sweep

Goal:
- rerun the cheap 3B-4B search with models more likely to obey structure
- use Ollama `/api/chat` with a real JSON schema, not only raw text

Articles:
- `A1`
- `A3`
- `A4`

Models:
- `llama3.2:3b` as control
- `qwen2.5-coder:3b`
- `phi4-mini`
- `ministral-3:3b`
- `qwen3.5:4b`

Prompt style:
- full body
- JSON schema via `format`
- `think:false`
- `keep_alive:"0s"`

Scoring fields:
- `ticker_exact`: exact main ticker match
- `event_match`: exact event taxonomy match
- `core trust hits`: exact match across the four lower-level judgment fields:
  - `impact_scope`
  - `source_authority`
  - `is_forward_looking`
  - `is_rumor`

Maximum scores in this round:
- `ticker_exact`: `3`
- `event_match`: `3`
- `core trust hits`: `12`

| Model | Avg sec | Peak RAM | Peak VRAM | Ticker exact | Event exact | Core trust hits | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| `qwen2.5-coder:3b` | `10.21s` | `2088.0 MiB` | `2472 MiB` | `3/3` | `1/3` | `7/12` | best cheap all-round pick |
| `phi4-mini` | `12.43s` | `2173.7 MiB` | `3312 MiB` | `2/3` | `1/3` | `12/12` | best judgment fields, bad ticker miss |
| `llama3.2:3b` | `11.93s` | `1883.9 MiB` | `2694 MiB` | `3/3` | `0/3` | `5/12` | parsable but semantically weak |
| `ministral-3:3b` | `18.19s` | `3456.2 MiB` | `3376 MiB` | `3/3` | `1/3` | `7/12` | too heavy for the gain |
| `qwen3.5:4b` | `19.33s` | `4476.2 MiB` | `3648 MiB` | `0/3` | `0/3` | `0/12` | reject |

### Per-model notes

#### `llama3.2:3b`
- stayed fully parseable
- kept the right ticker on all three articles
- but repeatedly collapsed non-earnings events into earnings / IPO categories
- examples:
  - `A1` debt issue -> `ipo_listing`
  - `A3` dividend -> `earnings_miss`
  - `A4` 2026 plan -> `earnings_miss`
- good cheap fallback, but not the best available result anymore

#### `qwen2.5-coder:3b`
- major improvement over raw `qwen2.5:3b`
- stayed inside the schema on all three articles
- kept the correct main ticker on all three articles
- got the cleanest overall cheap trade-off between:
  - memory
  - speed
  - structure obedience
  - usable semantic quality
- key misses:
  - `A1` debt issue -> `ipo_listing`
  - `A4` 2026 guidance -> `earnings_beat`
- durable conclusion:
  - current cheapest all-round local winner on this workstation

#### `phi4-mini`
- strongest lower-level judgment behavior in this round
- perfect `12/12` on the four core trust fields
- but made one fatal ticker error on a clean dividend article:
  - `A3` should have extracted `IDP`
  - it extracted `MCK`
- also misread the `A1` debt issue as `dividend_announce`
- durable conclusion:
  - best option only if a separate deterministic ticker guardrail exists
  - otherwise too risky despite good judgment fields

#### `ministral-3:3b`
- structured output stayed parseable
- memory use was too high for the gain on this machine
- produced strange event labels even on simple articles:
  - `A1` -> `index_inclusion`
  - `A4` -> `insider_buy`
- durable conclusion:
  - not worth re-probing on the current box unless the whole prompt contract
    changes materially

#### `qwen3.5:4b`
- this is especially important because it is still the unreviewed default model
  string in the legacy extractor code
- under the schema-enforced sweep it still failed the task badly:
  - returned custom keys like `ticker_set` or `ticker`
  - failed every scored field after normalization
  - used the most RAM of the tested small models
- durable conclusion:
  - do not treat `qwen3.5:4b` as a safe default just because it is already in
    code

## Consolidated Ranking On This Machine

### 1. Best cheap local all-rounder

`qwen2.5-coder:3b`

Why:
- best combined outcome on cost, structure obedience, and acceptable extraction
  behavior
- lower VRAM than the heavier 4B class
- materially better than `llama3.2:3b` once the schema was enforced

### 2. Best judgment fields if ticker extraction is guarded elsewhere

`phi4-mini`

Why:
- strongest lower-level field control in the structured sweep
- but the `IDP -> MCK` error is too dangerous if ticker extraction is left to
  the model

### 3. Lowest-rung fallback

`qwen2.5:1.5b`

Why:
- best sub-`3B` result
- only useful as a rough cheap tagger, not as a trusted schema extractor

### 4. Cheap backup if the coder model behaves oddly on a later prompt

`llama3.2:3b`

Why:
- consistently parseable
- lower RAM than the other serious candidates
- semantically weaker than `qwen2.5-coder:3b`

## Models That Should Not Be Re-Probed Under The Same Contract

These models already failed clearly enough on this machine that repeating the
same style of probe would have low information value:

- `gemma3:1b`
- `qwen2.5:0.5b`
- `qwen2.5:3b`
- `qwen3:4b`
- `gemma3:4b`
- `ministral-3:3b`
- `qwen3.5:4b`

Borderline keepers:
- `qwen2.5:1.5b`
  - keep only as the tiny fallback
- `llama3.2:3b`
  - keep only as the cheap generic backup
- `phi4-mini`
  - keep only if future work adds a non-LLM ticker guardrail

## Operational Rules Going Forward

For this workstation, future Ollama extraction work should keep these rules by
default:

- single-call or very small-call operation only
- no large batch sweeps
- `think:false`
- `keep_alive:"0s"`
- `num_ctx=2048`
- unload each model immediately after use

## Final Branch Conclusion

No tested cheap local Ollama model is trustworthy enough to replace the hosted
full-schema extractor end to end.

Current honest position:
- PhoBERT or other narrow local classifiers are still the right local path for
  task-specific work
- if a local small generator must be used anyway, choose `qwen2.5-coder:3b`
  first
- if a future branch needs stronger semantics than this, the next honest step
  is not another random 3B-4B sweep; it is either:
  - add deterministic guardrails around ticker and schema handling, or
  - probe a carefully selected larger model with explicit memory risk

## Round 5 - Reusable Probe Script Re-Run With New Candidates And XML Anchor

Artifact:
- `artifacts/ollama_probes/20260423_213155_ollama_news_probe.json`

Method:
- producer script:
  - `python data_tools/probe_ollama_news_models.py`
- models:
  - `granite3-moe:3b`
  - `smollm2:1.7b`
  - `deepseek-coder:1.3b`
  - `qwen2.5-coder:3b`
  - `llama3.2:3b`
  - `phi4-mini`
- articles:
  - `A1`
  - `A2`
  - `A3`
  - `A4`
- runtime:
  - one model at a time
  - one article at a time
  - `think:false`
  - `keep_alive:"0s"`
  - `num_ctx=2048`
  - Ollama `/api/chat`
  - real JSON schema via `format`
  - both prompt styles:
    - `plain_json`
    - `xml_anchor`
- safety:
  - RAM / VRAM sampled per call
  - `ollama stop <model>` after every article
  - final `ollama ps` empty

### Round 5 summary table

#### `plain_json`

| Model | Avg sec | Peak RAM | Peak VRAM | Parse failures | Ticker exact | Event exact | Core trust hits | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `granite3-moe:3b` | `6.09s` | `1604.82 MiB` | `2380 MiB` | `1` | `1/2` | `0/2` | `4/8` | reject |
| `smollm2:1.7b` | `8.33s` | `1545.91 MiB` | `2420 MiB` | `1` | `1/2` | `0/2` | `3/8` | reject |
| `deepseek-coder:1.3b` | `6.57s` | `1503.24 MiB` | `1356 MiB` | `1` | `0/2` | `0/2` | `2/8` | reject |
| `qwen2.5-coder:3b` | `14.46s` | `1874.42 MiB` | `2409 MiB` | `0` | `3/3` | `2/3` | `11/12` | best overall |
| `llama3.2:3b` | `12.57s` | `1929.48 MiB` | `2631 MiB` | `0` | `3/3` | `1/3` | `11/12` | best backup |
| `phi4-mini` | `15.78s` | `2157.02 MiB` | `3212 MiB` | `0` | `3/3` | `0/3` | `7/12` | too weak for the cost |

#### `xml_anchor`

| Model | Avg sec | Peak RAM | Peak VRAM | Parse failures | Ticker exact | Event exact | Core trust hits | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `granite3-moe:3b` | `12.47s` | `1935.7 MiB` | `2328 MiB` | `4` | `-` | `-` | `-` | reject hard |
| `smollm2:1.7b` | `12.24s` | `1833.06 MiB` | `2368 MiB` | `2` | `0/1` | `0/1` | `2/4` | reject |
| `deepseek-coder:1.3b` | `5.21s` | `1730.19 MiB` | `1304 MiB` | `0` | `0/3` | `0/3` | `3/12` | reject |
| `qwen2.5-coder:3b` | `10.05s` | `1960.66 MiB` | `2372 MiB` | `0` | `3/3` | `2/3` | `11/12` | still best |
| `llama3.2:3b` | `11.55s` | `1963.42 MiB` | `2730 MiB` | `0` | `3/3` | `1/3` | `9/12` | backup only |
| `phi4-mini` | `16.78s` | `2244.14 MiB` | `3317 MiB` | `0` | `3/3` | `1/3` | `6/12` | no gain from XML |

### What Round 5 changed

- the new cheap candidates did **not** beat the current baseline:
  - `granite3-moe:3b` failed by inventing ticker-like junk such as `SYSTEM`
  - `smollm2:1.7b` failed by inventing schema-like junk such as
    `CHANGE`, `NAME`, `PRICE`, `VOLUME`
  - `deepseek-coder:1.3b` stayed light on VRAM but mostly collapsed to empty
    extractions
- `qwen2.5-coder:3b` remained the best all-round local model on this box
- `llama3.2:3b` stayed the most credible backup, but it still over-collapses
  event typing into guidance / earnings-style labels
- `phi4-mini` no longer justifies its memory cost under the stricter reusable
  probe contract

### XML-anchor result

The XML-anchor prompt did **not** improve the shortlist overall.

- it made `granite3-moe:3b` materially worse
- it did not rescue `smollm2:1.7b` or `deepseek-coder:1.3b`
- it left `qwen2.5-coder:3b` essentially unchanged on the scored articles
- it slightly reduced `llama3.2:3b` core-trust quality
- it did not make `phi4-mini` trustworthy enough

Durable conclusion:
- keep `plain_json` as the default comparison prompt
- keep `xml_anchor` only as an optional diagnostic path, not the new default

### Updated ranking after Round 5

1. `qwen2.5-coder:3b`
2. `llama3.2:3b`
3. `phi4-mini`
4. `qwen2.5:1.5b`

Models newly ruled out under the reusable probe contract:
- `granite3-moe:3b`
- `smollm2:1.7b`
- `deepseek-coder:1.3b`

## Round 6 - Prompt And Field-Density Efficiency Grid For The Guarded Residual Lane

Artifact:
- `artifacts/run_summaries/20260425_190453_ollama_guarded_prompt_probe.json`
- `artifacts/run_summaries/latest_ollama_guarded_prompt_probe.json`

Goal:
- stop treating the local generator as a broad replacement extractor
- find the smallest prompt that can fill the residual semantic field BERT does
  not cover well enough: event family
- keep the run within the current `3GB VRAM / 10GB RAM` planning budget

Model:
- `qwen2.5-coder:3b`

Sample:
- `8` real raw CafeF articles
- `4` current hand-curated probe articles
- `4` legacy-cache labelled articles mapped back to their raw article text

Variables tested:
- expert header vs no header
- JSON vs XML vs CSV
- full five-field output vs event+rumor vs event-only
- `num_ctx` `512`, `1024`, `2048`
- raw body vs first `300` words
- schema at top vs schema at bottom
- no constraint vs no-chat style constraints
- result anchor and JSON prefill
- zero-shot vs one-shot
- `temperature=0.0` vs `0.1`

Winner:
- `lean_event_only_json_512_300_bottom`

Winner metrics:
- parse OK: `1.0`
- scored field: `event_family`
- event-family accuracy: `0.625`
- exact event-family rate: `0.625`
- average seconds/article: `1.7357272136250685`
- articles/second: `0.5761273961427952`
- average prompt tokens: `512.0`
- average eval tokens: `29.125`

What changed:
- compact Vietnamese taxonomy hints helped the event-family-only prompt,
  especially for M&A / asset-sale style articles
- schema-at-bottom was necessary; top-schema prompts at `512` context still
  failed badly
- `1024`/`2048` full-field JSON was semantically richer but roughly twice as
  slow and asks the model for fields now better owned by PhoBERT
- CSV was fast but not safe: it emitted custom labels such as `Financial News`
  and got zero exact event+rumor rows under the strict gate
- XML, one-shotting, anchors, prefill, and `temperature=0.1` did not beat the
  simple bottom-schema event-only JSON prompt

Operational decision:
- default the production guarded Ollama lane to event-family-only JSON
- keep `impact_scope` and `source_authority` as PhoBERT-owned features by
  default
- leave the wider Ollama field sets as explicit operator options, not the
  default backfill path

Backfill posture:
- ungated canary throughput was about `0.49` unique articles/second over
  `342135` tagged articles, too slow for a blind full run
- BERT-gated canary using
  `phobert_article_scope_prob_positive >= 0.28` reduced the queue to `146872`
  articles and stayed parse-clean
- the priority backfill now runs in detached tmux session
  `ollama_guarded_backfill` with `--checkpoint-rows 200`
