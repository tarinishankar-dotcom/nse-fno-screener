from openchart import NSEData

print("Starting NSE F&O data test...")

nse = NSEData()

# Search NIFTY Futures
fo = nse.search("NIFTY", "FO")

print("\n=== NIFTY FUTURES ===")

if fo is None or fo.empty:
    print("NO F&O SYMBOL FOUND")
else:
    print(fo.to_string(index=False))
    print("\nF&O SEARCH = OK")
