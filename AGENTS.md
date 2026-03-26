# AGENTS.md

Root coordination notes for coding agents working in `/home/manh/stocks`.

## Start Here

Read these first:

- `README.md`
- `alpha-research-lab/README.md`
- `VN-stock-RL/README.md`
- `VN-stock-RL/AGENTS.md` when changing RL runtime code

## Workspace Model

This workspace is an ecosystem, not a set of truly standalone repos.

Current responsibilities:

- `data/` is the canonical shared data root for the entire workspace
- `alpha-research-lab/` owns research pipelines and research outputs
- `manual-label-factory/` owns the manual buy-zone labelling UI
- `VN-stock-RL/` owns RL runtime logic and consumes artifacts from root `data/`

## Important Paths

- Shared raw + published data: `/home/manh/stocks/data`
- Research lab: `/home/manh/stocks/alpha-research-lab`
- Manual label factory: `/home/manh/stocks/manual-label-factory`
- RL runtime: `/home/manh/stocks/VN-stock-RL`

## Default Assumptions

- Prefer root `data/` over repo-local `data/` paths
- Do not reintroduce duplicate data stores inside child repos unless explicitly requested
- Treat cross-project path contracts as ecosystem-level contracts
- When changing producer/consumer boundaries, update docs in both the producer and consumer project

## Change Map

If changing research data production:

- work in `alpha-research-lab/`
- update research docs there

If changing manual labelling:

- work in `manual-label-factory/`

If changing RL feature consumption, defaults, or merge behavior:

- work in `VN-stock-RL/vn_stock_rl/`
- also read `VN-stock-RL/AGENTS.md`

If changing shared dataset conventions:

- update this root file
- update root `README.md`
- update both research and RL docs

## Safety

- The child repos may have independent git histories
- Do not assume a change in one child repo is isolated from the rest of the workspace
- Be careful with data moves: root `data/` is now canonical
