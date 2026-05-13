# Session 273 Log

**Date**: 2026-05-05
**Focus**: Signal promotion rule clarification

## Summary

- Clarified the repo-wide signal-library promotion rule after the S272 audit.
- Updated `README.md`, `notes/signal_library.md`, and
  `notes/findings_compact.md` so `IC > 0.05` is the strong standalone
  signal-promotion bar, not merely an informal shorthand.
- Made the parent-signal caveat explicit: filters, buckets, and rewrites of
  S1, C16, or any existing parent must be judged by incremental lift versus
  that parent and matched controls, not just by absolute IC versus random.

## Rule

Strong standalone signal promotion requires:
- IC `> 0.05`
- decision-time observability
- low correlation with existing library signals (`< 0.30`)
- positive IC in at least `60%` of tested years
- enough coverage for the claim
- no target-derived or future-derived state definition

Weak candidate/context:
- IC between `0.01` and `0.05`
- or IC `> 0.05` with sparse coverage, unresolved controls, or limited
  consumer fit

Parent-signal conditioner:
- must show incremental lift versus the parent signal and mechanism-matched
  controls. Absolute IC `> 0.05` is real market edge, but not enough to claim a
  new independent signal if the edge is mostly inherited from the parent.

## Files Updated

- `README.md`
- `notes/signal_library.md`
- `notes/findings_compact.md`
- `notes/findings-00331-00360.md`
- `notes/sessions_compact.md`
- `notes/live_state.md`

## Verification

```bash
git diff --check
```
