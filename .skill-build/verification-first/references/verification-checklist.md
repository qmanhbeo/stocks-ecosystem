# Verification-First Checklist

## Preflight

- Inspect the current path, schema, or contract.
- Confirm the real owner file or module.
- Decide whether the change is local or shared.

## Verification Ladder

- Syntax/import checks if structure changed.
- Focused unit or feature tests around the edited path.
- Broader suite only if a shared contract or public behavior changed.
- Runtime/manual verification only if the task actually requires it.

## Reporting

- What changed.
- What was verified.
- What was not verified.
- What command resumes the next step.
