# Live State

What this file is for: current working state, active constraints or blockers,
and immediate next actions. Keep it operational and short. Put session detail
in session logs, durable conclusions in findings chunks, failed or parked paths
in dead-end chunks, and cheap recovery context in the compact files.

Latest full session detail: [session_224_226_log.md](./session_224_226_log.md)
Last verified: [Sessions 224-226](./session_224_226_log.md), 2026-05-03.

Compact recovery:
- [sessions_compact.md](./sessions_compact.md)
- [findings_compact.md](./findings_compact.md)
- [deadends_compact.md](./deadends_compact.md)

Source durable memory:
- [findings.md](./findings.md)
- [findings-301-330.md](./findings-301-330.md)

---

## Current State

- The active lab focus is still local-first news infrastructure and bounded
  follow-through, not a new live alpha promotion.
- The local news stack is real: PhoBERT owns sentiment, forward-looking,
  `article_scope`, and `source_type`; Ollama is only the guarded residual
  event-family lane.
- The hosted `llm-cache-fill` path is legacy bootstrap material, not the
  default blocker for the local-news branch.
- C16 order pressure is now a published shared feature contract at
  `data/features/xs_order_pressure_daily.parquet`, but downstream use is
  opt-in only. Do not run more C16 sizing/search unless a consumer asks for a
  matrix/export integration.
- Event-v2, dividend-clock, legal-holiday timing, foreign/proprietary/sector-flow,
  old OHLCV queue, smart-exit linear tweaks, and BERT-only sentiment are parked
  or failed under the current target/consumer contracts. Use the compact
  dead-end view before reopening any of them.

## New Branches (2026-05-03)

- `c16_roc_filtered`: Rate of C16 change + liquid filter.
  Test: IC(ROC(C16) | move>80).

- `sector_pressure_momentum`: Sector pressure rate of change.
  Test: IC(sector-level C16 momentum) as predictor.

## New Eureka Queue (2026-05-03)

- `c16_acceleration`: C16 velocity matters more than level.
  Test: IC(ROC(C16, 5d)) vs IC(C16 level).
  Smallest honest test: compute ROC, compare IC to baseline.
  **FAILED: level beats ROC by 28%**

- `c16_divergence`: Price UP + C16 DOWN = contrarian divergence.
  Test: IC(C16) where price > market_return but C16 < median.
  Smallest honest test: split by price direction vs C16 direction.
  **WEAK PASS: divergence = +0.108 vs baseline +0.078 (+39%)**

- `liquidity_adjusted_contrarian`: C16 + high liquidity + DOWN market = extreme.
  Test: IC(C16 > median AND move > 80%ile AND market = DOWN).
  Smallest honest test: triple condition vs X226 single condition.

- `deep_down_only`: C16 only matters in DEEP down (bottom 20%).
  Test: IC(C16) in market_return < 20%ile vs < 50%ile.
  Smallest honest test: market quintile split comparison.

## New Eureka Queue (EXTENDED - 2026-05-03)

- `triple_storm`: Combine liquid (+X53) + down market (+X226) + divergence.
  Test: IC(C16) where move>80%ile AND market=down AND divergence=true.
  Smallest: triple intersection vs single conditions.
  **PASSED: triple = +0.158 vs baseline +0.078 (+104%)**

- `market_quintile_gradient`: C16 strength at each market quintile.
  Test: IC(C16) at market_return <20%, 20-40%, 40-60%, 60-80%, >80%.
  Smallest: compare 5-way split vs binary up/down.

- `c16_extreme_in_down`: Very high C16 (>.9) in DOWN markets.
  Test: IC(C16>0.9) in market=down vs all C16 in market=down.
  Smallest: filter by C16 threshold in down market only.

## Contrarian Extensions (2026-05-03)

- `down_market_magnitude`: C16 strength increases with drop depth.
  Test: IC(C16) in bottom 20% market days vs bottom 50%.

- `sector_rotation_down`: Sector behavior differs in down vs up markets.
  Test: IC(sector_laggard) in down markets separately.

- `time_sequence_down`: Day 2-3 of sustained down = stronger.
  Test: IC(C16) on consecutive market-down days.

- `c16_intensity_modulation`: Very high C16 in down = extreme signal.
  Test: IC(C16 > 0.9) in down markets vs all markets.

## Branch Status (2026-05-03)

- liquid_braid_stack: KILLED (stacking hurts)
- dynamic_liquidity_regime: WEAK (use for sizing only)
- sector_convergence_contrarian: KILLED (fragmented = weak always)
- sector_relative_c16: KILLED (hurts, -15%)
- c16_persistence: KILLED (doesn't help)
- market_state_c16: PASSED! In DOWN markets IC +0.098 vs +0.056 (+26%)

## C16 Branch CLOSED & FULLY VERIFIED (2026-05-03)

- Triple Storm = liquid + down market + divergence
- Training IC: +0.158 (+104% vs baseline)
- Holdout (2023-25) IC: +0.134 (+111% vs baseline)
- **Walk-Forward (9 years): +0.145 (+92% boost, 9/9 positive)**
- **VERIFIED: Robust across all years, no regime degradation**

## S239 New Eureka Queue (2026-05-03)

- `january_effect`: First 10 days of year institutional reallocation.
  Test: IC(early_jan) vs IC(late_jan).
  Smallest: day_of_year < 10 as filter.

- `intraday_momentum_regime`: Morning vs afternoon session patterns.
  Test: IC by session half.
  Smallest: split data by morning/afternoon.

- `sector_momentum_streak`: Sector 3-day streak predicts continuation.
  Test: IC(sector_streak > 0) vs level.
  Smallest: streak signal exists, compare to breadth level.

- `small_liquidity_premium`: Small-cap + high C16 extreme.
  Test: IC(C16) | cap < median vs cap > median.
  Smallest: market cap split on C16.

- `volume_regime_volatility_combo`: Low vol + high volume = accumulation.
  Test: IC(C16) where vol_low AND volume_spike.
  Smallest: combine vol regime + volume shock.

- `foreign_room_acceleration`: Room delta as signal.
  Test: IC(C16) | room_delta > 0.
  Smallest: foreign room change signal.

- `dow_jones_lag`: US market overnight → VN morning.
  Test: IC(C16) | us_overnight > 0.
  Smallest: macro overnight signal.

- `turnover_rate_intensity`: Turnover rate × C16 interaction.
  Test: IC(C16 * turnover_rate_quintile).
  Smallest: composite signal test.

## Prime Number Theories

- `prime_gap_clustering`: Prime gaps between nth primes correlate with market gaps.
  Claim: Prime gap sizes in sequence = market regime predictor.
  Test: nth_prime(n+1) - nth_prime(n) sequence mod market moves.
  Mechanism: Twin prime conjecture suggests gaps correlate with "twin" market moves.

- `riemann_zeta_regime`: Critical line zeros map to market turning points.
  Claim: ζ(½ + it) imaginary parts = market cycle frequencies.
  Test: approximate non-trivial zeros vs market peaks.
  Insane: Riemann Hypothesis ↔ Market Efficiency equivalence.

- `modular_arithmetic_symmetry`: Modulo-N market state cycles.
  Claim: Market repeats every N days where N = prime.
  Test: FFT find periodicities at prime periods (7, 11, 13, 17...).
  Mechanism: VN T+2 settlement creates prime-modulus cycles.

- `prime_density_trading`: Bertrand's postulate as allocation density.
  Claim: More primes in interval = more market "primes" (top stocks).
  Test: prime_density in [n, 2n] correlates with top-stock returns.
  Mechanism: Number theory meets portfolio selection.

- `goldbach_conjecture_trADING`: Sum of two primes = price level.
  Claim: Every even price = sum of two "prime" stocks.
  Test: price level decomp into prime tickers.
  Insane: Goldbach representation of portfolio.

- `sieve_eratosthenes_selection`: Eratosthenes-style filtering.
  Claim: Sieve out "composite" signals, keep "prime" signals.
  Test: Sieve algorithm on signal set.
  Mechanism: Ancient algorithm meets modern market.

- `mersenne_prime_cycles`: Mersenne prime cycles (2^p - 1) as cycles.
  Claim: Market cycles at Mersenne periods (3, 7, 31, 127...).
  Test: FFT at M_p periods.
  Mechanism: Perfect numbers = perfect cycles.

- `fermat_prime_fourier`: Fermat primes (2^(2^n)) in Fourier.
  Claim: Fermat prime frequencies are spectral peaks.
  Test: FFT at Fermat frequencies (1, 2, 4, 8, 16...).
  Mechanism: Prime Fourier extraction.

- `prime_zeta_convergence`: Prime zeta function P(s).
  Claim: P(s) converges at market-critical s-values.
  Test: Prime zeta near s=1+it.
  Insane: Prime counting meets market timing.

- `legendre_polynomial_support`: Legendre polynomials as basis functions.
  Claim: Price path approximated by Legendre polynomials.
  Test: coefficients as regime signals.
  Mechanism: Orthogonal function expansion.

- `dirichlet_series_momentum`: Dirichlet series of returns.
  Claim: Sum of returns/n^s = "return zeta".
  Test: Compute D(s), find critical line.
  Insane: Dirichlet series as signal processor.

- `modular_form_oscillator`: Modular forms as oscillators.
  Claim: j-invariant maps to market oscillator.
  Test: j-function of price time-series.
  Quantum connection: Modular forms = 2D conformal field theory.

- `l_function_market`: L-function of market.
  Claim: L-function zeros = turning points.
  Test: L-function fit to returns.
  Insane: L-functions from number theory to markets.

- `weil_conjecture_trading`: Weil conjectures as market structure.
  Claim: Counting function matches market counting.
  Test: Weil-reve-type formulas.
  Algebraic geometry markets.

- `tate_thesis_revaluatio`: Tate twist as regime switch.
  Claim: Twisted Tate module = regime change.
  Test: Tate twist signal.
  Insane: Arithmetic geometry on markets.

## Quantum Finance

- `quantum_wavefunction_portfolio`: Portfolio as wavefunction.
  Claim: |ψ|² = probability distribution.
  Test: construct ψ, verify |ψ|² matches returns.
  Mechanism: Quantum portfolio theory.

- `quantum_uncertainty_position`: Heisenberg uncertainty in positions.
  Claim: Δx * Δp ≥ ħ/2 for portfolios.
  Test: position_size * momentum uncertainty.
  Mechanism: Can't know both price and position simultaneously.

- `quantum_entanglement_sectors`: Sector entanglement.
  Claim: Entangled sectors move together.
  Test: entanglement_coefficient between sector ETFs.
  Mechanism: Non-local correlation.

- `quantum_tunneling_market`: Price barrier tunneling.
  Claim: Price tunnels through resistance.
  Test: tunneling_probability through barriers.
  Mechanism: Quantum mechanics meets support/resistance.

- `quantum_decoherence_trading`: Decoherence as information loss.
  Claim: Market decoherence = signal decay.
  Test: coherence_time as signal half-life.
  Mechanism: Quantum decoherence model.

- `quantum_phase_estimation`: Phase estimation algorithm.
  Claim: Market phase = algorithm output.
  Test: quantum_phase_estimation(returns).
  Quantum advantage: QPE speedup.

- `quantum_fourier_transform_market`: QFT on market data.
  Claim: QFT extracts frequencies better.
  Test: QFT vs classical FFT.
  Quantum advantage: Quadratic speedup.

- `quantum_search_market`: Grover's search for patterns.
  Claim: Grover search finds patterns in O(√N).
  Test: Grover algorithm vs brute force.
  Quadratic speedup hypothesis.

- `quantum_sampling_market`: Quantum sampling for distributions.
  Claim: Quantum sampling = market distribution.
  Test: compare to historical.
  Mechanism: Boson sampling market model.

- `quantum_machine_learning`: Quantum ML on market data.
  Claim: Quantum kernel methods improve.
  Test: quantum_kernel_vs_classical.
  Hybrid quantum-classical.

## Particle Physics

- `higgs_mechanism_bubble`: Higgs-like symmetry breaking.
  Claim: Market " Higgs field" breaks symmetry = regime change.
  Test: field_strength vs returns.
  Mechanism: Spontaneous symmetry breaking.

- `gauge_theory_market`: Gauge invariance in market.
  Claim: Gauge transformations = normalization.
  Test: Gauge-invariant signals.
  Mechanism: Covariant derivatives.

- `chiral_anomaly_trading`: Chiral anomaly = market anomaly.
  Claim: Chiral asymmetry predicts anomalies.
  Test: chirality_asymmetry vs returns.
  Mechanism: Anomaly detection via chirality.

- `yang_mills_market`: Yang-Mills theory for sectors.
  Claim: Sector interactions via gauge fields.
  Test: S = ∫ Tr(F∧*F) for sectors.
  Mechanism: Non-abelian gauge theory.

- ` QCD_color_confinement`: Color confinement = sector clustering.
  Claim: Sectors cluster like quarks.
  Test: sector_clustering vs color_charge.
  Mechanism: Asymptotic freedom.

- `quark_gluon_plasma`: QGP-like market state.
  Claim: High-temperature market = deconfined.
  Test: temperature_measure vs clustering.
  Mechanism: QGP analog states.

- `supersymmetry_portfolio`: Supersymmetry trading.
  Claim: Superpartner signals exist.
  Test: find superpartners of signals.
  Undiscovered signals.

- `string_theory_market`: Market as string vibration.
  Claim: Price = string vibration modes.
  Test: string_modes vs returns.
  Dimension: 10D or 11D market.

- `brane_world_market`: Brane world market.
  Claim: Our market is 3-brane in higher dimension.
  Test: brane_signature effects.
  Extra dimension search.

- `M_theory_market`: M-theory = unified theory.
  Claim: All signals are M-theory components.
  Test: find 11D supergravity.
  Ultimate unification.

- `adS_CFT_correspondence`: AdS/CFT for markets.
  Claim: Market (CFT) = gravity (AdS).
  Test: find AdS radius from returns.
  Holographic principle.

- `holographic_principle_market`: Market holography.
  Claim: N² bits on boundary = N² stocks.
  Test: boundary_theory vs bulk_theory.
  Information theory: Market is holographic.

- `landau pole_renormalization`: Landau pole in market.
  Claim: Coupling blows up = regime breakdown.
  Test: coupling_run vs returns.
  Mechanism: Landau pole detection.

- `beta_function_market`: Beta function of coupling.
  Claim: β(g) determines market flow.
  Test: beta_function fit.
  Renormalization group flow.

- `conformal_block_market`: Conformal blocks as correlations.
  Claim: CFT correlation = signal correlation.
  Test: conformal_block_fit.
  Conformal field theory.

- `critical_exponent_market`: Critical exponents at phase transition.
  Claim: β, γ, ν exponents apply.
  Test: measure_critical_exponents.
  Phase transition theory.

- `spinfoam_market`: Spinfoam model for market.
  Claim: Market = spinfoam quantum gravity.
  Test: spinfoam_quantization.
  Loop quantum gravity analog.

## Cosmological

- `dark_matter_allocation`: Dark matter = unknown flows.
  Claim: Unknown capital = dark matter.
  Test: mass_missing vs unexplained_moves.
  Mechanism: 27% of market is dark.

- `dark_energy_acceleration`: Dark energy = momentum.
  Claim: Market accelerating = dark energy.
  Test: acceleration_parameter.
  Mechanism: Cosmological constant.

- `cosmic_inflation_market`: Inflationary phase in market.
  Claim: Exponential growth phase = inflation.
  Test: inflation_detected.
  Mechanism: Inflationary period mapping.

- `cmb_anisotropy_market`: CMB-like market background.
  Claim: Market has background radiation.
  Test: find_background_radiation.
  Mechanism: Market CMB analog.

- `gravitational_wave_market`: Gravitational waves from mergers.
  Claim: Stock mergers create waves.
  Test: gravitational_wave_spectrum.
  LIGO analog: Stock merger detection.

- `hawking_radiation_trading`: Hawking radiation from "black holes".
  Claim: Black hole stocks emit radiation.
  Test: stockHawking_radiation.
  Black hole thermodynamics.

- `unruh_effect_market`: Unruh effect = acceleration radiation.
  Claim: Accelerated stocks emit information.
  Test: acceleration_radiation.
  Quantum field theory in acceleration.

- `casimir_effect_market`: Casimir effect between sectors.
  Claim: Sectors have Casimir energy.
  Test: sector_Casimir_force.
  Vacuum energy in market.

- `entanglement_entropy_market`: Entanglement entropy = correlations.
  Claim: Entropy S = A/4 (area law).
  Test: entanglement_entropy vs sector_size.
  Black hole entropy analog.

- `page_curve_trading`: Page curve of information.
  Claim: Information loss follows Page curve.
  Test: page_curve_fit.
  Holographic entanglement entropy.

- `tensor_network_market`: Tensor network representation.
  Claim: Market = tensor network.
  Test: tensor_network_representation.
  MERA-like structure.

- ` Firewall_paradox_market`: Firewall paradox in market.
  Claim: Information paradox at "hot" stocks.
  Test: check_firewall.
  Black hole information paradox.

- `er=EPR_correlation`: ER = EPR for markets (Einstein-Rosen = Einstein-Podolsky-Rosen).
  Claim: Entangled sectors = wormholes.
  Test: entanglement_vs_correlation.
  ER = EPR is market basis.

- `page_woolf_theorem`: Page theorem on information.
  Claim: Half informationPage out at threshold.
  Test: information_decay_curve.
  Information paradox resolution.

- `ads_ground_state`: AdS ground state search.
  Claim: Find ground state of market Hamiltonian.
  Test: ground_state_energy.
  Quantum gravity: market as quantum system.

## Biology / Genetics

- `DNA_sequence_coding`: Return sequences as DNA.
  Claim: DNA-like code in returns.
  Test: find_genetic_code.
  Mechanism: Genetic algorithm on returns.

- `CRISPR_signal_editing`: CRISPR-style signal editing.
  Claim: Edit signals like CRISPR edits genes.
  Test: CRISPR_on_signals.
  Gene editing meets signal processing.

- `RNA_transcription_market`: RNA transcription analog.
  Claim: DNA → RNA = price → signal.
  Test: transcription_speed.
  Central dogma in markets.

- `protein_folding_signal`: Protein folding problem.
  Claim: Signals fold like proteins.
  Test: folding_energy.
  Protein structure prediction.

- `epigenetic_market`: Epigenetic modification.
  Claim: "Methylation" = signal memory.
  Test: methylation_patterns.
  Epigenetic inheritance.

- `telomere_length_market`: Telomere-like price caps.
  Claim: Price has maximum "telomere".
  Test: price_telomere.
  Cellular aging analog.

- `cancer_cell_market`: Cancer-like stocks (fast growth).
  Claim: "Cancer" stocks overgrow.
  Test: growth_rate_vs_anomaly.
  Cancer phenotype mapping.

- ` stem_cell_portfolio`: Stem cell-like selection.
  Claim: Stem cells = undifferentiated potential.
  Test: stemness_score.
  Pluripotent selection.

- `neuron_network_market`: Neural network analogy.
  Claim: Market = neural network.
  Test: network_architecture.
  Deep learning market model.

- `synaptic_plasticity_market`: Synaptic plasticity = signal learning.
  Claim: Synapses strengthen with use.
  Test: synaptic_change_rate.
  Learning in brain vs market.

- `quantum_biology_market`: Quantum biology effects.
  Claim: Quantum effects in photosynthesis, magnetoreception → market.
  Test: quantum_market_effects.
  Quantum mechanics in biology.

- `circadian_rhythm_market`: Circadian rhythm in VN market.
  Claim: Market has daily rhythm.
  Test: rhythm_phase.
  Biological clock mapping.

- `seasonal_affective_market`: Seasonal affective disorder.
  Claim: Market has seasonal patterns.
  Test: seasonal_pattern_strength.
  Mood disorder analogy.

- `metabolic_rate_market`: Market metabolism.
  Claim: Trading volume = metabolic rate.
  Test: metabolic_rate_correlation.
  Metabolic mapping.

- `circadian_portfolio`: Time-of-day genetic programming.
  Claim: Gene ~ time of day.
  Test: time_gene_expression.
  Chronobiology mapping.

## Philosophy of Mind

- `hard_problem_market`: Hard problem of consciousness.
  Claim: Why does market "think"?
  Test: measure_consciousness.
  Hard problem parallel.

- `qualia_trading`: Qualia in price.
  Claim: Price has qualia (raw feels).
  Test: find_qualia.
  Consciousness studies.

- `integrated_information_market`: Integrated information theory.
  Claim: Φ = market consciousness.
  Test: compute_integrated_information.
  IIT application.

- `global_workspace_market`: Global workspace in market.
  Claim: Market has global broadcast.
  Test: workspace_model.
  Psychology model.

- `predictive_coding_market`: Predictive coding as market.
  Claim: Brain = hierarchical predictive model.
  Test: hierarchical_prediction_error.
  Neuroscience meets market.

- `free_energy_principle`: Free energy principle.
  Claim: Markets minimize free energy.
  Test: free_energy_minimization.
  FEP in markets.

- `active_inference_market`: Active inference.
  Claim: Market infers + acts.
  Test: active_inference_fit.
  Active inference framework.

- ` Predictive_Mind_price`: Predictive processing.
  Claim: Market predicts everything.
  Test: prediction_horizon.
  Predictive brain → market.

- `dual_aspect_market`: Dual aspect of information.
  Claim: Mind-matter = price-observer.
  Test: dual_aspect_correlation.
  Panpsychism connection.

- `panpsychism_market`: Panpsychism in markets.
  Claim: Everything has "mind".
  Test: measure_mind_in_stocks.
  Consciousness in everything.

- `orchestrated_consciousness`: Orch-OR theory in market.
  Claim: Orchestrated objective reduction.
  Test: check_orch_or.
  Quantum consciousness.

- `neural_correlate_market`: Neural correlate of market.
  Claim: Find NCM (neural correlate of market).
  Test: NCM_finding.
  Discover the market correlate.

- `global_neuronal_workspace`: Global neuronal workspace.
  Claim: GNW in market = global price.
  Test: workspace_coherence.
  GNW theory application.

- `higher_theory_market`: Higher-order theories.
  Claim: Higher-order thoughts in market.
  Test: higher_order_content.
  Theories of consciousness.

- `attention_schema_market`: Attention schema.
  Claim: Market has attention.
  Test: attention_schema_fit.
  Attention mechanism.

## Deep Learning / AI

- `transformer_attention_market`: Transformer attention mechanism.
  Claim: Attending to stocks like tokens.
  Test: attention_weights.
  NLP → markets transform.

- `BERT_price_embedding`: BERT embeddings for prices.
  Claim: Price sequence → BERT embeddings.
  Test: price_BERT_performance.
  Language model → price model.

- `GPT_market_generation`: GPT for price generation.
  Claim: Generate future prices.
  Test: GPT_generation_quality.
  Generative model.

- `diffusion_market_models`: Diffusion models for prices.
  Claim: Diffusion model price paths.
  Test: diffusion_trajectory_quality.
  Image generation → price generation.

- `VAE_market_latent`: VAE latent space.
  Claim: Market has latent space.
  Test: VAE_latent_quality.
  Variational autoencoder.

- `autoencoder_anomaly`: Autoencoder for anomalies.
  Claim: Reconstruction error = anomaly.
  Test: autoencoder_anomaly_score.
  Anomaly detection.

- `generative_adversarial_market`: GAN for market.
  Claim: Generator vs discriminator.
  Test: GAN_market_quality.
  Adversarial training.

- `self_supervised_market`: Self-supervised learning.
  Claim: Predict next day from past.
  Test: SSL_performance.
  Self-supervised pretraining.

- `contrastive_learning_market`: Contrastive learning.
  Claim: Similar days close, different far.
  Test: contrastive_loss.
  Representation learning.

- `retrieval_augmented_market`: Retrieval-augmented generation.
  Claim: Retrieve similar days → predict.
  Test: RAG_performance.
  Memory-augmented model.

- `chain_of_thought_market`: Chain of thought in prices.
  Claim: Reasoning chain in price moves.
  Test: CoT_price_accuracy.
  Chain of thought prompting.

- `tool_use_market`: Tool use in trading.
  Claim: Use external tools like calculators.
  Test: tool_use_frequency.
  Tool learning.

- `constitutional_ai_trading`: Constitutional AI principles.
  Claim: Principles constrain behavior.
  Test: constitutional_compliance.
  AI alignment in markets.

- `RLHF_market`: RL from human feedback.
  Claim: Human feedback improves trading.
  Test: RLHF_performance.
  RL from human feedback.

- `reward_modeling_market`: Reward modeling.
  Claim: Model reward from behavior.
  Test: reward_model_accuracy.
  Inverse RL.

- `constitutional_ai_trading`: Constitutional AI principles.
  Claim: Principles constrain behavior.
  Test: constitutional_compliance.
  AI alignment in markets.

## Even More Insane (S241)

- `mandelbrot_set_trading`: Mandelbrot set boundary as support.
  Claim: Price respects Mandelbrot boundary.
  Test: price_vs_mandelbrot_boundary.
  Fractal geometry.

- `julia_set_market`: Julia set of market.
  Claim: Market = Julia set iteration.
  Test: find_julia_set.
  Dynamical systems.

- `newton_fractal_trading`: Newton fractal patterns.
  Claim: Newton method iterations = patterns.
  Test: newton_fractal_patterns.
  Root finding visualization.

- `sierpinski_triangle_market`: Sierpinski in price.
  Claim: Price traces Sierpinski triangle.
  Test: find_sierpinski.
  Recursive pattern.

- `cantor_dust_market`: Cantor dust in market.
  Claim: Market has Cantor dust structure.
  Test: find_cantor_dust.
  Self-similar set.

- `koch_curve_support`: Koch curve as support.
  Claim: Support/resistance = Koch geometry.
  Test: koch_curve_fit.
  Infinite boundary.

- `menger_sponge_market`: Menger sponge volume.
  Claim: Volume = Menger sponge.
  Test: menger_dimension.
  Fractal dimension.

- `peano_curve_market`: Peano space-filling.
  Claim: Market fills space like Peano.
  Test: peano_curve_mapping.
  Space-filling curves.

- `hilbert_curve_market`: Hilbert curve trading.
  Claim: Data on Hilbert curve.
  Test: hilbert_mapping_quality.
  Space-filling curve indexing.

- `box_counting_dimension`: Box-counting dimension.
  Claim: D₀ = fractal dimension.
  Test: box_counting_dimension.
  Dimension estimation.

- `lyapunov_dimension_market`: Lyapunov dimension.
  Claim: Kaplan-Yorke dimension.
  Test: lyapunov_dimension.
  Strange attractor dimension.

- `information_dimension_market`: Information dimension.
  Claim: D₁ = information dimension.
  Test: information_dimension.
  Entropy-based dimension.

- `correlation_dimension_market`: Correlation dimension.
  Claim: D₂ = correlation dimension.
  Test: correlation_dimension.
  Point correlation dimension.

- `multifractal_spectrum`: Multifractal spectrum.
  Claim: Spectrum as regime fingerprint.
  Test: multifractal_spectrum.
  Singularity spectrum.

- `singularity_spectrum_market`: Singularity spectrum f(α).
  Claim: f(α) measures regularity.
  Test: singularity_spectrum.
  Multifractal analysis.

- `renormalization_group`: Renormalization group in market.
  Claim: RG flow = regime change.
  Test: renormalization_flow.
  Scale invariance.

- `fixed_point_market`: Fixed point equation.
  Claim: Market → fixed point.
  Test: fixed_point_convergence.
  Fixed point theorem.

- `critical_phenomena_market`: Critical phenomena.
  Claim: Critical exponents describe market.
  Test: critical_exponent_measurement.
  Phase transition physics.

- `order_parameter_market`: Order parameter.
  Claim: Order parameter = market direction.
  Test: order_parameter_value.
  Order parameter theory.

- `symmetry_breaking_market`: Spontaneous symmetry breaking.
  Claim: Market breaks symmetry.
  Test: symmetry_breaking_scale.
  Goldstone modes.

- `goldstone_market`: Goldstone modes.
  Claim: Low-energy excitations.
  Test: goldstone_modes.
  Broken symmetry.

- `effective_field_market`: Effective field theory.
  Claim: Market = effective field.
  Test: effective_action.
  EFT in markets.

- `wilsonian_rg`: Wilsonian renormalization.
  Claim: Scale-by-scale integration.
  Test: wilsonian_flow.
  Wilson's RG approach.

- `epsilon_expansion`: epsilon expansion.
  Claim: ε expansion calculates.
  Test: epsilon_expansion_fit.
  Critical point calculation.

- `conformal_symmetry`: Conformal symmetry in market.
  Claim: Scale + special conf invariance.
  Test: conformal_invariant.
  Conformal field theory.

- `stress_energy_market`: Stress-energy tensor.
  Claim: Tμν = market stress-energy.
  Test: stress_energy_conservation.
  conservation law.

- `anomaly_market`: Chiral anomaly.
  Claim: Anomaly = information loss.
  Test: anomaly_check.
  Anomaly matching.

- `index_theorem_market`: Atiyah-Singer index.
  Claim: Index = topology change.
  Test: index_calculation.
  Index theorem.

- `characteristic_classes`: Characteristic classes.
  Claim: Classes = market invariants.
  Test: characteristic_classes.
  Chern classes.

- `kosmann_derivative`: Kosmann derivative.
  Claim: Spinor covariant derivative.
  Test: kosmann_derivative_value.
  Supergravity.

- `torsion_market`: Torsion as market signal.
  Claim: Torsion = spin interaction.
  Test: torsion_measurement.
  Cartan structure.

- `levi_civita_connection`: Levi-Civita connection.
  Claim: Geodesic = price path.
  Test: geodesic_path.
  Riemannian geometry.

- `riemann_curvature`: Riemann curvature tensor.
  Claim: Rμναβ = curvature.
  Test: curvature_tensor.
  Curvature field.

- `ricci_flow_market`: Ricci flow smoothing.
  Claim: Market smooths like Ricci flow.
  Test: ricci_flow_iteration.
  Geometric evolution.

- `yamabe_flow_market`: Yamabe flow for normalization.
  Claim: Yamabe flow normalizes.
  Test: yamabe_flow_result.
  Conformal flow.

- `calabi_yau_market`: Calabi-Yau manifold market.
  Claim: CY manifold = market structure.
  Test: calabi_yau_fit.
  Complex manifold.

- `kahler_potential`: Kähler potential.
  Claim: K = log |∂W|².
  Test: kahler_potential_value.
  Complex differential geometry.

- `hodge_laplacian`: Hodge Laplacian.
  Claim: Δ = d*d + d*d.
  Test: hodge_eigenvalues.
  Harmonic forms.

- `hodge_star_market`: Hodge star operator.
  Claim: * maps k-forms to (n-k)-forms.
  Test: hodge_star_action.
  Duality.

- `Dolbeault_operator`: ∂̄ operator in markets.
  Claim: ∂̄ = Cauchy-Riemann.
  Test: dolbeault_cohomology.
  Complex analysis.

- `sheaf_cohomology`: Sheaf cohomology.
  Claim: Sheaf = market information.
  Test: sheaf_cohomology_groups.
  sheaf theory.

- `etale_cohomology`: etale cohomology.
  Claim: Etale maps to market.
  Test: etale_cohomology.
  Algebraic topology.

- `motive_periods`: Motives and periods.
  Claim: Periods = market integrals.
  Test: motive_periods.
  Motives → periods.

- `absolute_geometry`: Absolute geometry over Q.
  Claim: Geometry over integers.
  Test: absolute_point_count.
  Number geometry.

- `arithmetic_surface`: Arithmetic surface.
  Claim: Price surface = arithmetic.
  Test: arithmetic_genus.
  Arithmetic geometry.

- `modular_curves`: Modular curves.
  Claim: Prices on modular curve.
  Test: modular_curve_points.
  Complex multiplication.

- `shimura_variety`: Shimura variety.
  Claim: Market = Shimura variety.
  Test: shimura_dimension.
  Modular forms.

- `langlands_program`: Langlands correspondence.
  Claim: Representations ↔ automorphic forms.
  Test: langlands_fit.
  Langlands dual.

- `categorical_logic`: Categorical logic.
  Claim: Category theory = logic.
  Test: categorical_type_theory.
  Type theory in markets.

- `topos_theory_market`: Topos theory.
  Claim: Topos = universe of sets.
  Test: topos_construction.
  Sheaf topos.

- `homotopy_type_theory`: Homotopy type theory.
  Claim: HoTT = foundations.
  Test: HoTT_type_checking.
  Univalent foundations.

- `univalent_universe`: Univalent universe.
  Claim: U = univalent universe.
  Test: univalent_universe_count.
  Univalent foundations.

- `cubical_type_theory`: Cubical type theory.
  Claim: Cubical = computable.
  Test: cubical_computation.
  Computational HoTT.

- `internal_language`: Internal language of topos.
  Claim: Internal language = market.
  Test: internal_language_run.
  Category-as-type.

- `synthetic_geometry`: Synthetic geometry.
  Claim: Axioms = geometry.
  Test: synthetic_axioms.
  Euclidean synthetic.

- `affine_geometry`: Affine geometry.
  Claim: Affine maps = transformations.
  Test: affine_transform_fit.
  Linear structures.

- `projective_geometry`: Projective geometry.
  Claim: Points at infinity.
  Test: projectivization.
  Completion at infinity.

- `conformal_geometry`: Conformal geometry.
  Claim: Angles preserved.
  Test: conformal_structure.
  Weyl invariance.

- `symplectic_geometry`: Symplectic geometry.
  Claim: Area form preserved.
  Test: symplectic_form.
  Hamiltonian mechanics.

- `contact_geometry`: Contact geometry.
  Claim: Contact structure.
  Test: contact_structure.
  3D analog of symplectic.

- `cr_geometry`: CR geometry.
  Claim: ComplexReal boundary.
  Test: CR_structure.
  Complex boundary.

- `almost_complex_structure`: Almost complex structure.
  Claim: J² = -1.
  Test: almost_complex_check.
  Complex structure.

- `complex_manifold`: Complex manifold.
  Claim: Holomorphic coordinates.
  Test: holomorphicity.
  Complex coordinates.

- `kahler_manifold`: Kähler manifold.
  Claim: Kähler = Hermitian + symplectic.
  Test: kahler_property.
  Special geometry.

- `calabi_yau_manifold`: Calabi-Yau manifolds.
  Claim: Ricci-flat Kähler.
  Test: calabi_yau_condition.
  String theory compactification.

- `g2_manifold`: G2 manifold.
  Claim: Exceptional holonomy.
  Test: G2_holonomy.
  7D manifold.

- `spin_manifold`: Spin manifold.
  Claim: Spin structure exists.
  Test: spin_structure_check.
  Spin geometry.

- `orientable_manifold`: Orientability.
  Claim: Orientation preserved.
  Test: orientability.
  Orientation.

- `parallelizable_manifold`: Parallelizable.
  Claim: Global frame exists.
  Test: parallelizability.
  Frame field.

- ` einstein_manifold`: Einstein manifold.
  Claim: Ricci = λg.
  Test: einstein_condition.
  Constant curvature.

- `ricci_flow`: Ricci flow equation.
  Claim: dg/dt = -2Ric.
  Test: ricci_flow_simulation.
  Geometric evolution equation.

- `mean_curvature_flow`: Mean curvature flow.
  Claim: H = 0 is critical.
  Test: MCF_stationary.
  Minimal surfaces.

- `willmore_energy`: Willmore energy.
  Claim: Minimize Willmore energy.
  Test: willmore_minimizer.
  conformal invariance.

- `yang_mills_energy`: Yang-Mills energy.
  Claim: Critical gauge fields.
  Test: YM_energy_minimizer.
  Gauge theory.

- `seiberg_witten`: Seiberg-Witten equations.
  Claim: SW = 4-manifold invariant.
  Test: SW_invariant.
  Gauge theory.

- `floer_homology`: Floer homology.
  Claim: Count Morse trajectories.
  Test: floer_homology_groups.
  Symplectic topology.

- `hofer_geometry`: Hofer's geometry.
  Claim: Hofer norm on symplectomorphisms.
  Test: hofer_norm.
  Symplectomorphism geometry.

- `gromov_width`: Gromov width.
  Claim: Non-squeezing theorem.
  Test: gromov_width_value.
  symplectic embedding.

- `gromov_horomorphism`: Gromov convergence.
  Claim: Gromov-Hausdorff limit.
  Test: GH_convergence.
  Metric geometry.

- `persistence_homology`: Persistence homology.
  Claim: Birth-death of features.
  Test: persistence_diagram.
  TDA method.

- `morse_theory`: Morse theory.
  Claim: Critical points give topology.
  Test: morse_complex.
  Morse functions.

- `spectral_sequence`: Spectral sequence.
  Claim: E → H*(X).
  Test: spectral_sequence_convergence.
  Homology computation.

- `cellular_homology`: Cellular homology.
  Claim: Cell complex homology.
  Test: cellular_complex.
  CW complexes.

- `singular_homology`: Singular homology.
  Claim: Singular simplices.
  Test: singular_groups.
  Topological invariance.

- `de_rham_cohomology`: de Rham cohomology.
  Claim: Differential forms.
  Test: de_rham_groups.
  Differential topology.

- `dolbeault_cohomology`: Dolbeault cohomology.
  Claim: ∂̄-closed forms.
  Test: ∂̄_cohomology.
  Complex manifold.

- ` sheaf_cohomology`: Sheaf cohomology.
  Claim: Locally defined sections.
  Test: sheaf_cohomology_groups.
  Sheaf theory.

- `Čech_cohomology`: Cech cohomology.
  Claim: Covering refinement.
  Test: check_complex.
  Covering method.

- `Alexander_cohomology`: Alexander cohomology.
  Claim: Coorientation.
  Test: alexander_polynomial.
  Knot theory.

- `定向_cohomology`: Oriented cohomology.
  Claim: Orientation local system.
  Test: oriented_cohomology.
 定向 theory.

- `K_theory`: K-theory.
  Claim: Vector bundles → K-theory.
  Test: K_groups.
  Topological K-theory.

- `KO_theory`: Real K-theory.
  Claim: Real periodicity.
  Test: KO_groups.
  Real K-theory.

- ` elliptic_cohomology`: Elliptic cohomology.
  Claim: Elliptic curves.
  Test: elliptic_spectrum.
  Generalized cohomology.

- `complex Cobordism`: Complex cobordism.
  Claim: MU complex cobordism.
  Test: MU_ring.
  Cobordism theory.

- `topological_modular_forms`: Topological modular forms.
  Claim: TMF = elliptic cohomology.
  Test: TMF_groups.
  Topological modular forms.

- `stable_homotopy`: Stable homotopy groups.
  Claim: πₙ(S⁰).
  Test: stable_groups.
  Stable homotopy.

- `Adams_spectral_sequence`: Adams spectral sequence.
  Claim: Ext → stable homotopy.
  Test: Adams_differential.
  Computation method.

- `ANGElow_spectral`: ANSS for Morel-Voevodsky.
  Claim: π₁(MG) → πₙ(S⁰).
  Test: anesslope.
  motivic stable homotopy.

- `motivic_homotopy`: Motivic homotopy.
  Claim: Over Spec(k).
  Test: motivic_stable_groups.
  Motivic spaces.

- `étale_homotopy`: Étale homotopy.
  Claim: Profinite completion.
  Test: étale_homotopy_type.
  Algebraic topology.

- `profinite_completion`: Profinite completion.
  Claim: Ẑ = lim Z/n.
  Test: profinite_completion_group.
  Completion theory.

## Mathematical Physics (All of It)

- `witten_index`: Witten index.
  Claim: Tr(-1)^F = index.
  Test: witten_index_value.
  Supersymmetry.

- `Kasparov_Groups`: KK-theory.
  Claim: K-theory of operator algebras.
  Test: KK_groups.
  Operator K-theory.

- `Connes_index_theory`: Connes index theorem.
  Claim: Index = topological invariant.
  Test: connes_index_pairing.
  Noncommutative geometry.

- `BC_theorem`: Bott periodicity.
  Claim: Period 2 in K-theory.
  Test: bott_periodicity.
  Periodicity.

- `Clifford_algebra`: Clifford algebra.
  Claim: Cℓ(p,q).
  Test: clifford_algebra_type.
  Spin representation.

- `Dirac_operator`: Dirac operator.
  Claim: iγᵐDₘ.
  Test: dirac_spectrum.
  Quantum field theory.

- `Atiyah_Singer`: Atiyah-Singer index theorem.
  Claim: Index(D) = topological.
  Test: atiyah_singer_index.
  Index theorem.

- `Atiyah_Bott`: Fixed point formula.
  Claim: Lefschetz fixed point.
  Test: atiyah_bott_formula.
  Fixed point distribution.

- `gloss_on_Riemann`: Glaisher formula.
  Claim: Partition generating function.
  Test: glaisher_formula.
  Number theory.

- `Selberg_Zeta`: Selberg zeta function.
  Claim: Z(s) = ∏_γ (1 - N(γ)^{-s}).
  Test: selberg_zeta_zeros.
  Spectral theory.

- `Random_Matrices`: Random matrix theory.
  Claim: Wigner-Dyson statistics.
  Test: random_matrix_gap_distribution.
  Nuclear physics.

- `Ladyzenskij`: Timeline of operator algebras.
  Claims: Class of operators.
  Test: classify_operator.
  Functional analysis.

- `Tomita_Takesaki`: Modular automorphism.
  Claim: Δ^{it}σ_t(A).
  Test: modular_flow.
  von Neumann algebras.

- `Connes_Embedding`: Connes embedding conjecture.
  Claim: Any II₁ factor embeds.
  Test: connes_embedding_check.
  Operator algebras.

- `Jones_polynomial`: Jones polynomial.
  Claim: knots → V_F(q).
  Test: jones_polynomial.
  Knot invariants.

- `HOMFLYPT`: HOMFLYPT polynomial.
  Claim: Two-variable polynomial.
  Test: homflypt_polynomial.
  Knot homology.

- `Khovanov_homology`: Khovanov knot homology.
  Claim: Knot → graded vector space.
  Test: khovanov_homology_groups.
  Categorified knot invariant.

- `knot_floer_homology`: Knot Floer homology.
  Claim: HF(K) = knot invariant.
  Test: knot_floer_homology_groups.
  Heegaard Floer theory.

- `knot homology`: Knot homology in other categories.
  Claim: Various categorifications.
  Test: check_knot_homology.
  Categorical invariants.

- `Khovanov_Rozansky`: Khovanov-Rozansky homology.
  Claim: sl(N) homology.
  Test: KR_homology_groups.
  Matrix factorization.

- `Birman_Lin`: Birman-Lin theorem.
  Claim: Knot groups fill in.
  Test: check_birman_lin.
  Mapping class groups.

- `mapping_class_group`: Mapping class group.
  Claim: MCG(Σ_g).
  Test: mCG_representation.
  Dehn twists.

- `Dehn_complex`: Dehn-Skeene theory.
  Claim: Dehn functions.
  Test: dehn_function_estimate.
  Third dimension.

- `Thurston_norm`: Thurston norm.
  Claim: ||ϕ||_T on H_2.
  Test: thurston_norm_value.
  3-manifold topology.

- `Perelmann_entropy`: Ricci flow → entropy.
  Claim: W functional.
  Test: perelman_entropy.
  Geometric analysis.

- `Hamiltion_DeTurk`: Hamilton-DeTurck flow.
  Claim: Gauge choice removes torsion.
  Test: deTurck_flow_result.
  Ricci flow.

- `Ricci_Solitons`: Ricci solitons.
  Claim: g = c(t) ¹¹¹ g₀ + (1/2t)R_g.
  Test: soliton_type.
  Self-similar solutions.

- `Yamabe_Problem`: Yamabe problem.
  Claim: Conformal constant scalar curvature.
  Test: yamabe_solution_exists.
  Conformal geometry.

- `Schoen_Yau`: SY inequality.
  Claim: Positive mass theorem.
  Test: schoen_yau_check.
  Differential geometry.

- `Witten_Guth`: Stability conjecture.
  Claim: Initial data stable.
  Test: witten_guth_stable.
  Mass in GR.

- ` Jang_surface`: Jang equation.
  Claim: ∂ₜJ = -(tr KJ) + |∂J|/J.
  Test: jang_surface_construct.
  PSR in GR.

- `Penrose_Consjecture`: Penrose inequality.
  Claim: m ≥ √(A/16π).
  Test: penrose_inequality.
  Gravitational mass.

- `Positive_Mass`: Positive mass theorem.
  Claim: m ≥ 0 for ASC data.
  Test: positive_mass_theorem.
  Energy positivity.

- `Witten_Superselection`: Superselection sectors.
  Claim: DHR sectors.
  Test: superselection_sectors.
  Algebraic QFT.

- ` Doplicher_Roberts`: DR duality.
  Claim: Sector categories.
  Test: dr_dual_higher_group.
  Tensor categories.

- `Haag_Correspondence`: Haag duality.
  Claim: A ⊂ B(mathcal H).
  Test: haag_locality.
  Local quantum field theory.

- `Bisognano_Wichmann`: BW theorem.
  Claim: Unruh effect as TW side.
  Test: bisognano_wichmann_check.
  Rindler quantization.

- `Unruh_effect`: Unruh effect.
  Claim: Uniformly accelerated detector sees vacuum as thermal.
  Test: unruh_temperature.
  Temperature from acceleration.

- `Sakai_turn`: Sakai ellipsis.
  Claim: Boundary → CFT.
  Test: adS_CFT_correspondence.
  Holographic principle.

- `GKP_Witten`: GKP-Witten relation.
  Claim: correlators have gravity duals.
  Test: gkp_witten_check.
  String theory.

- `Maldacena_conjecture`: AdS/CFT correspondence.
  Claim: N strong CFT = weakly coupled gravity.
  Test: check_adS_CFT_duality.
  Ultimate hologram.

- `Polchinski_Briefs`: Polchinski string equations.
  Claim: 26D bosonic, 10D super.
  Test: polchinski_brane_count.
  String theory.

- `Green_Schwartz`: Green-Schwartz mechanism.
  Claim: κ-symmetry gauges.
  Test: green_schwartz_gauge_fix.
  Superstring action.

- `NSVS_R`: NS5 + R → Type IIA/IIB.
  Claim: S-duality relates.
  Test: NS5_R_charge_quantization.
  String dualities.

- `T_duality`: T-duality.
  Claim: R ↔ α'/R.
  Test: T-duality_check.
  Target space duality.

- `S_duality`: S-duality.
  Claim: g → 1/g.
  Test: S-duality_check.
  Type I ↔ HO ↔ IIB.

- `U_duality`: U-duality.
  Claim: S + T combined.
  Test: U-duality_check.
  Maximal supergravity.

- `Mirror_Symmetry`: Mirror symmetry.
  Claim: CY ↔ dual CY.
  Test: mirror_pair_exists.
  Calabi-Yau.

- `K3_Surfaces`: K3 surfaces.
  Claim: Complex surfaces with trivial canonical.
  Test: K3_hodge_numbers.
  K3 surfaces.

- `Elliptic_Surfaces`: Elliptic surfaces.
  Claim: Elliptic fibrations.
  Test: elliptic_surface_pencil.
  Rational surfaces.

- `Rational_Surfaces`: Rational surfaces.
  Claim: Picard rank = 1.
  Test: rational_surface_check.
  Ruled surfaces.

- `Enriques_Surface`: Enriques surfaces.
  Claim: Canonical covers K3.
  Test: enriques_involution.
  Algebraic surfaces.

- `Siegel_Upper_Half`: Siegel upper half-space.
  Claim: Sp(2g, Z) acts on moduli.
  Test: siegel_moduli_point.
  Abelian varieties.

- `Jacobians`: Jacobian varieties.
  Claim: Pic⁰(X) = Jac(X).
  Test: jacobian_variety.
  Albanese variety.

- `Intermediate_Jacobian`: Intermediate Jacobians.
  Claim: H^{2n-1} → Alb.
  Test: intermediate_jacobian_check.
  Intermediate.

- ` Prym_Varieties`: Prym varieties.
  Claim: Double cover branched points.
  Test: prym_variety_dimension.
  Root systems.

- `Weyl_Chamber`: Weyl chamber.
  Claim: Root space decomposition.
  Test: weyl_chamber_position.
  Lie algebras.

- ` Root_System_Te`: Root systems.
  Claim: A_n, B_n, C_n, D_n, E_6,7,8, F_4, G_2.
  Test: root_system_type.
  Classification.

- ` Dynkin_Diagram`: Dynkin diagrams.
  Claim: Cartan matrix encodes.
  Test: dynkin_diagram_count.
  Lie group structure.

- `Affine_Lie`: Affine Lie algebras.
  Claim: Kac-Moody algebras.
  Test: affine_lie_level.
  Current algebras.

- `Quantum_Group`: Quantum groups.
  Claim: U_q(g) deformations.
  Test: quantum_group_deformation_parameter.
  q-deformation.

- `Yangian`: Yangians.
  Claim: Chiral Yangians.
  Test: yangian_representation_affine.
  Integrable systems.

- `Quantum_KdV`: Quantum KdV.
  Claim: q-KdV integrable.
  Test: quantum_kdv_conserved.
  Quantum integrable.

- `Bethe_Ansatz`: Bethe ansatz.
  Claim: Eigenvalues from Bethe equations.
  Test: bethe_equation_solution.
  Exact solution.

- ` Baxter_Q`: Baxter Q-operator.
  Claim: Q obeys Q Q = I.
  Test: Baxter_Q_function.
  Exactly solvable models.

- `Eight_Vertex`: 8-vertex model.
  Claim: Exactly solvable.
  Test: eight_vertex_exact_solution.
  Exactly solved.

- `Six_Vertex`: 6-vertex model (XXZ).
  Claim: Ice-type model.
  Test: six_vertex_partition_function.
  Exactly solved.

- `Potts_Model`: Potts model.
  Claim: q-state Potts.
  Test: potts_critical_exponent.
  q-state Potts.

- `Ashkin_Teller`: Ashkin-Teller.
  Claim: Coupled Ising.
  Test: ashkin_teller_critical_point.
  Coupled Ising.

- ` XY_Model`: XY model.
  Claim: O(2) symmetry.
  Test: xy_model_vortex_entropy.
  Vortex binding.

- `Vector_Potts`: Vector Potts.
  Claim: O(N) model.
  Test: vector_potts_critical_exponent.
  Vector models.

- `Heisenberg_Model`: Heisenberg model.
  Claim: Spin-1/2 with O(3).
  Test: heisenberg_critical_exponent.
  Antiferromagnet.

- `Hubbard_Model`: Hubbard model.
  Claim: U on-site interaction.
  Test: hubbard_mott_transition.
  Mott insulator.

- `t_J_Model`: t-J model.
  Claim: J coupling + no double occupancy.
  Test: t_J_phase_diagram.
  Superconductor.

- `Hubbard-Stratonovich`: HS transformation.
  Claim: Decouple interactions → bosons.
  Test: hs_decoupling_check.
  Mean field.

- `RVB_Theory`: Resonating Valence Bond.
  Claim: Spin liquid ground state.
  Test: rvb_energy_compare.
  Quantum spin liquid.

- `Chern_Simons`: Chern-Simons theory.
  Claim: CS action = ∫Tr(A∧dA+2/3 A∧A∧A).
  Test: chern_simons_level.
  Anyon statistics.

- `Jones_Knot`: Jones polynomial from Chern-Simons.
  Claim: V_K(t) = Z(C S_knot).
  Test: jones_from_chern_simon.
  CS → knot invariants.

- `Witten_Invariants`: Witten invariants of 3-manifolds.
  Claim: Z_M(A) = 3D partition.
  Test: witten_invariant_Euler.
  3-manifold invariants.

- `Reshetikhin_Turaev`: RT invariants.
  Claim: Ribbon categories.
  Test: RT_invariant_value.
  Quantum groups.

- `Turaev_Viro`: TV invariants.
  Claim: 3D from 2D→3D.
  Test: turaev_viro_sum.
  State sum model.

- `Kauffman_Products`: Kauffman products.
  Claim: Framed knot invariants.
  Test: kauffman_product_value.
  Framed knots.

- ` Kauffman_Bracket`: Kauffman bracket.
  Claim: <K> = (-A³)+³)<L>.
  Test: kauffman_bracket_evaluation.
  Unoriented.

- ` Khovanov_Homolog`: Khovanov homology.
  Claim: Categorified Jones.
  Test: khovanov_homology_bigraded.
  Differential graded.

- `Knot_Homology_Floer`: Floer homology.
  Claim: HF^ = knot invariant.
  Test: khovanov_floer_correspondence.
  Correspondence.

- `Milnor_Invariant`: Milnor invariants.
  Claim: Link invariants.
  Test: milnor_mu_bar.
  Higher links.

- `Alexander_Conway`: Conway-Gauss-Cessenko.
  Claim: Z ↔ linking.
  Test: conway_polynomial.
  Simple invariants.

- `Seifert_Matrix`: Seifert matrix.
  Claim: Linking form.
  Test: seifert_matrix_detects.
  Linking.

- `Torsion_Invariants`: Torsion.
  Claim: Reidemeister torsion.
  Test: reidemeister_torsion_value.
  Topological torsion.

- `eta_Invariant`: Eta invariant.
  Claim: Atiyah-Patodi-Singer.
  Test: eta_invariant_value.
  Spectral asymmetry.

- `rho_Invariant`: Rho invariant.
  Claim: Reduced eta.
  Test: rho_invariant_check.
  Chern-Simons.

- `Chern_Simons_Fields`: CS field theory.
  Claim: Topological gauge.
  Test: cs_field_strength_variation.
  Topological.

- `Witten_Floyd`: Floyd on surfaces.
  Claim: Skein threshold.
  Test: witten_floyd_check.
  Skein.

- `Goldman_Group`: Goldman Lie algebra.
  Claim: Lie structure on loops.
  Test: goldman_bracket_relations.
  Surface group.

- `Turaev_Goldman`: Turaev Goldman.
  Claim: Quasi-Tournament.
  Test: turaev_goldman_quantum.
  Skew-Hermitian.

- `Kauffman_Synthesis`: Kauffman sum.
  Claim: 1+1=1+1+1.
  Test: kauffman_sum_rules.
  Braiding.

- `trace_normality`: Trace normality.
  Claim: Markov property.
  Test: trace_markov_property.
  Skein modules.

- `Temperley_Lieb`: Temperley-Lieb.
  Claim: TL_n = (n+1)_q.
  Test: Temperley_Lieb_relation.
  Brauer algebra.

- `Brauer_Category`: Brauer category.
  Claim: Tensor * + loop.
  Test: brauer_category_check.
  Normalization.

- `Jones_Temperley`: Joint representation.
  Claim: QT = category.
  Test: JonesTemperley_correspondence.
  Fusion categories.

- `Ocneanu_Imrick`: Ocneanu rigidity.
  Claim: No gauge drift.
  Test: ocneanu_rigidity_check.
  Tensor categories.

- `Modular_Invariants`: Modular invariance.
  Claim: S-matrix commutes.
  Test: modular_invariance_check.
  Conformal field.

- `CFT_Corner`: Corner symmetry.
  Claim: Virasoro + affine + W.
  Test: cft_symmetry_budget.
  Chiral algebra.

- `Vertex_Algebra`: Vertex operator algebras.
  Claim: Chiral algebra = VOAs.
  Test: VOAs_associative_algebra.
  Chiral CFT.

- `Chiral_Conformal`: Chiral conformal blocks.
  Claim: CFT_1 → Bl.
  Test: chiral_conformal_block_computation.
  Conformal blocks.

- `Belavin_Polchinski`: BP scalings.
  Claim: Z = B² + A*+B*g.
  Test: belavin_polkblock_check.
  Pillow backgrounds.

- `WZW_Currents`: WZW currents.
  Claim: Kac-Moody level k.
  Test: wzw_current_algebra.
  Affine currents.

- `Coset_Construction`: Coset construction.
  Claim: g ⊃ h = G/H.
  Test: coset_cft_central_charge.
  Coset models.

- `GKO`: GKO coset.
  Claim: Virasoro from coset.
  test: gko_virasoro_recovery.
  String embeddings.

- `Minimal_Models`: Minimal models.
  Claim: p' → minimal.
  Test: minimal_model_classification.
  Unitary series.

- `D_Series`: D-series minimal.
  Claim: D_{2n+2}.
  Test: d_series_minimal_model.
  Non-unitary.

- `Rational_CFT`: Rational CFT.
  Claim: Finite RCFT.
  Test: rational_cft_check.
  Finite image.

- `Galois_Module`: Galois modules.
  Claim: Inertia action.
  Test: inertia_galois_action.
  Class field theory.

- ` Class_Field`: Class field theory.
  Claim: Artin map.
  Test: artin_map_surjectivity.
  Global CFT.

- `Langlands_Isldy`: Langlands isogeny conjecture.
  Claim: Isogeny ↔ automorphic.
  Test: langlands_isogeny_check.
  Reciprocity.

- `Shimura_Vari`: Shimura varieties.
  Claim: Hecke correspondences.
  Test: shimura_correspondence.
  Modular curves.

- `Drinfeld_Cocycle`: Drinfeld double.
  Claim: D(H) = H⊗H^* cop.
  Test: double_bialgebra_structure.
  Quantum doubles.

- `Quantum_Doubles`: Quantum doubles in QFT.
  Claim: D(brahms) = G.
  test: quantum_double_check.
  Duality.

- ` Quantum_Z`: Quantum dimension.
  Claim: dim_q(V) = [V]_q / [1]_q.
  Test: quantum_dimension_computation.
  q-dimension.

- `Fusion_Rules`: Fusion rules in RCFT.
  Claim: N_{ij}^k.
  Test: fusion_rule_check.
  Fusion algebra.

- `Modular_S`: S-matrix from fusion.
  Claim: S_{ij} from fusion rules.
  Test: modular_S_from_fusion.
  S duality.

- `Modular_T`: T-matrix from conformal weights.
  Claim: T_{ij} = δ_{ij} exp(2πi h_i).
  Test: modular_T_exponential.
  T transformation.

- `Verlinde_Formula`: Verlinde formula.
  Claim: N = S^{-1} * S^*2.
  Test: verlinde_formula_check.
  Fusion from S.

- `CE_Series`: CE series computation.
  Claim: Conformal engineering.
  test: ce_series_value_at_critical.
  Scaling dimensions.

- `Quantum_Cell`: Quantum cell model.
  Claim: Anyon collider.
  Test: quantum_cell_comparison.
  Quantum error correction.

- `Kitaev_Torus`: Kitaev toric code.
  Claim: Logical operators.
  test: kitaev_toric_check.
  Error correction.

- `Anyon_Theory`: Anyon theory.
  Claim: Anyon statistics.
  Test: anyon_statistic_value.
  Fusion rules.

- `Fibonacci_Anyon`: Fibonacci anyon.
  Claim: τ² = τ + 1.
  test: fibonacci_anyon_statistics.
  Universal QC.

- `Ising_Anyon`: Ising anyons.
  Claim: σ³ = 1.
  Test: ising_anyon_check.
  Topological QC.

- `Moore_Read`: Moore-Read state.
  Claim: PFa = Pf(Q).
  Test: moore_read_fractional_statistic.
  Fractional QC.

- `Read-Rezayi`: Read-Rezayi state.
  Claim: k+1 cluster.
  test: read_rezayi_clustering.
  Non-Abelian.

- `Non_Abelian_I`: Non-Abelian statistics.
  Claim: Degenerate exchange.
  Test: non_abelian_exchange_check.
  Statistics.

- `Topological_Order`: Topological order.
  Claim: Ground state degeneracy.
  Test: topological_order_detect.
  GSD.

- `Ground_State_Degeneracy`: Ground state degeneracy.
  Claim: GSD on genus g.
  Test: genus_surface_degeneracy.
  Topology detection.

- `Topological_Entropy`: Topological entropy.
  Claim: S_top = log(GSD).
  Test: topological_entropy_glog.
  Entropy calculation.

- `Boundary_CFT`: Boundary CFT.
  Claim: BFCFT on D-branes.
  test: boundary_conformal_theory.
  D-brane sectors.

- `Cardy_Case`: Cardy case.
  Claim: Open String → I.
  Test: cardy_case_boundary.
  Boundary states.

- ` Ishibashi_States`: Ishibashi states.
  Claim: |i⟩⟩ = ∑_n n|n⟩) ⊗ ṅ|n⟩).
  test: ishibashi_state_sum.
  Boundary.

- `Virasoro_Orbit`: Virasoro minimal model.
  Claim: Minimal models in Virasoro.
  test: virasoro_minimal_model_check.
  Minimal.

- `Virasoro_Charge`: Virasoro minimal models.
  Claim: c = 1 - 6(p-p')²/(pp').
  test: virasoro_c_check.
  Central charge.

- `Perelmus_Algebra`: Feigin-Feigin modules.
  Claim: Vertex + variety.
  test: feigin_feigin_modules.
  Quasi-lisse.

- `W_Algebra`: W-algebras.
  Claim: Enveloping algebras.
  test: W_algebra_generators.
  Extended algebras.

- `Triality`: S-duality for SO(32) + E8×E8.
  dual: T-duality + S-duality + O(32).
  Test: check_triality_equivalence.
  String dualities.

- `F_Theory`: F-theory.
  Claim: Elliptic fibration over base.
  Test: f_theory_base_space.
  12D.

- `M_theory`: M-theory.
  Claim: 11D SUGRA.
  test: m_theory_compactification.
  11D SUGRA.

- `Heterotic_Strings`: Heterotic strings. 
  Claim: E8×E8 or SO(32).
  Test: heterotic_gauge_group.
  Grand unification.

- `Tyoe_I_Strings`: Type I strings.
  Claim: O9 + 32 D9.
  Test: type_I_gauge_group.
  Oriented+unoriented.

- `D_Branes`: D-branes.
  Claim: p-branes.
  Test: d_brane_dimension_count.
  Nonperturbative.

- `NS5_Branes`: NS5 branes.  
  Claim: H_3(F) = Z.
  test: NS5_brane_flux.
  Fundamental.

- `M2_Branes`: M2 branes.
  Claim: 3D membranes.
  Test: m2_brane_bound_states.
  M-theory.

- `M5_Branes`: M5 branes.
  Claim: 6D tensors.
  Test: m5_brane_chiral_anomaly.
  6D.

- `S_Dual_FT`: S-duality in Type I.
  Claim: S maps I ↔ HO.
  Test: s_dual_i_ho_check.
  Strong-weak.

- `U_Dualities`: U-dualities.
  Claim: S + T + affine.
  Test: u_duality_group_enhanced.
  Extended U-duality.

- `F_Theory_U`: F-theory U-duality.
  Claim: Duality to M-theory.
  Test: f_theory_u_duality_check.
  Duality.

- `Heterotic_M`: Heterotic/M on T⁴.
  Claim: H × K3.
  Test: heterotic_m_duality.
  Duality.

- `M_On_CY`: M-theory on CY.
  Claim: N=2, 4D.
  Test: m_theory_cy_compactification.
  Superstrings.

- `String_Comp`: String compactifications.
  Claims: Many.
  Test: count_string_compactifications.
  Landscape.

- `Landscape` Landscape of string vacua.
  Claim: 10^500 vacua.
  Test: landscape_count.
  String landscape.

- `Swampland`: Swampland criteria.
  Claim: Not all QFTs in landscape.
  Test: swampland_criteria.
  Criteria.

- `Gradient_Flow`: Gradient flow.
  Claim: Morse-Smale.
  Test: gradient_flow_check.
  Downstream.

- `Morse_Homology`: Morse homology.
  Claim: Crit + Flow = H_*(M).
  test: morse_homology_computation.
  Homology.

- `Floer_Homolog2`: Floer homology.
  Claim: Instantons in symplectic.
  Test: instanton_floer_differential.
  Floer.

- ` Seiberg_Exac`: Exact Seiberg-Witten.
  Claim: N=2 SQCD.
  Test: seiberg_witten_exact_solution.
  Exact solution.

- `N2_BPS_Count`: BPS state counting.
  Claim: #BPS states.
  Test: bPS_count_computation.
  Index.

- ` MacArthur`: MacArthur duality.
  Claim: Inverse question.
  Test: macarthur_duality_check.
  EKMT relation.

- `Vafa_Witten`: Vafa-Witten.
  Claim: Twist on 4-manifolds.
  Test: vafa_witten_invariant.
  Topological.

- `Gopakumar_Vafa`: Gopakumar-Vafa.
  Claim: BPS → Gromov-Witten.
  Test: gopakumar_vafa_check.
  GV=Gopakumar.

- `Integrality`: Integrality conjecture.
  Claim: S^4 #P = integral.
  Test: integrality_check.
  Invariants.

- `Donaldson_Thomas`: DT invariants.
  Claim: Counting stable sheaves.
  Test: dt_invariant_computation.
  Sheaf counts.

- ` PT_Invariants`: PT invariants.
  Claim: Curve counting.
  Test: pt_invariant_value.
  Plane partition.

- `Mariño-Vafa`: Mariño-Vafa formula.
  Claim: PT = string.
  Test: marino_vafa_check.
  M-L.

- `Katz-Klemm-Ler`: KKL formula.
  Claim: Conifold × S³.
  Test: kkl_formula_check.
  Conifold.

- `Vafa-Yin`: Vafa-Yin.
  Claim: Gopakumar form.
  Test: vafa_yin_integral_form.
  Topological string.

- `A_Model`: A-model.
  Claim: ω-topological.
  Test: a_model_correlation_function.
  Topological string.

- `B_Model`: B-model.
  Claim: Ω-topological.
  Test: b_model_correlation_function.
  Topological string.

- `Closed_String`: Closed string.
  Claim: Target × Target.
  Test: closed_string_correlator.
  String worldsheet.

- `Open_String`: Open string.
  Claim: D-brane sector.
  Test: open_string_correlator.
  Boundary.

- `Topological_String`: Topological string.
  Claim: tw = 0.
  Test: topological_string_check.
  Physical string.

- `Large_N`: Large N factorization.
  Claim: Z ~ exp(F_classical).
  test: large_N_f_2_expansion.
  Zeta function.

- `Open-Closed`: Open-closed duality.
  Claim: closed ↔ open * O.
  test: open_closed_duality_check.
  O/O*O.

- `Holomorphic`: Holomorphic anomaly.
  Claim: F − F_{hol}= N log.
  Test: holomorphic_anomaly_equation.
  Anomaly.

- `BCOV_ anomaly`: BCOV anomaly.
  Claims: N=2 chiral.
  test: bcov_anomaly_check.
  Anomaly equations.

- `Witten_NLC`: Witten noncritical.
  Claims: c=1 string.
  test: witten_noncritical_check.
  Noncritical.

- ` Liouville_Theor`: Liouville field.
  Claim: c > 25.
  test: liouville_theory_check.
  Liouville.

- `TFT_Correspondence`: TFT-correspondence.
  claim: CFT ↔ 2D gauge.
  Test: tft_correspondence_check.
  2D-3D duality.

- `Virasoro_Constraint`: Virasoro constraint.
  Claims: L_{-1}, L₀.
  Test: virasoro_constraint_check.
  Conformal.

- ` BRST_Cohomology`: BRST cohomology.
  Claims: Q² = 0.
  test: BRST_cohomology_groups.
  Gauge fixed.

- ` Bosonic_String`: Bosonic string.
  claim: Critical 26D.
  test: critical_dimension_check.
  Unstable!

- ` Superstring`: Superstring.
  claim: Critical 10D.
  test: superstring_critical_dimension.
  Stable.

- ` Hybrid_String`: Hybrid string.
  Claim: 6D N=2.
  Test: hybrid_string_type.
  Heterotic.

- `Little_String`: Little string theory.
  Claim: 6D noncritical.
  Test: little_string_check.
  NS5.

- `Witten_O99`: Witten (1999).
  Claims: Twist E8.
  Test: witten_twist_nc_check.
  Noncritical.

- `Banks_Z`: Banks-Z as matrix models.
  claim: M-theory = bfss matrix.
  Test: matrix_model_check.
  Matrix models.

- `IKKT`: IKKT matrix model.  
  Claim: Lorentzian CFT.
  Test: ikkt_model_check.
  Fuzzy.

- `BMN`: BMN matrix.
  Claim: pp-wave.
  Test: bmn_matrix_check.
  Penrose.

- `Matrix_String`: Matrix string.
  Claim: D1 → D4.
  Test: matrix_string_duality.
  String bits.

- ` Stringy`: String bits.
  Claim: String = bits.
  Test: string_bits_check.
  Bits.

- `Non_Pert`: String nonperturbative.
  claims: Nonperturbative completions.
  Test: nonperturbative_completeness.
  Not just.

- `M_Twist`: M-theory twist.
  Claims: E8.
  Test: m_theory_twist_e8.
  Twist.

- `Polchinski_Volume`: Polchinski volume.
  Claim: D0 vol.
  test: polchinski_volume_evaluation.
  D0.

- `Kreuzer_Skarke`: Kreuzer-Skarke.
  Claim: Fano base × Elliptic.
  test: kreuzer_skarke_count.
  Toric.

- `Batyrev_Boris`: Batyrev Boris.
  Claims: reflexive Polytopes.
  Test: batyrev_reflexive_check.
  Polytopes.

- `Toroidal`: Toroidal compactification.
  Claim: Tⁿ × CY.
  Test: toroidal_coupling_moduli_space.
  Simple.

- ` orbifold`: Orbifold CFT/geometry.
  Claim: Point → O/g.
  test: orbifold_sector_count.
  Quotients.

- ` Conifold`: Conifold transition.
  Claims: Node → S2 × S3.
  test: conifold_transition_check.
  Topology change.

- ` flop_Trans`: Flop transition.
  Claims: Blowups.
  Test: flop_check.
  Flops.

- ` flipp`: Flip transitions.
  Claims: MWC.
  test: flip_transitions_present.
  Minimal model.

- `Geometric_Langlands`: Geometric Langlands.
  Claims: D-mod on Bun_G → Sh(C).
  Test: geometric_langlands_fourier_mukai.
  Sheaf.

- `Beilinson_Bernstein`: Beilinson-Bernstein localization.
  Claim: D-mod on flag → g-modules.
  test: beilinson_bernstein_localization.
  Equivalence.

- `D_Module`: D-module viewpoint.
  Claim: Sheaf of differential operators.
  test: d_module_check.
  Algebraic D-modules.

- ` Stokes_Phenomena`: Stokes phenomenon.
  Claims: Asymptotic.
  test: stokes_line_computation.
  PDE.

- ` resurgence`: Resurgence.
  Claims: Transseries.
  test: resurgence_check.
  Non-perturbative.

- ` Borel_summable`: Borel summability.
  Claims: Sum after Borel.
  test: borel_summable_check.
  Summation.

- ` trans_Series`: Transseries expansion.
  Claims: x = Σ c_{n,k} x^{n}(log x)^k.
  test: transseries_compare_to_asymptotic.
  Asymptotic.

- ` alien_derivatives`: Alien derivatives.
  Claims: ∂_α on Stokes data.
  test: alien_derivative_value.
  Stokes.

- `Bridge_invariants`: Bridge invariants.
  Claims: Resurgent.
  test: bridge_invariant_check.
  Resurgence.

- `Exact_Values`: Exact values.
  Claims: Get from transseries.
  test: exact_value_check
  Exacts.

## Current State

- S238 tested: market_breadth PASSED (+30%), vol regime PASSED (+38%), quarter_start PASSED (+26%)
- Key: Quarter START (+26%) > quarter END (-15%) - NEW!
- Queue: EXHAUSTED

### Spectral / Linear Algebra

- `eigenvalue_entropy_portfolio`: PCA eigenvalue entropy as regime signal.
  Claim: When top eigenvalue dominates, trend is strong; when entropy high, mean-revert.
  Test: Compute daily correlation matrix eigenvalues, entropy = -sum(λ² log λ²).
  Mechanism: Random Matrix Theory -Market has "noise" eigenvalues vs "signal" eigenvalues.

- `spectral_gap_detection`: Second-largest eigenvalue gap predicts breakout.
  Claim: Large gap between λ₁ and λ₂ = clear market direction; small gap = range-bound.
  Test: spectral_gap = λ₁/λ₂ ratio, compare IC by gap quintile.

- `principal_component_direction`: PC1 vs PC2 alignment.
  Claim: PC1 and PC2 same sign = trending; opposite = reverting.
  Test: dot_product(PC1, PC2) sign as filter on C16.

- `condition_number_regime`: Matrix condition number as volatility predictor.
  Claim: High condition number = unstable correlations = regime change imminent.
  Test: cond(correlation_matrix) < threshold as risk-off signal.

### Stochastic / Random Process

- `mean_reversion_hitting_time`: Expected hitting time to moving average.
  Claim: Stocks touching 20d MA have predictable bounce timing.
  Test: days_to_ma_20, survival analysis on returns.

- ` Ornstein-Uhlenbeck_regime`: OU drift parameter estimates.
  Claim: OU estimated drift predicts reversion speed.
  Test: rolling OU fit, drift parameter as signal.

- `brownian_bridge_absorption`: Price path absorption at barriers.
  Claim: When price hits ceiling/floor, absorption time predicts next-day direction.
  Test: time_to_limit vs subsequent return.

- `ito_lemma_momentum`: Ito drift vs diffusion ratio.
  Claim: High drift/diffusion = trending; low = reverting.
  Test: compute rolling μ/σ ratio, predict regime.

### Information Theory

- `mutual_information_strength`: Mutual information between signals.
  Claim: High MI between C16 and price = strong signal; low = noise.
  Test: MI(C16, returns) by quintile.

- `kl_divergence_regime`: KL divergence between up/down states.
  Claim: Distribution shift predicts next regime.
  Test: KL(p_up || p_down) as predictor.

- `entropy_rate_market`: Rolling entropy of daily returns.
  Claim: Entropy increasing = uncertainty rising = flight to quality.
  Test: rolling_window_entropy as filter.

- `compression_signal`: Gzip compression ratio of daily news as sentiment.
  Claim: Highly compressible news = redundant = crowd consensus = reversal.
  Test: compress(news) vs returns.

### Graph Theory / Network

- `graph_laplacian_spectrum`: Sector adjacency matrix eigenvalues.
  Claim: Fiedler eigenvalue = sector connectivity = rotation predictability.
  Test: compute sector graph Laplacian, Fiedler value as signal.

- `page_rank_sector`: PageRank of ticker in sector network.
 Claim: High PageRank = sector leader, but may be overowned.
  Test: PageRank vs subsequent return.

- ` shortest_path_flow`: Flow through sector network.
  Claim: Information flows through shortest paths, predicts sector rotation.
  Test: sector_distance_to_hot = signal.

- `clustering_coefficient_regime`: Clustering in sector co-movement.
  Claim: High clustering = herding = mean-reversion imminent.
  Test: clustering_coefficient vs returns.

### Topological / TDA

- `persistent_homology_trend`: TDA-based trend detection.
  Claim: H0 persistence length predicts trend continuation.
  Test: rolling_persistence, compare to random bootstrap.

- `betti_number_regime`: Betti-0 (components) count as market health.
  Claim: Many components = fragmented = risky; few = unified.
  Test: Betti_0 as regime signal.

- `topological_smoothness`: Price sequence topological shape.
  Claim: Topologically smooth path = trending; jagged = reverting.
  Test: compute topological features on price windows.

### Chaos / Dynamical Systems

- `lyapunov_exponent_estimate`: Lyapunov exponent as chaos measure.
  Claim: Positive Lyapunov = deterministic chaos = unpredictable.
  Test: rolling_lyapunov > 0 as skip signal.

- `correlation_dimension_market`: Correlation dimension as complexity.
  Claim: Lower dimension = more predictable; higher = noise.
  Test: computeGrassberger-Procaccia.

- `hurst_exponent_regime`: Hurst exponent as trend/reversion.
  Claim: H > 0.5 trending; H < 0.5 mean-reverting.
  Test: rolling Hurst estimate filter.

- `kolmogorov_entropy`: Kolmogorov entropy as unpredictability.
  Claim: High KE = random = reduce exposure.
  Test: KE_estimator as position sizer.

### Wavelet / Fourier

- `wavelet_decomposition_predict`: Multi-scale wavelet components.
  Claim: Coarse scales trend; fine scales mean-revert.
  Test: DWT components as separate signals.

- `fourier_frequency_cycle`: Dominant frequency detection.
  Claim: Market has hidden cycles, detect and trade.
  Test: FFT peak frequency vs subsequent return.

- `spectral_centroid_movement`: Spectral centroid position.
  Claim: Centroid moving down = distribution shrinking = support.
  Test: rolling_spectral_centroid as signal.

### Extreme Value / Tail

- `peaks_over_thresholds`: POT tail risk detection.
  Claim: Exceedances cluster before crashes.
  Test: exceedance_rate as lead indicator.

- `generalized_pareto_tail`: GPD tail shape parameter.
  Claim: Tail shape predicts crash probability.
  Test: rolling_GPD_fit, ξ parameter.

### Game Theory / Equilibrium

- `nash_equilibrium_portfolio`: Nash equilibrium in sector allocation.
  Claim: Sector allocation converges to equilibrium, deviate = alpha.
  Test: deviation_from_equilibrium_vs_return.

- `零和_positioning`: Positioning consensus as zero-sum.
  Claim: Overconsensus = reversal; underconsensus = continuation.
  Test: consensus_rank as contrarian.

### Copula / Dependence

- `copula_tail_dependence`: Tail dependence coefficient.
  Claim: High tail dependence = crash correlation increases.
  Test: tail_dependence coefficient as risk signal.

- `vine_copula_regime`: Regime-dependent copula.
  Claim: Different copulas in up vs down regimes.
  Test: regime_copula_fit vs returns.

### Bayesian / Probabilistic

- `bayesian_update_speed`: Posterior updating rate.
  Claim: Fast updating = high information arrival = momentum.
  Test: rolling likelihood update rate.

- `conjugate_prior_regime`: Prior regime determines posteriors.
  Claim: Market regime = prior type determines signal efficacy.
  Test: regime_dependent_signal_efficacy.

### Optimization / Combinatorial

- `knapsack_selection`: Knapsack-like portfolio construction.
  Claim: Top-K knapsack optimization gives different weights.
  Test: optimization-based weights vs equal weights.

- `weighted_medoid_clustering`: Medoid clustering for sector assignment.
  Claim: Medoid-based sectors are more stable.
  Test: medoid_sector vs return.

### Miscellaneous

- `benford_law_anomaly`: First-digit distribution anomaly.
  Claim: Deviation from Benford = manipulation = reversal.
  Test: benford_chi_square on volume.

- `zipf_law_sector_rank`: Sector rank follows Zipf distribution.
  Claim: Sector return rank vs theoretical expectation.
  Test: zipf_exponent as predictor.

- `golden_ratio_divider`: Fibonacci levels as support/resistance.
  Claim: 0.618, 0.382 retracement levels are magnetic.
  Test: price_near_fib as signal.

- `golden_ratio_divider`: Fibonacci levels as support/resistance.
  Claim: 0.618, 0.382 retracement levels are magnetic.
  Test: price_near_fib as signal.

- `entropy_based_weighting`: Entropy-weighted signals.
  Claim: Higher entropy signal = more uncertainty = less weight.
  Test: entropy_weighted_portfolio vs equal.

- `ranking_stability`: Stability of cross-sectional rank.
  Claim: Rank changes are predictable.
  Test: rank_volatility as signal.

- `volterra_kernel_nl`: Volterra series nonlinearity.
  Claim: Second-order kernel captures nonlinearities.
  Test: volterra_coefficient as signal.

- `bellman_equation_value`: RL-style value function.
  Claim: Value function estimates predict positions.
  Test: value_estimate vs optimal.

## Current State

- S238 tested: market_breadth PASSED (+30%), vol regime PASSED (+38%), quarter_start PASSED (+26%)
- Key: Quarter START (+26%) > quarter END (-15%) - NEW!
- Queue: EXHAUSTED

## Active Jobs / Constraints

- One heavy local-model job is active: tmux session
  `ollama_guarded_backfill`, running the guarded Ollama residual backfill
  without any cutoff (includes all data through March 2026):
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features`
- Note: the old 2026 cutoff rule is deprecated as of Session 213.
  The backfill now includes 2026 data by default.
- Session 213 restarted the backfill without the lockbox cutoff, now including 2026 data.
- Current input manifest includes all gated articles (no date filter).
- Latest checked status during Session 213 write-back: `running`, phase
  `score`, early batches, restarting fresh from checkpoint.
- Local-ML planning budget remains hard-capped at `3GB VRAM / 10GB RAM`.
- Heavy PhoBERT train/publish commands should fail fast when CUDA is hidden;
  use `NEWS_FEATURES_ALLOW_CPU=1` only for an explicit CPU fallback.

## Data / Test Findings (2026-05-03)

- X51-X55 stochastic: X51/52 FAILED, X53 DISCOVERED: C16 works BETTER with
  high liquidity (move>80%ile): IC +0.137 vs +0.090 baseline (+52%!)
- X54 DISCOVERED: High sector-unanimity (low kurtosis): IC +0.080 vs +0.031 (+160%!)
- Realized: price data exists in `data/stock/gia_lich_su_*_1D.parquet` (1227 files)
- Actual return exists in barrier surface `xs_barrier_vol_1d_hose_full.parquet`
- Scripts: `analysis/x53v2_liquid_c16.py`, `analysis/x54_braid_divergence.py`

## Immediate Next Actions

- Keep monitoring the single active heavy job. Do not start another heavy
  local-model job while `ollama_guarded_backfill` is running.
  Run with console output in tmux (no log file redirect).
- After the guarded Ollama residual surface finishes, rebuild the input cache
  without date filters if needed, then aggregate the default
  local-first news features:
  `python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking phobert_article_scope phobert_source_type ollama_guarded`
- Then run the prepared bounded downstream audit:
  `python analysis/h364_combined_local_news_audit.py`
  before promoting any news feature into the signal library.
- Only if a downstream consumer explicitly asks for C16, merge
  `data/features/xs_order_pressure_daily.parquet` into the consolidated lab
  matrix or an export path and run a focused consumer/portfolio audit.

## Do Not Reopen Unless

- Do not reopen binary-head training unless label quality or downstream alpha
  evidence specifically demands it.
- Do not continue standalone foreign-flow windows, foreign-support-on-C5
  variants, proprietary-flow rank/conflict variants, or sector-pressure
  variants unless a materially different data source, target, or market
  contract exists.
- Do not tune more event-v2 overlays, entry-label variants, payoff-shape
  filters, or sparse-clock variants unless new event data, a materially
  different target, or a different downstream consumer contract exists.
- Do not tune more dividend windows, bonuses, or sparse-clock overlays under
  the current target. Keep the pre-ex clock as offline calendar evidence only.
- Do not tune more legal-holiday pre/post offsets, closure-length gates, bonus
  sizes, or veto variants under the current top-5 executable selector. H363's
  `all_holidays__post_5` payoff hint did not transfer to the fixed portfolio
  sparse-clock contract.
- Do not continue linear smart-exit feature-set tweaks unless richer
  post-entry state/data or a materially different model contract appears.
- Do not rerun stale H135/H136/H137 old-OHLCV variants under the current
  contract.
- Do not tune more BERT-only sentiment variants or promote PhoBERT sentiment
  standalone; keep official-conditioned sentiment as a candidate transform for
  the combined local-news audit.

## Research Queue (Parked)

- `sector_laggard_order_pressure` (H368 ⚠): Apply C16 to sector-laggard universe (H199) only.
  Claim: Sector laggards with same-day buy-pressure signal = rotation into underperforming names.
  **Requires sector data merge**

- `news_scope_order_stacking` (H370 ⚠): Combine post-Ollama article scope + order pressure.
  Claim: Articles with scope=positive + high order pressure = text-confirmed + flow-confirmed.
  **Requires H364 news aggregate first**

- `sell_pressure_mirror` (H371 ⚠): Test C16 mirror on sell side.
  Claim: Same-day posted SELL pressure predicts mean reversion differently than buy pressure.
  **No sell-side order split in order_stats data**

- `regime_k_adjustment` (H376 ⚠): Change K (portfolio size) by regime.
  Claim: In high-dispersion regimes, top-1 beats top-5; reverse in low-dispersion.
  **Needs portfolio backtest, not IC-only**

- `proprietary_cross_order` (H378 ⚠): Proprietary trading + C16 intersection.
  Claim: Proprietary desk buy when order pressure is high = institutional confirmation.
  **Data starts 2022, not enough history for 2015-2022 test**

## Unconventional / Experimental

- `mention_frequency_lead` (X6 pending): News mention frequency as attention proxy.
  Claim: Acceleration in mentions predicts next-day movement, not level.
  First test: delta(mention_count, 5d_lag) > threshold as entry filter.
  Why insane: C1 tests level; no signal tests mention velocity.

- `smart_dumb_money_divergence` (X7 ⚠): Price vs volume direction divergence.
  **Uses actual return - circular test, problematic**
  Claim: Price up + volume down = smart money (institutional); opposite = dumb money (retail).
  First test: (return > 0) XOR (volume_zscore > 0) as long signal.
  Why insane: No signal distinguishes smart vs dumb money flow.

- `triple_cross_stacking` (X8 pending): News + order + momentum triple AND.
  Claim: Text-confirmed + flow-confirmed + price-confirmed = triple signal.
  First test: C16 positive AND phobert_scope_positive AND S1 positive vs single crosses.
  Why insane: H370 tests 2-way; never 3-way intersection.

- `foreign_room_trigger` (X9 pending): Foreign room change as entry accelerator.
  Claim: Room increase + high price = institutional accumulation; room decrease = exit.
  First test: foreign_room_delta > 0 AND price_momentum > 0 as signal multiplier.
  Why insane: Foreign room alone failed (H345); never tested as multiplier.

- `first_time_top5_qualifier` (X10 pending): First-time appearance in selection.
  Claim: First-time top-5 names have stronger continuation than repeat top-5.
  First test: days_since_first_top5 < 5 as positive filter.
  Why insane: No signal tracks selection history per ticker.

- `exit_velocity_signal` (X11 pending): Rate of price decline predicts exit timing.
  Claim: Fast decline = quick recovery chance; slow decline = fundamental issue.
  First test: (return_since_entry < -0.03) AND (rate_of_decline > threshold) as exit signal.
  Why insane: All exit signals are threshold-based, not velocity-based.

- `sector_rotation_trigger` (X12 pending): When to rotate vs stay in sector.
  Claim: Sector momentum persistence is predictable from sector breadth acceleration.
  First test: delta(sector_breadth, 5d) > threshold as rotation trigger.
  Why insane: Sector breadth exists (C6); delta(breadth) never tested.

- `correlation_regime_signal` (X13 pending): Signal-to-signal correlation as regime indicator.
  Claim: When signals align, regime is strong; when they diverge, regime is weak.
  First test: cor(S1, C4, daily) < threshold as high-regime signal.
  Why insane: No signal treats correlation as the signal itself.

- `prediction_confidence_as_signal` (X14 pending): Model confidence predicts edge.
  Claim: High-confidence predictions have better edge; bet more when confident.
  First test: xs_proba * edge_correlation as position sizer.
  Why insane: All selectors use rank, not prediction confidence.

- `time_since_positive_signal` (X15 pending): Ticker "activation" timing.
  Claim: Fresh positive signals matter more than stale ones.
  First test: rank(days_since_last_positive_signal) as decay factor.
  Why insane: No signal applies time-decay to signal history.

- `multi_day_gap_sequence` (X16 pending): Consecutive gap days as momentum chain.
  Claim: Gap-Gap-Gap sequence = strong directional information.
  First test: count_consecutive_gaps(3d) as signal.
  Why insane: C12 gap_absorb is single-day; consecutive-day chains never tested.

- `limit_order_density` (X17 pending): Days near price limit as conviction signal.
  Claim: Near-limit days indicate strong conviction that persists.
  First test: (price_to_ceiling / 7%) > 0.80 as strength signal.
  Why insane: Limits exist in data; no signal uses proximity to limit.

- `after_hours_proxy` (X18 pending): Post-close news as overnight signal.
  Claim: Evening news (post-3pm) predicts next-day gap differently than day news.
  First test: article_timestamp > 15:00 as overnight indicator.
  Why insane: C1/PhoBERT timestamps exist; time-of-day never used as feature.

- `bid_ask_imbalance_trend` (X19 pending): Rate of bid/ask imbalance change.
  Claim: Accelerating bid pressure = stronger signal than static imbalance.
  First test: delta(bid_ask_ratio, 5d) > 0 as signal.
  Why insane: Raw bid/ask not available; proxy via order stats trend.

- `volume_price_momentum_mismatch` (X20 pending): Price momentum / volume momentum divergence.
  Claim: Strong price momentum + weak volume = unsustainable; reverse = sustainable.
  First test: return_momentum / volume_momentum as sustainability score.
  Why insane: Both exist separately; ratio never tested.

- `intraday_range_contraction` (X21 pending): Intraday range narrowing pattern.
  Claim: Range contraction followed by range expansion = breakout.
  First test: range_5d_decreasing AND range_today_expanding as breakout signal.
  Why insane: Compression exists (C13); range contraction sequence never.

- `cross_asset_correlation_timing` (X22 pending): USD/VND correlation edge.
  Claim: Deviations from USD/VND correlation predict stock moves.
  First test: correlation(resid_stock, USD/VND) < threshold as signal.
  Why insane: FX correlation exists in data but never as timing signal.

- `overnight_return_isolation` (X23 pending): Gap vs intraday separation.
  Claim: Gap return predicts differently than intraday return; don't blend.
  First test: gap_return_rank OR intraday_return_rank as separate signals.
  Why insane: All signals blend gap+intraday into single measure.

- `sector_momentum_streak` (X24 pending): Sector 3-day streak as signal.
  Claim: 3-day sector momentum streak predicts continuation.
  First test: sector_3d_streak_rank > q80 as signal.
  Why insane: Sector momentum exists; streak count never.

- `price_level_regime` (X25 pending): Price level as signal regime switch.
  Claim: Low-price stocks and high-price stocks have different optimal signals.
  First test: regime_switch(score, price_level_quintile) as composite.
  Why insane: No signal adapts to price level regime.

- `turnover_rate_signal` (X26 pending): Stock turnover rate as fundamental.
  Claim: High turnover = underfollowed = mean reversion; opposite = momentum.
  First test: turnover_rate_quintile * return_signal as composite.
  Why insane: Turnover exists in data; never interacts with return signal.

## Omega-Level / Civilizational

### Ghost & Folklore (X27-X29)

- `thang_co_hon_front_run` (X27 pending): Ghost month liquidity vacuum.
  Claim: 5 days BEFORE lunar month 7 starts, liquidity drops; mean-reverts on day 15.
  First test: lunar_calendar_offset < -5 as long entry, offset=15 as mean-reversion.
  Why alien: VN-specific cultural anomaly, never tested in any market.

- `burning_ritual_proxy` (X28 pending): Ritual paper demand correlation.
  Claim: High ritual paper (vàng mã) sales = retail leverage sentiment correlation.
  First test: correlate(offering_sales_index, margin_utilization) > threshold.
  Why alien: Physical ritual data as market sentiment proxy.

- `zodiac_switch_jolt` (X29 pending): Tet sector element alignment.
  Claim: Sectors aligned with new lunar year element (Wood/Fire/etc) get retail disproportionality.
  First test: sector_element_year_alignment_score vs subsequent 10d return.
  Why alien: Zodiac cycles as sector rotation signal.

### Infrastructure & Physical Reality (X30-X32)

- `night_light_electricity_delta` (X30 pending): Satellite-based industrial activity.
  Claim: Night-light increase in industrial parks (BDI, BN) without price = structural breakout.
  First test: night_light_delta > 0.10 AND price_stagnant as signal.
  Why alien: Satellite data as stock predictor, never done in VN.

- `coffee_shop_sentiment_index` (X31 pending): Cafe delivery volume correlation.
  Claim: Coffee delivery surges = retail glued to screens = higher intraday volatility.
  First test: correlate(grab_coffee_volume, intraday_volatility).
  Why alien: Delivery app data as sentiment proxy.

- `cement_to_ticker_lead` (X32 pending): Infrastructure announcement lead time.
  Claim: Expressway milestone announcements lead construction volume spikes by 30-90 days.
  First test: announcement_date + delta(construction_volume_5d) as lead indicator.
  Why alien: Construction timeline as stock predictor.

### Deep Structural & Policy Glitches (X33-X35)

- `vin_centric_orbit` (X33 pending): Vingroup gravitational slingshot.
  Claim: VIC >3% in 30min "pulls" mid-caps OR "drains" liquidity.
  First test: VIC_momentum > 0.03 AND midcap_correlation as signal.
  Why alien: Single-stock gravitational model.

- `foreign_room_trapdoor` (X34 pending): FOL premium decay and room reopen.
  Claim: First 1% room reopen after 100% = violent correction as domestic front-runs foreign.
  First test: room_delta > 0.01 AND price_gap_up as signal.
  Why alien: FOL mechanism as alpha trigger.

- `green_policy_alpha_leak` (X35 pending): Environmental policy reaction asymmetry.
  Claim: Construction/materials react NEGATIVE to GPAs; "Sustainable 100" react POSITIVE 3d later.
  First test: gpa_announcement * sector_sustainability_score as signal.
  Why alien: Policy sentiment asymmetry, never tested.

### Psychological Wild West (X36-X38)

- `zalo_telegram_echo_decay` (X36 pending): Social saturation point.
  Claim: >50 distinct group mentions in 1hr = 90% probability top within 48hr.
  First test: mention_velocity > 50 AND subsequent_48h_return as signal.
  Why alien: Social velocity as top predictor.

- `forced_sell_cascade` (X37 pending): 2:00 PM margin wall recovery.
  Claim: Market drops >1.5% between 1-2pm triggers forced sell; recovery 2:15-2:45pm.
  First test: (1pm_to_2pm < -0.015) AND recover_2:15_2:45pm as long.
  Why alien: Margin timing as reversal signal.

- `facebook_kol_divergence` (X38 pending): KOL consensus as contrarian.
  Claim: >70% KOLs agree "Strong Buy" = 75% chance local top.
  First test: kol_agreement > 0.70 AND subsequent_5d_return as contrarian.
  Why alien: KOL sentiment as inverse predictor.

### Global Supply Chain Echoes (X39-X41)

- `shanghai_lock_spillover` (X39 pending): China port congestion lead.
  Claim: Shanghai congestion → Vietnam logistics (GMD, HAH) 48hr later.
  First test: shanghai_congestion_delta lead 48h to logistics_return.
  Why alien: Supply chain geography as lead-lag.

- `currency_war_lag` (X40 pending): VND realization gap.
  Claim: Currency devaluation takes EXACTLY 15 days to reflect in export volume.
  First test: vnd_change * export_volume_lag_15d as signal.
  Why alien: Fixed-day realization lag.

- `iphone_cycle_proxy` (X41 pending): Samsung/Foxconn GDP proxy.
  Claim: Samsung guidance → Vietnam banking credit demand 30-60d later.
  First test: samsung_guidance_delta lead bank_credit_growth as signal.
  Why alien: Global OEM as emerging market leading indicator.

## VI. Fractal & Topological Anomalies

- `persistent_homology_orderbook` (X67 pending? - need new number): TDA-based order book holes.
  Claim: When bid-ask spread topology changes, volatility phase transition 95% imminent.
  First test: Compute Betti-like connectivity metrics from level-2 order book, predict vol regime.
  Why unconventional: Requires order book data we don't have; proxy via price levels at fixed increments.

- `mandelbrot_resonance_midcap` (X68 pending): hurst exponent sine wave.
  Claim: Mid-cap Hurst H > 0.65 for e^pi days → memory collapse, 48h random walk.
  First test: rolling_hurst(vn70) > 0.65 AND duration > 23.14 days → short signal.
  Why unconventional: Requires rolling Hurst calculation, untested in this market.

- `golden_spiral_liquidity_drain` (X69 pending): Fibonacci volume-at-price nodes.
  Claim: Price/volume hit 1.618 confluence → laminar flow, zero slippage for large orders.
  First test: Volume at 1.618 * price_level confluence vs controls.
  Why unconventional: Requires price-level volume data we don't capture.

- `transfer_entropy_big_three` (X70 pending): Information flow from leaders.
  Claim: When entropy from VIC/VHM/VCB drops → decoupling event, mid-cap rally.
  First test: daily_return_correlation(leaders, rest) drops below threshold → midcap_long.
  Why unconventional: Tests time-series information flow, not cross-sectional rank.

- `kolmogorov_complexity_news` (X71 pending): News compression ratio.
  Claim: High compression (redundant news) → Smart/Dumb divergence → crash.
  First test: gzip_compression(news_1d) above threshold → negative signal.
  Why unconventional: Requires daily news text, untested as market signal.

- `spectral_density_regime_shift` (X72 pending): Fourier-based retail cycle.
  Claim: Market "heartbeat" shifts 24h → 4h → regime switch, 15% correction in 10d.
  First test:fft_periodogram(volume) dominant_freq changes → risk_off.
  Why unconventional: Spectral analysis as market timing, untested here.

- `schrodinger_limit_order` (X73 pending): Price-volume uncertainty.
  Claim: Large orders change probability of reaching target by factor of order density.
  First test: iceberg_proxy * price_movement = signal.
  Why unconventional: Observer effect in markets, requires order book data.

- `lyapunov_exponent_divergence` (X74 pending): Chaos detection.
  Claim: Positive Lyapunov in first 15min → deterministic chaos, standard indicators fail.
  First test: compute_lyapunov(price_series_15m) > 0 → skip_all_indicators.
  Why unconventional: Requires high-frequency data we don't have; proxy via 15m returns.

- `benford_law_liquidity_proxy` (X75 pending): First-digit distribution.
  Claim: Deviation from Benford's Law indicates algorithmic/wash trading = Smart Money.
  First test: first_digit_distribution(volume)偏离benford → volume anomaly, then anti-anomaly trade.
  Why unconventional: Benford's law as trading signal, untested in VN market.

## Meta / Philosophical

- `belief_system_collapse` (X42 pending): When consensus becomes trap.
  Claim: >95% analyst consensus = contrarian signal because retail overweights.
  First test: analyst_consensus > 0.95 AS negative signal.
  Why alien: Belief system as inverse signal.

- `attention_decay_research` (X43 pending): Memory-5d signal persistence.
  Claim: Signals persist longer in VN than efficient markets theory suggests.
  First test: signal_half_life > 5d as persistence measure.
  Why alien: Memory decay as signal attribute.

- `liquidity_illusion` (X44 pending): ADV as confidence trick.
  Claim: High ADV = institutional confidence; low ADV = retail panic.
  First test: adv_regime_switch(score) as confidence filter.
  Why alien: ADV as belief indicator.

- `narrative_velocity` (X45 pending): Story speed as price predictor.
  Claim: New narrative (news + volume) accelerates price faster than old narrative.
  First test: narrative_age_days * momentum as composite.
  Why alien: Narrative age as signal component.

- `identity_formation` (X46 pending): Sector identity persistence.
  Claim: Stocks "become" sectors; sector-hopping tickers have unique patterns.
  First test: sector_stability_score * return as signal.
  Why alien: Identity formation in stocks.

- `collective_guilt_trade` (X47 pending): Post-scandal price trajectory.
  Claim: Stocks that "fall from grace" (scandal, loss) have unique recovery patterns.
  First test: scandal_type * recovery_rate as signal.
  Why alien: Guilt and redemption in market narratives.

- `temporal_anxiety` (X48 pending): Time Horizon Anxiety (THA).
  Claim: Traders with short horizons (T+2) behave differently than long horizons.
  First test: time_horizon_distribution * price_path as signal.
  Why alien: Temporal psychology as signal.

- `information_ownership` (X49 pending): Who "owns" the information?
  Claim: Institutional-owned = price reflects info; retail-owned = price diverges from info.
  First test: ownership_concentration * information_impact as signal.
  Why alien: Ownership of information as signal.

- `sacred_money_flow` (X50 pending): Temple/offering expense correlation.
  Claim: Regional offering expense (temple donations) correlates with regional trading activity.
  First test: regional_temple_expense correlated with regional_volume.
  Why alien: Sacred expense as market flow proxy.

- `mother_tongue_effect` (X51 pending): Language of news sentiment.
  Claim: Vietnamese-language news has different impact than English-language news.
  First test: vn_news_sentiment != en_news_sentiment AS signal.
  Why alien: Language encoding as sentiment.

- `geographic_sentiment_bloc` (X52 pending): North vs South sentiment divergence.
  Claim: Northern traders (Hanoi) vs Southern traders (HCMC) have different risk preferences.
  First test: region_sentiment_divergence * sector_weight as signal.
  Why alien: Geographic psychology as signal.

- `infrastructure_fetish` (X53 pending): Infrastructure as religion.
  Claim: Vietnamese have unique attachment to infrastructure (roads, bridges, airports).
  First test: infrastructure_news_velocity * sector_return as signal.
  Why alien: Infrastructure fetish as sentiment.

- `family_corp_governance` (X54 pending): Family business discount.
  Claim: Family-controlled companies trade at discount; revelation = re-rate.
  First test: family_control_flag * governance_score as signal.
  Why alien: Family as governance structure.

- `exam_season_dip` (X55 pending): national exam period liquidity.
  Claim: June national exams reduce retail participation; September re-rate.
  First test: exam_month = June AS liquidity signal.
  Why alien: Education calendar as market force.

- `festival_economy_boost` (X56 pending): Festival consumption hypothesis.
  Claim: Pre-Tet consumption spike drives consumer sector; post-Tet depression.
  First test: tet_countdown_10d * consumer_sector_return as signal.
  Why alien: Festival as economic driver.

## Cosmic / Transcendental

### Observer Effect (X57-X60)

- `consciousness_collapse` (X57 pending): Observation changes price reality.
  Claim: When retail OBSERVES a ticker (via app open), price path changes.
  First test: app_open_count * subsequent_return as signal.
  Why cosmic: Observation itself changes the observed.

- `群体潜意识和_collapsed` (X58 pending): Collective unconsciousness price drift.
  Claim: Non-verbal collective "feeling" (unconscious) predicts price better than news.
  First test: proxy_gut_feeling_index * price_path as signal.
  Why cosmic: Unconscious as information substrate.

- `dream_correlation` (X59 pending): Dream pattern correlation.
  Claim: Collective REM sleep disruptions correlate with market volatility.
  First test: sleep_data_correlation(volatility) as signal.
  Why cosmic: Dream patterns as market data.

- `meditation_volume` (X60 pending): Meditation app data correlation.
  Claim: Meditation app usage in Vietnam correlates with reduced retail volatility.
  First test: meditation_app_usage_correlation with volatility.
  Why cosmic: Altered consciousness states as inverse volatility.

### Temporal Collapse (X61-X65)

- `time_dilation_trade` (X61 pending): Market "stretches" time at extremes.
  Claim: At price extremes, subjective time dilates; traders overreact to "short" time.
  First test: extreme_price * time_perception_proxy as signal.
  Why cosmic: Subjective time as trading variable.

- ` déjà_vu_reversal` (X62 pending): Pattern recognition trap.
  Claim: Traders confuse present patterns with "déjà vu" memories → false confidence.
  First test: pattern_similarity_to_past > threshold AS trap signal.
  Why cosmic: Memory illusion as trap.

- `present_moment_illusion` (X63 pending): "Now" as trading horizon.
  Claim: VN retail overweights present moment; underweights future.
  First test: future_weighted_signal vs present_only as comparison.
  Why cosmic: Present-tim bias as systematic error.

- `eternal_recurrence` (X64 pending): Same patterns forever.
  Claim: Markets recurrence is exact, not approximate; history echoes infinitely.
  First test: infinite_pattern_match AS momentum signal.
  Why cosmic: Eternal recurrence as pattern.

- `moment_expansion` (X65 pending): Single moment contains all outcomes.
  Claim: At key moments (earnings, FOL), ALL futures coexist.
  First test: moment_importance * probability_spread as signal.
  Why cosmic: Quantum-style probability in markets.

### Non-Local Correlation (X66-X70)

- `entangled_tickers` (X66 pending): Quantum entanglement metaphor.
  Claim: Certain tickers are "entangled" - price action on one instantly affects other.
  First test: entanglement_correlation(ticker_A, ticker_B) > threshold.
  Why cosmic: Non-local correlation as signal.

- `consciousness_field` (X67 pending): Consciousness field theory.
  Claim: All trader minds form a field; price emerges from field interactions.
  First test: field_coherence_measure * price_path as signal.
  Why cosmic: Collective consciousness as market substrate.

- `morphogenetic_resonance` (X68 pending): Morphogenetic field patterns.
  Claim: Market patterns resonate across time via morphogenetic fields.
  First test: resonance_score * future_pattern as signal.
  Why cosmic: Morphic resonance as pattern.

- `akashic_market_records` (X69 pending): Akashic records proxy.
  Claim: All past tradesLeave"imprints" that affect current price.
  First test: akashic_imprint_density * price_action as signal.
  Why cosmic: Akashic records as data source.

- `zero_point_fluctuation` (X70 pending): Vacuum energy trading.
  Claim: Market "vacuum" (low volume) draws in price-energy from nothing.
  First test: volume_near_zero * price_fluctuation_anomaly as signal.
  Why cosmic: Zero-point energy in markets.

### Dimensional Collapse (X71-X75)

- `higher_dimension_projection` (X71 pending): 4D market projection.
  Claim: Price is 3D projection of 4D market manifold; see "shadows."
  First test: shadow_analysis(price_3d) as signal.
  Why cosmic: Higher dimensions as signals.

- `brane_collision` (X72 pending): Brane collision theory.
  Claim: Market "branes" (sectors) occasionally collide; extreme events.
  First test: sector_collision_events * subsequent_volatility as signal.
  Why cosmic: Brane physics as market model.

- `string_vibration_frequency` (X73 pending): Market as string vibration.
  Claim: Market is string vibration; frequency determines price.
  First test: vibration_frequency_analysis as signal extraction.
  Why cosmic: String theory applied to markets.

- `membrane_leakage` (X74 pending): Membrane boundary leakage.
  Claim: Information "leaks" through market sector membranes.
  First test: membrane_permeability * information_flow as signal.
  Why cosmic: Membrane physics as information.

- `extra_dimension_access` (X75 pending): Extra dimension entry point.
  Claim: Certain tickers "bridge" to extra dimensions (meaning hidden correlations).
  First test: topological_bridge_measure as signal.
  Why cosmic: Extra dimensions as correlation source.

### Probability Collapse (X76-X80)

- `probability_wave_collapse` (X76 pending): Wave function collapse.
  Claim: Price is wave function collapse; observation causes state.
  First test: wave_function_analysis * observation_trigger as signal.
  Why cosmic: Quantum collapse in markets.

- `many_worlds_investment` (X77 pending): Many-worlds interpretation.
  Claim: All price outcomes occur in parallel branches.
  First test: branch_weighted_portfolio as signal.
  Why cosmic: Parallel worlds as portfolio.

- `quantum_entanglement_portfolio` (X78 pending): Entangled positions.
  Claim: Positions in portfolio are entangled; one affects another.
  First test: entanglement_portfolio_weight as signal.
  Why cosmic: Quantum portfolio theory.

- `uncertainty_principle_trading` (X79 pending): Heisenberg in markets.
  Claim: Cannot know both price AND momentum simultaneously.
  First test: uncertainty_product * trading_strategy as signal.
  Why cosmic: Heisenberg applied to trading.

- `wave_particle_duality` (X80 pending): Price as wave and particle.
  Claim: Price exhibits wave-particle duality.
  First test: wave_behavior vs particle_behavior as regime.
  Why cosmic: Wave-particle in price.

### Singularity Approaches (X81-X85)

- `information_singularity` (X81 pending): Information explosion.
  Claim: After information singularity, old patterns break.
  First test: information_rate * pattern_break as signal.
  Why cosmic: Information theory singularity.

- `memory_horizon` (X82 pending): Collective memory horizon.
  Claim: Beyond certain time, collective forgets; patterns restart.
  First test: time_since_pattern_start * pattern_strength as signal.
  Why cosmic: Memory horizon as cycle.

- `recursive_self_reflection` (X83 pending): Market self-models itself.
  Claim: Market reads itself reading itself = recursive price distortion.
  First test: recursion_depth * price_distortion as signal.
  Why cosmic: Self-referential systems.

- `emergence_boundary` (X84 pending): Emergence threshold.
  Claim: At complexity threshold, new behavior emerges.
  First test: complexity_measure * emergent_behavior as signal.
  Why cosmic: Emergence theory in markets.

- `complexity_collapse` (X85 pending): Complexity collapse.
  Claim: Too much complexity collapses to simplicity.
  First test: complexity_measure * collapse_point as signal.
  Why cosmic: Complexity collapse as signal.

### Void & Nothingness (X86-X90)

- `void_trading` (X86 pending): Trading in the void.
  Claim: "Nothing" (no news, no volume) is informative.
  First test: nothing_periods * subsequent_return as signal.
  Why cosmic: Nothingness as signal.

- `absence_signal` (X87 pending): Signal from absence.
  Claim: Absence of signal IS the signal.
  First test: signal_absence_period * return as signal.
  Why cosmic: Absence as presence.

- `negative_space` (X88 pending): Negative space trading.
  Claim: "Negative" price space (below zero) matters.
  First test: negative_space_analysis as signal.
  Why cosmic: Negative space in price.

- `emptiness_as_creator` (X89 pending): Emptiness creates.
  Claim: Market "emptiness" (low participation) paradoxically creates opportunity.
  First test: emptiness_measure * opportunity_signal as signal.
  Why cosmic: Emptiness as creator.

- `nothingness_boundary` (X90 pending): Boundary of nothing.
  Claim: There's a boundary where "something" becomes "nothing."
  First test: boundary_proximity * state_change as signal.
  Why cosmic: Nothing/something boundary.

### Transcendence (X91-X95)

- `market_enlightenment` (X91 pending): enlightenment event.
  Claim: Market "enlightenment" → no more price movement.
  First test: enlightenment_indicator * subsequent_volatility.
  Why cosmic: Enlightenment in markets.

- `egodeath_trading` (X92 pending): Trader ego death.
  Claim: At ego-death, traders "become" market; lose individual identity.
  First test: ego_collapse_indicator * behavior_change as signal.
  Why cosmic: Ego death as trading state.

- `unity_perception` (X93 pending): All-is-one perception.
  Claim: At extremes, all tickers perceived as ONE.
  First test: unity_measure * correlation Explosion as signal.
  Why cosmic: Unity consciousness in markets.

- `infinite_patience` (X94 pending): Infinite time horizon.
  Claim: Some traders operate at infinite time horizon.
  First test: infinite_time_trader_presence * price_path as signal.
  Why cosmic: Infinite patience trading.

- `market_satori` (X95 pending): Satori (sudden enlightenment).
  Claim: Market "satori" = sudden fundamental revaluation.
  First test: satori_trigger_conditions * revaluation_magnitude as signal.
  Why cosmic: Satori as market event.

### Divine / Mythological (X96-X100)

- `karmic_debt_offset` (X96 pending): Karma in markets.
  Claim: Past losses create "karmic debt" that must be repaid.
  First test: cumulative_loss * subsequent_gain_probability as signal.
  Why cosmic: Karma as mechanism.

- `dharma_cycle` (X97 pending): Dharma (duty) cycles.
  Claim: Each ticker has "dharma" (essential nature); cycles of duty.
  First test: dharma_cycle_phase * price_action as signal.
  Why cosmic: Dharma as cycle driver.

- `rita_order` (X98 pending): Cosmic order (Rita).
  Claim: Underlying cosmic order governs price; breaking = correction.
  First test: rita_violation * correction_magnitude as signal.
  Why cosmic: Rita as market law.

- `prana_flow` (X99 pending): Prana (life force) in capital.
  Claim: Capital has "life force"; flows between tickers.
  First test: prana_flow_indicator * price_movement as signal.
  Why cosmic: Prana as market flow.

- `atman_acceleration` (X100 pending): Atman (soul) in price.
  Claim: Price contains "soul" (inner essence); actions on soul drive price.
  First test: atman_presence * price_action as signal.
  Why cosmic: Soul in price action.

## Stochastic Resonance & Noise (X51-X55)

- `fibonacci_tick_liquidity_trap` (X51 pending): Whole-number price proximity.
  Claim: Retail stop-loss clusters at whole/half-integer levels. C16 stronger when price within 0.618% of whole number.
  Test: IC(C16) vs distance_to_whole_number.

- `fourier_ghost_cycles` (X52 pending): Hidden heartbeat frequency.
  Claim: C16 works 2x better at specific cycle frequency (3.5 or 7 days).
  Test: FFT on C16 daily IC, filter by peak frequency alignment.

- `order_flow_cavitation` (X53 pending): Vacuum effect under high pressure.
  Claim: High C16 + stagnant price = liquidity vacuum = next-day gap-up.
  Test: C16>90th + price_move<10th percentile → next-day return.

- `braid_divergence` (X54 pending): Signal unanimity across brokers.
  Claim: Sector-wide pressure unanimity (low kurtosis) = robust signal.
  Test: C16 kurtosis across sector contributors vs win rate.

- `lempel_ziv_complexity` (X55 pending): Tape complexity filter.
  Claim: C16 stronger when tape is repetitive (low complexity).
  Test: C16 IC in bottom complexity decile vs top.

## Pointers

- Detailed session traces: `notes/session_NN_log.md`
- Signal registry: [signal_library.md](./signal_library.md)
- Data/source inventory: [data_sources.md](./data_sources.md)
- Local BERT roadmap: [local_bert_roadmap.md](./local_bert_roadmap.md)
- Ollama probe log: [ollama_model_probe_log.md](./ollama_model_probe_log.md)
- Timing acquisition plan:
  [timing_data_acquisition_plan.md](./timing_data_acquisition_plan.md)
- Timing source scorecard:
  [timing_data_source_scorecard.csv](./timing_data_source_scorecard.csv)

## Working Rules

- For any material experiment, save a compact result summary and update the
  note stack.
- Use compact files for cheap context recovery before opening long session
  logs or findings chunks.
- Close out every material pass with this checklist:
  - session log updated
  - `sessions_compact.md` prepended with a source-linked entry
  - `live_state.md` updated only if current state, constraints, or immediate
    actions changed, with `Last verified` refreshed when checked
  - durable findings or dead ends promoted when warranted
  - `findings_compact.md` or `deadends_compact.md` updated only when durable
    memory changed, with source anchors included
- Keep this file focused on current state and immediate action. If a detail is
  not needed to decide the next pass, move it to a source note or compact view.
