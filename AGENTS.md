# AGENTS.md

Root coordination notes for coding agents working in `/home/manh/stocks`.

## Start Here

Read these first:

- `README.md`
- `data/README.md` when the task touches shared datasets or source availability
- `alpha-research-lab/README.md`
- `shared-recommendation/README.md` when changing shared recommendation contracts or candidate artifacts
- `RL-trading-agent/README.md`
- `RL-trading-agent/AGENTS.md` when changing RL runtime code

## Workspace Model

This workspace is an ecosystem, not a set of truly standalone repos.

Current responsibilities:

- `data/` is the canonical shared data root for the entire workspace
- `data/foreign_flow/` is a raw historical CafeF foreign-flow surface
- `data/order_stats/` is a raw historical CafeF order-statistics surface
- `data/features/xs_order_pressure_daily.parquet` is the scoped published C16 order-pressure feature surface derived from `data/order_stats/` plus shared tradability
- `data/proprietary_trading/` is a raw historical CafeF proprietary-trading surface
- `data/foreign_flow_forward/` is a forward-only raw acquisition surface, not a historical feature backfill
- `data/official_disclosures/` is a raw official-disclosure acquisition surface; the first wired source is HNX mobile issuer disclosures
- `alpha-research-lab/` owns research pipelines and research outputs
- `manual-label-factory/` owns the manual buy-zone labelling UI
- `shared-recommendation/` owns shared model-agnostic recommendation contracts and artifact resolution
- `RL-trading-agent/` owns RL runtime logic and consumes artifacts from root `data/`
- `alpha-research-lab/` resolves shared datasets from root `data/` directly; a repo-local `alpha-research-lab/data` symlink is compatibility-only

## Important Paths

- Shared raw + published data: `/home/manh/stocks/data`
- Research lab: `/home/manh/stocks/alpha-research-lab`
- Manual label factory: `/home/manh/stocks/manual-label-factory`
- Shared recommendation package: `/home/manh/stocks/shared-recommendation`
- RL runtime: `/home/manh/stocks/RL-trading-agent`

## Default Assumptions

- Prefer root `data/` over repo-local `data/` paths
- Inside `alpha-research-lab/`, scripts should resolve the canonical shared root `data/` directly
- Do not reintroduce duplicate data stores inside child repos unless explicitly requested
- Treat cross-project path contracts as ecosystem-level contracts
- Treat `data/features/recommendations/` as a shared published surface, not an alpha-only private output
- Treat internal news-builder stage/checkpoint artifacts under `data/features/news/datasets/` such as `news_tabular_article_stage.parquet`, `embedding_input_articles.parquet`, `embedding_checkpoint/`, `phobert_input_articles.parquet`, `phobert_checkpoint/`, `ollama_guarded_input_articles.parquet`, and `ollama_guarded_checkpoint/` as producer-side caches, not shared consumer contracts
- Treat `data/model_checkpoints/` as durable producer-side checkpoint state, not a shared consumer contract
- Treat `data/foreign_flow/` as a raw source surface until a research-owned feature artifact is published from it
- Treat `data/order_stats/` as a raw source surface; use `data/features/xs_order_pressure_daily.parquet` for the published scoped C16 order-pressure contract
- Treat `data/proprietary_trading/` as a raw source surface until a research-owned feature artifact is published from it
- Treat `data/foreign_flow_forward/` as forward-only raw data; do not use it in historical alpha tests until enough post-collection history exists
- Treat `data/official_disclosures/` as a raw source surface; do not assume exchange-hosted disclosures are a published event feature contract yet
- When changing producer/consumer boundaries, update docs in both the producer and consumer project

## Lightweight-First Rule

Treat constrained local execution as a hard workspace constraint.

- Prefer modular, incremental, shard-based, or publish-only commands over full rebuilds
- Do not route a narrow refresh through a heavyweight aggregate pipeline when a direct producer or publish step is enough
- If a script is a true full rebuild, name or document it that way explicitly
- If a lighter publish-only or source-specific path exists, use it by default
- When adding a new pipeline, split heavyweight rebuilds from lightweight publish/export steps instead of making one command do everything
- When touching an existing heavy pipeline, prefer adding guardrails or a dedicated lightweight wrapper rather than teaching users to remember the dangerous path
- Keep the user's `10GB RAM` WSL planning constraint in mind; avoid designs that require large all-at-once in-memory joins when a modular path can produce the same published contract

## Thin-Orchestrator Rule

Treat maintainability and token discipline as hard workspace constraints.

- For any non-trivial new pipeline or major refactor, keep one stable
  user-facing entrypoint and split the real logic into focused stage or concern
  modules
- Prefer a thin master/orchestrator script that calls teacher/build/train/publish
  modules rather than one large mixed-responsibility file
- Do not add new `800-1000+` line monolith scripts when the work naturally
  separates into stages
- Optimize file boundaries so a future agent or engineer can inspect only the
  relevant stage instead of rereading unrelated code
- This is partly a token-usage rule: smaller, focused modules reduce repeated
  context-loading and make handoff/recovery cheaper
- Do not overcorrect into dozens of tiny files; prefer a small number of
  focused modules with clear ownership and one canonical entrypoint

## Repo Skill Specs

Repo-owned skill specifications live under `/home/manh/stocks-ecosystem/.skill-build/`.

- `low-resource-data-pipeline`: low-RAM, checkpoint-first data-tool and builder work
- `low-resource-local-ml`: low-VRAM, sequential local-model and distillation work

## Change Map

If changing research data production:

- work in `alpha-research-lab/`
- update research docs there

If changing manual labelling:

- work in `manual-label-factory/`

If changing RL feature consumption, defaults, or merge behavior:

- work in `RL-trading-agent/vn_stock_rl/`
- also read `RL-trading-agent/AGENTS.md`

If changing shared recommendation contracts, artifact registry defaults, or candidate-table schema:

- work in `shared-recommendation/`
- update this root file
- update root `README.md`
- update both alpha and RL docs if producer or consumer expectations change

If changing shared dataset conventions:

- update this root file
- update root `README.md`
- update both research and RL docs

## Safety

- The child repos may have independent git histories
- Do not assume a change in one child repo is isolated from the rest of the workspace
- Be careful with data moves: root `data/` is now canonical
