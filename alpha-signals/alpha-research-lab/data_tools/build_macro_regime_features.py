"""
Build composite macro regime features from available FX/commodity/news data.

Produces: data/features/macro_regime_daily.parquet

Columns (all computed without look-ahead — rolling windows use only past data):
  time
  vix_level          VIX closing level
  vix_mom_5d         VIX 5-day return (rising fear = positive)
  vix_mom_20d        VIX 20-day return
  vix_vs_ma60        VIX / 60d MA - 1 (how elevated vs recent average)

  us10y_level        US 10Y yield level (%)
  us10y_mom_20d      US 10Y yield 20-day change (rising rates = positive)

  vnm_vs_vni_5d      VNM ETF 5d return minus VNINDEX 5d return (foreign vs domestic flow)
  vnm_vs_vni_20d     VNM ETF 20d return minus VNINDEX 20d return

  cu_gold_ratio      Copper price / Gold price (risk appetite proxy)
  cu_gold_mom_20d    Copper/Gold ratio 20-day momentum

  vnd_usd_mom_20d    VND/USD rate 20-day return (positive = VND weakening)

  oil_mom_20d        Oil 20-day return
  gold_mom_20d       Gold 20-day return

  breadth_score      Count of assets in uptrend (20d return > 0) out of:
                     [Shanghai, HSI, Nikkei, Oil, Copper, VNM ETF]  → 0-6

  news_surge_5d      Max daily FPT news_surge over last 5 days (spike = info event)
  total_articles_ma5 5d MA of total_articles (market noise level)

Usage:
    conda run -n stocks python data_tools/build_macro_regime_features.py
"""
import pandas as pd
import numpy as np
from pathlib import Path

FX_DIR   = Path("data/fx-commodities")
FEAT_DIR = Path("data/features")
OUT_PATH = FEAT_DIR / "macro_regime_daily.parquet"

VNI_PATH = Path("data/stock/gia_lich_su_VNINDEX_1D.parquet")

NEW_TICKERS = {
    "fx_commodities_sp500_1D.parquet":  "sp500",
    "fx_commodities_us3m_1D.parquet":   "us3m",
    "fx_commodities_eem_1D.parquet":    "eem",
    "fx_commodities_hyg_1D.parquet":    "hyg",
    "fx_commodities_tlt_1D.parquet":    "tlt",
    "fx_commodities_kospi_1D.parquet":  "kospi",
    "fx_commodities_taiex_1D.parquet":  "taiex",
    "fx_commodities_btc_1D.parquet":    "btc",
    "fx_commodities_ewh_1D.parquet":    "ewh",
}


def load_close(filename: str, alias: str) -> pd.Series:
    path = FX_DIR / filename
    df = pd.read_parquet(path)[["time", "close"]].copy()
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates("time")
    return df.set_index("time")["close"].rename(alias)


def ret(s: pd.Series, n: int) -> pd.Series:
    return s / s.shift(n) - 1


def main():
    print("Loading raw data...")

    vix    = load_close("fx_commodities_vix_1D.parquet",      "vix")
    us10y  = load_close("fx_commodities_us10y_1D.parquet",    "us10y")
    vnm    = load_close("fx_commodities_vnm_etf_1D.parquet",  "vnm")
    copper = load_close("fx_commodities_hg_f_1D.parquet",     "copper")
    gold   = load_close("fx_commodities_gold_1D.parquet",     "gold")
    oil    = load_close("fx_commodities_oil_1D.parquet",      "oil")
    shanghai = load_close("fx_commodities_shanghai_1D.parquet", "shanghai")
    hsi    = load_close("fx_commodities_hsi_1D.parquet",      "hsi")
    nikkei = load_close("fx_commodities_nikkei_1D.parquet",   "nikkei")
    vnd    = load_close("fx_commodities_fx_vnd_usd_1D.parquet", "vnd_usd")

    vni_df = pd.read_parquet(VNI_PATH)[["time", "close"]].copy()
    vni_df["time"] = pd.to_datetime(vni_df["time"])
    vni_df = vni_df.sort_values("time").drop_duplicates("time")
    vni = vni_df.set_index("time")["close"].rename("vnindex")

    # Build a common date index (use VNINDEX trading days as spine)
    idx = vni.index

    def align(s):
        return s.reindex(idx, method="ffill")

    vix   = align(vix)
    us10y = align(us10y)
    vnm   = align(vnm)
    copper= align(copper)
    gold  = align(gold)
    oil   = align(oil)
    shanghai = align(shanghai)
    hsi   = align(hsi)
    nikkei= align(nikkei)
    vnd   = align(vnd)
    vni_a = align(vni)

    news = pd.read_parquet(FEAT_DIR / "fpt_news_daily.parquet")
    news["date"] = pd.to_datetime(news["date"])
    news = news.set_index("date")[["news_surge", "total_articles"]]
    news = news.reindex(idx, method="ffill").fillna(0)

    # Load new tickers (skip if file not present)
    new_series = {}
    for fname, alias in NEW_TICKERS.items():
        fpath = FX_DIR / fname
        if fpath.exists():
            s = load_close(fname, alias)
            new_series[alias] = align(s)
        else:
            print(f"  [WARN] {fname} not found, skipping")

    print("Computing regime indicators...")
    out = pd.DataFrame(index=idx)

    # VIX
    out["vix_level"]   = vix
    out["vix_mom_5d"]  = ret(vix, 5)
    out["vix_mom_20d"] = ret(vix, 20)
    out["vix_vs_ma60"] = vix / vix.rolling(60).mean() - 1

    # US10Y (stored as percentage points, not price — so use difference not return)
    out["us10y_level"]   = us10y
    out["us10y_mom_20d"] = us10y - us10y.shift(20)   # absolute change in yield

    # VNM ETF vs VNINDEX divergence (foreign investor flow signal)
    vnm_ret5  = ret(vnm, 5)
    vni_ret5  = ret(vni_a, 5)
    vnm_ret20 = ret(vnm, 20)
    vni_ret20 = ret(vni_a, 20)
    out["vnm_vs_vni_5d"]  = vnm_ret5  - vni_ret5
    out["vnm_vs_vni_20d"] = vnm_ret20 - vni_ret20

    # Copper/Gold ratio (risk appetite — high = risk-on)
    cu_gold = copper / gold
    out["cu_gold_ratio"]   = cu_gold
    out["cu_gold_mom_20d"] = ret(cu_gold, 20)

    # VND/USD (positive = VND weakening = pressure on Vietnamese stocks)
    out["vnd_usd_mom_20d"] = ret(vnd, 20)

    # Oil and Gold directional
    out["oil_mom_20d"]  = ret(oil, 20)
    out["gold_mom_20d"] = ret(gold, 20)

    # Multi-asset breadth (0-6): count of assets with positive 20d return
    breadth_assets = {
        "sh_up":  (ret(shanghai, 20) > 0).astype(int),
        "hsi_up": (ret(hsi, 20) > 0).astype(int),
        "nik_up": (ret(nikkei, 20) > 0).astype(int),
        "oil_up": (ret(oil, 20) > 0).astype(int),
        "cu_up":  (ret(copper, 20) > 0).astype(int),
        "vnm_up": (ret(vnm, 20) > 0).astype(int),
    }
    out["breadth_score"] = sum(breadth_assets.values())

    # News features
    out["news_surge_5d"]      = news["news_surge"].rolling(5).max()
    out["total_articles_ma5"] = news["total_articles"].rolling(5).mean()

    # ── New indicators from extended data ──────────────────────────────────────

    if "sp500" in new_series:
        sp5 = new_series["sp500"]
        out["sp500_mom_5d"]  = ret(sp5, 5)
        out["sp500_mom_20d"] = ret(sp5, 20)

    if "us3m" in new_series:
        us3m_s = new_series["us3m"]
        # Yield curve: 10Y minus 3M (positive = normal, negative = inverted = recession signal)
        out["yield_curve"]     = us10y - us3m_s          # in percentage points
        out["yield_curve_mom"] = (us10y - us3m_s) - (us10y.shift(20) - us3m_s.shift(20))

    if "hyg" in new_series and "tlt" in new_series:
        hyg_s = new_series["hyg"]
        tlt_s = new_series["tlt"]
        # HYG/TLT ratio: high = credit risk-on (junk bonds outpacing safe bonds)
        hyg_tlt = hyg_s / tlt_s
        out["hyg_tlt_ratio"]   = hyg_tlt
        out["hyg_tlt_mom_20d"] = ret(hyg_tlt, 20)
        out["hyg_mom_20d"]     = ret(hyg_s, 20)
        out["tlt_mom_20d"]     = ret(tlt_s, 20)

    if "eem" in new_series and "sp500" in new_series:
        eem_s = new_series["eem"]
        sp5   = new_series["sp500"]
        # EEM vs S&P: positive = EM outpacing US = capital flowing to EM
        out["eem_vs_sp500_20d"] = ret(eem_s, 20) - ret(sp5, 20)
        out["eem_mom_20d"]      = ret(eem_s, 20)

    if "kospi" in new_series:
        k = new_series["kospi"]
        out["kospi_mom_20d"] = ret(k, 20)

    if "taiex" in new_series:
        t = new_series["taiex"]
        out["taiex_mom_20d"] = ret(t, 20)

    if "btc" in new_series:
        b = new_series["btc"]
        out["btc_mom_20d"] = ret(b, 20)

    # Extended breadth score (add kospi, taiex, ewh to existing 6)
    extra_breadth = []
    for alias in ["kospi", "taiex", "ewh"]:
        if alias in new_series:
            extra_breadth.append((ret(new_series[alias], 20) > 0).astype(int))
    if extra_breadth:
        out["breadth_score_ext"] = out["breadth_score"] + sum(extra_breadth)  # 0-9

    # Credit regime composite: HYG + EEM both in uptrend = full risk-on
    if "hyg" in new_series and "eem" in new_series:
        out["credit_risk_on"] = (
            (ret(new_series["hyg"], 20) > 0).astype(int) +
            (ret(new_series["eem"], 20) > 0).astype(int) +
            (ret(new_series["sp500"], 20) > 0).astype(int)
            if "sp500" in new_series else 0
        )  # 0-3: how many risk assets in uptrend

    # Drop rows before 2012 (too early for most series)
    out = out[out.index >= "2012-01-01"]
    out = out.reset_index().rename(columns={"index": "time"})
    out["time"] = pd.to_datetime(out["time"])

    out.to_parquet(OUT_PATH, index=False)
    print(f"Saved: {OUT_PATH}  ({len(out):,} rows, {len(out.columns)} cols)")
    print(f"Date range: {out['time'].min().date()} → {out['time'].max().date()}")
    print(f"Columns: {list(out.columns)}")


if __name__ == "__main__":
    main()
