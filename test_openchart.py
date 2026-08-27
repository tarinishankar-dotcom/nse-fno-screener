from openchart import NSEData
from datetime import datetime, timedelta

print("Starting OpenChart Futures candle test...")

nse = NSEData()

fo = nse.search("NIFTY", "FO")

print("\n=== FO SEARCH RESULT ===")
print(fo.to_string(index=False))

futures = fo[
    fo["type"].astype(str).str.lower().isin(["futures", "future", "fut"])
]

print("\n=== FUTURES ONLY ===")

if futures.empty:
    print("NO FUTURES CONTRACT FOUND")
    raise SystemExit(1)

print(futures.to_string(index=False))

symbol = futures.iloc[0]["symbol"]

print(f"\nTesting candle data for: {symbol}")

end = datetime.now()
start = end - timedelta(days=2)

data = nse.historical(
    symbol,
    "FO",
    start,
    end,
    "5m"
)

print("\n=== 5 MINUTE CANDLES ===")

if data is None or data.empty:
    print("NO CANDLE DATA FOUND")
    raise SystemExit(1)

print(data.tail(20).to_string())

print("\nOPENCHART FUTURES + 5M DATA = OK")
