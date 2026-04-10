# AGENTS.md

Root coordination notes for coding agents working in `/home/manh/stocks`.

## Start Here

Read these first:

- `README.md`
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
- `data/proprietary_trading/` is a raw historical CafeF proprietary-trading surface
- `data/foreign_flow_forward/` is a forward-only raw acquisition surface, not a historical feature backfill
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
- Treat `data/foreign_flow/` as a raw source surface until a research-owned feature artifact is published from it
- Treat `data/order_stats/` as a raw source surface until a research-owned feature artifact is published from it
- Treat `data/proprietary_trading/` as a raw source surface until a research-owned feature artifact is published from it
- Treat `data/foreign_flow_forward/` as forward-only raw data; do not use it in historical alpha tests until enough post-collection history exists
- When changing producer/consumer boundaries, update docs in both the producer and consumer project

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
