# Findings Compact

(Thematic recovery view - newest first)

---

## F00007 — Cache parity: missing-date semantics fixed (2026-05-11)

[link: findings_00001_00030.md]

**BUG FIX**: Pre-computed vs legacy parity gap (~4% return gap).

**Root cause**: 
- `build_liquid_cache()` window logic differed from `check_liquid()`
- `check_liquid()` used fallback to last date; precomputed couldn't

**Fix**: 
- Updated `build_cache.py` window to `max(0, idx-5)`
- Updated `check_liquid()` to fail-closed (no fallback)
- Rebuilt cache - parity now passes

**HARD RULE**: "No exact ticker-date row, no claim." 
Missing-date = not liquid. Fallback creates lookahead bias. Cache is research logic.


---

## F00006 — 70/30 blend is optimal (2026-05-04)

[link: findings_00001_00030.md]

Blend grid (10-day rebal, with filters):
- 50/50: +51.99% (315tr)
- 60/40: +54.81% (364tr)
- **70/30: +82.39%** (397tr) ← USE LEGACY
- 80/20: +75.30% (431tr)

**NOTE**: Pre-computed lookups give +99.86% but have a bug - use for param selection only.
Always verify with legacy filters before publishing.


---

## F00005 — 10-day rebalance is the sweet spot (2026-05-04)

[link: findings_00001_00030.md]

S1 Top-5 grid search results:
- rebal=5d: -37.10% (770 trades) — DESTROYED by fees
- **rebal=10d: +43.14% (413 trades)** — BEATS VNINDEX!
- rebal=20d: +16.31% (229 trades)

Key insight: 10-day rebalance balances signal vs costs.


---

## F00004 — FIXED: Volume unit bug + turnover kills (2026-05-04)

[link: findings_00001_00030.md]

**BUG DISCOVERED**: Volume was in shares, not VND.
Corrected filter: 500k shares (not 10M VND).

S1 5-day: -37.10% (770 trades) — destroyed by fees.


---

## Findings Index

- `findings_00001_00030.md` — chunk 1 (entries 00001-00030)