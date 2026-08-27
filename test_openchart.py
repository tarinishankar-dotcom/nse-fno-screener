from openchart import NSEData
import requests

print("==========================================")
print("NSE F&O MASTER DATA TEST")
print("==========================================")

nse = NSEData()

print("\nSEGMENTS:")
print(nse.segments())

print("\nTIMEFRAMES:")
print(nse.timeframes())

print("\nSEARCH URL:")
print(nse.search_url)

print("\n==========================================")
print("TESTING NSE FO SEARCH")
print("==========================================")

symbols = [
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "INFY",
    "TCS",
    "SBIN",
    "AXISBANK",
    "TATAMOTORS"
]

for symbol in symbols:

    print("\n--------------------------------")
    print("SYMBOL:", symbol)
    print("--------------------------------")

    try:
        result = nse.search(symbol, "FO")

        print(result)

        if result is not None and not result.empty:
            print("RESULT COUNT:", len(result))
            print("COLUMNS:", list(result.columns))

    except Exception as e:
        print("ERROR:", type(e).__name__, e)

print("\n==========================================")
print("DIRECT NSE MASTER URL TEST")
print("==========================================")

try:

    response = requests.get(
        nse.search_url,
        timeout=30
    )

    print("HTTP STATUS:", response.status_code)
    print("CONTENT TYPE:", response.headers.get("content-type"))
    print("CONTENT LENGTH:", len(response.content))

    print("\nFIRST 500 CHARACTERS:")
    print(response.text[:500])

except Exception as e:

    print(
        "DIRECT URL ERROR:",
        type(e).__name__,
        e
    )

print("\n==========================================")
print("TEST COMPLETE")
print("==========================================")
