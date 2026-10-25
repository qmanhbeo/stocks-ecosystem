# Stock RL Trade Episode — Phase 3 Results

## Run

Six MaskablePPO models trained headlessly in **31.2 seconds**: 5,120 steps each, paired seeds 1208–1210 (30,720 total), CPU, one worker. Each completed 20 finite gradient updates, changed parameters, and saved/reloaded its final checkpoint. No GUI, plot, TensorBoard, or service ran.

Both conditions shared FPT dates/prices, next-open execution, three-interval minimum, unchanged terminal reward, and `gamma=1`. Baseline used 8 market + 5 state features (13 inputs); Alpha added S1 probability/availability and C16 rank/availability (17 inputs). Alpha coverage was 99.89%/98.11%. Scaling used 2015–2019 only. 2020–2022 was diagnostic; 2023–2025 is exploratory because Alpha selection used this history.

## Exploratory evaluation: 2023–2025

Values for PPO and random policies are averages across three seeds. Trade reward is the specified annualized log excess reward; calendar CAGR compounds realized portfolio wealth separately.

| Policy | Trades | Mean / median trade reward | Win rate | Exposure | Calendar CAGR | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Market PPO | 69.3 | 0.562 / 0.291 | 65.4% | 66.0% | 13.45% | −27.69% |
| Market + S1/C16 PPO | 71.0 | 0.491 / 0.266 | 65.2% | 64.7% | 11.01% | −27.69% |
| Random valid actions, 3 seeds | 121.7 | 0.048 / 0.033 | 52.0% | 66.0% | 7.20% | −34.43% |
| Buy immediately; sell at first legal opportunity | 186 | 0.267 / 0.143 | 53.8% | 74.9% | 28.95% | −24.83% |
| Buy and hold | — | — | — | 99.9% | 24.33% | −34.61% |
| 7% annual cash benchmark | — | — | — | 0% | 7.00% | 0% |

Market-only mean reward exceeded Alpha in all seeds. Calendar CAGR favored market PPO in two of three seeds; Alpha won one. Both PPO means trailed buy-and-hold and immediate entry/minimum hold. Validation CAGR was 43.41% market-only and 35.93% Alpha. This does not establish profitability or signal value.

## Checks and limitations

Test agents completed about 69–71 trades per seed. Market-only had one no-buy episode per seed; Alpha had zero or one (mean 0.67). No policy always bought immediately or always sold at minimum hold. Logs show zero invalid masked actions and zero completed trades below 3 intervals. Dates ended by 2025-12-31; shared input sizes and mtimes were unchanged. No 2026 rows were returned to feature/training/evaluation code. **Physical isolation is not guaranteed:** FPT OHLCV has one row group spanning 2026; filtering may decode its pages before discarding later rows.

Artifacts: `/tmp/stock-rl-trade-episode-phase3-20261025/` (`phase3_config.json`, `phase3_metrics.json`, `phase3_trades.csv`, `phase3_comparison.csv`, and six final checkpoints). The runner and episode audit logging are in the isolated worktree; original RL and Alpha Lab files were not changed.

**Phase 4 recommendation:** treat this as a bounded engineering result, not an Alpha win. Freeze the protocol and use a physically pre-2026-bounded input surface before any experiment that must guarantee zero reads of 2026; preserve 2026 as a candidate holdout until separately authorized.
