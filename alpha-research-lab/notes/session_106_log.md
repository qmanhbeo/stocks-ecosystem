# Session 106 Log

## Objective
Refresh the official live-monitoring surfaces on the matrix-supported freeze and record one narrow forward checkpoint:
- rerun `H179` and `H183` on the current official live chain through `2026-03-31`
- with explicit user permission, fetch only `ANV`, `PGV`, `PTB`, `PTL`, `VSI`, and `VNINDEX` to latest data and compute a one-off mark-to-market beyond the frozen matrix boundary

This session did not change the live branch rule.
It did use a narrow user-authorized exception beyond the frozen research boundary, but only for live monitoring, not for branch research.

## Starting point

Coming in:
- the active live branch was still:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- the last recorded official live state in the notes stack still pointed to:
  - signal date `2026-03-26`
  - execution date `2026-03-27`
  - holdings:
    - `ANV`
    - `PGV`
    - `PTB`
    - `PTL`
    - `VSI`
- the shared live surfaces were now current through `2026-03-31`, but the official live-paper notes had not yet been rerun on that boundary
- the user then allowed one special-case raw-data refresh for the currently relevant live names plus `VNINDEX`

## What changed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`
- `artifacts/run_summaries/latest_portfolio_live_activation_scoreboard.json`
- `artifacts/portfolio_baselines/20260404_141653_h179_live_activation_overlay_daily.parquet`
- `artifacts/portfolio_baselines/20260404_141653_h179_live_activation_overlay_detail.parquet`
- `artifacts/portfolio_baselines/20260404_141653_h179_live_activation_overlay_next_open_daily.parquet`
- `artifacts/portfolio_baselines/20260404_141653_h179_live_activation_overlay_next_open_detail.parquet`
- `artifacts/portfolio_baselines/20260404_141652_h183_live_activation_scoreboard_daily.parquet`

### H179 - Live Activation Overlay Refresh
**Question:**
What is the latest official completed live state on the matrix-supported surface?

**Command / code:**
`conda run -n stocks python analysis/h179_live_activation_overlay.py`

**Inputs:**
- official live chain only
- shared matrix:
  - `data/features/xs_rl_signal_matrix.parquet`
- shared activation surfaces:
  - `data/features/activation_state_daily.parquet`
  - `data/features/activation_meta_daily.parquet`
- current benchmark file:
  - `data/stock/gia_lich_su_VNINDEX_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`

| Metric | Value | Note |
|--------|-------|------|
| latest signal date | `2026-03-30` | latest matrix-supported signal |
| latest execution date | `2026-03-31` | latest completed official execution |
| activation | `OFF` | `recent_rel2` flipped negative |
| recent `rel2` | `-0.02019` | official trigger input |
| held names | `[]` | full cash |
| cash weight | `100.00%` | no holdings |
| day relative return vs VNINDEX | `-1.4270%` | benchmark rose while branch was in cash |
| next-open recommendation | `OFF / cash` | projected `2026-04-01` state |
| stale matrix flag | `true` | benchmark extends past matrix end |

**Result:**
The official live branch turned `OFF` on the `2026-03-30` signal and was fully in cash on the `2026-03-31` execution.

### H183 - Live Activation Scoreboard Refresh
**Question:**
What does the official `2026` YTD activated-vs-always-on scoreboard look like through `2026-03-31`?

**Command / code:**
`conda run -n stocks python analysis/h183_live_activation_scoreboard.py`

**Inputs:**
- same official live chain as `H179`
- evaluation year:
  - `2026`

**Saved artifact:**
`artifacts/run_summaries/latest_portfolio_live_activation_scoreboard.json`

| Metric | Value | Note |
|--------|-------|------|
| activated relative return | `+3.2810%` | vs VNINDEX |
| activated IR | `0.6267` | annualized |
| activated avg cash | `26.45%` | `2026` YTD |
| always-on relative return | `-12.7124%` | vs VNINDEX |
| always-on IR | `-1.8775` | annualized |
| delta relative return | `+15.9934%` | activated minus always-on |
| delta IR | `+2.5042` | activated minus always-on |
| latest activated holdings | `[]` | branch is now in cash |
| latest always-on holdings | `ANV, PGV, PTB, PTL, VSI` | stale always-on basket on `2026-03-31` |

**Result:**
The official live scoreboard improved materially after the `2026-03-31` refresh:
- activated sticky is now benchmark-positive relative for `2026` YTD
- always-on remains deeply worse

### One-Off Specific-Ticker Forward Checkpoint
**Question:**
What happened after the official `2026-03-31` live state if only the currently relevant tickers and `VNINDEX` are refreshed?

**Command / code:**
`conda run -n stocks python data_tools/fetch_stock.py --tickers ANV,PGV,PTB,PTL,VSI,VNINDEX --interval 1D --end 2026-04-04 --probe-cache-ttl-hours 0 --delay 0.5`

**Inputs:**
- refreshed raw daily files only:
  - `ANV`
  - `PGV`
  - `PTB`
  - `PTL`
  - `VSI`
  - `VNINDEX`

**Saved output:**
- updated raw stock files under `data/stock/`

| Metric | Value | Note |
|--------|-------|------|
| refreshed latest date | `2026-04-03` | all six files |
| official live branch state at start | `cash` | from `2026-03-31` execution |
| cash return `2026-03-31` close -> `2026-04-03` close | `0.0000%` | no holdings |
| VNINDEX return over same window | `+0.5703%` | benchmark moved higher |
| cash relative return vs VNINDEX | `-0.5703%` | one-off forward mark-to-market |
| static stale always-on basket return | `-0.6033%` | equal-weight `ANV, PGV, PTB, PTL, VSI` |
| cash vs static stale basket | `+1.1736%` | defensive branch still better than the stale basket |

**Result:**
This is a monitoring-only checkpoint.

What it shows:
- cash lagged a rising benchmark over the `2026-04-03` window
- but the official cash branch still beat the stale always-on basket of the five names that were live on `2026-03-31`

What it does **not** show:
- an official live-chain extension beyond `2026-03-31`
- any new research evidence for retuning the branch

## Branch decision

Do **not** change the live branch.

What Session 106 resolves:
- the official live branch is now:
  - `OFF`
  - `100% cash`
  on the latest matrix-supported execution date `2026-03-31`
- the official `2026` YTD scoreboard improved to:
  - activated sticky `+3.2810%` relative vs VNINDEX
  - sticky always-on `-12.7124%`
- the one-off `2026-04-03` forward checkpoint is monitoring-only:
  - useful for understanding the current book
  - not valid as a branch-research extension

## Validation

Completed for the official live refresh:
- `conda run -n stocks python analysis/h179_live_activation_overlay.py`
- `conda run -n stocks python analysis/h183_live_activation_scoreboard.py`
- read:
  - `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`
  - `artifacts/run_summaries/latest_portfolio_live_activation_scoreboard.json`

Completed for the one-off forward checkpoint:
- `conda run -n stocks python data_tools/fetch_stock.py --tickers ANV,PGV,PTB,PTL,VSI,VNINDEX --interval 1D --end 2026-04-04 --probe-cache-ttl-hours 0 --delay 0.5`
- verified all six refreshed raw files now extend to `2026-04-03`

Verdict:
- official live branch state: **UPDATED**
- one-off `2026-04-03` checkpoint: **RECORDED**
