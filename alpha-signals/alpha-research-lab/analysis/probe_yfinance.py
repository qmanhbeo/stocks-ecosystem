"""Probe yfinance for Vietnam-relevant macro/global data."""
import yfinance as yf
import pandas as pd

candidates = {
    # Vietnam macro proxies (no direct VN macro in yfinance)
    "VNM": "Vietnam ETF (US-listed, tracks VN stocks)",
    "EWH": "iShares MSCI Hong Kong ETF",

    # Asian/EM indices
    "^HSI": "Hang Seng Index",
    "^N225": "Nikkei 225",
    "000001.SS": "Shanghai Composite",
    "^STI": "Straits Times Index (Singapore)",
    "^KS11": "KOSPI (South Korea)",
    "^TWII": "Taiwan Weighted",
    "^BSESN": "BSE Sensex (India)",

    # US market / risk-on-off
    "^GSPC": "S&P 500",
    "^VIX": "CBOE VIX (fear index)",
    "^DXY": "DXY Dollar Index",

    # Rates
    "^TNX": "US 10-year Treasury yield",
    "^IRX": "US 13-week T-bill yield",

    # Commodities
    "GC=F": "Gold futures",
    "CL=F": "WTI Crude Oil",
    "NG=F": "Natural Gas",
    "HG=F": "Copper futures",
    "SI=F": "Silver futures",
    "PDBC": "Invesco Commodity ETF (diversified)",

    # FX
    "VND=X": "USD/VND",
    "CNY=X": "USD/CNY (China FX — top VN trade partner)",
    "SGD=X": "USD/SGD (Singapore — major regional)",
    "JPY=X": "USD/JPY",
    "EUR=X": "USD/EUR",
    "KRW=X": "USD/KRW",

    # Crypto (speculative / retail sentiment)
    "BTC-USD": "Bitcoin",
}

print(f"{'ticker':<15} {'alias':<45} {'start':>12} {'end':>12} {'rows':>6} {'status'}")
print("-" * 100)

results = {}
for ticker, alias in candidates.items():
    try:
        df = yf.download(ticker, start="2015-01-01", end="2026-03-01", progress=False, auto_adjust=False)
        if df.empty:
            print(f"  {ticker:<13} {alias:<43}  NO DATA")
            results[ticker] = None
        else:
            # Handle multi-level columns from yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            start = str(df.index.min().date())
            end = str(df.index.max().date())
            rows = len(df)
            print(f"  {ticker:<13} {alias:<43}  {start}  {end}  {rows:>6}  OK")
            results[ticker] = {"start": start, "end": end, "rows": rows}
    except Exception as e:
        print(f"  {ticker:<13} {alias:<43}  ERROR: {e}")
        results[ticker] = None

print(f"\n{sum(1 for v in results.values() if v is not None)}/{len(results)} tickers available")
