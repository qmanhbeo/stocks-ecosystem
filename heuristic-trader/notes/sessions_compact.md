# Sessions Compact

(Newest sessions first - source links go here)

---

## Sessions Index

- `session_00026.md` — Session 26: Lab-to-trader promotion contract bridge (MVP)
- `session_00025.md` — Session 25: Strict gate fail-fast enforcement (no eligible challenger)
- `session_00024.md` — Session 24: Profit-ready gated candidate emerged (C8 gate family)
- `session_00023.md` — Session 23: Tail-first risk gate v1 implementation + tests
- `session_00022.md` — Session 22: Signal vs Translation disambiguation (oracle, translation sweep, router)
- `session_00021.md` — Session 21: Reallocate fallback verdict (NEGATIVE/DEPRIORITIZED) + artifact cleanup
- `session_00020.md` — Session 20: Closing Memory Hygiene + Handoff (today)
- `session_00019.md` — Session 19: S1 Depth5 Full 11-Fold Validation (VALIDATED_CANDIDATE with risk caveat)
- `session_00015.md` — Session 15: Depth Frontier Walk-Forward VALID (s1_depth5 sweet spot found)
- `session_00014.md` — Session 14: Walk-Forward Execution Ablation VALID (canonical, parity passed)
- `session_00013.md` — Session 13: Execution Ablation CORRECTED (superseded by S00014)
- `session_00013.md` — Session 12: Execution Ablation INVALID (baseline mismatch, superseded; documented in corrected follow-up log)
- `session_00011.md` — Session 11: Cash Mechanics V2 Accounting (multi-factor confirmed)
- `session_00010.md` — Session 10: Cash Mechanics CORRECTED (superseded by V2)
- `session_00009.md` — Session 9: Cash Mechanics Autopsy (superseded)
- `session_00008.md` — Session 8: Signal wiring - C17/C18 integration
- `session_00007.md` — Session 7: Diagnostics + Ticker-Level PnL Attribution
- `session_00006.md` — Session 6: Lockbox + CLI + Artifact output (Phase 1)
- `session_00005.py` — Session 5: Pre-computed lookup optimization
- `session_00004.md` / `session_00004_fixed.md` — Session 4: Grid search
- `session_00003.md` — Session 3: Backtest engine + constraint-compliant baselines
- `session_00002.md` — Session 2: Trading constraints setup
- `session_00001.md` — Session 1: Signal discovery


---

## S00026 - 2026-05-22: Lab-to-trader promotion contract bridge (MVP)

[link: notes/session_00026.md]

- Added lab-side promotion contract publish in `audit_signal_execution_readiness.py`.
- Added heuristic strict contract consumption in `signal_sweep.py` with optional required-mode.
- Added feedback writeback (`signal_promotion_feedback.csv`) to shared recommendations path.
- Verified via unit tests, py_compile, contract publish run, and strict sweep run.

---

## S00025 - 2026-05-22: Strict gate fail-fast enforcement

[link: notes/session_00025.md]

- Ran canonical signal sweep + challenge selection under strict policy.
- Sweep outcome: `KILL=28/28`, strict-ready candidates `0`.
- Found a workflow flaw: previous selector could still pick fallback challenger even when no strict candidate existed.
- Fixed selector/shadow controls:
  - strict mode default (`PROMOTE_CANDIDATE` only),
  - emitted challenge metadata with `ready_for_shadow=false` when no strict candidate,
  - shadow phase now hard-stops on non-ready challenge sets.

---

## S00022 - 2026-05-19: Signal vs Translation disambiguation

[link: notes/session_00022.md]

- Ran 3-part disambiguation pack:
  - oracle-execution ablation (`exp1_*`)
  - translation parameter sweep (`exp2_*`)
  - train-only regime router (`exp3_*`)
- Source artifact pack:
  - `artifacts/signal_translation_disambiguation/20260519_213127/`
- Result:
  - Translation/execution is a real bottleneck (oracle and tuned variants improved strongly).
  - Risk/regime fragility remains (severe bad-year tails still present).
  - Simple yearly-state router was negative (deprioritized).

---

## S00023 - 2026-05-19: Tail-first risk gate v1 implementation

[link: notes/session_00023.md]

- Implemented strategy-level multi-regime exposure gate in core backtest path.
- Added extreme-only kill-switch with cooldown and state diagnostics.
- Propagated gate config across run/backtest, WFV, profit pipeline, and signal sweep paths.
- Added new tests for gate logic + integration; targeted suite passed.

---

## S00024 - 2026-05-19: Profit-ready gated candidate emerged

[link: notes/session_00024.md]

- Ran gate sweep on translation-best configs and found first profit-ready rows under explicit risk policy.
- Winning family: `m_c8_vol_zscore_5d` with tail-first gate.
- Refined best variant improved mean excess to about `+4.27%` with `8/11` positive folds and `6/11` benchmark-beating folds.
- Promoted strategy entries added for `f30` and refined `f35` floors.

---

## S00021 - 2026-05-13: Reallocate fallback verdict (negative/deprioritized)

[link: notes/session_00021.md]

- Ran patched-code apples-to-apples 2015-2025 walk-forward comparison across:
  - `s1_top5_rebal10`
  - `s1_top5_rebal10_depth5`
  - `s1_top5_rebal10_reallocate`
  - `s1_top5_rebal10_depth5_reallocate`
- Finding: `fallback_mode=reallocate_selected` worsened aggregate mean return/excess and drawdown versus comparators.
- Decision: keep variants for reproducibility, but mark as NEGATIVE/DEPRIORITIZED and not a candidate path.

---

## S00012 - 2026-05-11: Signal wiring pass - C17/C18 integration

[link: notes/session_00008.md]

- Wired C17 raw (`order_volume_ratio`) from `xs_order_pressure_daily.parquet`
- Wired C18 delta (`order_volume_ratio_rank_delta`) - derived signal with fail-closed
- Added SIGNAL_REGISTRY to signals.py (4 signals: S1, C16, C17, C18)
- Added strategies: c17_raw_top5_rebal10, c18_delta_top5_rebal10
- Walk-forward: C17 (-1.37% ann, 5/11 pos), C18 (+0.16% ann, 6/11 pos) - both FRAGILE
- C18 shows better bull-market performance than C17 (2017: -3.34% vs -10.76%)

NOT wired: C19-C26 (need derived formulas from alpha-research-lab)


## S00006 - 2026-05-08: Phase 1 - Lockbox + CLI + Artifacts

[link: notes/session_00006.md]

- Added `MAX_RESEARCH_YEAR = 2025` to signals.py (lockbox protection)
- Added `allow_2026` param to all loader functions
- Created `run_backtest.py` CLI with artifact output
- Artifacts: `artifacts/runs/<ts>/config.json`, `metrics.json`, `daily_equity.parquet`

Verified: s1_only (2019-2025): +41.57% (416tr, 2.2s) ✅


---

## S00007 - 2026-05-11: Diagnostics + Ticker-Level PnL Attribution

[link: notes/session_00007.md]

- Added `collect_diagnostics=True` to backtest.py (does NOT alter metrics)
- Created `test_diagnostics_regression.py` as permanent guardrail
- Trade-level analysis: cash ~70% in bull markets (failure) vs ~60% in success years
- Ticker PnL: blend_70_30_top5 generated +0.76B realized PnL, but underperformed due to cash
- c16_only_top5 is essentially a cash strategy (87-93% cash always)
- **Finding**: Cash drag (~30%) is the MECHANISM of bull-regime failure, not just correlation

Artifacts: `artifacts/ticker_pnl_regime/20260511_171621/`


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
