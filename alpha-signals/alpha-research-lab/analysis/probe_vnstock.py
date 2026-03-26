"""Probe vnstock to discover all available data beyond OHLCV."""
from vnstock import Vnstock

stock = Vnstock().stock(symbol="FPT", source="VCI")

print("=== stock.quote methods ===")
print([m for m in dir(stock.quote) if not m.startswith("_")])

print("\n=== stock object attributes ===")
print([m for m in dir(stock) if not m.startswith("_")])

# Try financial reports
try:
    print("\n=== stock.finance methods ===")
    print([m for m in dir(stock.finance) if not m.startswith("_")])
except Exception as e:
    print(f"  stock.finance: {e}")

# Try company info
try:
    print("\n=== stock.company methods ===")
    print([m for m in dir(stock.company) if not m.startswith("_")])
except Exception as e:
    print(f"  stock.company: {e}")

# Try to get financial data
try:
    print("\n=== Income Statement (last 8 quarters) ===")
    inc = stock.finance.income_statement(period="quarter", lang="en")
    print(inc.columns.tolist())
    print(inc.head(3).to_string())
except Exception as e:
    print(f"  income_statement error: {e}")

try:
    print("\n=== Balance Sheet ===")
    bs = stock.finance.balance_sheet(period="quarter", lang="en")
    print(bs.columns.tolist())
    print(bs.head(2).to_string())
except Exception as e:
    print(f"  balance_sheet error: {e}")

try:
    print("\n=== Cash Flow ===")
    cf = stock.finance.cash_flow(period="quarter", lang="en")
    print(cf.columns.tolist())
    print(cf.head(2).to_string())
except Exception as e:
    print(f"  cash_flow error: {e}")

try:
    print("\n=== Financial Ratios ===")
    fr = stock.finance.ratio(period="quarter", lang="en")
    print(fr.columns.tolist())
    print(fr.head(3).to_string())
except Exception as e:
    print(f"  ratio error: {e}")

# Dividends
try:
    print("\n=== Dividends ===")
    div = stock.company.dividends()
    print(div.columns.tolist())
    print(div.head(5).to_string())
except Exception as e:
    print(f"  dividends error: {e}")

# Company events / shareholders
try:
    print("\n=== Shareholders ===")
    sh = stock.company.shareholders()
    print(sh)
except Exception as e:
    print(f"  shareholders error: {e}")

# Insider transactions / insiders
try:
    print("\n=== Insider transactions ===")
    ins = stock.company.insiders_deals()
    print(ins.columns.tolist() if hasattr(ins, 'columns') else ins)
    print(ins.head(5).to_string() if hasattr(ins, 'head') else ins)
except Exception as e:
    print(f"  insiders_deals error: {e}")

# Foreign ownership
try:
    print("\n=== Foreign ownership ===")
    fo = stock.quote.history_foreign_ownership()
    print(fo.columns.tolist() if hasattr(fo, 'columns') else fo)
    print(fo.head(5).to_string() if hasattr(fo, 'head') else fo)
except Exception as e:
    print(f"  foreign_ownership error: {e}")

# Intraday
try:
    print("\n=== Intraday quote ===")
    intra = stock.quote.intraday()
    print(intra.columns.tolist() if hasattr(intra, 'columns') else intra)
    print(intra.head(3).to_string() if hasattr(intra, 'head') else intra)
except Exception as e:
    print(f"  intraday error: {e}")

# Trading stats
try:
    print("\n=== Trading statistics ===")
    ts = stock.trading.price_board(symbols_list=["FPT"])
    print(ts)
except Exception as e:
    print(f"  price_board error: {e}")

# Check for Vnstock top-level for market/macro
print("\n=== Vnstock top-level ===")
from vnstock import Vnstock as VS
vs = VS()
print([m for m in dir(vs) if not m.startswith("_")])

try:
    print("\n=== Market index / VN30 ===")
    idx = VS().stock(symbol="VNINDEX", source="VCI")
    print([m for m in dir(idx) if not m.startswith("_")])
except Exception as e:
    print(f"  VNINDEX: {e}")
