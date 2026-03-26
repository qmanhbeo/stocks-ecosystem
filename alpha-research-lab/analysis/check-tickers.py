from vnstock import Listing

ls = Listing()

a = ls.all_symbols()
print("all_symbols columns:", a.columns.tolist())
print(a.head().to_string())

b = ls.symbols_by_exchange()
print("symbols_by_exchange columns:", b.columns.tolist())
print(b.head().to_string())