## TL;DR

Global factor patterns such as momentum, value, size, and profitability remain prominent, and machine learning often enhances their cross-sectional extraction and profitability. Emerging- and Vietnam-specific studies report exploitable anomalies but recommend caution on generalization and transaction costs.

----

## Universal alpha signals

This section summarizes widely documented, broadly tested alpha signals and representative papers that analyze their construction and performance across large samples. The selected studies focus on signal definitions, implementation details, statistical evidence, cross-market tests, and whether machine learning augments signal discovery.

| Paper | Main signals identified | How signals are constructed | Profitability evidence | Market scope tested | ML or quantitative methods |
|---|---:|---|---|---|---|
| Azevedo 2022 | Many published anomalies aggregated from literature | 299 anomalies as predictors to forecast next‑month returns; baseline linear factors and nonlinear ML models compared | Nonlinear models produce OOS monthly returns ≈1.8–2.0% and risk‑adjusted alphas robust to transaction costs in many specifications [1] | Global cross‑section (broad sample) in baseline; emphasis on robustness post‑publication [1] | 30 ML approaches and ensembles across 250+ models including nonlinear learners [1] |
| Shu & Tiwari 2021 | Market value (size) emerges as dominant characteristic | Large characteristic set fed to Bayesian Additive Regression Trees to rank relevance | Sparse set including market value gives better statistical and economic performance than dense characteristic sets [2] | U.S. equities sample; framework intended for real‑time selection [2] | Bayesian Additive Regression Trees (BART) [2] |
| Han 2021 | Momentum heterogeneity and reclassification alpha | Cross‑sectional prediction to reclassify momentum groups; value‑weighted long‑short portfolios | Value‑weighted long‑short yields monthly alpha 2.4% (t=6.63) vs FF5+mom+rev controls [3] | U.S. market tested; results reported for US only [3] | Custom ML cross‑sectional prediction model (novel ML reclassification) [3] |
| Alberg & Lipton 2017 | Fundamental-based factors (book-to-market, EBIT/EV) improved via forecasting | Forecast future fundamentals (5‑year trailing inputs) with deep neural nets; compute factors using forecasted fundamentals | Backtester shows improvement in compounded returns (ML models outperform standard factor model in their simulation) [4] | U.S. stock universe in experiments [4] | Deep neural networks (MLP) to forecast fundamentals then factor construction [4] |
| Borisenko 2019 | Rich nonlinearity in price-based signals, momentum state dependence | Deep learning on many price‑based variables and time‑varying market states | Neural portfolios produce high and statistically significant returns with improved downside behavior vs benchmarks [5] | U.S. market; results emphasize state dependence in distressed periods [5] | Deep neural networks with automated hyperparameter tuning [5] |
| Blitz et al. 2023 | ML‑derived alphas depend on prediction horizon | ML trained on multiple horizons; longer horizons select slower, tradable signals | ML strategies on longer horizons yield significant positive net returns after costs; short‑horizon (1 month) net returns may be null since 2004 [6] | Broad historical samples (paper contrasts pre/post 2004 liquidity regime) [6] | Various ML models with portfolio construction rules tuned by horizon [6] |

- **Signals** Momentum, value, size, profitability and many bespoke characteristics are central inputs in large anomaly sets used by Azevedo and others to predict returns [1].  
- **Construction** Many papers build characteristic‑based predictors such as past returns (momentum), book‑to‑market (value), market capitalization (size), and profitability measures; some forecast fundamentals first and then compute factors [4] [1].  
- **Profitability** Nonlinear ensemble and deep models produce economically meaningful out‑of‑sample monthly alphas (often ~1–2% gross) and statistically significant t‑statistics in several studies after accounting for standard factor controls [1] [3] [6].  
- **Universality** Several authors test broad samples or stress cross‑validation, but many deep/ML studies report results mainly on U.S. or large‑market datasets so claims of universal performance are limited without further cross‑market tests [2] [5] [6].  
- **Vietnam applicability** These universal studies do not generally test Vietnam; direct applicability is therefore **insufficient evidence** unless a study explicitly samples Vietnam or similar emerging markets.  
- **ML methods** Common ML tools include BART, tree ensembles, deep neural networks (MLP, LSTM), custom cross‑sectional classifiers, and large ensembles combining hundreds of anomaly predictors [2] [4] [5] [1].

----

## Emerging market signals

This section covers papers that explicitly examine anomalies in emerging or international contexts and evidence for market‑specific effects. Open questions include whether classic factors translate and how institutional features change factor importance.

This group of studies shows that emerging markets often display exploitable anomalies, but factor prominence and implementation frictions differ from developed markets.

- **Opposites attract framework** The combined short‑term alpha momentum and long‑term reversal blended signal improves country and industry selection and yields economically significant monthly alphas in international equity markets [7].  
  - **Signals** Short‑term alpha momentum and long‑term alpha reversal blended into a single country/industry selection rule [7].  
  - **Construction** Equal‑weighting across indices sorted by short‑ and long‑term alphas [7].  
  - **Profitability** Monthly three‑factor model alphas of 1.16% (countries) and 1.44% (industries) reported [7].  
  - **Universality** Tests are international; robustness claimed across countries and industries in the paper [7].  
  - **Vietnam applicability** Not tested on Vietnam specifically in that study — **insufficient evidence** from this paper alone.  
  - **Methods** Traditional factor construction and cross‑sectional ranking with validation across markets [7].

- **Factor‑GAN Chinese subsample** Factor‑GAN finds shifts in factor importance during institutional transitions in the Chinese A‑share market, with momentum and growth more pronounced relative to fundamentals [8].  
  - **Signals** Liquidity, volatility, momentum, growth, and traditional fundamentals (importance shifts over state changes) [8].  
  - **Construction** GAN‑augmented factor investment using 70 firm characteristics and deep learning to enhance factor predictions [8].  
  - **Profitability** Deep learning improved long‑short portfolio returns and prediction accuracy in their Chinese subsample analysis [8].  
  - **Universality** Results document that factor importance can be market‑ and regime‑dependent (evidence from Chinese A‑shares) [8].  
  - **Vietnam applicability** The finding that institutional traits shift factor relevance implies possible differences in Vietnam, but direct evidence is **insufficient** in this paper [8].  
  - **Methods** Generative Adversarial Networks integrated with factor models [8].

- **Multifactor APT across portfolios** Research using a broad cross‑section (278 decile portfolios) finds a small set of common factors that price many anomalies, implying that some anomalies are manifestations of a lower‑dimensional factor structure [9].  
  - **Signals** Seven economic factors recovered from cross‑sectional structure; these explain many anomaly portfolios [9].  
  - **Construction** Statistical extraction of common factors across anomaly portfolios following APT principles [9].  
  - **Profitability** The multifactor model prices out many anomaly excess returns in the tested portfolios [9].  
  - **Universality** Analysis covers broad samples but specific emerging market coverage varies; implications are that factor structure can generalize if commonalities exist [9].  
  - **Vietnam applicability** Not directly tested for Vietnam in the paper — **insufficient evidence**.  
  - **Methods** Statistical factor extraction and pricing tests across many anomalous portfolios [9].

----

## Vietnam market signals

This section collects papers that specifically study the Vietnamese stock market and document local anomalies or ML‑based trading evidence. The opening paragraph highlights that Vietnam, as an emerging market, shows different efficiency and practical frictions that affect alpha discovery.

Vietnam studies in the supplied corpus find weaker market efficiency, exploitable short‑term predictability, and utility of ML methods like SVM and feature engineering, though sample sizes and methodology vary.

- **Short‑term trading with SVM and logistic regression** A rolling‑window study on VN‑Index and VN30 rejects weak‑form EMH and finds that SVM and logistic regression forecasts for daily up/down direction can guide profitable intraday trades after risk adjustments [10].  
  - **Signals** Price direction (short‑term return sign) forecasts using historical patterns rather than canonical factor labels [10].  
  - **Construction** SVM and logistic regression trained on historical price features in a rolling‑window framework for one‑day horizons [10].  
  - **Profitability** Reported abnormal returns relative to index benchmarks and rejection of weak‑form efficiency in their tests [10].  
  - **Universality** Results are specific to HoSE (Vietnam) sample and short horizons; broader cross‑market claims are not tested in the paper [10].  
  - **Vietnam applicability** Directly applicable — study is on Vietnamese data and finds exploitable short‑term predictability [10].  
  - **Methods** Support Vector Machine and logistic regression classifiers [10].

- **Machine learning plus feature engineering case study** A Vietnam case study combines ML, data envelopment analysis, and automatic feature engineering to predict returns on Vietnamese stocks and documents predictive improvements from engineered features [11].  
  - **Signals** Engineered features derived from price, volume, and firm attributes tailored to the Vietnamese context [11].  
  - **Construction** Automatic feature engineering pipelines plus ML models with DEA for efficiency screening [11].  
  - **Profitability** Authors report improved predictive accuracy in Vietnam; the study is descriptive and emphasizes model gains rather than complete trading‑strategy backtests [11].  
  - **Universality** The approach is adapted to Vietnam; transferability to other markets requires re‑engineering of features [11].  
  - **Vietnam applicability** Explicit Vietnam focus — evidence supports local model improvement [11].  
  - **Methods** SVM, feature engineering algorithms, and data envelopment analysis [11].

- **Practical notes on Vietnamese market efficiency** Several supplied Vietnam papers conclude the market shows weak‑form inefficiencies and that modern ML approaches can extract short‑horizon signals, but they also caution about sample period, liquidity and transaction cost impacts on implementability [10] [11].  

----

## Machine learning approaches for alpha discovery

This section describes systematic ML methods used to find and combine alpha signals, focusing on architectures, ensemble strategies, horizon design, and economic validation. The opening emphasizes that ML often increases raw predictive power but design choices (horizon, turnover, transaction costs, and cross‑validation) determine implementable alpha.

- **Large anomaly + ML ensembles** Aggregating hundreds of anomalies and applying many ML learners yields robust OOS returns and demonstrates that nonlinear models recover mispricing not captured by linear baselines [1].  
  - **Signals** Hundreds of published anomalies used as input features rather than proposing new single signals [1].  
  - **Construction** Standardize many characteristics, train ML models to predict next‑month returns, and compare with linear baselines [1].  
  - **Profitability** Ensemble ML produced monthly out‑of‑sample returns ≈1.8–2.0% with many models outperforming linear baselines after transaction cost adjustments in the paper's experiments [1].  
  - **Universality** The study emphasizes robustness but most experiments rely on large‑market historical samples; generalization to thin markets requires testing [1].  
  - **Vietnam applicability** The paper does not test Vietnam specifically, so applicability is **insufficient evidence** without local replication [1].  
  - **Methods** Large ML ensembles, nonlinear learners, and risk‑adjusted performance testing [1].

- **Deep learning expected returns and horizon design** Training ML on longer prediction horizons can select slower, more tradable signals and restore positive net performance after trading costs where one‑month models fail [6].  
  - **Signals** Time‑scale dependent features; longer horizons emphasize traditional factors and lower turnover signals [6].  
  - **Construction** Vary prediction horizon during training and use portfolio construction rules aligned with horizon [6].  
  - **Profitability** Longer‑horizon ML strategies show significant net returns in the authors' results, whereas short‑horizon ML can be null after costs [6].  
  - **Universality** Findings about horizon mattering are general design lessons; empirical results depend on dataset and liquidity regimes [6].  
  - **Methods** Deep learning and portfolio optimization varying horizon and turnover controls [6].

- **Feature forecasting then factor construction** Forecasting future fundamentals before computing factors improves factor signal quality and investment performance relative to static factor calculations in simulation studies [4].  
  - **Signals** Forecasted fundamentals lead to improved value/profitability factor signals [4].  
  - **Construction** Train neural nets on historical fundamentals to predict future fundamentals; compute factors from forecasts and form portfolios [4].  
  - **Profitability** Backtest results show higher compounded returns in their simulated portfolio when using forecasted fundamentals [4].  
  - **Universality** Tested on U.S. data; transferability to emerging markets requires retraining and testing [4].  
  - **Methods** Deep neural nets for fundamentals forecasting and backtesting simulators [4].

- **Tree ensembles and Bayesian trees for sparse factor discovery** BART and related tree ensembles identify sparse, high‑value characteristic sets (e.g., market value) that explain cross‑sectional returns better than many‑characteristic linear models [2].  
  - **Signals** Emphasis on a small number of highly relevant characteristics discovered endogenously [2].  
  - **Construction** Bayesian Additive Regression Trees rank and select characteristics under nonlinearity and interactions [2].  
  - **Profitability** Sparse BART‑based selection yields superior statistical and economic performance versus competing models in the paper [2].  
  - **Universality** Framework can be applied broadly but empirical tests were U.S. focused in the referenced study [2].  
  - **Methods** BART and ensemble tree methods with Bayesian inference [2].

- **Custom cross‑sectional ML classifiers** Reclassifying stocks based on predicted performance (rather than raw momentum rank) mitigates bimodal return risks and increases alpha in U.S. tests [3].  
  - **Signals** ML‑predicted reclassification of momentum groups refines traditional momentum signal [3].  
  - **Construction** Train a cross‑sectional predictor to separate momentum stocks into more homogeneous outcome buckets and form value‑weighted portfolios [3].  
  - **Profitability** Value‑weighted long‑short portfolio reported monthly alpha 2.4% (t=6.63) net of common factors in the paper's U.S. tests [3].  
  - **Universality** Results are demonstrated for the U.S.; extension to other markets needs replication [3].  
  - **Methods** Novel ML prediction architecture for cross‑sectional reclassification [3].

- **Practical implementation caveats** Several papers stress transaction costs, turnover controls, post‑publication decay, and realistic portfolio construction as critical to net performance, and they show that naive ML can be unimplementable without these considerations [1] [6] [12].  

----

## References

[1]V. G. Azevedo, “Enhancing stock market anomalies with machine learning,” Review of Quantitative Finance and Accounting, vol. 60, no. 1, pp. 195–230, Aug. 2022, doi: 10.1007/s11156-022-01099-z.

[2]E. H. Verbiest, “Stock Return Prediction by History Mapping,” Social Science Research Network, Nov. 2011, doi: 10.2139/SSRN.1963679.

[3]C. Han, “Bimodal Characteristic Returns and Predictability Enhancement via Machine Learning,” Jan. 2021.

[4]V. Azevedo, C. Hoegner, and M. Velikov, “The Expected Returns on Machine-Learning Strategies,” Social Science Research Network, doi: 10.2139/ssrn.4702406.

[5]J. Alberg and Z. C. Lipton, “Improving Factor-Based Quantitative Investing by Forecasting Company Fundamentals,” arXiv: Machine Learning, Nov. 2017.

[6]T. Shu and A. Tiwari, “Identifying Signals of the Cross Section of Stock Returns,” Social Science Research Network, Jan. 2021, doi: 10.2139/SSRN.3898282.

[7]D. Mai, “StockGPT: A GenAI Model for Stock Prediction and Trading,” Social Science Research Network, Apr. 2024, doi: 10.2139/ssrn.4787199.

[8]M. Sharma, “The Quantamental Revolution: Factor Investing in the Age of Machine Learning”, [Online]. Available: https://books.google.com/books?hl=en&lr=&id=HKC5EQAAQBAJ&oi=fnd&pg=PR1&dq=(alpha+signals+OR+factor+investing+OR+stock+anomalies)+AND+(predictive+factors+OR+return+prediction)+AND+(machine+learning+OR+quantitative+trading)&ots=ioU2RHHJ1l&sig=l14mys8mhSzDMSuZ4JHySZu668o

[9]S. J. Byun, S. Cho, and D.-H. Kim, “Can a Machine Learn from Behavioral Biases? Evidence from Stock Return Predictability of Deep Learning Models,” Social Science Research Network, Jan. 2022, doi: 10.2139/ssrn.4001583.

[10]D. Borisenko, “Dissecting Momentum: We Need to Go Deeper,” Social Science Research Network, July 2019, doi: 10.2139/SSRN.3424793.

[11]D. Blitz, M. X. Hanauer, T. Hoogteijling, and C. Howard, “The Term Structure of Machine Learning Alpha,” The journal of financial data science, vol. 5, no. 4, pp. 40–65, Sept. 2023, doi: 10.3905/jfds.2023.1.135.

[12]A. Zaremba, M. Umutlu, and A. Karathanasopoulos, “Opposites Attract: Combining Alpha Momentum and Alpha Reversal in International Equity Markets,” The Journal of Investing, vol. 29, no. 3, pp. 38–62, Feb. 2020, doi: 10.3905/JOI.2020.1.120.