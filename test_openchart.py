from openchart import NSEData
from datetime import datetime, timedelta

print("Starting OpenChart Futures test...")

nse = NSEData()

print("\n=== SEGMENTS ===")
print(nse.segments)

print("\n=== TIMEFRAMES ===")
print(nse.timeframes)

print("\n=== SEARCH NIFTY FO ===")

fo = nse.search("NIFTY", "FO")

print(fo.to_string(index=False))

print("\n=== TESTING NIFTY FUTURES DIRECTLY ===")

end = datetime.now()
start = end - timedelta(days=2)

symbol = "NIFTY26AUGFUT"

try:
    data = nse.historical(
        symbol,
        "FO",
        start,
        end,
        "5m"
    )

    print("\n=== RESULT ===")

    if data is None or data.empty:
        print("NO DATA FOR", symbol)
    else:
        print(data.tail(20).to_string())
        print("\nFUTURES 5M DATA = OK")

except Exception as e:
    print("\nERROR:")
    print(type(e).__name__, str(e))
