# Session 62 Log

## Objective
Complete the operational refresh and first local refinement wave around the current activation champion:
- `H181`: rebuild the live `full_library` matrix and activation surfaces through the latest stock date
- `H182`: rerun the live activation overlay on the refreshed matrix
- `H183`: compare activated vs always-on on current-year live paper data
- `H184`: sticky holdings / displacement margin
- `H185`: sector concentration cap
- `H186`: local exposure control around `rel2_gt0`

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Starting point

Session 61 defined the correct order:
1. make the `full_library` activation stack genuinely current
2. rerun the live overlay on honest current data
3. then test only local refinements around the champion

At the start of Session 62:
- stock data already extended through `2026-03-27`
- the live activation overlay existed
- but the shared `xs_rl_signal_matrix.parquet` and activation surfaces were still stale beyond `2025-12-31`
- the current champion was:
  - `full_library + k5_r5_eq + h175__rel2_gt0`

## H181 — current-date refresh

Infrastructure fixes added:
- built a current-year live `S1` extension:
  - `data/features/xs_barrier_vol_1d_hose_live_current.parquet`
- stopped `C4`, `C5`, and dispersion builders from inheriting the stale historical `S1` grid
- patched price-limit feature building to bootstrap the shared market-rules package consistently
- updated `build_rl_signal_matrix.py` to merge historical `S1` with the current-year live extension

Rebuilt through `2026-03-27`:
- `data/features/xs_open_close_asymmetry.parquet`
- `data/features/xs_insider_quality_features.parquet`
- `data/features/xs_dispersion_regime_daily.parquet`
- `data/features/xs_price_limit_daily.parquet`
- `data/features/xs_volume_zscore_daily.parquet`
- `data/features/xs_shortterm_reversal.parquet`
- `data/features/xs_sector_rotation_daily.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/activation_state_daily.parquet`
- `data/features/activation_meta_daily.parquet`

Key outcome:
- the live `full_library` / activation branch is now current through `2026-03-27`
- the blocker was stale producer infrastructure, not overlay logic

## H182 — current-date live activation overlay

Reran the live overlay on the refreshed matrix.

Final official sticky-overlay state:
- signal date: `2026-03-26`
- execution date: `2026-03-27`
- activation: `ON`
- recent `rel2`: `+0.013101`
- held names:
  - `ANV`
  - `PGV`
  - `PTB`
  - `PTL`
  - `VSI`
- cash weight: `0.00%`

This is now a genuine current-date overlay state, not a stale-matrix placeholder.

## H183 — activated vs always-on live scoreboard

Built the first current-year live scoreboard for the current branch.

`2026` YTD comparison so far:
- sticky activated:
  - relative vs VNINDEX: `-3.33%`
  - IR: `-0.36`
  - avg cash weight: `31.11%`
- sticky always-on:
  - relative vs VNINDEX: `-11.22%`
  - IR: `-1.65`
  - avg cash weight: `5.49%`

Reading:
- both books trail the benchmark over the short 2026 YTD window so far
- activation is still materially improving the realized path

## H184 — sticky holdings / displacement margin

Goal:
- reduce churn leakage without changing the selector or the activation family

Result:
- **PASS**
- best variant:
  - `sticky_bonus_0p015`
  - `+509.76%` relative vs VNINDEX
  - information ratio `0.9372`
  - avg daily turnover `0.2227`

Reference:
- plain `rel2_gt0`
  - `+480.72%` relative
  - information ratio `0.9095`
  - avg daily turnover `0.2269`

Branch decision:
- sticky retention is now part of the champion

## H185 — sector concentration cap

Goal:
- test whether mild sector diversification improves the activated selector

Result:
- **MIXED**
- best:
  - `sector_cap_3`
  - `+482.21%` relative vs VNINDEX
  - information ratio `0.9123`

Reading:
- a mild sector cap helps slightly relative to plain `rel2_gt0`
- but it does not beat the sticky champion

## H186 — local exposure control around `rel2_gt0`

Goal:
- see whether the same `recent_rel2` state should drive local 0/50/100 or continuous exposure changes

Result:
- **FAIL**
- all tested stepped or continuous exposure schedules underperformed the plain binary activated rule

Branch decision:
- keep activation binary once the recent-efficacy condition is met
- do not reopen local sizing unless a stronger state variable appears

## Session 62 branch decision

The current uncapped long-only champion is now:
- `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

This branch is now:
- current on live data through `2026-03-27`
- operational as a live-paper overlay
- better than the plain `rel2_gt0` champion

The next local queue is:
1. `H187`: combine `sticky_bonus_0p015` with `sector_cap_3`
2. `H188`: implementation-pain veto on the sticky champion
3. `H189`: basket-coherence / score-dispersion guard on the sticky champion

Secondary branches remain parked:
- `H151`
- `H152`
- RL beyond exploratory status

## Artifacts

Key run summaries:
- `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_scoreboard.json`
- `artifacts/run_summaries/latest_portfolio_activation_local_refinement.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h179_live_activation_overlay*`
- `artifacts/portfolio_baselines/*h183_live_activation_scoreboard*`
- `artifacts/portfolio_baselines/*h184_sticky_holdings*`
- `artifacts/portfolio_baselines/*h185_sector_cap*`
- `artifacts/portfolio_baselines/*h186_local_exposure_control*`

## Validation

Session 62 hygiene completed:
- `python -m py_compile` passed on changed code
- `git diff --check` passed

Important operational note:
- the valid H184/H185/H186 results are the reruns after fixing:
  - activation-meta warm-up coverage
  - `recent_rel2` index alignment
- the earlier all-cash variants should not be treated as authoritative
