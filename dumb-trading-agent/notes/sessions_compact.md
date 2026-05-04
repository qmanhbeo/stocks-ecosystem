# Sessions Compact

(Newest sessions first - source links go here)

---

## Sessions Index

- `session_00001.md` — Session 1: Signal discovery
- `session_00002.md` — Session 2: Trading constraints setup  
- `session_00003.md` — Session 3: Backtest engine + constraint-compliant baselines


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