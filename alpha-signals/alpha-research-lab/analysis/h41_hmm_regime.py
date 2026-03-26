"""
H41: Hidden Markov Model for data-driven regime discovery.

Instead of hand-selecting VIX [15,30], fit an HMM on market features to discover
latent states. Then check: which HMM state produces the highest XS model accuracy?

The discovered states should map to something economically interpretable:
  - "Asia risk-on": low VIX, positive TAIEX/KOSPI momentum → signal is clean
  - "Global stress": high VIX, negative momentum → signal is noisy
  - "Idiosyncratic": low VIX but VN-specific noise → signal is mixed

If the data-driven state matches what we found manually, it's strong validation.
If it finds something different, we learn something new.

Usage:
    conda run -n stocks python analysis/h41_hmm_regime.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import binomtest

try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    print("[WARN] hmmlearn not installed. Run: conda install -c conda-forge hmmlearn")

MACRO_PATH = Path("data/features/macro_regime_daily.parquet")
XS_PROBA   = Path("data/features/xs_barrier_fpt_proba.csv")
SS_PROBA   = Path("data/features/ss_fpt_proba_e32.csv")
VIX_PATH   = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")

# Features for HMM — all standardized before fitting
HMM_FEATURES = [
    "vix_level",        # absolute VIX level
    "vix_mom_20d",      # VIX momentum (rising/falling)
    "taiex_mom_20d",    # Taiwan tech momentum
    "kospi_mom_20d",    # Korea industrial momentum
    "sp500_mom_20d",    # global equity trend
    "breadth_score",    # VN market breadth (0-5)
    "yield_curve",      # US yield curve (recession signal)
]

N_STATES = 3   # try 2,3,4 states


def load_features():
    macro = pd.read_parquet(MACRO_PATH)
    macro["time"] = pd.to_datetime(macro["time"])

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix_close"})
    vix["time"] = pd.to_datetime(vix["time"])
    macro = macro.merge(vix, on="time", how="left")
    macro["vix_level"] = macro["vix_close"].ffill()

    xs = pd.read_csv(XS_PROBA, parse_dates=["time"])
    ss = pd.read_csv(SS_PROBA, parse_dates=["time"])

    df = xs.merge(ss[["time", "ss_proba"]], on="time", how="inner")
    df = df.merge(macro[["time"] + HMM_FEATURES], on="time", how="left")
    for c in HMM_FEATURES:
        df[c] = df[c].ffill().fillna(0)
    return df


def fit_hmm(df: pd.DataFrame, n_states: int, train_cutoff_year: int = 2018):
    """Fit HMM on pre-2019 data, decode full period."""
    # Use all macro dates for fitting (more data), then align with XS proba dates
    macro = pd.read_parquet(MACRO_PATH)
    macro["time"] = pd.to_datetime(macro["time"])
    # vix_level already present in macro_regime_daily; fill gaps with raw VIX if needed
    if "vix_level" not in macro.columns:
        vix = pd.read_parquet(VIX_PATH)[["time","close"]].rename(columns={"close":"vix_level"})
        vix["time"] = pd.to_datetime(vix["time"])
        macro = macro.merge(vix, on="time", how="left")
    macro["vix_level"] = macro["vix_level"].ffill()

    avail = [c for c in HMM_FEATURES if c in macro.columns]
    macro_clean = macro[["time"] + avail].dropna().sort_values("time").reset_index(drop=True)

    # Normalize features
    train = macro_clean[macro_clean["time"].dt.year <= train_cutoff_year]
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    scaler.fit(train[avail].values)

    X_all = scaler.transform(macro_clean[avail].values)
    lengths = [len(X_all)]

    model = GaussianHMM(n_components=n_states, covariance_type="full",
                        n_iter=200, random_state=42)
    model.fit(X_all, lengths)
    states = model.predict(X_all)

    macro_clean["hmm_state"] = states
    return macro_clean[["time", "hmm_state"]], model, avail, scaler


def describe_states(macro_with_states: pd.DataFrame, feature_cols: list, model):
    """Print mean feature values per state for interpretability."""
    print("\n  State characteristics (feature means):")
    header = f"  {'State':>6}  {'n_days':>7}  " + "  ".join(f"{c[:10]:>10}" for c in feature_cols)
    print(header)
    print("  " + "-" * len(header))

    macro = pd.read_parquet(MACRO_PATH)
    macro["time"] = pd.to_datetime(macro["time"])
    macro["vix_level"] = macro["vix_level"].ffill()
    merged = macro_with_states.merge(macro[["time"] + feature_cols], on="time", how="left")

    for s in sorted(macro_with_states["hmm_state"].unique()):
        rows = merged[merged["hmm_state"] == s]
        vals = "  ".join(f"{rows[c].mean():>+10.3f}" for c in feature_cols)
        print(f"  {s:>6}  {len(rows):>7}  {vals}")


def evaluate_hmm_as_filter(df: pd.DataFrame, macro_with_states: pd.DataFrame, n_states: int):
    """
    For each HMM state, compute the XS+SS ensemble accuracy on FPT.
    Identify which state is the 'good' regime for trading.
    """
    df = df.merge(macro_with_states[["time", "hmm_state"]], on="time", how="left")
    df["hmm_state"] = df["hmm_state"].fillna(-1).astype(int)

    MIN_CONF = 0.55

    print(f"\n  Per-state ensemble accuracy (XS barrier + E32, min_conf={MIN_CONF}, agree-only):")
    print(f"  {'state':>6}  {'n_days':>7}  {'n_conf':>7}  {'conf_acc':>9}  {'edge':>8}  {'pval':>8}")
    print("  " + "-" * 60)

    state_results = {}
    for state in range(n_states):
        s_df = df[df["hmm_state"] == state]
        actual = s_df["actual"].values
        naive  = actual.mean() if len(actual) > 0 else 0.5

        xs_conf = (s_df["xs_proba"] > MIN_CONF) | (s_df["xs_proba"] < (1 - MIN_CONF))
        ss_conf = (s_df["ss_proba"] > MIN_CONF) | (s_df["ss_proba"] < (1 - MIN_CONF))
        xs_dir  = (s_df["xs_proba"] > 0.5).astype(int).values
        ss_dir  = (s_df["ss_proba"] > 0.5).astype(int).values
        agree   = xs_dir == ss_dir
        conf    = xs_conf.values & ss_conf.values & agree

        n_conf = conf.sum()
        if n_conf >= 10:
            preds = xs_dir[conf]
            y     = actual[conf]
            acc   = (preds == y).mean()
            edge  = acc - naive
            pval  = binomtest(int((preds == y).sum()), n_conf, naive).pvalue
            sig   = "*" if pval < 0.05 else " "
            print(f"  {state:>6}  {len(s_df):>7}  {n_conf:>7}  {acc*100:>8.1f}%  {edge*100:>+7.2f}%  {pval:>7.4f}{sig}")
            state_results[state] = {"edge": edge, "n_conf": n_conf, "acc": acc, "naive": naive}
        else:
            print(f"  {state:>6}  {len(s_df):>7}  {n_conf:>7}  {'LOW':>9}  {'N/A':>8}  {'N/A':>8}")
            state_results[state] = {"edge": float("nan"), "n_conf": n_conf}

    return state_results


def hmm_vs_vix_filter(df: pd.DataFrame, macro_with_states: pd.DataFrame, best_state: int):
    """Compare HMM-filtered ensemble vs VIX [15,30] filter, year by year."""
    df = df.merge(macro_with_states[["time", "hmm_state"]], on="time", how="left")
    df["hmm_state"] = df["hmm_state"].fillna(-1).astype(int)

    VIX_PATH2 = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
    vix = pd.read_parquet(VIX_PATH2)[["time","close"]].rename(columns={"close":"vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()

    MIN_CONF = 0.55

    print(f"\n  Year-by-year: HMM state={best_state} vs VIX [15,30]")
    print(f"  {'year':>5}  {'hmm_n':>6}  {'hmm_edge':>9}  {'vix_n':>6}  {'vix_edge':>9}")
    print("  " + "-" * 50)

    all_hmm, all_vix = [], []
    for year, grp in df.groupby(pd.to_datetime(df["time"]).dt.year):
        if year < 2019:
            continue
        actual = grp["actual"].values
        naive  = actual.mean()
        xs_dir = (grp["xs_proba"] > 0.5).astype(int).values
        ss_dir = (grp["ss_proba"] > 0.5).astype(int).values
        xs_conf = (grp["xs_proba"].values > MIN_CONF) | (grp["xs_proba"].values < (1-MIN_CONF))
        ss_conf = (grp["ss_proba"].values > MIN_CONF) | (grp["ss_proba"].values < (1-MIN_CONF))
        agree   = xs_dir == ss_dir
        base    = xs_conf & ss_conf & agree

        hmm_mask = (grp["hmm_state"].values == best_state) & base
        vix_mask = (grp["vix"].values >= 15) & (grp["vix"].values <= 30) & base

        def calc_edge(mask):
            n = mask.sum()
            if n < 5:
                return float("nan"), n
            preds = xs_dir[mask]
            y     = actual[mask]
            return (preds == y).mean() - naive, n

        hmm_edge, hmm_n = calc_edge(hmm_mask)
        vix_edge, vix_n = calc_edge(vix_mask)

        hmm_str = f"{hmm_edge*100:>+8.2f}%" if not np.isnan(hmm_edge) else "     N/A"
        vix_str = f"{vix_edge*100:>+8.2f}%" if not np.isnan(vix_edge) else "     N/A"
        print(f"  {year:>5}  {hmm_n:>6}  {hmm_str}  {vix_n:>6}  {vix_str}")
        if not np.isnan(hmm_edge):
            all_hmm.append(hmm_edge)
        if not np.isnan(vix_edge):
            all_vix.append(vix_edge)

    print(f"\n  HMM avg edge : {np.mean(all_hmm)*100:+.2f}%  ({len(all_hmm)} years)")
    print(f"  VIX avg edge : {np.mean(all_vix)*100:+.2f}%  ({len(all_vix)} years)")


def run():
    if not HMM_AVAILABLE:
        print("Install hmmlearn first: conda install -c conda-forge hmmlearn")
        return

    print("=" * 70)
    print("H41: HIDDEN MARKOV MODEL REGIME DISCOVERY")
    print(f"  Features: {HMM_FEATURES}")
    print(f"  N states: {N_STATES} | Train cutoff: 2018")
    print("=" * 70)

    print("\nLoading data...")
    df = load_features()
    print(f"  FPT XS+SS rows: {len(df)} ({df['time'].min().date()} → {df['time'].max().date()})")

    for n in [2, 3, 4]:
        print(f"\n{'='*70}")
        print(f"HMM with {n} states")
        print("=" * 70)

        macro_states, model, avail_feats, scaler = fit_hmm(df, n_states=n)
        print(f"  Fitted HMM: {n} states | convergence log-likelihood: {model.monitor_.history[-1]:.1f}")
        describe_states(macro_states, avail_feats, model)

        state_results = evaluate_hmm_as_filter(df, macro_states, n_states=n)

        valid = {s: r for s, r in state_results.items() if not np.isnan(r.get("edge", float("nan")))}
        if valid:
            best_state = max(valid, key=lambda s: valid[s]["edge"])
            print(f"\n  Best state for trading: State {best_state} (edge={valid[best_state]['edge']*100:+.2f}%)")
            hmm_vs_vix_filter(df, macro_states, best_state)


if __name__ == "__main__":
    run()
