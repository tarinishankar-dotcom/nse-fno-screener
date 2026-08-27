from openchart import NSEData
import pandas as pd
from datetime import datetime

print("=" * 60)
print("FULL NSE F&O FUTURES DISCOVERY")
print("=" * 60)

nse = NSEData()

print("\n[1] SEGMENTS")
print(nse.segments())

print("\n[2] TIMEFRAMES")
print(nse.timeframes())

# ---------------------------------------------------------
# VERY IMPORTANT:
# Download NSE + NFO master data first
# ---------------------------------------------------------
print("\n[3] DOWNLOADING NSE/NFO MASTER DATA...")

try:
    result = nse.download()
    print("MASTER DOWNLOAD:", result)
except Exception as e:
    print("MASTER DOWNLOAD ERROR:", e)
    raise SystemExit(1)

# ---------------------------------------------------------
# Stock symbols whose futures we want
# ---------------------------------------------------------
stocks = [
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "AXISBANK",
    "INFY",
    "TCS",
    "HCLTECH",
    "WIPRO",
    "LT",
    "ITC",
    "BHARTIARTL",
    "KOTAKBANK",
    "MARUTI",
    "M&M",
    "TATAMOTORS",
    "TATASTEEL",
    "SUNPHARMA",
    "ADANIENT",
    "ADANIPORTS",
]

all_futures = []

print("\n" + "=" * 60)
print("SEARCHING STOCK FUTURES")
print("=" * 60)

for stock in stocks:

    print("\n----------------------------------------")
    print("STOCK:", stock)
    print("----------------------------------------")

    try:
        df = nse.search(stock, "FO")

        if df is None or df.empty:
            print("NO FO RESULT")
            continue

        print("TOTAL RESULTS:", len(df))

        # Only Futures
        futures = df[
            df["type"].astype(str).str.lower() == "futures"
        ].copy()

        if futures.empty:
            print("NO FUTURES FOUND")
            continue

        print("FUTURES FOUND:", len(futures))

        print(
            futures[
                ["symbol", "scripcode", "description", "type", "exchange"]
            ].to_string(index=False)
        )

        for _, row in futures.iterrows():

            symbol = str(row["symbol"])

            # Keep only actual FUT contracts
            if symbol.upper().endswith("FUT"):

                all_futures.append({
                    "underlying": stock,
                    "symbol": symbol,
                    "scripcode": row["scripcode"],
                    "description": row["description"],
                    "type": row["type"],
                    "exchange": row["exchange"]
                })

    except Exception as e:
        print("ERROR:", e)

# ---------------------------------------------------------
# Create dataframe
# ---------------------------------------------------------
print("\n" + "=" * 60)
print("FINAL FUTURES LIST")
print("=" * 60)

if not all_futures:

    print("\nNO STOCK FUTURES FOUND")
    print("\nThis means the OpenChart master download/search")
    print("is not returning NFO data correctly.")

    raise SystemExit(1)

final_df = pd.DataFrame(all_futures)

# Remove duplicate contracts
final_df = final_df.drop_duplicates(
    subset=["symbol", "scripcode"]
).reset_index(drop=True)

# Sort
final_df = final_df.sort_values(
    ["underlying", "symbol"]
).reset_index(drop=True)

print("\nTOTAL FUTURES:", len(final_df))

print("\n")
print(final_df.to_string(index=False))

# ---------------------------------------------------------
# Separate index futures
# ---------------------------------------------------------
index_names = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50"
]

index_futures = final_df[
    final_df["underlying"].isin(index_names)
].copy()

stock_futures = final_df[
    ~final_df["underlying"].isin(index_names)
].copy()

# ---------------------------------------------------------
# Save files
# ---------------------------------------------------------
final_df.to_csv(
    "all_futures.csv",
    index=False
)

stock_futures.to_csv(
    "stock_futures.csv",
    index=False
)

index_futures.to_csv(
    "index_futures.csv",
    index=False
)

print("\n" + "=" * 60)
print("FILES CREATED")
print("=" * 60)

print("all_futures.csv")
print("stock_futures.csv")
print("index_futures.csv")

print("\n" + "=" * 60)
print("COUNTS")
print("=" * 60)

print("ALL FUTURES :", len(final_df))
print("STOCK FUTURES:", len(stock_futures))
print("INDEX FUTURES:", len(index_futures))

print("\nTEST COMPLETE")
