# Sessions Compact

(Newest sessions first - source links go here)

---

## Sessions Index

- `session_00006.md` — Session 6: Lockbox + CLI + Artifact output (Phase 1)
- `session_00005.md` — Session 5: Pre-computed lookup optimization
- `session_00004.md` / `session_00004_fixed.md` — Session 4: Grid search
- `session_00003.md` — Session 3: Backtest engine + constraint-compliant baselines
- `session_00002.md` — Session 2: Trading constraints setup
- `session_00001.md` — Session 1: Signal discovery


---

## S00006 - 2026-05-08: Phase 1 - Lockbox + CLI + Artifacts

[link: notes/session_00006.md]

- `run_backtest.py` CLI with `--allow-lockbox` flag
- `signals.py` loaders enforce MAX_RESEARCH_YEAR=2025
- Artifacts: `artifacts/runs/<ts>/config.json`, `metrics.json`, `daily_equity.parquet`

Verified: s1_only (2019-2025): +41.57% (416tr, 2.2s) ✅


---

## S00005 - 2026-05-04: Pre-computed lookup optimization

[link: session_00005.py]

- Implemented pre-computed liquid_lookup + trad_lookup
- Quick run: ~2.5s vs legacy ~5min


---

## S00004 FIXED - 2026-05-04: Grid search

[link: notes/session_00004_fixed.md]

**FINDINGS F00005 + F00006**:
- S1 5-day: -37.10% (770 trades) — fees kill
- **S1 10-day: +43.14%** (413 trades) — sweet spot
- S1 20-day: +16.31% (229 trades)
- C16 10-day: +31.97% (68 trades)
- **S1+C16 blend: +51.99%** (315 trades) ← BEST


---

## S00003 - 2026-05-04: Constraint-compliant backtest

[link: notes/session_00003.md]

Key finding F00001: Transaction costs dominate. VNINDEX: +94%, S1 Top-5 (20-day): +3.84%, Daily: -80%.
Found F00002: Lab's C16 is much stronger (IC 0.0738 vs S1 ~0 under fees).
Found F00003: Lab solved transaction costs with 5-day rebalance + H211 exits + H175 activation.

---

## S00002 - 2026-05-04: Trading constraints setup

[link: notes/session_00002.md]

Created `constraints.py` mirroring RL-trading-agent rules.

---

## S00001 - 2026-05-04: Signal discovery

[link: notes/session_00001.md]

Created `signals.py` with lab signals.