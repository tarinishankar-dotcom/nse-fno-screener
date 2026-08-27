from openchart import NSEData
from datetime import datetime
import pandas as pd

print("==========================================")
print("FULL NSE F&O FUTURES DISCOVERY")
print("==========================================")

nse = NSEData()

# Search broad F&O universe
print("\nSearching complete FO master...")

try:
    df = nse.search("FUT", "FO")
except Exception as e:
    print("FUT search failed:", e)
    df = None

# If FUT search doesn't return the complete list,
# try common current-month expiry patterns.
if df is None or df.empty:
    print("Trying alternative FO search...")

    results = []

    for q in [
        "FUT",
        "26AUGFUT",
        "26SEPFUT",
        "26OCTFUT",
        "26NOVFUT",
        "26DECFUT"
    ]:
        try:
            r = nse.search(q, "FO")
            if r is not None and not r.empty:
                results.append(r)
        except Exception as e:
            print("Search error:", q, e)

    if results:
        df = pd.concat(results, ignore_index=True)

if df is None or df.empty:
    print("\nERROR: No F&O data returned.")
    raise SystemExit(1)

# Remove duplicates
df = df.drop_duplicates(subset=["symbol"])

print("\nTotal FO records found:", len(df))

# Keep Futures only
if "type" in df.columns:
    futures = df[
        df["type"].astype(str).str.lower().str.contains("future")
    ].copy()
else:
    futures = df[df["symbol"].astype(str).str.endswith("FUT")].copy()

# Remove option contracts
futures = futures[
    futures["symbol"].astype(str).str.endswith("FUT")
].copy()

# Sort
futures = futures.sort_values("symbol").reset_index(drop=True)

print("\n==========================================")
print("ALL FUTURES CONTRACTS")
print("==========================================")

print(futures.to_string(index=False))

print("\n==========================================")
print("FUTURES COUNT:", len(futures))
print("==========================================")

# Separate index futures and stock futures
index_names = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50"
]

def is_index_future(symbol):
    symbol = str(symbol).upper()

    for x in index_names:
        if symbol.startswith(x) and symbol.endswith("FUT"):
            return True

    return False

futures["category"] = futures["symbol"].apply(
    lambda x: "INDEX FUTURE"
    if is_index_future(x)
    else "STOCK FUTURE"
)

stock_futures = futures[
    futures["category"] == "STOCK FUTURE"
].copy()

index_futures = futures[
    futures["category"] == "INDEX FUTURE"
].copy()

print("\n==========================================")
print("INDEX FUTURES:", len(index_futures))
print("STOCK FUTURES:", len(stock_futures))
print("==========================================")

print("\n========== STOCK FUTURES ==========")

print(
    stock_futures[
        ["symbol", "scripcode", "description", "type", "exchange"]
    ].to_string(index=False)
)

# Save complete list
futures.to_csv("all_futures.csv", index=False)
stock_futures.to_csv("stock_futures.csv", index=False)

print("\n==========================================")
print("FILES CREATED")
print("all_futures.csv")
print("stock_futures.csv")
print("==========================================")

print("\nFULL NSE F&O FUTURES TEST = OK")
