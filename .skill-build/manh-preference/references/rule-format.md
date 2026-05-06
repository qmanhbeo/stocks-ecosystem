# Preference Rule Format

What this file is for: the exact shape for machine-wide preference entries so
future agents do not invent their own rule structure.

Each preference entry should be written using these fields:

- `Default`
- `Scope`
- `Carve-out`
- `Legacy behavior`
- `Related`

## Field Meanings

### Default

State the actual operating rule in a way that can be applied mechanically.

### Scope

State where the rule applies:
- task types
- surfaces
- repos
- files
- workflows

### Carve-out

Name the explicit situations where the default does not apply or may be
relaxed. Do not leave exceptions implicit when they matter.

### Legacy behavior

State how to treat existing older surfaces that predate the current rule.
Default posture:
- grandfather coherent legacy behavior
- repair on material touch

### Related

Point to the owning or dependent skills and references that should stay aligned.

## Writing Rules

- Prefer short, exact wording.
- Avoid long essays or repeated examples.
- Do not encode a preference as a vague aspiration.
- If the user repeatedly corrects the same behavior, the rule should become
  more mechanical, not more narrative.
