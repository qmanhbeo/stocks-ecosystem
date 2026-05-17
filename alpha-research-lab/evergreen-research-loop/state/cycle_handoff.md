# Evergreen Cycle Handoff

## Cycle 33 — 2026-05-17

**Last action:** Session 390 (H107 Signal Order as Hidden State) - FAILED, D084

**Outcome:** Signal order does NOT add value. first_any IC=0.2360 vs composite=0.2445 (-0.0085). Dead-end D084.

**Key findings:**
- F447: composite_2+×low_breadth = 0.2651 (BEST)
- F445: composite_2+ = 0.2445
- F440: cofire Q1 = 0.2064
- H121 (triple): 0.2702 (MIXED)
- H107 (signal order): FAILED, D084

**Updated:**
- `notes/session_00390_log.md`
- `notes/sessions_compact.md` - Sessions 387-390
- `notes/live_state.md` - sessions 387-390, D082-D084, new ideas 126-132
- `notes/deadends-00031-00060.md` - D084
- `notes/deadends_compact.md` - D084

**Next queue head:** H108 (Multi-Signal × Blocked Triple) or new ideas 127/129/132

**Blockers:** Intraday BLOCKED, order arrival BLOCKED, volume D060, ultra_negative UNAVAILABLE

**Source of truth:** `notes/live_state.md` + `notes/sessions_compact.md` + `artifacts/run_summaries/YYYYMMDD_*.json`

---

`cd alpha-research-lab && make loop`