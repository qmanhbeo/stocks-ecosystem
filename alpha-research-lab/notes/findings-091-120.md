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

---
## F98: Signal-Date Liquidity Alignment Is a Hard Market-Rule Invariant, Not an Implementation Detail (2026-03-28, Session 49)

Session 49 found a one-day timing bug in the deterministic portfolio engine:

- `can_buy_next_open`, `can_sell_next_open`, and `ADV20` were being read from the
  **execution-date** row (`T+1`)
- but the shared execution contract defines those quantities on the **signal-date** row (`T`),
  because they govern the next open after that date

That meant the engine was leaking one day of liquidity/tradability information into:
- buy/sell blocking
- ADV participation caps
- the retail deployability experiments built on top of those controls

The fix was to align all of those liquidity/tradability inputs to the signal-date row while
keeping the portfolio timing contract unchanged:
- signal at `T` close
- buy at `T+1` open
- earliest sell decision at `T+3` close
- earliest sell fill at `T+4` open

**Key finding:** once market rules become part of the scientific claim, a one-day indexing mistake
is not a minor bug. It changes the economic meaning of the result. Session 48 H138/H139 figures
should therefore be treated as superseded by the Session 49 reruns.

**Implication:** tradability and capacity inputs must always be indexed by the information set
available at decision time, not by the later execution row.

---
## F99: After Correcting Liquidity Timing, Simple Fixed Long-Only Constructions Are Stronger Than Session 48 Suggested, but Only in Uncapped Form (2026-03-28, Session 49)

Session 49 reran H138 and H139 under the corrected signal-date liquidity alignment.

Corrected H138 holdout results (`2019-2025`):

| Rule | Total Return | Annualized | Relative vs VNINDEX | Information Ratio | Positive Years |
|---|---:|---:|---:|---:|---:|
| `k5_r5_eq` | **+769.49%** | **+36.59%** | **+346.29%** | **0.81** | **7/7** |
| `k3_r5_eq` | +748.57% | +36.11% | +335.55% | 0.70 | 6/7 |
| `k5_r10_eq` | +573.69% | +31.65% | +245.79% | 0.67 | 4/7 |

Corrected H139 fee/capacity stress preserved the same qualitative split:
- with **no ADV cap**, the fixed rules remain economically strong
- at `0.50%` round-trip cost and **no cap**, all three candidates stay positive benchmark-relative
- with **any positive ADV cap** in the tested `0.5% / 1.0% / 2.0%` grid, positive benchmark-relative
  scenario count remains **0**

Best relative return by ADV cap in corrected H139:
- `0.0%`: **+346.29%**
- `0.5%`: **-47.52%**
- `1.0%`: **-46.36%**
- `2.0%`: **-43.24%**

Minimum average cash weight by ADV cap:
- `0.5%`: **99.40%**
- `1.0%`: **98.81%**
- `2.0%`: **97.74%**

**Key finding:** the corrected engine makes the uncapped long-only opportunity look better, not
worse. But it does **not** change the deployability conclusion: the edge is still highly dependent
on effectively uncapped position sizing.

**Implication:** do not confuse “stronger honest uncapped baseline” with “retail-capacity solved.”
Those are different questions.

---
## F100: Retail-Sized Long-Only Deployability Still Fails Under Explicit ADV Floors and Participation Caps (2026-03-28, Session 49)

H140 tested the actual retail question directly on the honest `2019-2025` holdout:
- notionals `20m, 50m, 100m, 200m VND`
- ADV caps `2%, 5%, 10%`
- ADV20 floors `250m, 500m, 1B, 2B, 5B VND`
- round-trip costs `0.30%, 0.50%`
- candidate menu = the corrected H138 fixed rules

Retail-viability gate:
- `relative_total_return > 0`
- `avg_cash_weight < 25%`
- `positive_years >= 5/7`

**Result:** viable scenario count = **0**.

Best H140 scenario:
- `k5_r10_eq`
- `20m` portfolio notional
- `2%` ADV cap
- `1B` ADV20 floor
- `0.30%` round-trip cost

Even that “best” case only produced:
- total return **+12.00%**
- relative vs VNINDEX **-42.51%**
- average cash weight **87.13%**
- positive years **2/7**

**Key finding:** once explicit retail-sized liquidity rules are imposed, the current long-only
portfolio library does not have a deployable region. The failure is not just a scaling-to-1B
problem. It persists even when the notional is pushed down to `20m-200m VND`.

**Implication:** the next honest move is **not** more long-only tuning or RL. It is either:
- hedged / benchmark-relative constructions, or
- an explicitly tiny-capital illiquidity-harvesting path with no scalability pretense

---
## F101: Without a Viable Retail Region, H141 and H142 Become a Stop Signal, Not a Promotion Path (2026-03-28, Session 49)

H141 was designed to re-open a tiny long-only construction sweep **only** inside the viable retail
region discovered by H140.

Because H140 found **zero** viable liquidity settings:
- H141 stopped immediately and wrote an empty-result summary
- there was no honest long-only region left to optimize

H142, the new live/paper-trade blotter exporter, was still implemented and then run manually on
the top H140 scenario as a diagnostic only.

Latest diagnostic snapshot (`2025-12-31` execution date):
- portfolio held only `SHB`
- target notional about `19.70m VND`
- target usage about `1.87%` of ADV20
- cash still **12.06%**

**Key finding:** the new blotter tooling is ready, but the candidate itself is not worthy of live
promotion. When the “best” capacity-aware long-only setup often degenerates into a one-name book
with large cash drag, that is a sign to change research direction rather than keep polishing the
same construction class.

**Implication:** treat H141/H142 as the end of the current long-only retail deployability branch.
The next branch should be hedged construction research, not RL overlays on a non-deployable book.
