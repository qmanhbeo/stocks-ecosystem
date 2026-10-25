# Future research and resumption plan

The trade-episode branch is intentionally parked after Phase 4D. It is preserved for future work; no additional PPO run is currently justified by the recorded evidence.

## Priority order

1. **Establish target-relevant predictive information.** Revisit S1/C16 and candidate features with causal availability timestamps, explicit coverage, ticker/time-block validation, and a genuinely untouched evaluation period. Keep feature selection separate from that final period.
2. **Test executable decision value.** Freeze entry dates to isolate exits, then compare any signal-driven controller against matched random exits and fixed 3/10/20-interval controls on identical prices, fills, and dates. Report prediction metrics separately from chronological returns, exposure, drawdown, and trades. A positive IC or lower prediction error is not sufficient.
3. **Choose the economic objective explicitly.** The current reward is annualized excess log return per completed trade; it is not chronological portfolio wealth. If the intended target is calendar-time wealth, first agree a new objective and protocol. Do not silently reinterpret prior results.
4. **Investigate PPO only when justified.** If a frozen predictive rule beats controls but PPO does not under identical entry opportunities, then test exploration, credit assignment, critic behavior, and training sufficiency. Change one factor at a time and keep the existing PPO evidence frozen.
5. **Compare simple rules first.** Any new RL training must share the same universe, dates, fills, and capital assumptions as mechanical, randomized, and supervised decision policies. Avoid large training budgets until the smaller comparison passes.

## Restart gate

**No-go for more PPO training now.** Phase 4A/4B policies did not establish a robust advantage, H1/H5 were inconclusive, and Phase 4D did not establish an economic edge for supervised exits. More PPO steps alone would not resolve those gaps.

Resume RL work only after all of the following are true:

- A point-in-time feature set shows reproducible predictive value on a period not used for signal selection.
- A simple executable policy converts it into a positive, economically meaningful advantage over the predeclared mechanical and matched-random controls, with paired uncertainty that supports the claim and transfer beyond the fitted tickers.
- Entry/exit timing, corporate-action price basis, costs, portfolio allocation, and the intended reward/wealth objective are explicitly frozen.
- The expected PPO-specific question is stated in advance (for example, whether it can recover a proven decision rule), rather than assuming additional training will create alpha.

Define the economic margin before opening the evaluation period. Phase 4D preregistered a two-percentage-point annualized-CAGR hurdle for its particular comparison; that value is not a universal threshold. If results are mixed or uncertainty spans the hurdle, remain in signal/control research rather than scaling PPO. A negative result on these tests would reject the tested setup, not RL as a field.

## Safe resumption checklist

1. Read this file, [README.md](README.md), [RESEARCH_FINDINGS.md](RESEARCH_FINDINGS.md), and the relevant phase protocol. Confirm branch/worktree state before editing:

   ```bash
   git -C /home/manh/stocks-ecosystem-worktrees/rl-trade-episode status --short --branch
   git -C /home/manh/stocks-ecosystem-worktrees/rl-trade-episode rev-parse HEAD
   ```

2. Use the existing worktree and `exp/stock-rl-trade-episode` branch; do not merge it into `main`. Recheck the shared data root and do not modify shared datasets:

   ```bash
   export STOCKS_DATA_ROOT=/home/manh/stocks-ecosystem/data
   cd /home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent
   conda activate stocks
   export PYTHONPATH=.
   ```

3. Verify the relevant code SHA, config/protocol hash, seed list, data files, prepared-input fingerprints, and model hashes before a rerun. Phase 4B/4D frozen PPO checkpoints depend on `/tmp/stock-rl-trade-episode-phase4a-20261025/`; Phase 2/3/4A outputs are also under `/tmp`. `/tmp` is not durable: if a required artifact is missing or its hash differs, stop and decide whether to regenerate it under a new preregistered run. Phase 4A has no recorded generating Git SHA, so its checkpoint hashes cannot recover that missing source provenance.
4. Run the focused test command in the README. Reproduce prior outputs only into new, empty, experiment-specific locations; never overwrite the tracked results or the ignored checkpoint directories. The Phase 4B and 4D runners require a clean worktree to bind results to a commit.
5. Write and commit the next protocol/config before evaluation. Record the run-code SHA before loading data/models, date boundaries, seeds, data fingerprints, exact artifact paths, and a stopping rule. Keep all reports explicit about exploratory versus untouched periods.

No action in this roadmap is an authorization to train or alter the environment; a future research phase should receive its own explicit scope and run budget.
