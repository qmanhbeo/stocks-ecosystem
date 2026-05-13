# Session 60 Log

## Objective
Complete the direct follow-up queue around the Session 59 activation champion:
- `H178`: robustness stress for `h175__rel2_gt0`
- `H179`: live-paper activation overlay for the deterministic selector branch
- `H180`: only small augmentations around `rel2_gt0`

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Starting point

Session 59 had already established the new activation champion:
- `full_library + k5_r5_eq + h175__rel2_gt0`
- `+1052.77%` total
- `+491.69%` relative vs VNINDEX
- IR `0.93`
- max DD `-20.57%`

The remaining question was no longer “can we invent a better activation family?”
It was:
- is the champion robust?
- can it be operationalized?
- do any tiny nearby guards improve it without reopening a broad search?

## H178 — robustness stress

Stress design:
- fixed activation-memory warm-up from `2015`
- evaluation starts: `2016`, `2017`, `2018`, `2019`
- RT cost grid: `0.10%`, `0.30%`, `0.50%`, `0.70%`

Result:
- `15 / 16` scenarios beat always-on on both relative return and IR
- original reference scenario still held exactly:
  - always-on: `+346.40%` relative, IR `0.81`
  - `h175__rel2_gt0`: `+491.69%` relative, IR `0.93`

Best stress scenario:
- start `2016`, RT `0.10%`
- `+1181.98%` relative
- IR `0.94`

Only failure:
- start `2017`, RT `0.10%`
- relative underperformance vs always-on: `-0.5904`
- IR underperformance: `-0.0030`

Reading:
- the activation champion is real enough to operationalize
- it is not just a one-window backtest artifact

## H179 — live-paper activation overlay

Implemented an execution-facing overlay runner for the activation champion.

Latest matrix-supported state:
- signal date: `2025-12-30`
- execution date: `2025-12-31`
- activation: `ON`
- recent `rel2`: `+0.008169`
- held names:
  - `DBT`
  - `FIT`
  - `KLB`
  - `PDN`
  - `TMT`

Critical blocker surfaced cleanly:
- stock data extends to `2026-03-27`
- `data/features/xs_rl_signal_matrix.parquet` still ends at `2025-12-31`

So the overlay runner works, but it is not yet a true current-date live system.
The next blocker is live feature freshness, not another activation idea.

## H180 — small augmentations around the champion

Tested only local guards:
- hit-rate guards
- selector-confidence guards
- entry-quality guards
- drawdown guard
- blocked-buy pressure guard

Best augmentation:
- `h180__rel2_gt0_conf_q50`
- `+413.39%` relative
- IR `0.88`
- max DD `-18.94%`

Champion still better:
- `h175__rel2_gt0`
- `+491.69%` relative
- IR `0.93`
- max DD `-20.57%`

Reading:
- local cosmetic tweaks are exhausted for now
- keep the plain champion

## Branch decision

Activation branch outcome after Session 60:
- the fixed champion is robust enough to keep
- the live overlay path exists
- small nearby tweaks did not improve it

So the next active branch changes from:
- “find a better activation gate”

to:
- “make the current activation champion genuinely live by refreshing the full-library signal surface”

## Next queue

1. `H181`: rebuild / extend `xs_rl_signal_matrix.parquet` and activation surfaces through the latest market date
2. `H182`: rerun the activation overlay on the refreshed matrix and start a dated paper blotter
3. `H183`: compare activated vs always-on paper books only after the overlay is current
4. keep `H151/H152` parked behind the operational activation branch
5. keep RL exploratory only

## Artifacts

Run summaries:
- `artifacts/run_summaries/latest_portfolio_activation_h175_robustness_stress.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`
- `artifacts/run_summaries/latest_portfolio_activation_h175_small_augmentations.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h178_h175_robustness_stress*`
- `artifacts/portfolio_baselines/*h179_live_activation_overlay*`
- `artifacts/portfolio_baselines/*h180_h175_small_augmentations*`

Operational note:
- these Session 60 artifacts were written from the workspace root, so the actual files are currently under `/home/manh/stocks/artifacts/`
- that differs from the usual convention of running scripts inside `alpha-research-lab/`, which would place them under `/home/manh/stocks/alpha-research-lab/artifacts/`
