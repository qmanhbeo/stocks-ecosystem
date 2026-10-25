# Stock RL Phase 4A — Results

## Outcome

Completed in the isolated `exp/stock-rl-trade-episode` worktree. Loaders now enforce exact in-memory date bounds before feature construction. Maximum observation date was **2025-12-31**; shared-file sizes and modification times were unchanged.

## Design and verification

One shared, ticker-agnostic MaskablePPO trained on ACB, BCG, FPT, GAS, HPG, MWG, PVD, REE, SSI, VCB, VIC, and VNM. DGC, MBB, and VHC were held out entirely. The roster spans several sectors; BCG adds ended/suspended-history coverage but stops on 2025-10-08.

Features scale each stock’s returns, intraday moves, gaps, and ranges by lagged 60-day volatility (floor 0.005). Volume uses prior-20-day log-volume z-scores; realized and absolute volatility are log-scaled. Bounded S1/C16 values and availability bits are preserved; missing signals use a 0.5 sentinel. Unrealized return uses entry-time volatility. No global fit or clipping is used.

**44 tests passed**; Ruff and byte-compilation passed. Six models (two variants × three seeds) trained for 12,288 steps each: **73,728 steps**, 48 updates/model, 167 seconds total. Gradients were finite and nonzero; checkpoints reloaded. No GUI or 2026 observations were used.

## Exploratory test results

Figures below are unweighted means across independent single-stock backtests and seeds, **not a multi-stock portfolio**. Mean completed-trade reward is annualized excess log return.

| Policy/group | Mean trade reward | Win rate | Exposure | Mean stock CAGR | Mean max drawdown |
|---|---:|---:|---:|---:|---:|
| Market features, 12 training stocks | 1.72 | 88.7% | 94.1% | 16.6% | −35.8% |
| Market + S1/C16, 12 training stocks | 1.72 | 92.6% | 97.2% | 17.8% | −36.2% |
| Market features, 3 unseen stocks | 1.60 | 88.3% | 93.9% | 14.0% | −36.9% |
| Market + S1/C16, 3 unseen stocks | 2.00 | 92.3% | 96.9% | 14.1% | −37.5% |

Buy-and-hold averaged 17.9%/15.7% mean stock CAGR on training/unseen stocks; immediate-entry three-day trading averaged 18.7%/22.8%. Alpha improved CAGR in 17/36 paired training and 3/9 unseen stock-seed results, so a reliable signal lift is not established. Agents were usually invested; training-stock mean holds were 55–60 days. No sub-minimum trades or open-position time-limit truncations occurred.

The requested matched-exposure, fixed-three-day random baseline proved infeasible: validation calibration chose entry probability 1.0 for every ticker, making it identical to mechanical trading at 74.9% test exposure, versus a 95.6% PPO target (20.7 percentage-point gap). Matching higher exposure requires a different holding-duration control.

VNINDEX rose each year: 2023 +8.2% (high volatility), 2024 +11.9% (low), 2025 +40.5% (high); no down-year regime was tested. Alpha selection used 2023–2025, making these results exploratory. Dividend adjustment is user-confirmed; S1/C16 after-close availability is assumed because publication timestamps are absent.

## Recommendation

For Phase 4B, use a time period untouched by Alpha selection and a validation-calibrated randomized benchmark whose holding durations can reach PPO-like exposure; keep the fixed-three-day mechanical result as a separate low-exposure reference.

Machine-readable outputs and checkpoints: `/tmp/stock-rl-trade-episode-phase4a-20261025/`.
