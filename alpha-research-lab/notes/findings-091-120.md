## F91: The RL Signal Library Does Not Yet Monetize as a Realistic Long-Only Portfolio (2026-03-28, Session 45)

H135 tested the promoted RL signal library as a deterministic long-only portfolio under the
workspace execution contract:
- signal observed at `T` close
- execute at `T+1` open
- cannot sell before `T+3` close / `T+4` open
- zero-volume and ceiling/floor tradability blocks active
- 0.30% round-trip cost (`0.15%` buy + `0.15%` sell)
- top-5 equal-weight portfolio
- 3-day rebalance cadence
- no ADV capacity cap in the baseline run

**Result:** the current library does **not** survive as a standalone long-only money machine.

| Strategy | Total Return | Annualized | Relative vs VNINDEX | Info Ratio | Max DD | Positive Years |
|---|---:|---:|---:|---:|---:|---:|
| `s1_only` | -68.33% | -10.01% | -90.20% | -0.57 | -88.84% | 4/11 |
| `recent_core` (`S1+C10-C14`) | -83.44% | -15.21% | -94.88% | -0.67 | -96.19% | 3/11 |
| `full_library` (`S1+C4-C14`) | **-9.76%** | **-0.94%** | **-72.08%** | **-0.24** | **-77.25%** | **5/11** |

The benchmark VNINDEX compounded to **+223.17%** over the same 2015-2025 window.

**Key finding:** the signal library is still useful as a diverse state surface, but it is not yet a
plug-and-play long-only portfolio strategy under realistic execution. That means **RL is not the
next monetization shortcut**. The blocking problem is portfolio construction and execution reality,
not lack of more standalone signal IC.

**Implication:** before more RL training, the lab must search for a deterministic construction that
actually survives `T+2.5` settlement, turnover, and tradability constraints.

---
## F92: Capacity Is a First-Order Stress Variable, Not a Safe Default Constant (2026-03-28, Session 45)

A separate H135 stress run added a simple ADV participation cap:
- portfolio notional = `1B VND`
- max participation = `1%` of `ADV20`

Under that constraint, the portfolio became almost entirely uninvested:

| Strategy | Avg Cash Weight | Avg Holdings | Total Return |
|---|---:|---:|---:|
| `s1_only` | 99.88% | 12.52 | -1.08% |
| `recent_core` | 99.97% | 9.69 | -0.04% |
| `full_library` | 99.90% | 9.47 | -0.92% |

**Key finding:** a seemingly modest capacity rule can dominate the result on this historical HOSE
universe. The right interpretation is **not** “the strategy is safe because losses are small.” The
real interpretation is that the backtest is mostly sitting in cash because capacity has become the
main bottleneck.

**Implication:** capacity must be treated as a sweep / stress dimension, not hard-coded as the one
true default. The next honest step is a grid over portfolio notional and ADV participation, so the
lab can see where the strategy is actually deployable instead of arguing from a single arbitrary cap.

---
## F93: The Initial H135 Library-Blend Failure Was Caused by a Signal-Scale Bug, Not by the Library Being Economically Dead (2026-03-28, Session 46)

Session 46 re-audited the H135 deterministic baseline and found a structural bug in the blend
construction:

- non-presence signals were averaged directly in raw matrix scale
- `C4` and `C5` were not already on a common `0-1` rank scale inside
  `data/features/xs_rl_signal_matrix.parquet`
- this let raw-scale columns distort the `recent_core` / `full_library` score blends

The fix was to cross-sectionally rank each **non-presence** signal by date before averaging it into
the portfolio score. Presence flags remain `0/1`.

Under the corrected blend logic, the same realistic H135 contract:
- signal at `T` close
- buy at `T+1` open
- earliest sell at `T+3` close / `T+4` open
- zero-volume and ceiling/floor blocks
- `0.30%` round-trip cost
- top-5 equal-weight
- 3-day rebalance

now produces:

| Strategy | Total Return | Annualized | Relative vs VNINDEX | Info Ratio |
|---|---:|---:|---:|---:|
| `s1_only` | -68.33% | -10.01% | -90.20% | -0.57 |
| `recent_core` | -46.81% | -5.63% | -83.54% | -0.40 |
| `full_library` | **+72.10%** | **+5.11%** | **-46.75%** | **-0.05** |

**Key finding:** the earlier “the library does not monetize at all” reading was too strong. The
library is weak under the default realistic construction, but it is **not** economically dead.
Session 45's original H135 `full_library` fail should be treated as superseded by this corrected
blend logic.

**Implication:** before making strategic decisions from any portfolio blend, enforce a common
cross-sectional scale across all input signals. Raw-signal averaging is not a harmless shortcut.

---
## F94: Portfolio Construction, Not More Signal Mining, Is the Dominant Lever After H136 (2026-03-28, Session 46)

H136 swept the corrected `full_library` blend across:
- `top_k = 3, 5, 8, 10`
- rebalance cadence `= 3, 5, 10` signal days
- weighting `= equal, linear, square`
- score gates `= none, 0.521, 0.570, 0.600`

Best configuration:
- `top_k = 5`
- rebalance every `5` signal days
- `equal` weighting
- score gate effectively irrelevant (`none`, `0.521`, and `0.570` tie)

Best result:

| Metric | Value |
|---|---:|
| Total Return | **+1105.71%** |
| Annualized Return | **+25.66%** |
| Relative vs VNINDEX | **+273.09%** |
| Information Ratio | **0.50** |
| Max Drawdown | **-59.76%** |
| Positive Years | **8 / 11** |
| Avg Daily Turnover | **33.54%** |

Grid-level pattern:
- `5d` cadence is the best regime
- `10d` cadence is next-best
- `3d` cadence is materially worse
- `equal` weighting beats `linear` and `square`
- `top_k = 5` is the best absolute performer
- moderate score gating does not matter in the winning region because the top names already clear it

**Key finding:** once the blend is normalized correctly, the monetization frontier shifts away from
“find more signals” and toward **portfolio construction and honest validation**.

**Implication:** the next work should be:
- honest out-of-sample validation of the H136 winner
- capacity and fee/slippage stress on that winner
- only after that, RL as a portfolio overlay that must beat the deterministic baseline

---
## F95: Simple ML-Style Construction Selection Does Not Yet Survive Honest Walk-Forward Testing (2026-03-28, Session 47)

H137 implemented the honest version of “let the machine choose the portfolio construction”:

- expanding train window
- minimum `4` train years
- candidate menu = the same H136 construction grid
- on each split, pick the best config on train years only
- freeze that config and test it on the next year
- stitched out-of-sample test years: `2019-2025`

The selected configs were not exotic:
- `top_k=5`, rebalance every `10` signal days, `equal` weighting was chosen `4/7` test years
- early years briefly chose `top_k=3`, `5d`, `equal`
- one year chose `top_k=10`, `5d`, `equal`

Out-of-sample stitched result:

| Metric | Value |
|---|---:|
| Total Return | **+21.38%** |
| Annualized Return | **+2.84%** |
| Relative vs VNINDEX | **-42.46%** |
| Information Ratio | **-0.08** |
| Max Drawdown | **-55.65%** |

Per-year test outcomes were mixed:
- positive in `2019`, `2020`, `2021`, `2023`
- negative in `2022`, `2024`, `2025`
- the final three test years were all benchmark-relative disappointments

**Key finding:** the full-sample H136 winner was too optimistic. A simple nested selector over the
existing construction grid does **not** validate “machine-learned configuration” as a near-term
production edge.

**Implication:** do not add more ML complexity yet. The next honest path is:
- reduce to a tiny fixed menu of simple constructions
- test those honestly
- if long-only still fails benchmark-relative, move to hedged constructions before RL

---
## F96: Fixed Simple Constructions Beat the Benchmark Out of Sample Better Than the ML-Style Selector (2026-03-28, Session 48)

H138 removed yearly re-selection entirely and tested a tiny fixed menu on the honest holdout
`2019-2025`:

- `k3_r5_eq` = top-3, rebalance every 5 signal days, equal weight
- `k5_r5_eq` = top-5, rebalance every 5 signal days, equal weight
- `k5_r10_eq` = top-5, rebalance every 10 signal days, equal weight

All three fixed rules beat VNINDEX on the holdout:

| Rule | Total Return | Annualized | Relative vs VNINDEX | Information Ratio | Positive Years |
|---|---:|---:|---:|---:|---:|
| `k3_r5_eq` | **+303.01%** | **+22.25%** | **+106.86%** | **0.43** | 5/7 |
| `k5_r5_eq` | +271.38% | +20.82% | +90.62% | 0.42 | **6/7** |
| `k5_r10_eq` | +241.90% | +19.39% | +75.49% | 0.38 | 4/7 |

For comparison, H137’s nested selector only achieved:
- `+21.38%` total
- `-42.46%` relative vs VNINDEX

**Key finding:** the yearly ML-style selector was worse than a few simple fixed rules. The problem
was not “the long-only construction idea is dead”; the problem was overfitting through re-selection.

**Implication:** before any more ML selection or RL overlays, the lab should treat a tiny menu of
simple deterministic constructions as the real baseline class.

---
## F97: The Long-Only Edge Survives Fee Stress but Collapses Under Any Tested ADV Participation Cap (2026-03-28, Session 48)

H139 stress-tested the H138 fixed-rule candidates on the same `2019-2025` holdout across:
- notionals `50m, 100m, 250m, 500m, 1B VND`
- ADV participation caps `0.0%, 0.5%, 1.0%, 2.0%`
- round-trip costs `0.30%, 0.50%`

Uncapped results remain economically strong:
- at `0.50%` RT and **no ADV cap**, all three candidates still stay positive benchmark-relative
- best uncapped stressed rule:
  - `k5_r10_eq`: `+154.31%` total, `+30.53%` relative vs VNINDEX

But capacity destroys deployability:
- number of scenarios with `relative_total_return > 0` and `max_adv_participation > 0`: **0**
- best relative return by ADV cap:
  - `0.0%`: **+106.86%**
  - `0.5%`: **-48.66%**
  - `1.0%`: **-48.64%**
  - `2.0%`: **-48.45%**
- minimum average cash weight by ADV cap:
  - `0.5%`: **99.32%**
  - `1.0%`: **98.64%**
  - `2.0%`: **97.34%**

**Key finding:** the edge is not killed first by fees; it is killed first by capacity. The current
long-only constructions are only attractive in effectively uncapped backtests.

**Implication:** the next bottleneck is not more ML. It is finding a **capacity-aware construction**
that preserves enough of the edge to stay benchmark-competitive under explicit deployability
constraints.
