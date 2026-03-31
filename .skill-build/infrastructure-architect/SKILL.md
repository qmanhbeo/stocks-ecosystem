---
name: infrastructure-architect
description: Infrastructure-change skill for the stocks workspace that understands how data, artifacts, schemas, and defaults flow across the shared root `data/`, `alpha-research-lab`, `shared-recommendation`, and `RL-trading-agent`. Use when adding, removing, or modifying shared paths, published feature artifacts, recommendation contracts, matrix adapters, execution/tradability contracts, producer-consumer boundaries, or other cross-repo infrastructure behavior that must stay coherent end to end.
---

# Infrastructure Architect

## Overview

Treat the workspace as one system. Change the canonical owner once, then propagate the contract through producers, registry, consumers, and docs so paths, schemas, and defaults do not drift.

## Read Order

1. Read workspace coordination first.
- `AGENTS.md`
- `README.md`

2. Read the research producer contract.
- `alpha-research-lab/README.md`
- `alpha-research-lab/README_for_AGENTS.md` when the change touches published research outputs or lab artifacts

3. Read the shared registry contract.
- `shared-recommendation/README.md`
- `shared-recommendation/shared_recommendation/artifacts.py`

4. Read the RL consumer contract.
- `RL-trading-agent/README.md`
- `RL-trading-agent/AGENTS.md`
- `RL-trading-agent/docs/pipeline_contracts.md`

## System Flow

1. Durable shared data lives under root `data/`.
2. `alpha-research-lab/` produces research features and publishes shared artifacts into root `data/`.
3. `alpha-research-lab/artifacts/` stores lab-local summaries and experiment outputs, not the canonical shared data surface.
4. `shared-recommendation/` owns artifact resolution, candidate output paths, and recommendation-table contracts.
5. `RL-trading-agent/` consumes shared research exports from root `data/` and adapts the consolidated lab matrix into the RL per-ticker contract.
6. `RL-trading-agent/artifacts/` stores RL runtime outputs such as trained models and evaluations.

## Ownership Rules

- Shared durable artifact defaults belong in `shared-recommendation/shared_recommendation/artifacts.py`.
- Lab-local artifact anchoring belongs in `alpha-research-lab/src/repo_paths.py` and `alpha-research-lab/src/run_summary.py`.
- Recommendation request/result contracts belong in `shared-recommendation/shared_recommendation/contracts.py`.
- Recommendation write behavior belongs in `shared-recommendation/shared_recommendation/engine.py` and `shared-recommendation/shared_recommendation/io.py`.
- RL shared-feature default paths belong in `RL-trading-agent/vn_stock_rl/external_features.py`.
- RL lab-matrix adaptation belongs in `RL-trading-agent/vn_stock_rl/data_tools/export_lab_signal_matrix.py`.
- RL merge semantics and observation behavior belong in `RL-trading-agent/vn_stock_rl/env/base.py` and related env modules.
- Shared execution realism belongs in `docs/execution_reality.md`, `shared-market-rules/`, the lab producer `alpha-research-lab/data_tools/build_tradability_flags.py`, and RL env consumers.

## Infrastructure Workflow

1. Classify the change.
- Decide whether it is a:
  - shared data-path change
  - published artifact/schema change
  - recommendation contract change
  - RL adapter or merge change
  - execution/tradability contract change
  - lab-local artifact-path change

2. Find the canonical owner.
- Update the owner first.
- Do not start with downstream wrappers or compatibility shims unless the user explicitly wants a migration layer.

3. Patch the boundary surfaces together.
- Producer: where the artifact or schema is written.
- Registry: where the shared path or key is resolved.
- Consumer: where the artifact is loaded, adapted, or merged.
- Docs: every place the path, command, or contract is user-facing.

4. Keep storage rules intact.
- Root `data/` is the canonical shared warehouse.
- Do not reintroduce repo-local duplicate data stores.
- Keep lab experiment summaries under `alpha-research-lab/artifacts/`.
- Keep RL run outputs under `RL-trading-agent/artifacts/`.

5. Verify end to end.
- Confirm the producer writes the expected artifact.
- Confirm the registry resolves the same path.
- Confirm the consumer reads the updated contract successfully.
- Confirm docs and defaults match the implementation.

## Change Map

- If changing shared data roots or published artifact defaults:
  - `shared-recommendation/shared_recommendation/artifacts.py`
  - `RL-trading-agent/vn_stock_rl/external_features.py`
  - root `AGENTS.md`
  - root `README.md`

- If changing recommendation candidate paths, manifests, or table contracts:
  - `shared-recommendation/shared_recommendation/contracts.py`
  - `shared-recommendation/shared_recommendation/engine.py`
  - `shared-recommendation/shared_recommendation/io.py`
  - `shared-recommendation/shared_recommendation/policies.py` when eligibility or policy columns change
  - `shared-recommendation/README.md`
  - alpha or RL docs if producer or consumer expectations change

- If changing the consolidated lab matrix contract:
  - the alpha producer that writes `data/features/xs_rl_signal_matrix.parquet`
  - `RL-trading-agent/vn_stock_rl/data_tools/export_lab_signal_matrix.py`
  - `RL-trading-agent/vn_stock_rl/external_features.py` if defaults or helpers change
  - `RL-trading-agent/docs/pipeline_contracts.md`
  - `RL-trading-agent/README.md`

- If changing RL feature defaults, merge behavior, or observation composition:
  - `RL-trading-agent/vn_stock_rl/external_features.py`
  - `RL-trading-agent/vn_stock_rl/config/cli_shared.py`
  - `RL-trading-agent/vn_stock_rl/env/base.py`
  - related env modules when the change is mode-specific

- If changing lab-local artifact output behavior:
  - `alpha-research-lab/src/repo_paths.py`
  - `alpha-research-lab/src/run_summary.py`
  - the producing analysis or `src/` module that writes the output
  - `alpha-research-lab/README.md`

- If changing execution/tradability rules:
  - `docs/execution_reality.md`
  - `shared-market-rules/`
  - `alpha-research-lab/data_tools/build_tradability_flags.py`
  - RL env rule consumers
  - root and RL docs that describe the strict-core behavior

## Verification Patterns

- For shared path changes:
  - resolve the path through `shared_recommendation.artifacts`
  - confirm the producer writes there
  - confirm the consumer reads there

- For lab artifact-path changes:
  - run the narrowest alpha tests around repo-anchored artifacts
  - verify summaries land in `alpha-research-lab/artifacts/run_summaries/`

- For RL matrix changes:
  - run `python -m vn_stock_rl.data_tools.export_lab_signal_matrix`
  - run `python -m vn_stock_rl.data_tools.inspect_research_exports --require-lab-matrix --require-lab-adapter`

- For recommendation contract changes:
  - run the focused shared-recommendation tests
  - confirm `latest_candidates.parquet` and `manifest.json` still write to the expected profile root

- For execution/tradability changes:
  - verify the produced `data/features/execution/tradability_daily.parquet`
  - verify RL consumers still enforce the same contract end to end

## Guardrails

- Prefer one canonical owner per contract.
- Do not move durable shared outputs into repo-local `artifacts/`.
- Do not patch only the consumer when the producer or registry owns the real contract.
- Do not change a shared path default without updating the user-facing docs at the same time.
- Do not treat cross-repo producer-consumer boundaries as local implementation details.
- When a schema or default changes, update both the producing and consuming sides in the same pass.

## Output Pattern

When advising or implementing, state:

- `change category`
- `canonical owner`
- `files that must change together`
- `producer impact`
- `consumer impact`
- `verification plan`

End with the exact contract after the change: path, schema, command, or default behavior.
