from openchart import NSEData
from datetime import datetime, timedelta

print("Starting OpenChart F&O master data test...")

nse = NSEData()

print("Downloading NSE/NFO master data...")
nse.download()

print("Master data download = OK")

print("\nSearching NIFTY Futures...")

fo = nse.search("NIFTY", "FO")

print("\n=== NIFTY F&O ===")
print(fo.to_string(index=False))

futures = fo[
    fo["type"].astype(str).str.lower() == "futures"
]

print("\n=== FUTURES ONLY ===")

if futures.empty:
    print("NO FUTURES FOUND")
    raise SystemExit(1)

print(futures.to_string(index=False))

symbol = futures.iloc[0]["symbol"]

print(f"\nTesting 5-minute data: {symbol}")

end = datetime.now()
start = end - timedelta(days=2)

data = nse.historical(
    symbol,
    "FO",
    start,
    end,
    "5m"
)

print("\n=== 5-MINUTE DATA ===")

if data is None or data.empty:
    print("NO CANDLE DATA FOUND")
    raise SystemExit(1)

print(data.tail(20).to_string())

print("\nOPENCHART F&O + 5M DATA = OK")
