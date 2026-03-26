"""Probe vnstock deeper: trading stats, price depth, world index, historical financials."""
import sys, io
_out = open("probe_vnstock2_output.txt", "w", encoding="utf-8", errors="replace")
sys.stdout = _out
from vnstock import Vnstock
import pandas as pd

stock = Vnstock().stock(symbol="FPT", source="VCI")

# 1. Full price board columns
print("=== price_board columns (78 cols) ===")
try:
    pb = stock.trading.price_board(symbols_list=["FPT", "VCB", "HPG"])
    print(pb.columns.tolist())
    print(pb.to_string())
except Exception as e:
    print(f"  ERROR: {e}")

# 2. Price depth (order book)
print("\n=== price_depth ===")
try:
    pd_df = stock.quote.price_depth(symbol="FPT")
    print(pd_df)
except Exception as e:
    print(f"  ERROR: {e}")

# 3. Company events (earnings dates?)
print("\n=== company events ===")
try:
    ev = stock.company.events()
    print(ev.columns.tolist() if hasattr(ev, 'columns') else ev)
    print(ev.to_string() if hasattr(ev, 'to_string') else ev)
except Exception as e:
    print(f"  ERROR: {e}")

# 4. Company overview (sector, industry)
print("\n=== company overview ===")
try:
    ov = stock.company.overview()
    print(ov)
except Exception as e:
    print(f"  ERROR: {e}")

# 5. How many quarters of financial data?
print("\n=== Financial ratio history (how many quarters?) ===")
try:
    fr = stock.finance.ratio(period="quarter", lang="en")
    print(f"  {len(fr)} quarters available")
    print(f"  Columns: {[c[1] for c in fr.columns if c[0]!='Meta']}")
    print(fr[['Meta']].head(20).to_string())
except Exception as e:
    print(f"  ERROR: {e}")

# 6. Annual financials
print("\n=== Financial ratio (annual) ===")
try:
    fr_a = stock.finance.ratio(period="year", lang="en")
    print(f"  {len(fr_a)} years available")
    print(fr_a[['Meta']].to_string())
except Exception as e:
    print(f"  ERROR: {e}")

# 7. World index from vnstock
print("\n=== Vnstock world_index ===")
try:
    vs = Vnstock()
    wi = vs.world_index
    print(dir(wi))
    print(wi.all_symbols())
except Exception as e:
    print(f"  ERROR: {e}")

# 8. FX from vnstock
print("\n=== Vnstock fx ===")
try:
    vs = Vnstock()
    fx = vs.fx
    print(dir(fx))
except Exception as e:
    print(f"  ERROR: {e}")

# 9. Listing - all stocks with sector info
print("\n=== stock.listing ===")
try:
    ls = stock.listing
    print(dir(ls))
    all_stocks = ls.all_symbols()
    print(f"  {len(all_stocks)} symbols in listing")
    print(all_stocks.columns.tolist() if hasattr(all_stocks, 'columns') else all_stocks[:5])
    print(all_stocks.head(5).to_string() if hasattr(all_stocks, 'head') else all_stocks)
except Exception as e:
    print(f"  ERROR: {e}")

# 10. Check if FPT financial ratio has EPS, P/E over time
print("\n=== FPT EPS + P/E quarterly history ===")
try:
    fr = stock.finance.ratio(period="quarter", lang="en")
    # flatten multi-level columns
    fr.columns = ['_'.join(c).strip('_') for c in fr.columns]
    print(fr.columns.tolist())
    eps_cols = [c for c in fr.columns if 'EPS' in c or 'P/E' in c or 'yearReport' in c or 'lengthReport' in c]
    print(fr[eps_cols].to_string())
except Exception as e:
    print(f"  ERROR: {e}")

_out.flush()
_out.close()
