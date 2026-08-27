import requests
import pandas as pd
from io import BytesIO
import gzip

print("=" * 60)
print("NSE F&O MASTER DATA - FULL TEST")
print("=" * 60)

url = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/csv,application/csv,*/*",
    "Referer": "https://www.nseindia.com/"
}

print("\nDownloading NSE F&O data...")

try:
    r = requests.get(url, headers=headers, timeout=30)

    print("HTTP STATUS:", r.status_code)
    print("DATA SIZE:", len(r.content), "bytes")

    if r.status_code != 200:
        raise Exception(f"NSE returned HTTP {r.status_code}")

    print("\nReading data...")

    df = pd.read_csv(BytesIO(r.content))

    print("ROWS:", len(df))
    print("COLUMNS:", list(df.columns))

    print("\nFIRST 20 ROWS:")
    print(df.head(20).to_string(index=False))

    print("\n" + "=" * 60)
    print("MASTER TEST COMPLETE")
    print("=" * 60)

except Exception as e:
    print("\nERROR:", type(e).__name__, str(e))
    raise
