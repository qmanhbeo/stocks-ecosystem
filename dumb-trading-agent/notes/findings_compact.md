# Findings Compact

(Thematic recovery view - newest first)

---

## F00006 — S1+C16 blend beats S1 alone (2026-05-04)

[link: findings_00001_00030.md]

With 10-day rebalance:
- VNINDEX: +94.72% (2 trades)
- S1 10-day: +43.14% (413 trades)
- C16 10-day: +31.97% (68 trades)
- **S1+C16 blend: +51.99%** (315 trades)

Blend (50/50) captures complementary signal value.


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