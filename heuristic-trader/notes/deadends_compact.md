# Dead Ends Compact

---

## D00003 — Fallback challenger selection from non-strict rows (deprioritized as default flow) (2026-05-22)

[link: notes/session_00025.md]

- Selecting a challenger from non-`PROMOTE_CANDIDATE` rows when strict candidate count is zero is a process dead end.
- It can advance shadow comparisons on known non-promotable strategies and masks true gate failure.
- Reopen only for explicitly labeled diagnostics (`selection_mode=research|any`), not promotion flow.

---

## D00002 — Coarse yearly regime router is negative (2026-05-19)

[link: notes/session_00022.md]

- Tested train-only router with state = prior-year VNINDEX sign (`bull`/`bear`).
- Router reduced mean excess for all tested top strategies vs canonical always-on.
- Decision: deprioritize this router design; reopen only with richer regime-state features and tighter risk objective.

---

## D00001 — S1 reallocate-selected fallback (deprioritized) (2026-05-13)

Provenance:
- Artifacts were generated during the 2026-05-13 patched-code WFV comparison and removed after metrics were extracted into this note/session log.

- Tested `fallback_mode=reallocate_selected` as first execution fallback experiment.
- Result: worsened aggregate WFV metrics vs patched-code comparators for S1 baseline and S1 depth5.
- Decision: retain configs for reproducibility, but treat as negative/deprioritized and do not promote.

---

## Dead Ends Index

- `dead_ends_00001_00030.md` — chunk 1 (entries 00001-00030)
