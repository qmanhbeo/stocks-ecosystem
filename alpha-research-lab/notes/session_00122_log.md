# Session 122 Log — 2026-05-08

## H473: news_velocity_as_signal

**Decision: FAILED**

### Hypothesis
News VELOCITY (3d count delta = 5d - 1d article count) tests a third dimension beyond
novelty (H440) and presence (H445): fast-arriving news = breaking alpha, slow/steady = absorbed.

### Command / code
```bash
python analysis/h473_news_velocity_as_signal.py
```

### Inputs
- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet` (start_year=2018)
- News: `data/features/news/datasets/news_daily_features.parquet`
- PhoBERT article counts (1d and 5d), 406 tickers

### Saved artifact
`artifacts/run_summaries/20260508_193939_news_velocity_as_signal_research_branch.json`

### Results

| State | IC | Lift vs Baseline | Positive Years |
|-------|-----|-------------------|----------------|
| all_rows (baseline) | 0.1196 | — | 8/8 |
| mid_velocity (Q3) | 0.1275 | +0.0079 | 8/8 |
| no_news (1d) | 0.1259 | +0.0063 | 8/8 |
| has_news (1d) | 0.0968 | **-0.0228** | 8/8 |
| high_velocity (Q5) | 0.0876 | **-0.0320** | 8/8 |
| high_vel_has_news | 0.0849 | **-0.0347** | 8/8 |
| burst_has_news (delta > 3) | 0.0823 | **-0.0373** | 8/8 |
| low_velocity (Q1) | NaN | — | 0/8 (too sparse) |
| low_vel_has_news | NaN | — | 0/8 (too sparse) |

Panel: 652,527 rows, 22.1% have PhoBERT news.

### Interpretation

**High news velocity is ANTI-predictive**: high_velocity (Q5) = IC 0.088 (-0.032 lift),
burst_has_news = IC 0.082 (-0.037). The fastest-arriving news is the worst signal.
This is the OPPOSITE of the hypothesis — fast news is already crowd-priced, not hidden alpha.

**mid_velocity (Q3) = IC 0.128 (+0.008)**: moderate velocity is slightly positive,
but not strong enough for promotion.

**has_news = IC 0.097 (-0.023)**: confirms H445 — news is harmful overall.
no_news = IC 0.126 (+0.006): confirms H445 — absence of news is positive.

**low_velocity = NaN (too sparse)**: most tickers have 0 news, so low-velocity
bucket has insufficient rows per year. The distribution is too skewed for this test.

**Key insight**: News VELOCITY adds no value beyond news PRESENCE. The third dimension
(H440 novelty, H445 presence, AM velocity) is noise. The lab should stop testing
raw article count derivatives. Only structured features (source-type, sentiment
with forward-looking, official disclosure) have survived.

### Result: FAILED

News velocity (3d delta) is anti-predictive at high velocity, and the low-velocity
bucket is too sparse. The mechanism is inverted: fast news = crowd-following,
not hidden information.

### Verdict: FAILED

**Next:** Queue item AM (news_velocity_as_signal) is DEAD-END. Continue with AN
(capacity_as_signal_not_veto) — tradability percentile. Do not reopen news
velocity as a standalone ranker or news-count derivative.