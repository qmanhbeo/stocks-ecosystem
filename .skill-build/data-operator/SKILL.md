---
name: data-operator
description: Workspace data-operations skill for the stocks ecosystem that understands the canonical root `data/` warehouse and the producer scripts in `alpha-research-lab/data_tools/`. Use when inspecting, refreshing, backfilling, repairing, validating, or extending shared datasets or published feature artifacts; when a user asks to update stock/news/macro/intraday data; when a parquet is stale or missing; when a live feature surface such as `xs_rl_signal_matrix.parquet`, `activation_state_daily.parquet`, or `event_surface_daily.parquet` must be rebuilt; or when Codex needs to know which script owns a file under `data/`.
---

# Data Operator

## Overview

Operate the workspace as one shared data system. Treat `/home/manh/stocks/data` as the canonical warehouse, treat `/home/manh/stocks/alpha-research-lab/data_tools/` as the main producer surface, and map each user request to the narrowest safe fetch, rebuild, repair, or audit workflow.

## Read Order

1. Read the workspace contract first.
- `/home/manh/stocks/AGENTS.md`
- `/home/manh/stocks/README.md`

2. Read the research producer contract next.
- `/home/manh/stocks/alpha-research-lab/README.md`
- `/home/manh/stocks/alpha-research-lab/data_tools/README.md`

3. Read the lab workflow manual when the request touches live/current-date surfaces, published research artifacts, or branch-sensitive rebuilds.
- `/home/manh/stocks/alpha-research-lab/README_for_AGENTS.md`

4. Load bundled references only as needed.
- `references/data-inventory.md` for the current root `data/` layout and maintained artifacts
- `references/data-playbooks.md` for common update, repair, and rebuild commands

## Core Model

- Root `data/` is canonical for the whole workspace.
- `alpha-research-lab/data` is a symlink back to root `data/`; do not create duplicate repo-local data stores.
- `alpha-research-lab/artifacts/` is for lab-local summaries and experiment outputs, not for canonical shared datasets.
- `alpha-research-lab/data_tools/README.md` is the primary operator manual for script ownership, status, and outputs.
- Prefer the narrowest safe command that solves the user request without truncating history or rebuilding unrelated artifacts.

## Request Classifier

1. Classify the request before acting.
- `inspect/audit`: find what exists, what is stale, and which script owns it
- `refresh raw data`: top up stock, news, macro, insider, intraday, or cache inputs
- `rebuild derived artifacts`: regenerate feature parquets from existing raw inputs
- `repair`: recover from truncated history, corrupted parquet, or missing downstream artifacts
- `contract change`: change published paths, schemas, or producer-consumer expectations

2. Use the matching workflow.
- For `inspect/audit`, inspect the real files first, then confirm ownership in `data_tools/README.md`.
- For `refresh raw data`, run the relevant fetcher from `alpha-research-lab/` with the safest date window.
- For `rebuild derived artifacts`, run the builder that owns the target artifact and then verify the output exists and is current.
- For `repair`, restore the upstream dependency first, then rerun the downstream chain.
- For `contract change`, update producer code and docs together; if the change crosses repo boundaries or shared published surfaces, also use the workspace infrastructure workflow instead of treating it as a local data tweak.

## Operating Rules

- Run data-tool commands from `/home/manh/stocks/alpha-research-lab/`.
- Prefer `conda run -n stocks python ...` unless the active shell is already inside the correct environment.
- After any stock-history change, assume downstream stock-derived artifacts may be stale until verified.
- Never use a recent `--start` window on stock refresh scripts when the next step needs long lookback history.
- Always check `data/stock/gia_lich_su_VNINDEX_1D.parquet` after stock refreshes; benchmark truncation alone can break live `S1`.
- There is no single supported "refresh every feature" command; compose the specific fetchers and builders the request actually needs.
- Treat `data/features/recommendations/` and other `data/features/` outputs as shared published surfaces, not private scratch space.
- Do not delete maintained artifacts just because a narrower research branch failed; distinguish active, limited-coverage, legacy, and archive-only files.

## Canonical Playbooks

### Inspect Or Audit

- Inspect the real directory or target file first.
- Use `alpha-research-lab/data_tools/README.md` to map a data file to its fetcher or builder.
- Use `references/data-inventory.md` when you need a quick view of the maintained root layout.
- Report:
  - current file or directory state
  - canonical owner script
  - whether the artifact is active, limited, legacy, or archive-only
  - the narrowest safe next step

### Refresh Raw Data

- For single or small stock refreshes, use `data_tools/fetch_stock.py`.
- For current-universe top-ups, use `data_tools/fetch_refresh_all.py`.
- For full-history stock restoration after truncation, use the safe full-range refresh in `references/data-playbooks.md`.
- For new HOSE names, use `data_tools/fetch_hose_universe.py`.
- For news, distinguish full archive restore from daily incremental crawling.
- For intraday, prefer the explicit CafeF chain first:
  1. fetch raw CafeF hourly bars
  2. adjust them onto the VCI daily backbone if cross-day continuity matters
- Use SSI intraday only when the request explicitly accepts credentials or the open CafeF path is insufficient.

### Rebuild Derived Artifacts

- Rebuild only the artifact family affected by the upstream change.
- When stock history changed and the user needs live/current-date maintained surfaces, use the live-chain workflow in `references/data-playbooks.md`.
- When the target is a specific maintained feature file, run the builder that owns that file and verify the output timestamp and row coverage if relevant.
- When a downstream artifact depends on another maintained feature surface, rebuild or verify the dependency first instead of assuming it is current.

### Repair Broken Data

- If a parquet is missing or corrupted, restore the smallest upstream source that can recreate it.
- If stock history was truncated:
  1. restore full daily history first
  2. verify `VNINDEX`
  3. rerun stock-derived maintained builders needed by the user’s task
- If a live/current-date surface is stale after a stock refresh, rerun the full live chain rather than patching just the final file.
- If a limited-coverage artifact is the issue, confirm whether the real fix is a full-universe rerun rather than a bug in the builder.

### Change Published Contracts

- If the user wants to change where canonical data lives, rename published artifacts, alter schemas, or change which repo consumes a shared output, do not stop at the local script.
- Update the producer, the workspace docs, and every affected consumer contract together.
- Treat this as a workspace contract change, not just a data refresh.

## High-Value Maintained Surfaces

- `data/stock/gia_lich_su_<TICKER>_1D.parquet`: canonical daily HOSE price history
- `data/features/xs_barrier_vol_1d_hose_full.parquet`: historical `S1`
- `data/features/xs_barrier_vol_1d_hose_live_current.parquet`: current-date `S1` live extension
- `data/features/xs_rl_signal_matrix.parquet`: consolidated maintained RL feature matrix
- `data/features/execution/tradability_daily.parquet`: shared execution/liquidity contract
- `data/features/activation_state_daily.parquet`: date-level activation state surface
- `data/features/activation_meta_daily.parquet`: selector-efficacy activation-meta surface
- `data/features/event_surface_daily.parquet`: canonical corporate-event surface

Read `references/data-inventory.md` for the broader maintained, limited, and archive-only inventory.

## Output Pattern

When advising or acting, end with:

- `request class`
- `owner script or scripts`
- `inputs touched`
- `outputs expected`
- `verification`
- `follow-on rebuilds required`

If the request changes a shared published contract, also state which docs and consumers must change together.
