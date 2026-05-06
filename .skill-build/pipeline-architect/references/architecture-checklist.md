# Pipeline Architecture Checklist

## Before Refactoring

- Identify the stable user-facing command.
- Identify which stages are truly distinct.
- Identify shared contracts: paths, schemas, manifests, docs, consumers.

## Good Target Shape

- One thin entrypoint or orchestrator.
- A small number of stage modules.
- Shared helpers only where reuse is real.
- No speculative framework.

## Verify After Refactoring

- Imports and CLI still work.
- Focused tests around changed stages pass.
- Shared-contract docs stay aligned.
